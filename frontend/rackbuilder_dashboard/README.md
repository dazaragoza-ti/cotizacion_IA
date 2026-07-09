# RackBuilder Dashboard — Flutter

Migración del dashboard Angular a Flutter. Funcionalidad idéntica:
- Métricas globales de proyectos (tokens, costo, proyectos)
- Alimentar IA (documentos de Supabase Storage)
- Compresor Draco CAD (modelos 3D, optimización automática)
- Auto-conexión a Supabase desde el backend (.env del servidor)

## Setup

```bash
# 1. Instalar dependencias
flutter pub get

# 2. Configurar backend URL en .env
echo "BACKEND_URL=http://localhost:8000" > .env

# 3. Correr la app
flutter run -d chrome        # web
flutter run -d windows       # desktop Windows
flutter run                  # dispositivo conectado
```

## Estructura

```
lib/
├── main.dart                   # Punto de entrada
├── models/models.dart          # DashboardMetrics, StorageFileItem
├── services/dashboard_service.dart  # Equivalente a dashboard.service.ts
├── widgets/widgets.dart        # KpiCard, TokenBar, ModelFileCard, etc.
└── screens/dashboard_screen.dart    # Pantalla principal (dashboard-shell)
```

## Equivalencias Angular → Flutter

| Angular | Flutter |
|---------|---------|
| `DashboardShellComponent` | `DashboardScreen` |
| `DashboardService` | `DashboardService` (singleton) |
| `MetricCardsComponent` | `KpiCard` widget |
| `ActivityPanelComponent` | Lista en `_buildAnaliticas()` |
| `ngFor` | `List.map()` + `Column` |
| `[class.active]` | `AnimatedContainer` condicional |
| `localStorage` | `SharedPreferences` |
| `fetch()` | `http` package |

## Notas

- Las credenciales de Supabase se obtienen automáticamente del backend (`GET /config/supabase`)
- Si el backend no responde, se usan las guardadas en `SharedPreferences`
- El backend URL se configura en el archivo `.env`
