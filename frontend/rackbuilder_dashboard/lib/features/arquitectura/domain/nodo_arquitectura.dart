import "package:flutter/material.dart";

enum EstadoNodo { implementado, parcial, noImplementado }

class NodoArquitectura {
  final String id;
  final String label;
  final String descripcion;
  final IconData icon;
  final EstadoNodo estado;
  final Offset posicion; // fraccion 0..1 del canvas
  final String? capituloManual; // referencia a AI_ENGINEERING_MANUAL.md
  final String entradas; // que recibe este componente
  final String salidas; // que produce/entrega este componente
  const NodoArquitectura({
    required this.id,
    required this.label,
    required this.descripcion,
    required this.icon,
    required this.posicion,
    this.estado = EstadoNodo.implementado,
    this.capituloManual,
    this.entradas = "",
    this.salidas = "",
  });
}

class ConexionArquitectura {
  final String desde;
  final String hacia;
  final String? etiqueta;
  final bool observabilidad; // true = LangSmith observando (linea punteada distinta)
  const ConexionArquitectura(this.desde, this.hacia, {this.etiqueta, this.observabilidad = false});
}

/// Un paso numerado dentro de uno de los dos flujos explicados debajo del
/// diagrama: la generacion de un diseno y el aprendizaje continuo a partir
/// de correcciones. Cada paso apunta al mismo `id` usado en ArquitecturaData.nodos
/// para que la UI pueda resaltarlo si el usuario lo toca. `relacionados` cubre
/// nodos que tambien participan en ese paso sin ser el protagonista (ej. Supabase
/// se escribe/lee en casi todos los pasos, LangSmith observa varios) -- sin esto,
/// tocar Supabase o LangSmith en el mapa no resaltaba nada en ningun flujo.
class PasoFlujo {
  final int numero;
  final String nodoId;
  final String titulo;
  final String detalle;
  final List<String> relacionados;
  const PasoFlujo(this.numero, this.nodoId, this.titulo, this.detalle, {this.relacionados = const []});

  bool coincideCon(String nodoSeleccionado) =>
      nodoId == nodoSeleccionado || relacionados.contains(nodoSeleccionado);
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
      entradas: "Mensaje de texto, foto de un rack existente, PDF de una cotizacion previa.",
      salidas: "Solicitud cruda enviada al bot de Telegram.",
    ),
    NodoArquitectura(
      id: "fastapi", label: "FastAPI", icon: Icons.dns,
      posicion: Offset(0.22, 0.5),
      descripcion: "Backend (app/main.py + routers/ + telegram/): recibe la solicitud "
          "y orquesta el flujo completo. Nunca contiene logica de negocio.",
      capituloManual: "Cap. 2 - Estructura del backend",
      entradas: "Webhook de Telegram o request HTTP del dashboard Flutter.",
      salidas: "Llama a Context Builder y devuelve la respuesta final (PDF, XLSX, GLB, mensaje).",
    ),
    NodoArquitectura(
      id: "context_builder", label: "Context Builder", icon: Icons.build_circle_outlined,
      posicion: Offset(0.40, 0.5),
      descripcion: "app/ai/context_builder.py: arma el texto final para Claude -- "
          "proyecto anterior + catalogo filtrado (Compatibility Engine) + "
          "correcciones (RAG) + relaciones aprendidas (Knowledge Graph). "
          "No decide nada, solo junta lo que ya recuperaron los demas motores.",
      capituloManual: "Cap. 5 - Context Builder",
      entradas: "Solicitud del usuario + historial del proyecto si existe.",
      salidas: "Un unico prompt de texto, ya enriquecido, listo para Claude.",
    ),
    NodoArquitectura(
      id: "rag", label: "RAG\n(pgvector)", icon: Icons.manage_search,
      posicion: Offset(0.40, 0.22),
      descripcion: "app/ai/rag/*: busca correcciones parecidas por similitud "
          "semantica (Voyage AI, 1024 dims) en knowledge_chunks. Nunca decide, "
          "solo recupera evidencia.",
      capituloManual: "Cap. 6 - RAG y busqueda semantica",
      entradas: "Descripcion del rack solicitado (texto plano).",
      salidas: "Top-N correcciones y piezas de catalogo mas similares, con su score.",
    ),
    NodoArquitectura(
      id: "graph", label: "Knowledge\nGraph", icon: Icons.hub_outlined,
      posicion: Offset(0.40, 0.78),
      descripcion: "app/ai/rag/graph.py: relaciones reemplaza_por / evitar_con / "
          "compatible_con entre SKUs, reforzadas atomicamente (RPC "
          "reforzar_relacion) cada vez que hay una correccion (Sprint 2).",
      capituloManual: "Cap. 8 - Knowledge Graph y aprendizaje continuo",
      entradas: "SKU afectado + tipo de correccion detectada por SkuDiffExtractor.",
      salidas: "Relaciones con peso (occurrence count) que el Context Builder inyecta al prompt.",
    ),
    NodoArquitectura(
      id: "claude", label: "Claude\n(Proyectista)", icon: Icons.psychology_outlined,
      posicion: Offset(0.58, 0.5),
      descripcion: "Unico LLM del sistema (claude_client.py). Recibe el contexto ya "
          "armado y razona: diseno, despiece, cotizacion, JSON -- un solo turno, "
          "sin tool-calling dinamico. Nunca calcula cargas ni compatibilidades.",
      capituloManual: "Cap. 4 y 7.11 - Un unico Claude, por que basta",
      entradas: "Prompt final del Context Builder.",
      salidas: "JSON estructurado: despiece, dimensiones, texto de respuesta al cliente.",
    ),
    NodoArquitectura(
      id: "engineering", label: "Engineering\nEngine", icon: Icons.engineering_outlined,
      posicion: Offset(0.74, 0.5),
      descripcion: "validator_engine.py + compatibility.py: deterministas, sin IA. "
          "Verifican reglas estructurales, NOM-006/251, cargas, factor de "
          "seguridad. Si hay error bloqueante, el diseno VUELVE a Claude "
          "(max. 2 intentos) antes de responder al cliente.",
      capituloManual: "Cap. 3 - Engineering Engine (deterministico)",
      entradas: "JSON de diseno propuesto por Claude.",
      salidas: "Veredicto: aprobado, o lista de errores que regresan a Claude para corregir.",
    ),
    NodoArquitectura(
      id: "promotion", label: "Promotion\nEngine", icon: Icons.trending_up,
      posicion: Offset(0.58, 0.8),
      descripcion: "app/engineering/promotion.py (Sprint 2): cuando una relacion del "
          "grafo se repite mucho (50+ correcciones), se materializa como regla "
          "permanente en reglas_armado -- el sistema deja de \"redescubrirla\" cada vez.",
      capituloManual: "Cap. 8.4 - Umbrales de promocion (5 / 20 / 50)",
      entradas: "Contador de ocurrencias de cada relacion del Knowledge Graph.",
      salidas: "Regla nueva en reglas_armado cuando se cruza el umbral de 50 repeticiones.",
    ),
    NodoArquitectura(
      id: "generadores", label: "Generadores", icon: Icons.picture_as_pdf_outlined,
      posicion: Offset(0.90, 0.5),
      descripcion: "app/ai/generators/*: PDF de planos, XLSX de despiece/cotizacion, "
          "modelo 3D (GLB/DAE) y renders PNG -- deterministas, a partir del JSON "
          "final que ya paso el validador.",
      capituloManual: "Cap. 9 - Generadores de salida",
      entradas: "JSON de diseno ya aprobado por el Engineering Engine.",
      salidas: "Archivos entregables: PDF, XLSX, GLB/DAE, PNG.",
    ),
    NodoArquitectura(
      id: "supabase", label: "Supabase", icon: Icons.storage_outlined,
      posicion: Offset(0.58, 0.2),
      descripcion: "Postgres + pgvector + Storage: la unica fuente de verdad "
          "(catalogo, reglas, correcciones, chunks, relaciones, historial, "
          "archivos). El vector store nunca reemplaza estas tablas.",
      capituloManual: "Cap. 1 - Fuente unica de verdad",
      entradas: "Escrituras desde Claude, Engineering, RAG, Knowledge Graph y Promotion Engine.",
      salidas: "Toda lectura del sistema: catalogo, historial, chunks, relaciones, archivos.",
    ),
    NodoArquitectura(
      id: "langsmith", label: "LangSmith", icon: Icons.visibility_outlined,
      posicion: Offset(0.90, 0.2),
      descripcion: "app/ai/tracing.py: traza cada llamada a Claude (prompt real, "
          "tokens, costo via usage_metadata, retriever, run_id correlacionado "
          "con disenos_racks). Activo: LANGSMITH_API_KEY configurada, proyecto \"racks\". "
          "No-op automatico si la key llegara a faltar.",
      capituloManual: "Cap. 10 - Observabilidad",
      entradas: "Cada llamada a Claude, RAG y Engineering Engine (via decoradores).",
      salidas: "Trazas visibles en el dashboard de LangSmith: costo, latencia, prompt exacto.",
    ),
    NodoArquitectura(
      id: "multiagente", label: "Multi-agente\n(LangGraph)", icon: Icons.share_outlined,
      posicion: Offset(0.74, 0.85),
      estado: EstadoNodo.noImplementado,
      descripcion: "Descartado A PROPOSITO (manual, capitulo 7.11): \"un unico "
          "Claude basta\" -- no hay razonamiento verdaderamente independiente "
          "entre dominios en el diseno de racks. Solo se justificaria si "
          "aparece un dominio distinto (ej. Ventas) con decisiones propias.",
      capituloManual: "Cap. 7.11 / 7.12 - Cuando SI justificaria multi-agente",
      entradas: "-",
      salidas: "-",
    ),
    NodoArquitectura(
      id: "ventas", label: "Ventas /\nCotizador IA", icon: Icons.storefront_outlined,
      posicion: Offset(0.90, 0.85),
      descripcion: "app/services/ventas_service.py + ai/clients/ventas_client.py: "
          "el primer y unico segundo agente del sistema -- se justifica porque razona "
          "sobre un dominio distinto (negocio) del proyectista tecnico. El descuento "
          "y el historial del cliente se calculan en Python determinista (nunca los "
          "inventa el LLM); Claude solo redacta la propuesta comercial persuasiva.",
      capituloManual: "Cap. 7.12 - Dominio independiente que si justifica multi-agente",
      entradas: "JSON de cotizacion ya con precios reales + historial de compras del cliente (tabla clientes).",
      salidas: "Mensaje de Telegram con la propuesta comercial y el descuento aplicable, si hay uno.",
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
    ConexionArquitectura("generadores", "ventas", etiqueta: "descuento + propuesta comercial"),
    ConexionArquitectura("ventas", "usuario", etiqueta: "propuesta comercial"),
    ConexionArquitectura("ventas", "supabase"),
    ConexionArquitectura("langsmith", "claude", observabilidad: true),
    ConexionArquitectura("langsmith", "engineering", observabilidad: true),
    ConexionArquitectura("langsmith", "rag", observabilidad: true),
  ];

  /// Flujo 1: como se genera un diseno de rack, desde que el usuario escribe
  /// hasta que recibe los archivos. Los pasos siguen el camino "feliz"; el
  /// paso 7 documenta el unico bucle real del sistema (correccion del validador).
  static const flujoGeneracion = [
    PasoFlujo(1, "usuario", "El cliente pide un rack",
        "Por Telegram, en texto libre, con o sin foto/PDF de referencia."),
    PasoFlujo(2, "fastapi", "FastAPI recibe la solicitud",
        "El webhook de Telegram entrega el mensaje al backend, que no decide nada, solo orquesta."),
    PasoFlujo(3, "rag", "RAG busca correcciones parecidas",
        "Se buscan por similitud semantica (Voyage AI) correcciones previas relevantes al tipo de rack pedido.",
        relacionados: ["supabase", "langsmith"]),
    PasoFlujo(4, "graph", "Knowledge Graph aporta relaciones aprendidas",
        "SKUs que se suelen reemplazar, evitar o combinar entre si, acumulados de correcciones pasadas.",
        relacionados: ["supabase"]),
    PasoFlujo(5, "context_builder", "Context Builder arma el prompt final",
        "Combina el catalogo filtrado, las correcciones del RAG y las relaciones del grafo en un solo texto.",
        relacionados: ["promotion"]),
    PasoFlujo(6, "claude", "Claude disena el rack",
        "Un unico turno de razonamiento: dimensiones, despiece, cotizacion -- todo en un JSON estructurado.",
        relacionados: ["langsmith", "supabase"]),
    PasoFlujo(7, "engineering", "Engineering Engine valida (determinista)",
        "Si hay un error bloqueante (NOM-006/251, carga, factor de seguridad), el diseno regresa a Claude -- maximo 2 intentos.",
        relacionados: ["langsmith"]),
    PasoFlujo(8, "generadores", "Se generan los entregables",
        "PDF de planos, XLSX de despiece y cotizacion, modelo 3D GLB/DAE y renders PNG."),
    PasoFlujo(9, "ventas", "Cotizador IA calcula el descuento y redacta la propuesta",
        "Identifica al cliente, revisa su historial de compras y aplica reglas de descuento "
        "deterministas; Claude solo redacta el texto persuasivo con ese resultado ya calculado."),
    PasoFlujo(10, "usuario", "El cliente recibe la respuesta",
        "Archivos + cotizacion tecnica + propuesta comercial, todo en el mismo hilo de Telegram."),
  ];

  /// Flujo 2: como una correccion manual (un vendedor corrigiendo un diseno)
  /// termina convirtiendose en conocimiento reutilizable del sistema.
  static const flujoAprendizaje = [
    PasoFlujo(1, "usuario", "Alguien corrige un diseno",
        "Ej.: cambia un SKU por otro, o marca que dos piezas no deben ir juntas -- via Telegram o el dashboard.",
        relacionados: ["fastapi"]),
    PasoFlujo(2, "graph", "SkuDiffExtractor detecta el cambio",
        "Compara el despiece original contra el corregido y extrae que SKU cambio por cual, o que combinacion se evito."),
    PasoFlujo(3, "graph", "Se refuerza la relacion en el grafo",
        "RPC atomico reforzar_relacion incrementa el contador de esa relacion especifica (reemplaza_por / evitar_con / compatible_con).",
        relacionados: ["supabase"]),
    PasoFlujo(4, "graph", "El contador cruza umbrales",
        "5 repeticiones = relacion importante, 20 = candidata a regla, 50 = se promueve a regla permanente.",
        relacionados: ["supabase"]),
    PasoFlujo(5, "promotion", "Promotion Engine materializa la regla",
        "Al llegar a 50, la relacion deja de vivir solo como dato del grafo y se escribe como regla en reglas_armado.",
        relacionados: ["supabase"]),
    PasoFlujo(6, "context_builder", "La proxima solicitud ya usa lo aprendido",
        "El Context Builder inyecta la relacion (o la regla ya promovida) directo en el prompt de Claude, sin que nadie la repita manualmente.",
        relacionados: ["supabase", "rag", "claude"]),
  ];
}
