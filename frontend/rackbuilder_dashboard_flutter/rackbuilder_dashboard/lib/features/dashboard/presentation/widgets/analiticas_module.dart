import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../core/utils/formatters.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/dashboard_cubit.dart";
import "../cubit/dashboard_state.dart";
import "../../domain/entities/metrics_entity.dart";

class AnaliticasModule extends StatelessWidget {
  const AnaliticasModule({super.key});

  @override
  Widget build(BuildContext context) => BlocBuilder<DashboardCubit, DashboardState>(
    builder: (ctx, state) {
      final metrics = state is DashboardConnected ? state.metrics : MetricsEntity.empty();
      final loading = state is DashboardConnected && state.loadingMetrics;
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        ResponsiveRow(children: [
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text("Métricas Globales", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
            const Text("Monitoreo en tiempo real de diseños y costo de APIs.", style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
          ]),
          Align(alignment: Alignment.centerRight, child: ElevatedButton.icon(
            onPressed: () => ctx.read<DashboardCubit>().refreshMetrics(),
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text("Actualizar"),
          )),
        ]),
        const SizedBox(height: 16),
        loading ? const AppShimmer() : _KpiGrid(metrics: metrics),
        const SizedBox(height: 14),
        ResponsiveRow(breakpoint: 700, children: [
          Padding(padding: const EdgeInsets.only(bottom: 0), child: PanelCard(
            title: "Uso de tokens", subtitle: "Resumen del flujo actual",
            child: Column(children: [
              TokenBar(label: "Input tokens",
                  valueLabel: "${Formatters.thousands(metrics.inputTokens)} tokens",
                  percent: metrics.totalTokens > 0 ? metrics.inputTokens / metrics.totalTokens * 100 : 0,
                  color: AppColors.cyan),
              const SizedBox(height: 12),
              TokenBar(label: "Output tokens",
                  valueLabel: "${Formatters.thousands(metrics.outputTokens)} tokens",
                  percent: metrics.totalTokens > 0 ? metrics.outputTokens / metrics.totalTokens * 100 : 0,
                  color: AppColors.purple),
              const SizedBox(height: 14),
              Wrap(spacing: 10, runSpacing: 10, children: [
                SummaryItem(label: "Tokens totales",     value: Formatters.thousands(metrics.totalTokens)),
                SummaryItem(label: "Prom. por proyecto", value: Formatters.thousands(metrics.avgTokensPerProject.round())),
                SummaryItem(label: "Costo estimado",     value: Formatters.currency(metrics.estimatedCost)),
              ]),
            ]),
          )),
          PanelCard(
            title: "Actividad reciente", subtitle: "Desde Supabase",
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: metrics.proyectos == 0
                ? [const Text("Conectando a Supabase...", style: TextStyle(color: AppColors.textSecond, fontSize: 13))]
                : [
                    Text("${metrics.proyectos} proyectos cargados", style: const TextStyle(fontSize: 13, color: AppColors.textSecond)),
                    const SizedBox(height: 6),
                    Text("Total: ${Formatters.thousands(metrics.totalTokens)} tokens", style: const TextStyle(fontSize: 13, color: AppColors.textSecond)),
                    const SizedBox(height: 6),
                    Text("Prom: ${Formatters.thousands(metrics.avgTokensPerProject.round())} tokens/diseño", style: const TextStyle(fontSize: 13, color: AppColors.textSecond)),
                  ]),
          ),
        ]),
      ]);
    },
  );
}

class _KpiGrid extends StatelessWidget {
  final MetricsEntity metrics;
  const _KpiGrid({required this.metrics});
  @override
  Widget build(BuildContext context) => ResponsiveRow(breakpoint: 500, children: [
    KpiCard(label: "Proyectos", value: metrics.proyectos.toString(), hint: "Registros en disenos_racks",
        iconBg: AppColors.indigoLight, iconFg: AppColors.indigoDark, icon: Icons.folder_open),
    KpiCard(label: "Tokens", value: Formatters.thousands(metrics.totalTokens), hint: "Entrada + salida",
        iconBg: AppColors.amberLight, iconFg: AppColors.amber, icon: Icons.bar_chart),
    KpiCard(label: "Costo estimado", value: Formatters.currency(metrics.estimatedCost), hint: "Sonnet 4.6 real",
        iconBg: AppColors.emeraldLight, iconFg: AppColors.emerald, icon: Icons.attach_money),
  ]);
}
