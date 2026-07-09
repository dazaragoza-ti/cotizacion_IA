# Especificaciones del Proyecto — Plataforma de Diseño de Racks Industriales

> Documento generado el 2026-07-09. Describe el estado **real** del código a esta
> fecha (no la visión aspiracional de `AI_ENGINEERING_MANUAL.md`, aunque se apoya
> en él). Cualquier cosa que no esté marcada como "implementado" en este documento
> puede no reflejar cambios posteriores — para el estado más actual, revisar el
> código y `git log`.

---

## 1. Resumen ejecutivo

Plataforma para **PM La Piedad / Grupo PEME** que automatiza el diseño técnico de
racks industriales (selectivo, cantilever, entrepiso/mezanine). Un vendedor o
cliente describe lo que necesita por **Telegram** (texto, fotos, PDF de planos),
y el sistema entrega automáticamente: descripción del diseño, despiece,
cotización, un JSON estructurado del proyecto, planos PDF, XLSX de despiece y
cotización, modelo 3D (GLB/DAE), renders PNG, y un link a un visor 3D interactivo
en el navegador.

El sistema **aprende de las correcciones humanas**: cuando alguien ajusta un
diseño, el sistema detecta el cambio, lo refuerza en un grafo de conocimiento, y
si un mismo ajuste se repite muchas veces, se convierte en una regla permanente
que se aplica automáticamente en adelante — sin que nadie tenga que repetirla.

Hay dos superficies de usuario:
- **Telegram** — el canal real de trabajo diario (vendedores/clientes).
- **Dashboard Flutter** (`frontend/rackbuilder_dashboard/`) — panel administrativo
  para supervisar el sistema: catálogo, historial, estadísticas de aprendizaje,
  búsqueda semántica, arquitectura del sistema, compresión de modelos 3D.

---

## 2. Arquitectura real (no la aspiracional)

```
Usuario (Telegram)
   │
   ▼
FastAPI (app/main.py + routers/ + telegram/)
   │
   ▼
proyecto_pm_service.py  ── orquesta todo el flujo ──┐
   │                                                 │
   ├─▶ Claude (único LLM, un solo turno, con visión) │
   │      system.md + proyectista.md + catálogo real │
   │      + reglas + correcciones + fichas técnicas   │
   │                                                 │
   ├─▶ Validator Engine (determinista, sin IA)        │
   │      valida NOM-006/251, cargas, factor seg.,    │
   │      combinaciones de catálogo — si falla,       │
   │      regresa a Claude (máx. 2 intentos)          │
   │                                                 │
   ├─▶ Compatibility Engine (determinista)             │
   │      valida contra catalogo_pm en vivo            │
   │                                                 │
   ├─▶ Corrección de precios (determinista)            │
   │      sobreescribe precios del JSON de Claude con  │
   │      los reales de Supabase (catalogo_pm)         │
   │                                                 │
   ├─▶ Pipeline de generadores (subprocess, deterministas):
   │      modelo_3d.py → GLB/DAE + 5 renders PNG
   │      render_html.py → visor 3D HTML autocontenido
   │      pm_plano.py → PDF de planos (4 hojas)
   │      exportar_xlsx.py → XLSX despiece + cotización
   │                                                 │
   └─▶ Supabase (disenos_racks, correcciones_armado,   │
        reglas_armado, catalogo_pm, knowledge_*)       │
                                                        │
   Si hubo corrección manual ─────────────────────────┘
        │
        ▼
   Knowledge Graph (SkuDiffExtractor detecta el cambio,
   RPC reforzar_relacion incrementa contador atómico)
        │
        ▼
   Promotion Engine (umbrales 5 / 20 / 50 repeticiones →
   nueva / importante / candidata / regla permanente en
   reglas_armado)
        │
        ▼
   Próxima solicitud: Context Builder inyecta la relación
   (o la regla ya promovida) directo en el prompt de Claude
```

**Decisión de arquitectura explícita (documentada en el propio manual, Cap.
7.11):** un único Claude, sin LangGraph ni multi-agente. La tarea es
"extracción estructurada de una sola pasada", no razonamiento abierto — no hay
dominio con razonamiento verdaderamente independiente todavía que lo justifique.

---

## 3. Backend (`backend/app/`)

### 3.1 Núcleo

| Archivo | Qué hace |
|---|---|
| `main.py` | Crea la app FastAPI, registra CORS, routers, lifespan del bot de Telegram, y dos exception handlers globales que persisten errores 5xx/no manejados en `sistema_errores` (visible en el dashboard). |
| `config.py` | Variables de entorno centralizadas (`URL_FRONTEND`, `CORS_ORIGINS`, etc.). |
| `clients.py` | Clientes singleton: `supabase`, `anthropic_client`. |
| `cors.py` | Middleware que permite cualquier `http://localhost:*` en desarrollo (Flutter web cambia de puerto en cada corrida). |
| `core/logger.py` | `logging.basicConfig()` centralizado — antes de esto, ningún log se veía. |
| `core/error_logger.py` | `registrar_error()` — best-effort, inserta en `sistema_errores`; `inferir_componente()` mapea la ruta que falló a un nodo del mapa de Arquitectura. |

### 3.2 Routers (`routers/`) — la API pública

| Router | Endpoints | Qué expone |
|---|---|---|
| `sistema.py` | `GET /`, `GET /config/supabase`, `GET /sistema/errores`, `POST /sistema/errores/{id}/resolver` | Health check, credenciales de Supabase para el frontend, fallos recientes del backend. |
| `disenos.py` | `GET /disenos/historial`, `GET /disenos/sesion/{id}` | Historial de diseños generados y sus versiones. |
| `catalogo.py` | `GET /catalogo/piezas`, `POST /catalogo/upload-modelo`, `DELETE`, endpoint de descarga | CRUD del catálogo de piezas con modelos 3D reales (Draco). |
| `correcciones.py` | `GET /correcciones`, `DELETE /correcciones/{id}` | Correcciones capturadas del agente — auditoría, se aplican automáticamente sin aprobación humana. |
| `rag.py` | `POST /rag/search`, `POST /rag/sync` | Búsqueda semántica y sincronización de embeddings. |
| `stats.py` | `GET /stats/sku/{sku}`, `GET /stats/top` | Contadores `knowledge_stats` (usado/reemplazado/rechazado/recomendado) por SKU. |
| `storage.py` | Explorador de Supabase Storage (buckets cotizaciones, precios unitarios, modelos), subida de archivos, OCR de entrenamiento. |

### 3.3 Services (`services/`) — coordinan casos de uso

| Servicio | Rol |
|---|---|
| `proyecto_pm_service.py` | **El orquestador real.** Llama a Claude (visión), corre el validador con reintento (máx. 2), corrige precios contra `catalogo_pm`, guarda en `disenos_racks`, corre el pipeline de generadores, registra correcciones si aplica. |
| `pm_proyectista.py` | Utilidades del prompt del proyectista PM. |
| `catalogo_service.py` / `catalogo_pm_service.py` | Consultan `catalogo_piezas` (modelos 3D reales) y `catalogo_pm` (precios reales), con fallback a JSON local si Supabase falla. |
| `correcciones_pm_service.py` | Detecta si un cambio es una "corrección" (vs. un diseño nuevo) y arma la fila para `correcciones_armado`. |
| `reglas_service.py` | Consulta `reglas_armado` (incluye las promovidas por Promotion Engine) y el último diseño de una sesión. |
| `historial_service.py` | Registra cada generación (éxito o error) para auditoría interna. |
| `storage_service.py` | Explorador/gestor de Supabase Storage — incluye el fix del "archivo fantasma" (HEAD real a la URL antes de listar). |
| `ocr_service.py` | OCR de documentos subidos (Whisper/Groq para voz por Telegram; procesamiento de imágenes/PDF). |

### 3.4 `ai/` — todo lo relacionado a Claude y RAG

| Módulo | Qué hace |
|---|---|
| `context_builder.py` | Arma el contexto que se le da a Claude (catálogo filtrado + correcciones RAG + relaciones del grafo). |
| `tracing.py` | Integración con LangSmith — no-op si no está configurado. Traza prompt real, tokens, costo, run_id correlacionado con `disenos_racks`. |
| `clients/claude_client.py` | Cliente de Anthropic. |
| `prompts/system.md` + `proyectista.md` | **El prompt real en producción** (idéntico contenido, dos copias). Incluye checklist obligatorio (NOM-251, NOM-006, montacargas, pasillo central), fichas técnicas con prioridad sobre la memoria del modelo, reglas estructurales exactas del catálogo (frentes, fondos, alturas, cargadores, anclaje, familias, peraltes), formato de salida estricto (contrato JSON `layout`). |
| `prompts/supervisor.md`, `cotizador.md`, `renderizador.md`, `validador.md` | **Código muerto** — residuo del esquema multi-agente original (Cap. 1 del manual). Ningún archivo Python los importa. |
| `pipelines/pipeline.py` | Orquesta los 4 generadores en secuencia, tolerante a fallos (si uno falla, sigue con el resto). |
| `generators/modelo_3d.py` | Genera GLB/DAE + 5 renders PNG (perspectiva, planta, frontal, lateral, módulo de detalle) con trimesh + matplotlib. Geometría paramétrica real (postes 73mm carga pesada, x-bracing en zigzag), sin fotos ni texturas. |
| `generators/render_html.py` | Genera un visor 3D HTML autocontenido (embebe el GLB en base64) — determinista, sin depender de Supabase. |
| `generators/pm_plano.py` | PDF de planos (4 hojas), incrusta los PNG generados. |
| `generators/exportar_xlsx.py` | XLSX de despiece y cotización — el precio unitario ahora se verifica contra `catalogo_pm` antes de generar (fix de esta sesión). |
| `adapters/adaptador_visor.py` | Traduce el JSON del proyectista (`layout`/`materiales`) al contrato `marcos/vigas/mensulas/cargadores` que lee el visor 3D en vivo (GitHub Pages). Prioriza SKUs reales con `.glb`; genera cargadores con dimensiones calculadas (no hay `.glb` real para esa pieza en ningún proveedor). |
| `rag/*` | Pipeline RAG completo: `embeddings.py` (Voyage AI, 1024 dims), `vector_store.py`, `search.py`, `sync.py`, `checksum.py` (evita recalcular embeddings sin cambios), `chunkers.py`, `graph.py` + `graph_builder.py` (Knowledge Graph), `repository.py`, `ingestors/catalogo.py` + `correcciones.py` (batched, 2 pasadas, para no agotar el rate-limit de Voyage). |

### 3.5 `engineering/` — la ingeniería determinista (sin IA)

| Módulo | Qué hace |
|---|---|
| `validator_engine.py` | Valida el JSON de Claude: frentes/fondos/alturas de catálogo exactos, cantidad de cargadores según frente (2 si ≥2804mm, si no 1), anclaje según altura, factor de seguridad ≥1.5, familias sin mezclar (pesada vs. ligera), despiece coherente. |
| `compatibility.py` | Compatibility Engine — compatibilidad de piezas contra `catalogo_pm` en vivo. |
| `sku_diff.py` | `SkuDiffExtractor` — compara un despiece antes/después de una corrección y extrae qué SKU cambió por cuál. |
| `correction_processor.py` | Registra la corrección (automática, sin aprobación humana) y dispara el refuerzo del grafo. |
| `learning.py` | Heurística de relaciones `evitar_con`/`compatible_con` (piezas de otra familia que conviven o dejan de convivir en el despiece). |
| `promotion.py` | **PromotionEngine** — traduce ocurrencias acumuladas en estado (nueva/importante/candidata/permanente) y materializa en `reglas_armado` a las 50 repeticiones, idempotente. |
| `metrics.py` | Contadores de `knowledge_stats` (veces usado/reemplazado/rechazado/recomendado). |
| `evaluacion.py` | Dataset de evaluación contra ejemplos "dorados". |

### 3.6 `telegram/`

`bot.py` + `handlers.py` — reciben mensajes/imágenes/PDF/voz, orquestan la llamada a `proyecto_pm_service`, envían los archivos generados de vuelta. Nunca contienen lógica de negocio.

---

## 4. Frontend (`frontend/rackbuilder_dashboard/`, Flutter Web)

Arquitectura limpia por feature (`domain/presentation/data`), BLoC/Cubit, capa de red centralizada (Dio + retry con backoff).

| Feature | Pantalla | Qué hace |
|---|---|---|
| `dashboard` | Analíticas | Métricas globales en vivo: proyectos, tokens (real, consulta directa a Supabase), costo real (Sonnet 4.6: $3/$15 por millón). |
| `catalogo` | Subir Catálogo | Sube modelos `.glb`/`.gltf` con compresión Draco, los registra en `catalogo_piezas`. Vista previa 3D al tocar una pieza con modelo. |
| `historial` | Historial de Diseños | Lista sesiones y versiones. Botón "Ver render 3D" por versión — abre el visor en vivo embebido (iframe) usando las credenciales de Supabase cacheadas. |
| `estadisticas` | Aprendizaje continuo | Explica en 3 pasos cómo aprende el sistema, lista correcciones reales con progreso visual hacia regla permanente (umbrales 5/20/50), ranking de piezas, búsqueda por SKU con explicación de cada contador. |
| `rag` | Búsqueda RAG | Búsqueda semántica sobre `knowledge_chunks` + botón de sincronización manual. |
| `modelos_3d` | Compresor Draco CAD | Lista y optimiza modelos 3D del bucket, vista previa 3D. |
| `alimentar_ia` | Alimentar IA | Explorador de Storage (cotizaciones, precios unitarios, modelos), sube archivos, crea subcarpetas. Vista previa 3D si el archivo es un modelo. |
| `arquitectura` | Arquitectura del Sistema | Mapa tipo red de los componentes reales, con nodos en rojo + insignia si hay un fallo reciente (polling cada 30s contra `sistema_errores`). Dos flujos numerados (generación / aprendizaje) que se filtran al tocar un nodo, mostrando solo los pasos donde ese nodo participa. |

---

## 5. Base de datos (Supabase)

### Tablas conocidas
| Tabla | Para qué |
|---|---|
| `disenos_racks` | Cada versión de cada diseño generado (JSON, tokens, historial de comentarios como lista acumulada). |
| `catalogo_piezas` | Piezas con modelo `.glb` real (Draco), usadas por el visor 3D. |
| `catalogo_pm` | Catálogo real con precios — fuente de verdad para cotización, fallback a JSON local. |
| `correcciones_armado` | Correcciones capturadas, con `veces_repetida` (alimenta Promotion Engine). |
| `reglas_armado` | Reglas técnicas activas — incluye las materializadas automáticamente por Promotion Engine. |
| `knowledge_chunks` / `knowledge_sources` | RAG — fragmentos vectorizados (pgvector) del catálogo y correcciones. |
| `knowledge_edges` | Knowledge Graph — relaciones `reemplaza_por`/`evitar_con`/`compatible_con` con contador de ocurrencias. |
| `knowledge_stats` | Contadores por SKU (usado/reemplazado/rechazado/recomendado). |
| `sistema_errores` | Fallos del backend (5xx/excepciones), consumido por el módulo Arquitectura. |
| `cotizaciones` | **Solo bitácora de archivos subidos para entrenamiento OCR** — no es la tabla de cotizaciones de clientes. |

### Storage (buckets)
`modelos` (piezas + `modelos 3d terminados` de ejemplo), `cotizaciones`, `precios unitarios` — estos dos últimos son **almacenamiento pasivo hoy**: nada los procesa automáticamente.

### Migraciones (`backend/db/migrations/`)
0001 (knowledge_stats) a 0007 (sistema_errores) — todas aplicadas en producción a esta fecha, excepto que conviene reconfirmar 0006/0007 tras esta sesión.

---

## 6. Qué funciona hoy de verdad (verificado en esta sesión)

- Flujo completo Telegram → Claude → Validator → Pipeline → entrega de archivos.
- Aprendizaje continuo real: corrección → grafo → umbral → regla permanente (confirmado con datos reales: correcciones con 3 y 7 repeticiones en producción).
- Tokens y costo reales en el dashboard (no simulados): 61 diseños, 790,903 tokens, ~$3.29 USD verificado.
- Cotización final usa precio real de `catalogo_pm`, no el que Claude recuerda.
- Visor 3D en vivo sin piezas hundidas en el piso (fix de pivote) y con cargadores generados con proporciones correctas (antes, ausentes por completo).

---

## 7. Qué falta / pendiente

**Crítico, sin resolver:**
- **Verificar políticas RLS en Supabase.** El link del visor 3D embebe la anon key en la URL. Si RLS no está bien acotado en `catalogo_piezas`/`disenos_racks`, cualquiera con ese link tiene acceso de lectura/escritura vía la API REST pública. No se ha podido confirmar (requiere el dashboard de Supabase).

**Backlog técnico:**
- Parser real de PDFs de listas de precios subidos a los buckets `cotizaciones`/`precios unitarios` — hoy son carpetas sin procesar. Pendiente hasta que existan muestras reales que definan el formato.
- Mejorar la calidad visual de los renders (`modelo_3d.py`) — hoy son cajas geométricas de colores fijos, sin materiales ni fotos reales. Deferido, requiere definir primero qué nivel de realismo se necesita.
- Limpiar los 4 prompts muertos (`supervisor.md`, `cotizador.md`, `renderizador.md`, `validador.md`) que nadie importa.
- `.dart_tool/` sigue trackeado en git en algunos commits históricos — es la mayor fuente de ruido del repo.
- Confirmar si el archivo `frontend/index.html` (visor GitHub Pages) y `frontend/rackbuilder_dashboard/lib/features/arquitectura/presentation/widgets/red_arquitectura_painter.dart` deben mantenerse sincronizados manualmente entre ramas (`main` vs `josue` tienen historiales de git no relacionados).
- Guía de pruebas end-to-end de aprendizaje continuo — documentada en conversación, no como archivo formal todavía.

**No implementado, a propósito (decisión documentada):**
- LangGraph / multi-agente — descartado explícitamente (Cap. 7.11 del manual), se reconsideraría solo si aparece un dominio con razonamiento verdaderamente independiente.
- Ventas / Cotizador IA — iniciativa separada acordada pero no iniciada (descuentos por volumen, propuesta comercial, historial de cliente tipo CRM).
- Managed Agents (Anthropic) — evaluado explícitamente para el flujo de diseño y descartado: la tarea es extracción estructurada de una sola pasada, no razonamiento abierto; adoptarlo aumentaría tokens y complejidad sin beneficio.
- Multiempresa, CI/CD formal, backups propios (fuera de los de Supabase), auditoría de cambios a reglas/catálogo.

---

## 8. Opciones de mejora (recomendaciones, no compromisos)

1. **Cerrar el hallazgo de RLS** — es lo único con riesgo de seguridad real conocido y sin resolver.
2. **Ingestión de precios reales**: si se consigue una muestra real de PDF de lista de precios, un solo llamado a Claude con visión (extracción estructurada) puede parsearlo y upsertear a `catalogo_pm` — no requiere un agente, es el mismo patrón de "una sola pasada" que ya usa el proyectista.
3. **Materiales/render más realistas**: si el negocio lo justifica, mejorar `modelo_3d.py` con shading por familia de pieza antes de invertir en fotos reales (más barato, buen salto de calidad percibida).
4. **Formalizar la guía de pruebas de aprendizaje continuo** como archivo versionado, no solo explicada en conversación.
5. **Auditoría de cambios a `reglas_armado`/`catalogo_pm`** — hoy cualquiera con acceso a Supabase puede editar precios/reglas sin dejar rastro de quién/cuándo/por qué.
6. **Revisar consistencia de umbrales de cargadores** entre `modelo_3d.py` (usaba 2700mm en una función) y la regla documentada/validada (2804mm) — ya corregido en `adaptador_visor.py` esta sesión, falta confirmar si `modelo_3d.py` tiene el mismo desfase.
