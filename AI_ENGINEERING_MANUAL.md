# AI_ENGINEERING_MANUAL.md

**Versión:** 1.0
**Proyecto:** Plataforma IA para Diseño Automático de Racks Industriales
**Autor:** Arquitectura IA

> **Nota de implementación (agregada por Claude, julio 2026):** Este manual describe
> la visión completa del sistema. No todo se implementó tal cual — en particular,
> el Capítulo 7 (7.11-7.12) del propio manual advierte contra usar múltiples
> agentes LLM, contradiciendo el diagrama de Supervisor→Planner→Retriever→...→Renderizador
> del Capítulo 1: **"Nosotros utilizaremos un único agente... En nuestro proyecto,
> todo el razonamiento es de ingeniería. Un único Claude basta."** Esa es la
> decisión que se siguió: un solo Claude (el proyectista), con un
> **Engineering Engine determinista** (`app/engineering/`: `validator_engine.py`,
> `compatibility.py`), un **Context Builder** (`app/ai/context_builder.py`) y un
> **RAG real** (`app/ai/rag/`) — sin LangGraph ni multi-agente todavía, porque no
> hay un caso de uso concreto que lo justifique hoy. Si aparece uno (ver
> sección 7.12: "razonamiento independiente" real, no solo separación estética),
> se agrega desde ahí, no antes.

---

## CAPÍTULO 1 — VISIÓN DEL PROYECTO

### 1.1 Propósito

Este proyecto tiene como objetivo construir un Ingeniero CAD Industrial Autónomo
especializado en el diseño de sistemas de almacenamiento industrial.

No es un chatbot. No es un asistente conversacional. No es un generador de texto.

Es una plataforma de ingeniería asistida por Inteligencia Artificial capaz de
diseñar estructuras reales utilizando reglas de ingeniería, experiencia histórica,
conocimiento técnico y modelos de lenguaje.

El sistema debe ser capaz de: diseñar racks industriales, seleccionar componentes,
validar compatibilidades, calcular posiciones tridimensionales, aplicar
restricciones técnicas, aprender de correcciones humanas, recordar proyectos
anteriores, generar documentación técnica, explicar las decisiones tomadas.

### 1.2 Filosofía

La inteligencia del sistema no reside únicamente en el modelo de IA. Está
distribuida entre distintos motores especializados, cada uno con una
responsabilidad específica: Engineering, RAG, Knowledge Graph, orquestados
por el LLM, con LangSmith dando observabilidad sobre todo.

El LLM únicamente razona. Nunca debe realizar cálculos determinísticos que
puedan implementarse mediante código.

### 1.3 Objetivo final

Un usuario únicamente describe su necesidad ("Necesito un rack selectivo para
24 pallets europeos de 1200x1000mm con tres niveles y capacidad de 1200kg por
pallet") y el sistema genera: diseño estructural, componentes, coordenadas 3D,
lista de materiales, plano, render, cotización, PDF, Excel, explicación técnica.

### 1.4 Lo que NO es el proyecto

No pretende construir: un chatbot, un GPT personalizado, un sistema de
preguntas y respuestas, un buscador semántico, un generador de JSON. Todos
esos componentes pueden existir, pero son herramientas del sistema, no el
sistema.

### 1.5 Principios fundamentales

- **Ingeniería primero** — la ingeniería siempre tiene prioridad sobre el modelo.
- **Determinismo** — todo lo que pueda resolverse con algoritmos, se resuelve con código, nunca con prompts.
- **Evidencia** — toda decisión del modelo debe estar respaldada por información existente (catálogo, reglas, proyectos, correcciones, manuales, Knowledge Graph, RAG). Nunca inventar.
- **Aprendizaje continuo** — cada proyecto y cada corrección representan nuevo conocimiento.
- **Arquitectura modular** — sin dependencias circulares, todo componente reemplazable.

### 1.8 Regla fundamental

Toda nueva funcionalidad debe responder primero: **¿Debe resolverla la IA o
puede resolverla un algoritmo?** Si puede implementarse mediante código,
deberá implementarse mediante código.

---

## CAPÍTULO 2 — ARQUITECTURA GENERAL DEL SISTEMA

La plataforma sigue una arquitectura modular, desacoplada y escalable, con
capas: Presentation (Telegram/FastAPI) → Application (Services) →
Domain (Engineering/Knowledge Graph/Compatibility) → Infrastructure
(Supabase/Storage/Claude/Embeddings).

Principios SOLID aplicados explícitamente: Single Responsibility (cada
archivo resuelve un único problema), Open/Closed (proveedores de embeddings
intercambiables sin tocar el resto), Liskov (todo provider implementa
`embed(text)` igual), Interface Segregation (repositorios chicos y
específicos, no uno gigante), Dependency Injection (los clientes se inyectan,
no se crean dentro de la lógica).

**Regla de oro:** antes de implementar algo nuevo, responder — ¿pertenece al
dominio de ingeniería? ¿al RAG? ¿al Knowledge Graph? ¿al backend? ¿al LLM?
Si la respuesta no es clara, detenerse hasta definir la responsabilidad.

---

## CAPÍTULO 3 — ARQUITECTURA DEL BACKEND

`main.py` solo crea la app, registra middlewares/routers, configura CORS y
lifespan — nunca contiene lógica de negocio. `config.py` centraliza variables
de entorno. `clients.py` crea clientes compartidos (singleton). `routers/`
solo valida entrada, llama un service y devuelve respuesta — nunca usa
Supabase o Claude directamente. `services/` coordinan casos de uso, no
calculan. `telegram/` recibe/envía mensajes, nunca contiene ingeniería.

---

## CAPÍTULO 4 — SUPABASE + PGVECTOR + RAG HÍBRIDO

La fuente de verdad siempre es Supabase. La base vectorial únicamente acelera
la recuperación de contexto — nunca es la fuente oficial. El modelo nunca
consulta directamente Supabase, siempre pasa por el Context Builder, que
combina Vector Search + Metadata Search + Knowledge Graph + SQL Search +
Business Rules + Historial de proyectos + Correcciones humanas.

`knowledge_sources` representa las fuentes originales (nunca embeddings).
`knowledge_chunks` contiene fragmentos preparados para búsqueda semántica
(nunca reemplaza las tablas originales). Toda la información estructurada
va en `metadata`, no solo texto plano.

Sincronización incremental por checksum: si el contenido no cambió, no se
recalculan embeddings. Cuatro modos: full sync, incremental, por tabla, por
registro.

**Regla fundamental:** el RAG no existe para responder preguntas. Existe
para proporcionar evidencia al motor de razonamiento.

---

## CAPÍTULO 5 — KNOWLEDGE GRAPH

El RAG responde "¿qué información es parecida?". El Knowledge Graph responde
"¿qué relación existe entre estas piezas?". Relaciones: `compatible_con`,
`misma_familia`, `misma_categoria`, `reemplaza`, `usado_con`, `evitar_con`,
`recomendado_para`, `aprendido_de`, `corregido_por`, `derivado_de`,
`requiere`, `depende_de`, `alternativa_a`.

Cada relación tiene `confidence` (1.0 validada por ingeniería, 0.95 aprendida
de muchos proyectos, 0.70 inferida automáticamente, 0.40 hipótesis) y
`origen` (builder, engineering, manual, usuario, proyecto, correccion,
catalogo, heuristica).

El `AutomaticGraphBuilder` descubre relaciones evidentes (misma familia,
misma categoría) sin usar LLM. El `CompatibilityEngine` (sin IA, ingeniería
pura) determina compatibilidad real usando dimensiones, capacidad, carga,
reglas e historial.

**Regla fundamental:** todas las relaciones deben ser trazables, explicables
y, cuando sea posible, derivadas de reglas de ingeniería o experiencia
validada.

---

## CAPÍTULO 6 — ENGINEERING ENGINE

El corazón del sistema. Nunca hay cálculos dentro del prompt. Claude solo
puede decir "necesito calcular la carga" y llamar `calculate_load()`.

Módulos: `calculator.py`, `compatibility.py`, `coordinates.py`,
`corrections.py`, `dimensions.py`, `loads.py`, `planner.py`,
`recommendations.py`, `replacements.py`, `rules.py`.

El Engineering Engine nunca devuelve texto — devuelve estructuras
(`{warnings, errors, components, coordinates, metrics, recommendations}`).
Claude interpreta ese resultado.

**Regla fundamental:** la IA nunca debe inventar una coordenada, una carga o
una compatibilidad. Toda decisión técnica debe provenir del Engineering
Engine. El LLM actúa como orquestador y comunicador, no como calculista.

---

## CAPÍTULO 7 — CLAUDE + TOOLS + LANGGRAPH + LANGSMITH + MCP

Claude únicamente: comprende la intención, planifica, decide qué Tool usar,
redacta la respuesta. Nunca calcula, valida, consulta SQL, busca embeddings
o decide compatibilidades directamente.

### 7.11 ¿Necesitamos muchos agentes? — **No.**

Ese es uno de los mayores errores actuales. Cada agente adicional que llama
un LLM multiplica llamadas, tiempo y costo. **Nosotros utilizaremos un único
agente: Claude + Tools + Engineering + RAG + Graph.**

### 7.12 ¿Cuándo usar varios agentes?

Solo cuando exista razonamiento independiente real (ej. Ventas, Ingeniería,
Compras, Legal piensan distinto). En este proyecto todo el razonamiento es
de ingeniería — un único Claude basta.

*(Aclaración importante, discutida durante el desarrollo: un nodo de
LangGraph NO tiene que ser una llamada al LLM — la mayoría pueden ser Python
puro. La crítica a "9 agentes = 9 llamadas caras" solo aplica si cada nodo
efectivamente invoca un LLM. Un grafo con 2 nodos LLM (Supervisor +
Proyectista) y el resto determinista es razonable y no contradice 7.11/7.12.)*

**Regla fundamental:** Claude no es la inteligencia del proyecto. La
inteligencia es la combinación de ingeniería determinística + RAG +
Knowledge Graph + Supabase + Tools + memoria. Claude es el director de
orquesta.

---

## CAPÍTULO 8 — MEMORIA, APRENDIZAJE CONTINUO Y AUTO-MEJORA

Cuatro memorias: **Conversacional** (temporal, vive solo la sesión),
**del Proyecto** (permanece toda la vida del proyecto, versionada — nunca se
sobrescribe), **de Conocimiento** (el RAG, crece continuamente), y
**Operacional** (telemetría: tokens, costo, tiempo, errores).

No todo debe aprenderse — solo lo que un ingeniero valide. Pipeline:
Proyecto finalizado → Validado → Extraer conocimiento → Chunk → Embedding →
Knowledge Graph → Knowledge Base. Nunca se almacena el proyecto completo,
solo el conocimiento reutilizable.

**Regla fundamental:** el sistema no aprende porque un modelo "recuerde".
Aprende porque transforma experiencias validadas en conocimiento
estructurado, versionado y reutilizable.

---

## CAPÍTULO 9 — PRODUCCIÓN, OBSERVABILIDAD, SEGURIDAD Y DESPLIEGUE

Nunca guardar claves en el código — todo en `.env` (ver `backend/.env.example`).
Nunca exponer API keys/tokens en prompts. Todo debe generar logs — nunca
`print()` en producción. LangSmith traza toda interacción: prompt, contexto,
herramientas, tokens, tiempo, costos, resultado.

**Regla fundamental:** la infraestructura debe ser invisible para el
usuario, pero completamente observable para el equipo de desarrollo. Todo
debe ser trazable, reproducible, auditable y recuperable.

---

## CAPÍTULO 10 — EL PROYECTISTA IA

Claude nunca diseña directamente — coordina. El diseño emerge de Claude +
Engineering Engine + RAG + Knowledge Graph + Catálogo + Reglas +
Correcciones + Historial.

Si falta información crítica, el sistema pregunta — nunca inventa.

**Principio final:** el objetivo nunca fue crear un chatbot. Es construir una
plataforma de ingeniería asistida por IA donde el conocimiento esté
estructurado, las decisiones sean trazables, los cálculos sean
determinísticos, la IA razone sobre información confiable, y cada proyecto
mejore al siguiente. El LLM deja de ser "la inteligencia" y se convierte en
el coordinador de un sistema de ingeniería completo.

---


## Estado real, historial y hoja de ruta

> Unifica lo que antes vivía separado en ESTADO_DEL_PROYECTO.md. Última
> actualización: julio 2026 (cierre de Sprint 2, fases 2-5, rama `josue`).
> El detalle línea por línea de Sprint 2 vive en `SPRINT2_APRENDIZAJE_CONTINUO.md`;
> aquí queda el resumen ejecutivo y el historial de las sesiones grandes.

### Tabla de estado por pieza del manual

| Pieza del manual | Estado |
|---|---|
| FastAPI + Telegram + Supabase + Claude | Implementado y funcionando |
| RAG (embeddings + vector search + sync) | Implementado (`app/ai/rag/`) — Voyage AI, 1024 dims; `match_knowledge` verificado en vivo contra Supabase |
| Knowledge Graph (reemplaza_por / evitar_con / compatible_con) | Implementado (`app/ai/rag/graph.py`) — upsert atomico via RPC, lectura inyectada al prompt via Context Builder |
| Compatibility Engine | Implementado (`app/engineering/compatibility.py`) — determinista, sin IA |
| Context Builder | Implementado (`app/ai/context_builder.py`) — incluye relaciones del grafo desde Sprint 2 |
| Validator Engine + reintento automatico | Implementado — errores bloqueantes regresan a Claude (Cap. 6.4) antes de responder |
| PromotionEngine (aprendizaje -> regla permanente) | Implementado (`app/engineering/promotion.py`) — pendiente que se apliquen migraciones para tener efecto real con datos de produccion |
| Dataset de evaluacion (Cap. 8) | Implementado (`app/engineering/evaluacion.py`) |
| LangSmith (costo, retriever, run_id, 2a ruta LLM) | Implementado (`app/ai/tracing.py`) — no-op si no esta configurado |
| LangGraph multi-agente | No implementado a proposito — ver nota del Capitulo 7 |
| MCP | No implementado — sin caso de uso concreto todavia |
| Dashboard Flutter (panel humano sobre correcciones/RAG) | En progreso, en paralelo (ver seccion de pendientes) |

### Historial — sesion de auditoria + Fase 3 (previa a Sprint 2)

Bugs criticos encontrados y corregidos (rutas rotas tras una reestructuracion
de carpetas de `app/services/` a `app/ai/` + `app/engineering/`):

1. `claude_client.py` cargaba el prompt de sistema VACIO (`SYSTEM_PROMPT_BASE`
   con 0 caracteres) por una ruta `BASE` mal calculada. Corregido.
2. `pipeline.py` no encontraba los generadores (PDF/XLSX/modelo 3D) por la
   misma causa. Corregido.
3. `catalogo_pm_service.py` apuntaba a una carpeta de conocimiento que ya no
   existia — el fallback devolvia `[]`. Corregido.
4. `validator_engine.py` tenia la misma ruta rota, mas una funcion muerta y
   rota (`validar_proyecto_pm`, residuo de una version anterior, nunca
   llamada). Ruta corregida, funcion eliminada.
5. `langsmith_extra` colaba un `TypeError` si LangSmith no estaba instalado.
   Corregido.
6. `chunkers.py` habia perdido la funcion `correccion_to_document` entre
   copias de trabajo. Restaurada.

Piezas nuevas de esa sesion: Compatibility Engine, Context Builder, reintento
automatico ante errores bloqueantes, indexacion RAG en tiempo real (antes solo
via `/rag/sync` manual), dataset de evaluacion contra ejemplos "dorados".

### Historial — Sprint 2: aprendizaje continuo, fases 2-5 (esta sesion)

Con Fase 0/1 ya resueltas en una sesion anterior (SkuDiffExtractor,
CorrectionProcessor, cableado en el flujo vivo), esta sesion cerro el resto:

- **Fase 2 (estadisticas):** endpoint `GET /stats/top` y `GET /stats/sku/{sku}`
  sobre `knowledge_stats`.
- **Fase 3 (grafo, cierre):** upsert atomico de relaciones via RPC
  `reforzar_relacion` (elimina la condicion de carrera del select+update
  anterior); relaciones nuevas `evitar_con`/`compatible_con` ademas de
  `reemplaza_por`; el Context Builder ahora LEE el grafo e inyecta las
  relaciones aprendidas al prompt (antes era write-only).
- **Fase 4 (PromotionEngine):** estados explicitos por ocurrencias
  (nueva -> importante -> candidata -> permanente) que materializan la
  relacion como fila real en `reglas_armado`.
- **Fase 5 (LangSmith):** `usage_metadata` para que calcule costo real sobre
  ambas rutas LLM (proyectista PM + agente rapido de ensamble), system
  prompt real en la traza, span de retriever en la busqueda RAG, `run_id`
  persistido en `disenos_racks` para correlacionar fila <-> traza.
- **Limpieza:** eliminado el duplicado muerto `app/services/pm_rackbot/*`,
  los stubs de 0 bytes de `app/graph/*` y varios de `app/engineering/*` y
  `app/{models,schemas}/*` (nada los importaba); normalizador de SKU
  unificado (`sku_diff.normalizar_sku` <- `validator_engine._codigo_base`);
  `node_modules/` sacado del indice de git (no del disco).
- **Merge con `origin/josue`:** esa rama remota tenia 4 commits paralelos
  (trabajo de otra sesion/maquina sobre estos mismos archivos, en un punto
  anterior a varias de las correcciones de arriba). Se resolvieron ~16
  conflictos de contenido comparando ambas versiones; en casi todos los
  casos la version de `origin` era la mas antigua (predatabla a la
  reestructuracion de carpetas o a CorrectionProcessor) y se conservo la
  version actual. Se rescato de paso `sql_rag_match_function.sql` (suelto en
  la raiz del repo) como migracion versionada `0005_rag_match_knowledge.sql`,
  y se confirmo en vivo que ya esta aplicada en Supabase (dimension real:
  1024, no 1536 como decia el archivo suelto).

### Pendiente / proximos pasos

0. **CRITICO — verificar politicas RLS en Supabase (hallazgo de revision senior de BD):**
   `proyecto_pm_service.py` genera el link del visor 3D embebiendo
   `SUPABASE_URL` + `SUPABASE_KEY` (la anon key) directamente en la URL,
   para que el frontend consulte Supabase sin pasar por el backend. Si las
   politicas RLS de `catalogo_piezas`/`disenos_racks` no estan acotadas
   (solo lectura, por fila/sesion), cualquiera con ese link tiene acceso de
   lectura/escritura a esas tablas via la API REST publica de Supabase. No
   se pudo confirmar el estado de RLS con la key disponible (requiere el
   dashboard de Supabase o una key con permisos de admin) —
   **verificarlo manualmente es la accion mas urgente de todo este documento.**
1. **Migraciones sin aplicar en Supabase** (`backend/db/migrations/0002` a
   `0004`, mas la nueva `0006` de indices — `0001` y `0005` ya
   confirmadas aplicadas en vivo, corrigiendo el estado anterior que daba
   `0001` por pendiente): requieren connection string directa de Postgres
   o pegar el SQL a mano en el SQL Editor. Sin esto: el upsert atomico de
   relaciones falla (confirmado con error PGRST202 al invocar el RPC;
   best-effort, se loguea) y `langsmith_run_id` no se persiste.
   `knowledge_stats`/`/stats/*` SI funcionan ya (migracion 0001 aplicada).
   Ver instrucciones exactas en `backend/db/migrations/README.md`.


### Decisiones de arquitectura tomadas (para no repetir la discusion)

- **Un solo Claude, sin LangGraph multi-agente** — decision explicita
  documentada arriba (Capitulo 7): no hay razonamiento verdaderamente
  independiente que lo justifique hoy.
- **RAG complementa, no reemplaza** — el catalogo completo se sigue mandando
  siempre a Claude; el RAG solo inyecta correcciones aprendidas por
  similitud semantica. No se implemento "hybrid search" completo con ranking
  multi-fuente del manual — version mas simple, suficiente para el volumen
  actual.
- **Compatibility Engine y validador son deterministas, sin IA** — cumple la
  regla central del manual ("la IA nunca debe inventar una compatibilidad").
- **Umbrales del grafo de conocimiento:** confidence sube hasta 0.95 a las 30
  ocurrencias; promocion a regla permanente (`reglas_armado`) a las 50.
  Estados intermedios del PromotionEngine: 5 (importante), 20 (candidata).
- **Heuristica v1 de `evitar_con`/`compatible_con`:** conservadora y
  documentada en `learning.py` — se basa en que piezas de OTRA familia
  convivan (o dejen de convivir) en el mismo despiece tras una correccion.
  A revisar/ajustar conforme se acumulen datos reales.
- **`node_modules` en git:** sacado del indice (no del disco), agregado a
  `.gitignore` junto con las reglas de Flutter/Dart.

### Sugerencias

- **Prioridad 1:** aplicar las 4 migraciones pendientes en Supabase — es lo
  unico que bloquea que Fases 2, 3 y 4 de Sprint 2 tengan efecto real (hoy
  el codigo ya esta listo y es best-effort, pero sin las tablas/RPC no hay
  datos que mostrar).
- **Resolver la duplicacion del dashboard Flutter** antes de que crezca mas:
  hoy coexisten (al menos) una copia vacia (scaffold de `flutter create`,
  ya en `origin/josue`) y una o mas copias con app real avanzada (en el
  worktree paralelo y en el stash de esta sesion). Vale la pena una sesion
  dedicada solo a esto, sin trabajo de backend en paralelo, para evitar
  reconciliaciones como la de hoy.
- **Decidir si vale la pena arreglar `diseno_service.py`** (el bug de import
  preexistente) o eliminarlo del todo si el "Agente de Ensamble rapido" ya
  no se va a usar — hoy es codigo muerto que puede confundir a quien lo lea.
- **Considerar `pg_dump` del esquema real** (`0000_baseline.sql`, mencionado
  en `backend/db/migrations/README.md`) la proxima vez que alguien tenga
  acceso directo a Postgres — cierra la brecha de documentacion del schema
  real vs. lo que el codigo asume.
- **Revisar los archivos duplicados en la raiz del repo** (`main.py`,
  `package.json`, `package-lock.json` — espejos de sus equivalentes en
  `backend/`): si no tienen un proposito de despliegue especifico, valdria
  la pena eliminarlos para evitar que diverjan silenciosamente.

### Historial — revision senior (empty files, BD, ML, frontend) + nuevas features

Sesion de seguimiento: se lanzaron 3 revisiones en paralelo (archivos vacios
del backend, Supabase/BD + pipeline de embeddings, Flutter) actuando como
senior de cada area, y se ejecuto el plan resultante:

- **44 archivos vacios eliminados** (`app/agents/*`, `app/tools/*`,
  `app/graph/*`, `app/engineering/{calculator,coordinates,corrections,
  dimensions,engine,loads,planner,recommendations,replacements,rules}.py`,
  `app/models/*`, `app/schemas/*`, `app/core/{dependencies,settings}.py`,
  `app/ai/rag/ingestors/{manuales,proyectos,reglas}.py`) — esqueleto de la
  arquitectura multi-agente de los capitulos 1/6/7, descartada por decision
  de diseno del propio manual. Se discutio explicitamente con el usuario si
  valia la pena reconstruir ese multi-agente (ver seccion de Ventas/Cotizador
  abajo) antes de eliminar — se opto por NO reconstruirlo para el alcance
  actual.
- **`app/core/logger.py` implementado**: antes NO existia ningun
  `logging.basicConfig()` en el proyecto — la mayoria de los `log.info(...)`
  de las 19 loggers de `app/` nunca se veian. Ahora configurado al arrancar
  (`app/main.py`), nivel via `LOG_LEVEL`.
- **`repository.proyectos()` eliminado** (tabla `proyectos_pm`, sin caller).
- **Documentacion de migraciones corregida**: `knowledge_stats`/
  `increment_stat` (migracion 0001) YA estaba aplicada en produccion — se
  confirmo invocando el RPC en vivo. El estado anterior la daba por
  pendiente por error.
- **`voyage_provider.py`**: retry con backoff ante rate-limit/errores
  transitorios (antes una sola falla tumbaba `/rag/sync` completo).
- **Nueva migracion `0006_indices_sugeridos.sql`**: indices sobre
  `correcciones_armado` y `knowledge_edges` (patrones de consulta ya
  existentes en el codigo, sin soporte de indice).
- **Flutter**: 0 warnings (antes 3, imports sin uso); dos features nuevas
  con el mismo patron de capas del resto (`estadisticas`: pantalla sobre
  `/stats/top` y `/stats/sku/{sku}`, antes sin ninguna superficie humana;
  `rag`: buscador semantico + boton de sincronizacion sobre `/rag/search`
  y `/rag/sync`); retry interceptor en `ApiClient`; `AppTheme.dark`
  definida pero NO activada (ver nota abajo).
- **`main.dart` reconfirmado presente y correcto** (el usuario pidio
  "agregarlo de nuevo" por precaucion; ya estaba desde el merge anterior).

#### Nota — tema oscuro parcial, a proposito
`AppTheme.dark` existe pero `main.dart` sigue forzando `theme: AppTheme.light`
sin `darkTheme`/`themeMode`. Motivo: casi todos los widgets propios
(`PanelCard`, `KpiCard`, etc. en `shared/widgets/app_widgets.dart`, y cada
pantalla) usan colores de `AppColors` fijos en vez de consultar
`Theme.of(context)` — activar `ThemeMode.system` hoy dejaria paneles claros
flotando sobre un fondo oscuro (dark mode roto a medias), peor que no
tenerlo. Falta retocar esos widgets antes de activarlo.

#### Discusion — ¿el multi-agente descartado si tendria sentido para Ventas/Cotizador?
El usuario señalo, correctamente, que el bot ya entrega cotizacion (ademas
del render 3D, planos, despiece). Al revisar el codigo: la cotizacion de
hoy es aritmetica pura (`importe = pzas × precio_catalogo`, generada por el
mismo Claude que diseña, en `exportar_xlsx.py`) — no hay razonamiento de
ventas independiente todavia, asi que un segundo agente NO se justificaba
para lo que existe. El usuario confirmo que SI quiere construir eso de
verdad: descuentos/paquetes por volumen, propuesta comercial persuasiva
separada del reporte tecnico, e historial de cliente tipo CRM. Esto queda
como **iniciativa separada, pendiente de diseño propio** (tablas nuevas en
Supabase, punto de generacion de la propuesta, posible pantalla en Flutter)
antes de implementarse — no se toco codigo de esto en esta sesion.

### Historial — bucket de ejemplos, modulo de arquitectura, bug de archivo fantasma

Sesion de seguimiento (mismo dia): el usuario agrego un bucket con racks de
ejemplo terminados en Supabase Storage (`modelos/modelos 3d terminados/`) y
carpetas preparadas para precios unitarios/cotizaciones futuras, pidio un
modulo visual del tipo "red neuronal" de como funciona el proyecto, y
reporto un bug (modelo eliminado en Supabase que seguia apareciendo en el
Compresor Draco CAD con 0 B).

- **Bug del archivo fantasma — corregido:** `storage_service.py`
  (`_infer_modelo_files_from_catalogo`) sintetiza la lista de modelos a
  partir de la columna `catalogo_piezas.url_modelo_glb` como *ultimo
  recurso*, cuando el listado real de Storage viene vacio (p. ej. si era
  el unico archivo de la carpeta). Al borrar el archivo directo en el
  dashboard de Supabase (sin pasar por la app), la fila de la tabla queda
  huerfana con una URL que ya no existe — y esa fila fantasma se seguia
  mostrando con tamaño 0 en vez de omitirse. Ahora se hace HEAD a la URL
  real: si responde 404 (o el fallback del SDK tampoco confirma que
  exista), la fila se omite en vez de mostrarse con 0 B.
- **Bucket de racks de ejemplo — accesible desde Alimentar IA:** se agrego
  `StorageBucket.modelosTerminados` (bucket `modelos`, raiz fija en
  `modelos 3d terminados`, separado de `modelos 3d de racks` que administra
  el Compresor Draco CAD) como tercera pestaña del explorador. Hoy solo
  contiene el primer ejemplo subido por el usuario
  (`(-)_RACK_180X61X151.glb`); las carpetas `cotizaciones/Racks` y
  `precios unitarios/productos` existen pero siguen vacias (placeholders) —
  nada que ingestar todavia. Pendiente de decidir (no resuelto aqui): si
  estos racks de ejemplo deben alimentar el RAG/Knowledge Graph de alguna
  forma automatica, o si por ahora solo sirven de referencia manual.
- **Nuevo modulo "Arquitectura del Sistema"** (`features/arquitectura/`):
  visualizacion tipo red — nodos (Usuario, FastAPI, Context Builder, RAG,
  Knowledge Graph, Claude, Engineering Engine, PromotionEngine,
  Generadores, Supabase, LangSmith, Multi-agente) conectados segun el flujo
  real, con un pulso animado viajando por cada conexion. Refleja el estado
  REAL de cada pieza (verde = implementado, ambar = parcial, gris punteado
  = descartado a proposito — el nodo "Multi-agente/LangGraph" aparece asi,
  consistente con la decision del capitulo 7.11). Tocar un nodo muestra su
  descripcion. Contenido 100% estatico (sin llamadas al backend), sin
  cubit/datasource — es documentacion viva, no telemetria en vivo.
- **Migraciones — TODAS (0001-0005) confirmadas aplicadas en produccion**
  (se corrige el estado anterior: 0002/0003/0004 se creian pendientes,
  pero ya estaban aplicadas). Solo `0006_indices_sugeridos.sql` (creada
  en la sesion anterior, son indices de performance, no bloqueantes) sigue
  pendiente. El hallazgo CRITICO de RLS (seccion de pendientes arriba)
  sigue sin verificar — no se pudo confirmar con la key disponible.

Verificado con `flutter analyze`: 0 issues. Backend: 12/12 tests, import
completo sin errores.

### Historial — fix de rate-limit en /rag/sync, modulo de arquitectura ampliado

Sesion de seguimiento (mismo dia): el usuario reporto un log de produccion con
`/rag/sync` devolviendo 500 tres veces seguidas, siempre agotando los 3
reintentos contra `RateLimitError` de Voyage AI (tier gratis: 3 RPM / 10K TPM,
sin metodo de pago). Tambien pidio "explayar" el modulo de Arquitectura del
Sistema y una guia para probar de punta a punta que el sistema aprende de
verdad.

- **Causa raiz del rate-limit — no era solo el backoff:** `CatalogoIngestor.sync()`
  y `CorreccionesIngestor.sync()` llamaban a `embedding_service.embed_text()`
  **una vez por cada fila** (79 piezas de catalogo + ~6 correcciones), aunque
  el proveedor (`voyage_provider.py`) ya tenia `embed_documents()` implementado
  para mandar varios textos en una sola llamada. Con 3 RPM, 79 llamadas
  secuenciales agotan el limite casi de inmediato.
- **Fix aplicado (dos partes):**
  1. `voyage_provider.py`: se separo el manejo de `RateLimitError` del resto
     de errores transitorios — backoff propio de `21 * intento` segundos
     (suficiente para que el limite de 3 RPM se libere) en vez del backoff
     corto de `2 * intento` que ya usaban timeouts/desconexiones.
  2. `catalogo.py` y `correcciones.py`: reescritos en dos pasadas. La primera
     pasada calcula checksums y decide que filas cambiaron **sin llamar a
     Voyage**. La segunda pasada embebe SOLO las filas pendientes, agrupadas
     en lotes de 20 via `embed_documents()`, con una pausa proactiva de 21s
     entre lotes si hay mas de uno. Resultado: un sync completo de las 79
     piezas pasa de ~79 llamadas a Voyage a ~4, y ya no depende de que el
     reintento reactivo alcance — la mayoria de los sincronizados de aqui en
     adelante (solo hay cambios incrementales) ni siquiera necesitan un
     segundo lote.
- **Modulo "Arquitectura del Sistema" — ampliado:** cada nodo ahora tiene
  capitulo del manual de referencia (`capituloManual`), que recibe
  (`entradas`) y que entrega (`salidas`) — visible al tocar el nodo. Se
  agrego el nodo `ventas` (Ventas / Cotizador IA, estado "futuro", conectado
  desde Generadores) reflejando la iniciativa separada de Ventas/Cotizador
  discutida y confirmada con el usuario. Se agregaron dos listas numeradas
  debajo del diagrama: **Flujo 1 — Como se genera un diseño** (9 pasos, del
  mensaje del cliente a los archivos entregados) y **Flujo 2 — Como aprende
  el sistema** (6 pasos, de una correccion manual a una regla promovida en
  `reglas_armado`). Tocar un paso resalta el nodo correspondiente en el mapa.
  Sigue siendo contenido 100% estatico, sin llamadas al backend.
- **Guia de pruebas de aprendizaje continuo:** documentada para el usuario en
  la conversacion (no se creo un archivo nuevo) — cubre como verificar con
  datos reales que una correccion manual efectivamente refuerza el
  Knowledge Graph, que la siguiente solicitud usa lo aprendido, y que
  PromotionEngine materializa una regla al cruzar 50 repeticiones.

Verificado con `flutter analyze`: 0 issues. Backend: 12/12 tests (`test_sku_diff.py`
+ `test_learning.py`), import completo (`app.main`) sin errores.
