import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../core/di/service_locator.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/dashboard_cubit.dart";
import "../cubit/dashboard_state.dart";
import "../../../modelos_3d/presentation/cubit/modelos_cubit.dart";
import "../../../catalogo/presentation/cubit/catalogo_cubit.dart";
import "../../../historial/presentation/cubit/historial_cubit.dart";
import "../../../alimentar_ia/presentation/cubit/alimentar_ia_cubit.dart";
import "../../../estadisticas/presentation/cubit/estadisticas_cubit.dart";
import "../../../rag/presentation/cubit/rag_cubit.dart";
import "../../../arquitectura/presentation/cubit/arquitectura_cubit.dart";
import "../widgets/topbar_widget.dart";
import "../widgets/sidebar_widget.dart";
import "../widgets/analiticas_module.dart";
import "../../../modelos_3d/presentation/screens/modelos_screen.dart";
import "../../../catalogo/presentation/screens/catalogo_screen.dart";
import "../../../historial/presentation/screens/historial_screen.dart";
import "../../../alimentar_ia/presentation/screens/alimentar_ia_screen.dart";
import "../../../estadisticas/presentation/screens/estadisticas_screen.dart";
import "../../../rag/presentation/screens/rag_screen.dart";
import "../../../arquitectura/presentation/screens/arquitectura_screen.dart";

enum DashModule { analiticas, alimentar, draco, catalogo, historial, estadisticas, rag, arquitectura }

/// Fuente única de verdad de icono/etiqueta por módulo — la usan sidebar,
/// tablet rail y bottom nav para que ningún módulo quede fuera por listas
/// mantenidas a mano por separado (pasaba antes: mobile/tablet ocultaban
/// RAG, Arquitectura y Alimentar IA por completo).
typedef DashModuleInfo = ({DashModule module, IconData icon, String shortLabel, String longLabel});

const List<DashModuleInfo> kDashModules = [
  (module: DashModule.analiticas,   icon: Icons.bar_chart,     shortLabel: "Métricas",     longLabel: "Métricas y Tokens"),
  (module: DashModule.alimentar,    icon: Icons.psychology,    shortLabel: "IA",           longLabel: "Alimentar IA"),
  (module: DashModule.draco,        icon: Icons.compress,      shortLabel: "Draco",        longLabel: "Optimizar Draco CAD"),
  (module: DashModule.catalogo,     icon: Icons.cloud_upload,  shortLabel: "Catálogo",     longLabel: "Subir al Catálogo"),
  (module: DashModule.historial,    icon: Icons.history,       shortLabel: "Historial",    longLabel: "Historial de Diseños"),
  (module: DashModule.estadisticas, icon: Icons.insights,      shortLabel: "Stats",        longLabel: "Aprendizaje (Estadísticas)"),
  (module: DashModule.rag,          icon: Icons.manage_search, shortLabel: "RAG",          longLabel: "Búsqueda RAG"),
  (module: DashModule.arquitectura, icon: Icons.hub,           shortLabel: "Arquitectura", longLabel: "Arquitectura del Sistema"),
];

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  DashModule _module = DashModule.analiticas;

  /// Dispara la carga del módulo activo cuando la conexión ya está lista.
  void _loadActiveModule(BuildContext ctx) {
    switch (_module) {
      case DashModule.alimentar:
        ctx.read<AlimentarIaCubit>().abrirExplorador();
      case DashModule.draco:
        ctx.read<ModelosCubit>().loadModelos();
      case DashModule.catalogo:
        ctx.read<CatalogoCubit>().loadCatalogo();
      case DashModule.historial:
        ctx.read<HistorialCubit>().loadHistorial();
      case DashModule.estadisticas:
        ctx.read<EstadisticasCubit>().cargarTodo();
      case DashModule.rag:
        break; // el buscador RAG espera a que el usuario escriba una consulta
      default:
        break;
    }
  }

  void _switch(BuildContext ctx, DashModule m) {
    setState(() => _module = m);
    // Carga si FastAPI o Supabase ya respondieron (módulos usan uno u otro)
    if (ctx.read<DashboardCubit>().state.backendOk ||
        ctx.read<DashboardCubit>().state.supabaseOk) {
      switch (m) {
        case DashModule.alimentar:
          ctx.read<AlimentarIaCubit>().abrirExplorador();
        case DashModule.draco:
          ctx.read<ModelosCubit>().loadModelos();
        case DashModule.catalogo:
          ctx.read<CatalogoCubit>().loadCatalogo();
        case DashModule.historial:
          ctx.read<HistorialCubit>().loadHistorial();
        case DashModule.estadisticas:
          ctx.read<EstadisticasCubit>().cargarTodo();
        case DashModule.rag:
          break;
        default:
          break;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isMobile  = Bp.isMobile(context);
    final isDesktop = Bp.isDesktop(context);

    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => sl<DashboardCubit>()..autoConnect()),
        BlocProvider(create: (_) => sl<ModelosCubit>()),
        BlocProvider(create: (_) => sl<CatalogoCubit>()),
        BlocProvider(create: (_) => sl<HistorialCubit>()),
        BlocProvider(create: (_) => sl<AlimentarIaCubit>()),
        BlocProvider(create: (_) => sl<EstadisticasCubit>()),
        BlocProvider(create: (_) => sl<RagCubit>()),
        BlocProvider(create: (_) => sl<ArquitecturaCubit>()),
      ],
      child: BlocConsumer<DashboardCubit, DashboardState>(
        listenWhen: (prev, next) {
          final statusChanged = prev.backendOk != next.backendOk ||
              prev.supabaseOk != next.supabaseOk ||
              (prev is DashboardConnecting) != (next is DashboardConnecting);
          final errorChanged = next is DashboardDisconnected &&
              (prev is! DashboardDisconnected ||
                  prev.message != next.message);
          final warningChanged = next is DashboardConnected &&
              next.warning != null &&
              next.warning !=
                  (prev is DashboardConnected ? prev.warning : null);
          return statusChanged || errorChanged || warningChanged;
        },
        listener: (ctx, state) {
          if (state is DashboardDisconnected) {
            showAppError(ctx, state.message);
          } else if (state is DashboardConnected && state.warning != null) {
            showAppWarning(ctx, state.warning!);
          }
          if ((state.backendOk || state.supabaseOk) &&
              state is! DashboardConnecting) {
            _loadActiveModule(ctx);
          }
        },
        builder: (ctx, state) => Scaffold(
          backgroundColor: AppColors.bg,
          bottomNavigationBar: isMobile
              ? _BottomNav(module: _module, onTap: (m) => _switch(ctx, m))
              : null,
          body: SafeArea(child: Column(children: [
            TopbarWidget(state: state),
            Expanded(child: isDesktop
                ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    SidebarWidget(module: _module, state: state, onSwitch: (m) => _switch(ctx, m)),
                    Expanded(child: _content(ctx)),
                  ])
                : Bp.isTablet(context)
                    ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        _TabletRail(module: _module, onSwitch: (m) => _switch(ctx, m)),
                        Expanded(child: _content(ctx)),
                      ])
                    : _content(ctx)),
          ])),
        ),
      ),
    );
  }

  Widget _content(BuildContext ctx) => Container(
    margin: const EdgeInsets.all(12),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: AppColors.surface, borderRadius: BorderRadius.circular(18),
      border: Border.all(color: AppColors.border),
      boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 18)],
    ),
    child: SingleChildScrollView(child: AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: switch (_module) {
        DashModule.analiticas => const AnaliticasModule(key: ValueKey("analiticas")),
        DashModule.alimentar  => const AlimentarIaScreen(key: ValueKey("alimentar")),
        DashModule.draco      => const ModelosScreen(key: ValueKey("draco")),
        DashModule.catalogo   => const CatalogoScreen(key: ValueKey("catalogo")),
        DashModule.historial  => const HistorialScreen(key: ValueKey("historial")),
        DashModule.estadisticas => const EstadisticasScreen(key: ValueKey("estadisticas")),
        DashModule.rag => const RagScreen(key: ValueKey("rag")),
        DashModule.arquitectura => const ArquitecturaScreen(key: ValueKey("arquitectura")),
      },
    )),
  );
}

// ── Bottom Nav (móvil) ────────────────────────────────────────────────────────
// Solo 3 accesos directos (los de uso más frecuente) + "Más" para el resto,
// así cada botón tiene espacio suficiente para tocarse cómodo en pantallas
// angostas. Antes se mostraban 5 módulos fijos y los otros 3 (Alimentar IA,
// RAG, Arquitectura) eran directamente inalcanzables en móvil.
const List<DashModule> _kBottomNavPrimarios = [
  DashModule.analiticas, DashModule.catalogo, DashModule.historial,
];

class _BottomNav extends StatelessWidget {
  final DashModule module;
  final void Function(DashModule) onTap;
  const _BottomNav({required this.module, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final primarios = kDashModules.where((m) => _kBottomNavPrimarios.contains(m.module)).toList();
    final enMas = !_kBottomNavPrimarios.contains(module);

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: Row(children: [
        ...primarios.map((item) => Expanded(child: _BottomNavItem(
          icon: item.icon, label: item.shortLabel,
          active: module == item.module,
          onTap: () => onTap(item.module),
        ))),
        Expanded(child: _BottomNavItem(
          icon: Icons.more_horiz, label: "Más",
          active: enMas,
          onTap: () => _abrirMas(context),
        )),
      ]),
    );
  }

  void _abrirMas(BuildContext context) {
    final resto = kDashModules.where((m) => !_kBottomNavPrimarios.contains(m.module)).toList();
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (sheetCtx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: resto.map((item) {
          final active = module == item.module;
          return ListTile(
            leading: Icon(item.icon, color: active ? AppColors.indigo : AppColors.slate),
            title: Text(item.longLabel, style: TextStyle(
              fontWeight: FontWeight.w600,
              color: active ? AppColors.indigo : AppColors.slate,
            )),
            onTap: () { Navigator.pop(sheetCtx); onTap(item.module); },
          );
        }).toList()),
      ),
    );
  }
}

class _BottomNavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;
  const _BottomNavItem({required this.icon, required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 10),
      color: Colors.transparent,
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 22, color: active ? AppColors.indigo : AppColors.textHint),
        const SizedBox(height: 3),
        Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600,
            color: active ? AppColors.indigo : AppColors.textHint)),
      ]),
    ),
  );
}

// ── Tablet Rail ───────────────────────────────────────────────────────────────
class _TabletRail extends StatelessWidget {
  final DashModule module;
  final void Function(DashModule) onSwitch;
  const _TabletRail({required this.module, required this.onSwitch});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 70,
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(right: BorderSide(color: AppColors.border)),
      ),
      // Scroll en vez de altura fija: con los 8 módulos ya no garantizamos
      // que quepan sin cortarse en tablets bajas (landscape chico).
      child: SingleChildScrollView(
        child: Column(children: [
          const SizedBox(height: 8),
          ...kDashModules.map((item) {
            final active = module == item.module;
            return GestureDetector(
              onTap: () => onSwitch(item.module),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: active ? AppColors.indigoLight : Colors.transparent,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Icon(item.icon, size: 20, color: active ? AppColors.indigo : AppColors.textHint),
                  const SizedBox(height: 4),
                  Text(item.shortLabel, textAlign: TextAlign.center, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600,
                      color: active ? AppColors.indigo : AppColors.textHint)),
                ]),
              ),
            );
          }),
        ]),
      ),
    );
  }
}
