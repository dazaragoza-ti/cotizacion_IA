# RackBuilder Dashboard — Flutter

Dashboard de control para RackBuilder 3D: métricas, catálogo, historial, Draco,
aprendizaje continuo, RAG y mapa de arquitectura. Habla con **FastAPI** (Dio) y
**Supabase** (cliente directo + Realtime).

## Setup

```bash
# 1. Dependencias
flutter pub get

# 2. Variables de entorno (copiar y ajustar)
cp .env.example .env
# BACKEND_URL=http://localhost:8000
# VISOR_3D_URL=https://dazaragoza-ti.github.io/cotizacion_IA/index.html

# 3. Correr
flutter run -d chrome        # web
flutter run -d windows       # desktop Windows
flutter run                  # dispositivo conectado
```

Requisitos: backend FastAPI en marcha (`GET /` debe responder `healthy`).

## Arquitectura

Clean Architecture por **feature** + **Cubit** (flutter_bloc) + **GetIt** + **Dio**.

```
lib/
├── main.dart
├── core/
│   ├── constants/          # AppConstants, ApiEndpoints
│   ├── di/service_locator.dart
│   ├── network/api_client.dart   # Dio + retry + errores
│   ├── theme/
│   └── utils/
├── shared/widgets/         # ConnectionBadge, KPIs, visor_3d_dialog, …
└── features/               # 8 módulos
    ├── dashboard/          # shell, topbar, métricas, health dual
    ├── alimentar_ia/       # explorador Storage
    ├── modelos_3d/         # Draco CAD
    ├── catalogo/           # piezas + upload GLB
    ├── historial/          # diseños / versiones + visor 3D
    ├── estadisticas/       # aprendizaje continuo
    ├── rag/                # búsqueda semántica + sync
    └── arquitectura/       # mapa en vivo + Realtime
```

Cada feature tipicamente: `data/` (datasource Dio + models) → `domain/` (entities, usecases, repos) → `presentation/` (cubit + screens).

## Los 8 módulos

| Módulo | Qué hace | Backend |
|--------|----------|---------|
| Métricas | Tokens, costo, proyectos | Supabase `disenos_racks` |
| Alimentar IA | Carpetas/archivos Storage | `GET/POST /storage/...` |
| Optimizar Draco | Listar/comprimir GLB | `/storage/files`, `/optimize` |
| Catálogo | CRUD piezas + modelo | `/catalogo/...` |
| Historial | Sesiones y versiones | `/disenos/...` + visor iframe |
| Estadísticas | Ranking SKU + correcciones | `/stats/...`, `/correcciones` |
| RAG | Search + sync embeddings | `/rag/...` |
| Arquitectura | Mapa + errores en vivo | `/sistema/...` + Realtime |

## Conexión dual (topbar)

Al arrancar el dashboard:

1. **FastAPI** — `GET /` vía `ApiClient.checkHealth()` → badge `FastAPI OK` / `Off`
2. **Supabase** — credenciales de `GET /config/supabase` (o cache en `SharedPreferences`) → badge `Supabase OK` / `Off`

Los módulos Dio pueden operar si FastAPI está OK aunque Supabase falle (y viceversa para métricas).

## Visor 3D

`mostrarVisor3D` abre un iframe a `VISOR_3D_URL` con **solo** `?session_id=...`.
Las credenciales Supabase viven como defaults en `frontend/index.html` (alineado con el bot / `URL_FRONTEND` del backend). Ya no se pasan `sb_url` / `sb_key` en la URL.

## Errores visibles

Los datasources/cubits principales **no** tragan excepciones con `return []` o `catch` vacío: fallos de red/API llegan a `*Error` state, `AppEmptyState` o SnackBar (`showAppError` / `showAppWarning`).

## Notas

- Credenciales Supabase: backend `GET /config/supabase` → cache local
- HTTP: paquete **Dio** (no `http` crudo), interceptores de retry y detalle de error
- `.env` está en `pubspec.yaml` → `assets` (obligatorio para web/desktop)
