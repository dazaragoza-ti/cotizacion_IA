"""Cuestionario interactivo por tipo de rack (Telegram).

Flujo:
  1. Detectar o preguntar el **tipo** (selectivo / cantilever / entrepiso).
  2. Pedir solo campos **bloqueantes** para ese tipo (alineados a
     `knowledge/cuestionario_*.md`), no el checklist completo.
  3. Validar números mínimos (dims, peso, pasillo o "manual") antes de generar.

Modo híbrido (igual que antes):
  - Todo OK → `generar`.
  - Faltan 1–3 → mensaje agrupado.
  - Faltan ≥4 → paso a paso (modo guiado).

Si ya hay proyecto en la sesión y el usuario no está a medio cuestionario,
se salta el cuestionario (correcciones). Ver `procesar(..., hay_proyecto_anterior)`.

Estado por usuario: caché en memoria + persistencia Supabase vía
`telegram_session_store` (chat_id). Ver migración 0012.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

log = logging.getLogger("cuestionario")

TIPOS_RACK = ("selectivo", "cantilever", "entrepiso")

# Umbral: si faltan más de esto → modo guiado; si no → agrupado.
_MAX_AGRUPADO = 3


# ── Definición de campos críticos ──────────────────────────────────────────
@dataclass
class CampoCritico:
    key: str
    nombre: str
    pregunta_corta: str
    pregunta_larga: str
    palabras_clave: list[str]
    # Si True, además de keywords hace falta evidencia numérica mínima.
    requiere_numero: bool = False
    # Regex extra opcional (p. ej. unidades de peso). Si None y requiere_numero,
    # basta con cualquier número razonable en contexto.
    regex_numerico: str | None = None
    # Mínimo de matches de keywords (default 1).
    min_keywords: int = 1


def _campo_tipo_rack() -> CampoCritico:
    return CampoCritico(
        key="tipo_rack",
        nombre="Tipo de rack",
        pregunta_corta=(
            "¿Qué sistema necesitas? "
            "(selectivo / cantiléver / entrepiso)"
        ),
        pregunta_larga=(
            "🏗️ **Tipo de sistema**\n\n"
            "¿Qué vamos a cotizar?\n"
            "• **Selectivo** — racks de tarima / entrepaño (carga pesada o ligera)\n"
            "• **Cantiléver** — brazos voladizos (tubos, perfiles, madera)\n"
            "• **Entrepiso** — mezzanine / piso elevado\n\n"
            "Responde con una de esas tres palabras."
        ),
        palabras_clave=[
            r"selectiv", r"cantil[eé]ver", r"cantilever",
            r"entrepiso", r"mezzanine", r"mezanine", r"mezzanín",
            r"rack\s+de\s+tarima", r"estanter[ií]a\s+selectiv",
        ],
    )


# Campos compartidos / por tipo — priorizan lo que Claude no debe asumir.
_PRODUCTO = CampoCritico(
    key="producto",
    nombre="Producto a almacenar",
    pregunta_corta="¿Qué vas a almacenar? (producto, material, mercancía)",
    pregunta_larga=(
        "📦 **¿Qué vas a almacenar?**\n\n"
        "Necesito el producto: harina, refacciones, tubos, archivo, etc. "
        "Define normas (p. ej. NOM-251) y el tipo de carga."
    ),
    palabras_clave=[
        r"alimento", r"h?arina", r"granel", r"grano", r"refacci",
        r"mueble", r"archivo", r"caja", r"producto", r"mercanc",
        r"material", r"insumo", r"empaque", r"electr[oó]nic",
        r"bebida", r"botella", r"\bsal\b", r"az[uú]car", r"cereal",
        r"polvo", r"qu[ií]mico", r"farmac", r"medicament", r"textil",
        r"ropa", r"calzado", r"tornill", r"pieza", r"refrigera",
        r"l[aá]cteo", r"carne", r"verdura", r"fruta", r"l[ií]quido",
        r"papel", r"libro", r"document", r"computa", r"servidor",
        r"agroqu[ií]m", r"fertilizante", r"plaguicida", r"pintura",
        r"herramienta", r"juguete", r"bobina", r"rollo",
        r"automotr[ií]z", r"tubo", r"perfil", r"madera", r"tabla",
        r"viga", r"l[aá]mina", r"barra", r"almacenar", r"guardar",
        r"tarimas?\s+de\s+\w{3,}",
        r"sacos?\s+de\s+\w{3,}",
        r"costales?\s+de\s+\w{3,}",
        r"cajas?\s+de\s+\w{3,}",
        r"bultos?\s+de\s+\w{3,}",
    ],
)

_DIM_ESPACIO = CampoCritico(
    key="dimensiones_espacio",
    nombre="Dimensiones del espacio",
    pregunta_corta=(
        "¿Dimensiones del espacio? (frente, fondo y altura libre en m)"
    ),
    pregunta_larga=(
        "📐 **Dimensiones del espacio**\n\n"
        "Necesito 3 datos del lugar:\n"
        "• **Frente** (ancho disponible)\n"
        "• **Fondo** (profundidad)\n"
        "• **Altura libre** (la MÁS BAJA: lámparas, A/C, anti-incendio)\n\n"
        "Ejemplo: *\"10 m de frente, 8 m de fondo, 6 m de altura libre\"*."
    ),
    palabras_clave=[
        r"frente", r"fondo", r"largo", r"ancho", r"altura", r"alto",
        r"bodega", r"espacio", r"almac[eé]n", r"nave",
        r"\d+\s*(m|metros|cm)\s*(de|x|por|×)",
        r"\d+\s*(x|×)\s*\d+",
        r"\d+\s*m[²2]",
    ],
    requiere_numero=True,
    regex_numerico=r"\d+(\.\d+)?\s*(m|metros|cm)\b",
    min_keywords=1,
)

_TARIMA_VS_ENTREPANO = CampoCritico(
    key="tarima_vs_entrepano",
    nombre="Tarima o entrepaño",
    pregunta_corta=(
        "¿Carga en **tarima**, en **entrepaño**, o **mixto**?"
    ),
    pregunta_larga=(
        "🪵 **¿Tarima o entrepaño?**\n\n"
        "• **Solo tarima** → largueros sin escalón\n"
        "• **Solo entrepaño** → largueros con escalón\n"
        "• **Mixto** → largueros híbridos TEM\n\n"
        "Responde con una de esas tres opciones."
    ),
    palabras_clave=[
        r"entrepa[nñ]o", r"solo\s+tarima", r"mixto",
        r"con\s+escal[oó]n", r"sin\s+escal[oó]n",
        r"h[ií]brido", r"largueros?\s+(con|sin)\s+escal",
        r"\btarima\b", r"\bpallet\b", r"\bpaleta\b",
    ],
)

_UNIDAD_CARGA_SELECTIVO = CampoCritico(
    key="unidad_carga",
    nombre="Unidad de carga (medidas y peso)",
    pregunta_corta=(
        "¿Medidas y peso de la unidad de carga? "
        "(p. ej. tarima 1.2×1.0 m, 800 kg, 2 por nivel)"
    ),
    pregunta_larga=(
        "📏 **Unidad de carga**\n\n"
        "Necesito:\n"
        "• **Medidas** (largo × ancho, y alto si aplica)\n"
        "• **Peso** por unidad (kg o ton)\n"
        "• **Cuántas** por nivel / módulo\n\n"
        "Ejemplo: *\"tarima 1.2 × 1.0 m, 1 tonelada, 2 por nivel\"*."
    ),
    palabras_clave=[
        r"tarima", r"pallet", r"paleta", r"caja", r"bulto", r"saco",
        r"costal", r"tambo", r"peso", r"carga", r"por\s+nivel",
        r"\d+\s*(kg|kilos|kilogramo|ton|tonelada)",
        r"\d+(\.\d+)?\s*(x|×)\s*\d+",
    ],
    requiere_numero=True,
    regex_numerico=r"\d+(\.\d+)?\s*(kg|kilos|kilogramo|ton|tonelada|t)\b",
)

_NIVELES_SELECTIVO = CampoCritico(
    key="niveles",
    nombre="Número de niveles",
    pregunta_corta=(
        "¿Cuántos **niveles de carga** (sin contar piso) y si lleva nivel a piso?"
    ),
    pregunta_larga=(
        "📚 **Niveles**\n\n"
        "• Número de **niveles de carga** (sin contar el piso)\n"
        "• ¿Lleva **nivel a piso**? (sí / no)\n\n"
        "Ejemplo: *\"4 niveles + nivel a piso\"*."
    ),
    palabras_clave=[
        r"nivel(?:es)?", r"pisos?\s+de\s+carga", r"nivel\s+a\s+piso",
        r"\d+\s*niveles?",
    ],
    requiere_numero=True,
    regex_numerico=r"\d+\s*niveles?\b|\bniveles?\s*[:=]?\s*\d+|\d+\s*niv",
)

_PESADA_LIGERA = CampoCritico(
    key="pesada_ligera",
    nombre="Carga pesada o ligera",
    pregunta_corta=(
        "¿Sistema **carga pesada** (gota 73 mm) o **carga ligera** (gota 38 mm)?"
    ),
    pregunta_larga=(
        "⚖️ **Carga pesada o ligera**\n\n"
        "• **Pesada** — poste 73 mm, hasta ~4500 kg/sección\n"
        "• **Ligera** — poste 38 mm, hasta ~2500 kg/sección\n\n"
        "Si no sabes, indícalo y lo inferimos del peso por módulo "
        "(pero preferimos que lo confirms)."
    ),
    palabras_clave=[
        r"carga\s+pesada", r"carga\s+ligera", r"pesada\s+gota",
        r"ligera\s+gota", r"poste\s*73", r"poste\s*38",
        r"\bpesad[ao]\b", r"\bliger[ao]\b",
    ],
)

_MONTACARGAS = CampoCritico(
    key="montacargas",
    nombre="Montacargas y pasillo",
    pregunta_corta=(
        "¿Tipo de montacargas y ancho de pasillo? "
        "(o *manual* / patín si no hay montacargas)"
    ),
    pregunta_larga=(
        "🚛 **Montacargas y pasillo**\n\n"
        "• **Tipo**: contrabalanceado / reach / VNA / apilador / patín / **manual**\n"
        "• **Ancho de pasillo** (m o mm), si aplica\n\n"
        "Si el acceso es solo manual o con patín, dímelo — cambia defensas (NOM-006)."
    ),
    palabras_clave=[
        r"montacarga", r"reach", r"contrabalan", r"\bvna\b",
        r"apilador", r"pat[ií]n", r"manual", r"diablo", r"traspaleta",
        r"pasillo", r"angosto", r"acceso", r"circulaci[oó]n",
    ],
    # Número de pasillo O mención explícita de acceso manual/patín.
    requiere_numero=False,
)

_CARGA_CANTILEVER = CampoCritico(
    key="carga_cantilever",
    nombre="Carga en cantiléver (largo y peso)",
    pregunta_corta=(
        "¿Largo de la carga (mm/m) y peso por brazo (kg)?"
    ),
    pregunta_larga=(
        "📏 **Carga en cantiléver**\n\n"
        "• **Largo** de la pieza / carga\n"
        "• **Peso por brazo** (kg)\n"
        "• ¿Sobresale del brazo? (sí/no)\n\n"
        "Ejemplo: *\"tubos de 6 m, 400 kg por brazo\"*."
    ),
    palabras_clave=[
        r"brazo", r"largo", r"peso", r"kg", r"ton", r"sobresale",
        r"\d+(\.\d+)?\s*(m|metros|mm|cm)",
        r"\d+(\.\d+)?\s*(kg|kilos|ton)",
    ],
    requiere_numero=True,
    regex_numerico=r"\d+(\.\d+)?\s*(kg|kilos|ton|tonelada|t|m|metros|mm)\b",
)

_ESTRUCTURA_CANTILEVER = CampoCritico(
    key="estructura_cantilever",
    nombre="Estructura cantiléver",
    pregunta_corta=(
        "¿Sencillo o doble? ¿Altura de columna y nº de niveles de brazos?"
    ),
    pregunta_larga=(
        "🔩 **Estructura cantiléver**\n\n"
        "• Configuración: **sencillo** (un lado) o **doble** (back-to-back)\n"
        "• **Altura** total de columna\n"
        "• **Número de niveles** de brazos\n"
        "• Largo de brazo si lo conoces\n\n"
        "Ejemplo: *\"doble, columna 4.5 m, 5 niveles de brazos\"*."
    ),
    palabras_clave=[
        r"sencillo", r"doble", r"back[\s-]*to[\s-]*back",
        r"columna", r"brazo", r"nivel(?:es)?", r"inclinad",
        r"horizontal",
    ],
    requiere_numero=True,
    regex_numerico=r"\d+(\.\d+)?\s*(m|metros|mm|cm)\b|\d+\s*niveles?\b",
)

_GEOMETRIA_ENTREPISO = CampoCritico(
    key="geometria_entrepiso",
    nombre="Geometría del entrepiso",
    pregunta_corta=(
        "¿Superficie (L×A o m²), altura al primer nivel y nº de niveles?"
    ),
    pregunta_larga=(
        "📐 **Geometría del entrepiso**\n\n"
        "• Superficie total (**L × A** o m²)\n"
        "• **Altura** desde piso al primer entrepiso\n"
        "• **Número de niveles** (1, 2, 3…)\n\n"
        "Ejemplo: *\"12 × 8 m, altura 3 m al primer nivel, 1 entrepiso\"*."
    ),
    palabras_clave=[
        r"m[²2]", r"superficie", r"entrepiso", r"mezzanine",
        r"altura", r"nivel(?:es)?", r"largo", r"ancho",
        r"\d+\s*(x|×)\s*\d+",
    ],
    requiere_numero=True,
    regex_numerico=r"\d+(\.\d+)?\s*(m|metros|mm|cm|m[²2])\b",
)

_CARGA_ENTREPISO = CampoCritico(
    key="carga_entrepiso",
    nombre="Carga de diseño del entrepiso",
    pregunta_corta=(
        "¿Carga viva (kg/m²)? ¿Habrá montacargas/patín sobre el entrepiso?"
    ),
    pregunta_larga=(
        "⚖️ **Carga de diseño**\n\n"
        "• **Carga viva** en kg/m² (típicos: 250 / 350 / 500)\n"
        "• ¿Habrá **montacargas o patín** sobre el entrepiso? (sí/no y tipo)\n"
        "• ¿Estantería integrada tipo X853? (sí/no)\n\n"
        "Ejemplo: *\"350 kg/m², solo patín, sin estantería\"*."
    ),
    palabras_clave=[
        r"carga\s+viva", r"kg\s*/\s*m", r"kg/m", r"250", r"350", r"500",
        r"montacarga", r"pat[ií]n", r"estanter", r"x853",
        r"sobre\s+el\s+entrepiso",
    ],
    requiere_numero=True,
    regex_numerico=r"\d+(\.\d+)?\s*(kg\s*/\s*m|kg/m|kg)\b|\b(250|350|500)\b",
)

_ACCESOS_ENTREPISO = CampoCritico(
    key="accesos_entrepiso",
    nombre="Accesos (escaleras / barandales)",
    pregunta_corta=(
        "¿Cuántas escaleras y barandales? ¿Compuerta de carga?"
    ),
    pregunta_larga=(
        "🪜 **Accesos**\n\n"
        "• Número y posición de **escaleras**\n"
        "• **Barandales** / pasamanos (sí, ambos lados / solo perímetro)\n"
        "• ¿**Compuerta de carga**? (sí/no)\n\n"
        "Ejemplo: *\"1 escalera recta, barandal perimetral, sin compuerta\"*."
    ),
    palabras_clave=[
        r"escalera", r"barandal", r"pasamanos", r"compuerta",
        r"acceso", r"per[ií]metro",
    ],
)


CAMPOS_POR_TIPO: dict[str, list[CampoCritico]] = {
    "selectivo": [
        _PRODUCTO,
        _DIM_ESPACIO,
        _TARIMA_VS_ENTREPANO,
        _UNIDAD_CARGA_SELECTIVO,
        _NIVELES_SELECTIVO,
        _PESADA_LIGERA,
        _MONTACARGAS,
    ],
    "cantilever": [
        _PRODUCTO,
        _DIM_ESPACIO,
        _CARGA_CANTILEVER,
        _ESTRUCTURA_CANTILEVER,
        _MONTACARGAS,
    ],
    "entrepiso": [
        _PRODUCTO,
        _GEOMETRIA_ENTREPISO,
        _CARGA_ENTREPISO,
        _ACCESOS_ENTREPISO,
        _DIM_ESPACIO,  # nave / claro libre si lo dan; útil para validar altura
    ],
}

# Compat: lista plana usada en demos / introspección.
CAMPOS: list[CampoCritico] = [_campo_tipo_rack()] + [
    c for tipo in TIPOS_RACK for c in CAMPOS_POR_TIPO[tipo]
]


# ── Detección de tipo ──────────────────────────────────────────────────────
_PATRONES_TIPO: list[tuple[str, re.Pattern[str]]] = [
    ("selectivo", re.compile(
        r"selectiv|rack\s+de\s+tarima|estanter[ií]a\s+selectiv|carga\s+(pesada|ligera)\s+gota",
        re.I,
    )),
    ("cantilever", re.compile(r"cantil[eé]ver|cantilever", re.I)),
    ("entrepiso", re.compile(r"entrepiso|mezzanine|mezanine|mezzanín", re.I)),
]


def detectar_tipo_rack(texto: str) -> str | None:
    """Devuelve 'selectivo' | 'cantilever' | 'entrepiso' o None."""
    if not texto:
        return None
    # Preferir mención explícita; si hay varias, gana la primera en el texto.
    hits: list[tuple[int, str]] = []
    for tipo, pat in _PATRONES_TIPO:
        m = pat.search(texto)
        if m:
            hits.append((m.start(), tipo))
    if not hits:
        return None
    hits.sort(key=lambda x: x[0])
    return hits[0][1]


# ── Validaciones numéricas / semánticas extra ──────────────────────────────
def _tiene_dims_minimas(texto: str) -> bool:
    """Al menos 2 medidas con unidad, o un patrón L×A×H / L×A."""
    txt = texto.lower()
    nums_con_unidad = re.findall(r"\d+(?:\.\d+)?\s*(?:m|metros|cm|mm)\b", txt)
    if len(nums_con_unidad) >= 2:
        return True
    if re.search(r"\d+(?:\.\d+)?\s*(?:x|×)\s*\d+(?:\.\d+)?(?:\s*(?:x|×)\s*\d+(?:\.\d+)?)?", txt):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*m[²2]\b", txt):
        return True
    return False


def _montacargas_ok(texto: str) -> bool:
    """Pasillo con número, o acceso manual/patín/diablo explícito."""
    txt = texto.lower()
    if re.search(r"manual|pat[ií]n|diablo|traspaleta|sin\s+montacarga", txt):
        return True
    if re.search(r"pasillo.{0,40}\d", txt) or re.search(r"\d+(?:\.\d+)?\s*(m|metros|mm|cm).{0,20}pasillo", txt):
        return True
    if re.search(r"(contrabalan|reach|\bvna\b|apilador|montacarga).{0,40}\d", txt):
        return True
    # Tipo de equipo sin pasillo aún: no alcanza solo con "montacargas".
    return False


def _campo_satisfecho(campo: CampoCritico, texto: str) -> bool:
    txt = texto.lower()
    matches = sum(1 for kw in campo.palabras_clave if re.search(kw, txt))
    if matches < campo.min_keywords:
        return False

    if campo.key == "dimensiones_espacio" or campo.key == "geometria_entrepiso":
        return _tiene_dims_minimas(txt)

    if campo.key == "montacargas":
        return _montacargas_ok(txt)

    if campo.requiere_numero:
        if campo.regex_numerico:
            return bool(re.search(campo.regex_numerico, txt, re.I))
        return bool(re.search(r"\d", txt))

    return True


def detectar_campos_presentes(texto: str, tipo: str | None = None) -> set[str]:
    """Campos que el texto ya cubre. Si `tipo` es None, solo evalúa tipo_rack."""
    if not texto:
        return set()
    presentes: set[str] = set()
    tipo_detectado = detectar_tipo_rack(texto)
    if tipo_detectado:
        presentes.add("tipo_rack")

    tipo_eff = tipo or tipo_detectado
    if not tipo_eff or tipo_eff not in CAMPOS_POR_TIPO:
        return presentes

    for campo in CAMPOS_POR_TIPO[tipo_eff]:
        if _campo_satisfecho(campo, texto):
            presentes.add(campo.key)
    return presentes


# ── Estado por usuario ─────────────────────────────────────────────────────
@dataclass
class EstadoUsuario:
    """Estado del cuestionario para un usuario."""
    texto_acumulado: str = ""
    campos_recolectados: set[str] = field(default_factory=set)
    tipo_rack: str | None = None
    modo_guiado: bool = False
    siguiente_pregunta_idx: int = 0

    def agregar_texto(self, txt: str) -> None:
        if not txt:
            return
        self.texto_acumulado += "\n" + txt
        if not self.tipo_rack:
            self.tipo_rack = detectar_tipo_rack(self.texto_acumulado)
        self.campos_recolectados = detectar_campos_presentes(
            self.texto_acumulado, self.tipo_rack
        )

    def lista_campos(self) -> list[CampoCritico]:
        if not self.tipo_rack:
            return [_campo_tipo_rack()]
        return CAMPOS_POR_TIPO[self.tipo_rack]

    @property
    def faltantes(self) -> list[CampoCritico]:
        if not self.tipo_rack:
            return [_campo_tipo_rack()]
        keys = self.campos_recolectados
        # tipo_rack ya resuelto; no pedirlo de nuevo
        return [c for c in CAMPOS_POR_TIPO[self.tipo_rack] if c.key not in keys]

    @property
    def completo(self) -> bool:
        return self.tipo_rack is not None and len(self.faltantes) == 0


# Caché en memoria (por user_id). La fuente de verdad entre reinicios es
# Supabase (`telegram_sesiones`), hidratada desde handlers con chat_id.
_ESTADOS: dict[int, EstadoUsuario] = {}


def estado_de(uid: int) -> EstadoUsuario:
    if uid not in _ESTADOS:
        _ESTADOS[uid] = EstadoUsuario()
    return _ESTADOS[uid]


def limpiar(uid: int) -> None:
    _ESTADOS.pop(uid, None)


def serializar_estado(uid: int) -> dict:
    """Snapshot JSON-friendly del estado en memoria (para persistir)."""
    from ...services.telegram_session_store import estado_a_dict
    return estado_a_dict(estado_de(uid))


def hidratar_estado(uid: int, data: dict | None) -> EstadoUsuario:
    """Restaura estado desde persistencia sin pisar si ya hay conversación local."""
    from ...services.telegram_session_store import aplicar_estado_dict
    est = estado_de(uid)
    if data and not est.texto_acumulado.strip():
        aplicar_estado_dict(est, data)
    return est


# ── Construcción de mensajes ───────────────────────────────────────────────
def mensaje_faltantes_agrupado(faltantes: list[CampoCritico], tipo: str | None = None) -> str:
    if not faltantes:
        return ""
    tipo_lbl = f" ({tipo})" if tipo else ""
    if len(faltantes) == 1:
        intro = f"⚠️ Antes de generar el proyecto{tipo_lbl}, me falta este dato:"
    else:
        intro = (
            f"⚠️ Antes de generar el proyecto{tipo_lbl}, "
            f"me faltan estos {len(faltantes)} datos:"
        )
    bullets = "\n".join(
        f"• **{c.nombre}** — {c.pregunta_corta}" for c in faltantes
    )
    return (
        f"{intro}\n\n{bullets}\n\n"
        "Mándame los datos en un mensaje (también puedes adjuntar plano/fotos).\n"
        "_`/cancelar` para abandonar._"
    )


def mensaje_pregunta_guiada(campo: CampoCritico, idx: int, total: int) -> str:
    return (
        f"📋 **Paso {idx + 1} de {total}**\n\n"
        f"{campo.pregunta_larga}\n\n"
        "_Comandos disponibles:_ `/cancelar` para abandonar."
    )


# ── Entry point ────────────────────────────────────────────────────────────
@dataclass
class DecisionCuestionario:
    accion: str  # "generar" | "preguntar" | "esperar"
    mensaje: str = ""
    texto_completo: str = ""


def procesar(uid: int, nuevo_texto: str,
              hay_archivos_pendientes: bool = False,
              hay_proyecto_anterior: bool = False) -> DecisionCuestionario:
    """Procesa un mensaje y decide generar / preguntar / esperar.

    `hay_proyecto_anterior`: si True y no hay cuestionario en curso, salta
    el cuestionario (flujo de correcciones en Telegram).
    """
    est = estado_de(uid)

    ya_habia_conversacion_en_curso = bool(est.texto_acumulado.strip())

    if hay_proyecto_anterior and not ya_habia_conversacion_en_curso and nuevo_texto.strip():
        limpiar(uid)
        return DecisionCuestionario(accion="generar", texto_completo=nuevo_texto.strip())

    est.agregar_texto(nuevo_texto)

    if not est.texto_acumulado.strip() and not hay_archivos_pendientes:
        return DecisionCuestionario(accion="esperar")

    faltantes = est.faltantes

    if not faltantes:
        texto = est.texto_acumulado.strip()
        # Prefijo explícito del tipo para Claude / context builder.
        if est.tipo_rack and "tipo de rack" not in texto.lower() and est.tipo_rack not in texto.lower():
            texto = f"[Tipo de rack: {est.tipo_rack}]\n{texto}"
        limpiar(uid)
        return DecisionCuestionario(accion="generar", texto_completo=texto)

    # Sin tipo aún → siempre una sola pregunta (no spam de checklist).
    if not est.tipo_rack:
        est.modo_guiado = True
        campo = faltantes[0]
        return DecisionCuestionario(
            accion="preguntar",
            mensaje=mensaje_pregunta_guiada(campo, 0, 1),
        )

    total_campos = len(CAMPOS_POR_TIPO[est.tipo_rack])

    if len(faltantes) <= _MAX_AGRUPADO:
        est.modo_guiado = False
        return DecisionCuestionario(
            accion="preguntar",
            mensaje=mensaje_faltantes_agrupado(faltantes, est.tipo_rack),
        )

    est.modo_guiado = True
    campo = faltantes[0]
    # Índice relativo al checklist del tipo (campos ya cubiertos + 1).
    idx = total_campos - len(faltantes)
    return DecisionCuestionario(
        accion="preguntar",
        mensaje=mensaje_pregunta_guiada(campo, idx, total_campos),
    )


def es_comando_cancelar(texto: str) -> bool:
    if not texto:
        return False
    t = texto.strip().lower()
    return t in ("/cancelar", "/cancel", "/reset", "/abandonar")


_RE_REGENERAR = re.compile(
    r"^\s*(?:/"  # slash opcional estilo comando
    r")?(?:regenerar|regenera|regen|otra\s*vez|rehacer|"
    r"corrige(?:\s+el)?\s*3d|vuelve?\s+a\s+generar)\s*"
    r"(?:el\s+(?:proyecto|3d|modelo|diseño))?\s*[.!]?\s*$",
    re.IGNORECASE,
)


def es_comando_regenerar(texto: str) -> bool:
    """True si el usuario pide regenerar (tras aviso QA u otro fallo)."""
    if not texto or not texto.strip():
        return False
    t = texto.strip()
    if _RE_REGENERAR.match(t):
        return True
    # Frases cortas con la raíz regener-
    low = t.lower()
    if len(t) <= 40 and re.search(r"\bregener", low):
        return True
    return False


def texto_regeneracion(texto_usuario: str | None = None) -> str:
    """Prompt explícito para Claude cuando el usuario escribe regenerar."""
    base = (
        "REGENERAR: vuelve a generar el proyecto completo (JSON + entregables) "
        "corrigiendo defectos de calidad 3D / armado del intento anterior. "
        "Conserva la misma clave y sube la revisión. No reinicies el diseño "
        "desde cero salvo que el layout sea inviable."
    )
    extra = (texto_usuario or "").strip()
    if extra and not es_comando_regenerar(extra):
        return f"{base}\n\nAjuste pedido por el cliente: {extra}"
    if extra and es_comando_regenerar(extra) and len(extra) > 20:
        return f"{base}\n\nDetalle del cliente: {extra}"
    return base


# ── Stub para pruebas manuales ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
        d = procesar(1, msg)
        print(f"Acción: {d.accion}")
        if d.mensaje:
            print(f"\n--- mensaje al usuario ---\n{d.mensaje}")
        if d.texto_completo:
            print(f"\n--- texto a Claude ---\n{d.texto_completo}")
        e = estado_de(1)
        print(f"\nTipo: {e.tipo_rack}")
        print(f"Campos presentes: {e.campos_recolectados}")
        print(f"Faltantes: {[c.key for c in e.faltantes]}")
    else:
        mensajes_prueba = [
            "Necesito un rack selectivo",
            "Para almacenar harina",
            "10 m de frente, 8 m de fondo, 6 m de altura libre",
            "Solo tarima",
            "Tarima de 1.2 × 1.0 m, 1 tonelada, 2 por nivel",
            "4 niveles con nivel a piso",
            "Carga pesada",
            "Montacargas contrabalanceado, pasillo 3 m",
        ]
        uid = 42
        for m in mensajes_prueba:
            print(f"\n>>> USUARIO: {m}")
            d = procesar(uid, m)
            print(f"    Acción: {d.accion}")
            if d.mensaje:
                print(f"    Mensaje:\n{d.mensaje[:220]}...")
            if d.accion == "generar":
                print(f"\n    TEXTO COMPLETO A CLAUDE:\n{d.texto_completo}")
                break
