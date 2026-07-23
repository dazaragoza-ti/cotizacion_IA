import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/dashboard_cubit.dart";
import "../cubit/dashboard_state.dart";
import "../screens/dashboard_screen.dart";

class SidebarWidget extends StatelessWidget {
  final DashModule module;
  final DashboardState state;
  final void Function(DashModule) onSwitch;
  const SidebarWidget({super.key, required this.module, required this.state, required this.onSwitch});

  @override
  Widget build(BuildContext context) {
    final connected = state is DashboardConnected;
    return Container(
      width: 260,
      margin: const EdgeInsets.fromLTRB(12, 12, 0, 12),
      child: Column(children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppColors.surface, borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text("HERRAMIENTAS", style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.textHint, letterSpacing: 1.5)),
            const SizedBox(height: 10),
            ...kDashModules.map((item) => NavButton(
              icon: item.icon, label: item.longLabel,
              active: module == item.module,
              onTap: () => onSwitch(item.module),
            )),
          ]),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: AppColors.border)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text("ESTADO", style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.textHint, letterSpacing: 1.5)),
            const SizedBox(height: 10),
            Row(children: [
              PulseDot(color: connected ? AppColors.emerald : AppColors.red),
              const SizedBox(width: 8),
              Text(connected ? "Conexión Activa" : "Desconectado",
                  style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.slate)),
            ]),
            if (!connected) ...[
              const SizedBox(height: 8),
              SizedBox(width: double.infinity, child: OutlinedButton.icon(
                onPressed: () => context.read<DashboardCubit>().autoConnect(),
                icon: const Icon(Icons.refresh, size: 14),
                label: const Text("Reconectar", style: TextStyle(fontSize: 12)),
              )),
            ],
          ]),
        ),
      ]),
    );
  }
}
