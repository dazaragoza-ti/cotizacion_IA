import "package:flutter/material.dart";

enum EstadoNodo { implementado, parcial, noImplementado }

class NodoArquitectura {
  final String id;
  final String label;
  final String descripcion;
  final IconData icon;
  final EstadoNodo estado;
  final Offset posicion; // fraccion 0..1 del canvas
  const NodoArquitectura({
    required this.id,
    required this.label,
    required this.descripcion,
    required this.icon,
    required this.posicion,
    this.estado = EstadoNodo.implementado,
  });
}

class ConexionArquitectura {
  final String desde;
  final String hacia;
  final String? etiqueta;
  final bool observabilidad; // true = LangSmith observando (linea punteada distinta)
  const ConexionArquitectura(this.desde, this.hacia, {this.etiqueta, this.observabilidad = false});
}

/// Contenido estatico -- refleja la arquitectura REAL descrita en
/// AI_ENGINEERING_MANUAL.md (capitulos 2-10), no un ideal aspiracional.
/// Un unico Claude (Proyectista) orquestado por Python determinista, con
/// Engineering/RAG/Knowledge Graph como motores separados, tal como decide
/// explicitamente el manual en 7.11 ("un unico Claude basta").
class ArquitecturaData {
  ArquitecturaData._();

  static const nodos = [
    NodoArquitectura(
      id: "usuario", label: "Usuario", icon: Icons.person,
      posicion: Offset(0.06, 0.5),
      descripcion: "Vendedor o cliente escribe por Telegram: texto, imagenes o PDF "
          "de un rack que necesita.",
    ),
    NodoArquitectura(
      id: "fastapi", label: "FastAPI", icon: Icons.dns,
      posicion: Offset(0.22, 0.5),
      descripcion: "Backend (app/main.py + routers/ + telegram/): recibe la solicitud "
          "y orquesta el flujo completo. Nunca contiene logica de negocio.",
    ),
    NodoArquitectura(
      id: "context_builder", label: "Context Builder", icon: Icons.build_circle_outlined,
      posicion: Offset(0.40, 0.5),
      descripcion: "app/ai/context_builder.py: arma el texto final para Claude — "
          "proyecto anterior + catalogo filtrado (Compatibility Engine) + "
          "correcciones (RAG) + relaciones aprendidas (Knowledge Graph). "
          "No decide nada, solo junta lo que ya recuperaron los demas motores.",
    ),
    NodoArquitectura(
      id: "rag", label: "RAG\n(pgvector)", icon: Icons.manage_search,
      posicion: Offset(0.40, 0.22),
      descripcion: "app/ai/rag/*: busca correcciones parecidas por similitud "
          "semantica (Voyage AI, 1024 dims) en knowledge_chunks. Nunca decide, "
          "solo recupera evidencia.",
    ),
    NodoArquitectura(
      id: "graph", label: "Knowledge\nGraph", icon: Icons.hub_outlined,
      posicion: Offset(0.40, 0.78),
      descripcion: "app/ai/rag/graph.py: relaciones reemplaza_por / evitar_con / "
          "compatible_con entre SKUs, reforzadas atomicamente (RPC "
          "reforzar_relacion) cada vez que hay una correccion (Sprint 2).",
    ),
    NodoArquitectura(
      id: "claude", label: "Claude\n(Proyectista)", icon: Icons.psychology_outlined,
      posicion: Offset(0.58, 0.5),
      descripcion: "Unico LLM del sistema (claude_client.py). Recibe el contexto ya "
          "armado y razona: diseño, despiece, cotizacion, JSON — un solo turno, "
          "sin tool-calling dinamico. Nunca calcula cargas ni compatibilidades.",
    ),
    NodoArquitectura(
      id: "engineering", label: "Engineering\nEngine", icon: Icons.engineering_outlined,
      posicion: Offset(0.74, 0.5),
      descripcion: "validator_engine.py + compatibility.py: deterministas, sin IA. "
          "Verifican reglas estructurales, NOM-006/251, cargas, factor de "
          "seguridad. Si hay error bloqueante, el diseño VUELVE a Claude "
          "(max. 2 intentos) antes de responder al cliente.",
    ),
    NodoArquitectura(
      id: "promotion", label: "Promotion\nEngine", icon: Icons.trending_up,
      posicion: Offset(0.58, 0.8),
      descripcion: "app/engineering/promotion.py (Sprint 2): cuando una relacion del "
          "grafo se repite mucho (50+ correcciones), se materializa como regla "
          "permanente en reglas_armado — el sistema deja de \"redescubrirla\" cada vez.",
    ),
    NodoArquitectura(
      id: "generadores", label: "Generadores", icon: Icons.picture_as_pdf_outlined,
      posicion: Offset(0.90, 0.5),
      descripcion: "app/ai/generators/*: PDF de planos, XLSX de despiece/cotizacion, "
          "modelo 3D (GLB/DAE) y renders PNG — deterministas, a partir del JSON "
          "final que ya paso el validador.",
    ),
    NodoArquitectura(
      id: "supabase", label: "Supabase", icon: Icons.storage_outlined,
      posicion: Offset(0.58, 0.2),
      descripcion: "Postgres + pgvector + Storage: la unica fuente de verdad "
          "(catalogo, reglas, correcciones, chunks, relaciones, historial, "
          "archivos). El vector store nunca reemplaza estas tablas.",
    ),
    NodoArquitectura(
      id: "langsmith", label: "LangSmith", icon: Icons.visibility_outlined,
      posicion: Offset(0.90, 0.2),
      estado: EstadoNodo.parcial,
      descripcion: "app/ai/tracing.py: traza cada llamada a Claude (prompt real, "
          "tokens, costo via usage_metadata, retriever, run_id correlacionado "
          "con disenos_racks). No-op si no esta configurado.",
    ),
    NodoArquitectura(
      id: "multiagente", label: "Multi-agente\n(LangGraph)", icon: Icons.share_outlined,
      posicion: Offset(0.74, 0.85),
      estado: EstadoNodo.noImplementado,
      descripcion: "Descartado A PROPOSITO (manual, capitulo 7.11): \"un unico "
          "Claude basta\" — no hay razonamiento verdaderamente independiente "
          "entre dominios en el diseño de racks. Solo se justificaria si "
          "aparece un dominio distinto (ej. Ventas) con decisiones propias.",
    ),
  ];

  static const conexiones = [
    ConexionArquitectura("usuario", "fastapi"),
    ConexionArquitectura("fastapi", "context_builder"),
    ConexionArquitectura("context_builder", "rag"),
    ConexionArquitectura("context_builder", "graph"),
    ConexionArquitectura("rag", "supabase"),
    ConexionArquitectura("graph", "supabase"),
    ConexionArquitectura("context_builder", "claude"),
    ConexionArquitectura("claude", "engineering"),
    ConexionArquitectura("engineering", "claude", etiqueta: "si hay error, regresa"),
    ConexionArquitectura("engineering", "generadores"),
    ConexionArquitectura("generadores", "usuario"),
    ConexionArquitectura("claude", "supabase"),
    ConexionArquitectura("graph", "promotion"),
    ConexionArquitectura("promotion", "supabase"),
    ConexionArquitectura("langsmith", "claude", observabilidad: true),
    ConexionArquitectura("langsmith", "engineering", observabilidad: true),
    ConexionArquitectura("langsmith", "rag", observabilidad: true),
  ];
}
