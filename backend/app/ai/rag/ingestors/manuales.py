"""
Ingestor de fichas técnicas / manuales locales.

Indexa `app/ai/knowledge/tecnico/*.{md,txt}` y, si PyMuPDF está disponible,
el texto extraíble de los PDF del mismo directorio. Los prompts y golden
examples NO se mueven a Supabase: siguen en disco; aquí solo se vectorizan
para búsqueda semántica (`tipo=manual` en knowledge_chunks).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from app.ai.rag.checksum import ChecksumService
from app.ai.rag.chunkers import chunk_texto, manual_to_document
from app.ai.rag.config import get_rag_settings
from app.ai.rag.embeddings import embedding_service
from app.ai.rag.repository import repository

logger = logging.getLogger(__name__)

TAMANO_LOTE = 20
PAUSA_ENTRE_LOTES_SEG = 21

# app/ai/rag/ingestors/manuales.py → app/ai/knowledge/tecnico
TECNICO_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "tecnico"
EXTENSIONES_TEXTO = {".md", ".txt"}
EXTENSIONES_PDF = {".pdf"}
ORIGEN_TABLA = "manuales_locales"


def _extraer_texto_pdf(path: Path) -> str:
    """Best-effort con PyMuPDF. Si no hay texto (PDF escaneado) o falta el
    paquete, devuelve cadena vacía y el sync lo omite con warning."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF no disponible — se omite PDF %s", path.name)
        return ""

    try:
        doc = fitz.open(path)
        partes: list[str] = []
        for pagina in doc:
            partes.append(pagina.get_text("text") or "")
        doc.close()
        return "\n".join(partes).strip()
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo leer PDF %s: %s", path.name, e)
        return ""


def _leer_archivo(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in EXTENSIONES_TEXTO:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    if suf in EXTENSIONES_PDF:
        return _extraer_texto_pdf(path)
    return ""


def _listar_fichas() -> list[Path]:
    if not TECNICO_DIR.is_dir():
        return []
    return [
        p for p in sorted(TECNICO_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in (EXTENSIONES_TEXTO | EXTENSIONES_PDF)
    ]


def _borrar_chunks_archivo(origen_id: str, max_fragmentos: int = 200) -> None:
    """Limpia chunks previos del archivo (`referencia_id = nombre#i`)."""
    for i in range(max_fragmentos):
        repository.delete_chunks("manual", f"{origen_id}#{i}")


class ManualesIngestor:
    """Sincroniza fichas técnicas locales al vector store (incremental por checksum)."""

    def sync(self) -> None:
        logger.info("========== SINCRONIZANDO MANUALES / FICHAS TÉCNICAS ==========")
        settings = get_rag_settings()
        archivos = _listar_fichas()

        if not archivos:
            logger.warning("No hay fichas en %s", TECNICO_DIR)
            return

        total_archivos = len(archivos)
        ignorados = 0
        # (path, origen_id, docs, checksum, existe)
        pendientes: list[tuple[Path, str, list[str], str, bool]] = []

        for path in archivos:
            texto = _leer_archivo(path)
            if not texto:
                logger.warning("Sin texto extraíble — se omite %s", path.name)
                continue

            origen_id = path.name
            checksum = ChecksumService.calculate({
                "nombre": path.name,
                "texto": texto,
            })
            source = repository.get_source(ORIGEN_TABLA, origen_id)
            existe = bool(source.data)

            if existe and source.data[0]["checksum"] == checksum:
                ignorados += 1
                continue

            fragmentos = chunk_texto(
                texto,
                chunk_size=settings.CHUNK_SIZE,
                overlap=settings.CHUNK_OVERLAP,
            )
            docs = [
                manual_to_document(path.name, frag, i, len(fragmentos))
                for i, frag in enumerate(fragmentos)
            ]
            pendientes.append((path, origen_id, docs, checksum, existe))

        nuevos = sum(1 for _, _, _, _, existe in pendientes if not existe)
        actualizados = len(pendientes) - nuevos
        total_chunks = sum(len(docs) for _, _, docs, _, _ in pendientes)

        plan_flat: list[tuple[Path, str, int, str]] = []
        for path, origen_id, docs, _checksum, _existe in pendientes:
            _borrar_chunks_archivo(origen_id)
            for i, doc in enumerate(docs):
                plan_flat.append((path, origen_id, i, doc))

        for inicio in range(0, len(plan_flat), TAMANO_LOTE):
            lote = plan_flat[inicio:inicio + TAMANO_LOTE]
            docs_lote = [doc for _, _, _, doc in lote]
            embeddings_lote = embedding_service.embed_documents(docs_lote)

            for (path, origen_id, idx, doc), embedding in zip(lote, embeddings_lote):
                repository.insert_chunk({
                    "tipo": "manual",
                    "fuente": "knowledge/tecnico",
                    "referencia_id": f"{origen_id}#{idx}",
                    "contenido": doc,
                    "metadata": {
                        "archivo": path.name,
                        "fragmento": idx,
                        "extension": path.suffix.lower(),
                    },
                    "embedding": embedding,
                })

            if inicio + TAMANO_LOTE < len(plan_flat):
                time.sleep(PAUSA_ENTRE_LOTES_SEG)

        for path, origen_id, _docs, checksum, _existe in pendientes:
            repository.save_source({
                "nombre": path.name,
                "tipo": "manual",
                "origen_tabla": ORIGEN_TABLA,
                "origen_id": origen_id,
                "checksum": checksum,
                "activo": True,
            })

        logger.info("===================================")
        logger.info("Archivos        : %s", total_archivos)
        logger.info("Nuevos          : %s", nuevos)
        logger.info("Actualizados    : %s", actualizados)
        logger.info("Sin cambios     : %s", ignorados)
        logger.info("Chunks indexados: %s", total_chunks)
        logger.info("===================================")


manuales_ingestor = ManualesIngestor()
