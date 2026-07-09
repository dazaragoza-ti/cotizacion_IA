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
import "../widgets/topbar_widget.dart";
import "../widgets/sidebar_widget.dart";
import "../widgets/analiticas_module.dart";
import "../../../modelos_3d/presentation/screens/modelos_screen.dart";
import "../../../catalogo/presentation/screens/catalogo_screen.dart";
import "../../../historial/presentation/screens/historial_screen.dart";
import "../../../alimentar_ia/presentation/screens/alimentar_ia_screen.dart";

enum DashModule { analiticas, alimentar, draco, catalogo, historial }

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
      default:
        break;
    }
  }

  void _switch(BuildContext ctx, DashModule m) {
    setState(() => _module = m);
    // Solo carga si ya hay conexión activa
    if (ctx.read<DashboardCubit>().state is DashboardConnected) {
      switch (m) {
        case DashModule.alimentar:
          ctx.read<AlimentarIaCubit>().abrirExplorador();
        case DashModule.draco:
          ctx.read<ModelosCubit>().loadModelos();
        case DashModule.catalogo:
          ctx.read<CatalogoCubit>().loadCatalogo();
        case DashModule.historial:
          ctx.read<HistorialCubit>().loadHistorial();
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
      ],
      child: BlocConsumer<DashboardCubit, DashboardState>(
        // Escuchar cuando la conexión se establece y disparar carga del módulo activo
        listener: (ctx, state) {
          if (state is DashboardConnected && !state.loadingMetrics) {
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
      },
    )),
  );
}

// ── Bottom Nav (móvil) ────────────────────────────────────────────────────────
class _BottomNav extends StatelessWidget {
  final DashModule module;
  final void Function(DashModule) onTap;
  const _BottomNav({required this.module, required this.onTap});

  @override
  Widget build(BuildContext context) {
    const items = [
      (DashModule.analiticas, Icons.bar_chart,    "Métricas"),
      (DashModule.draco,      Icons.compress,     "Draco"),
      (DashModule.catalogo,   Icons.cloud_upload, "Catálogo"),
      (DashModule.historial,  Icons.history,      "Historial"),
    ];
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: Row(children: items.map((item) {
        final (mod, icon, label) = item;
        final active = module == mod;
        return Expanded(child: GestureDetector(
          onTap: () => onTap(mod),
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
        ));
      }).toList()),
    );
  }
}

// ── Tablet Rail ───────────────────────────────────────────────────────────────
class _TabletRail extends StatelessWidget {
  final DashModule module;
  final void Function(DashModule) onSwitch;
  const _TabletRail({required this.module, required this.onSwitch});

  @override
  Widget build(BuildContext context) {
    const items = [
      (DashModule.analiticas, Icons.bar_chart,    "Métricas"),
      (DashModule.alimentar,  Icons.psychology,   "IA"),
      (DashModule.draco,      Icons.compress,     "Draco"),
      (DashModule.catalogo,   Icons.cloud_upload, "Catálogo"),
      (DashModule.historial,  Icons.history,      "Historial"),
    ];
    return Container(
      width: 70,
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(right: BorderSide(color: AppColors.border)),
      ),
      child: Column(children: [
        const SizedBox(height: 8),
        ...items.map((item) {
          final (mod, icon, label) = item;
          final active = module == mod;
          return GestureDetector(
            onTap: () => onSwitch(mod),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: active ? AppColors.indigoLight : Colors.transparent,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(icon, size: 20, color: active ? AppColors.indigo : AppColors.textHint),
                const SizedBox(height: 4),
                Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600,
                    color: active ? AppColors.indigo : AppColors.textHint)),
              ]),
            ),
          );
        }),
      ]),
    );
  }
}
