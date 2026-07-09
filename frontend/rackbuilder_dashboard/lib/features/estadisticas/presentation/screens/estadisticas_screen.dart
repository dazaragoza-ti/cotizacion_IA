import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../../data/datasources/estadisticas_remote_datasource.dart" show camposEstadisticas;
import "../cubit/estadisticas_cubit.dart";
import "../cubit/estadisticas_state.dart";

const Map<String, String> _etiquetasCampo = {
  "veces_usado": "Más usados",
  "veces_reemplazado": "Más reemplazados",
  "veces_rechazado": "Más rechazados",
  "veces_recomendado": "Más recomendados",
};

class EstadisticasScreen extends StatefulWidget {
  const EstadisticasScreen({super.key});
  @override State<EstadisticasScreen> createState() => _EstadisticasScreenState();
}

class _EstadisticasScreenState extends State<EstadisticasScreen> {
  final _buscarCtrl = TextEditingController();

  @override void dispose() {
    _buscarCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BlocBuilder<EstadisticasCubit, EstadisticasState>(
    builder: (ctx, state) {
      final campo = state is EstadisticasLoaded ? state.campo : camposEstadisticas.first;
      final top = state is EstadisticasLoaded ? state.top : const [];
      final busqueda = state is EstadisticasLoaded ? state.busqueda : null;
      final mensajeBusqueda = state is EstadisticasLoaded ? state.mensajeBusqueda : null;

      return SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text("Aprendizaje continuo — Estadísticas por SKU",
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
        const SizedBox(height: 4),
        const Text("Qué pieza falla, recomiendan o reemplazan más — knowledge_stats (Sprint 2).",
            style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
        const SizedBox(height: 20),

        PanelCard(title: "Buscar un SKU", subtitle: "GET /stats/sku/{sku}", child: Column(children: [
          Row(children: [
            Expanded(child: TextField(
              controller: _buscarCtrl,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(hintText: "Ej. LRS7355", isDense: true),
              onSubmitted: (v) => ctx.read<EstadisticasCubit>().buscarSku(v),
            )),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: () => ctx.read<EstadisticasCubit>().buscarSku(_buscarCtrl.text),
              child: const Text("Buscar"),
            ),
          ]),
          if (mensajeBusqueda != null) Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text(mensajeBusqueda, style: const TextStyle(color: AppColors.textSecond, fontSize: 12)),
          ),
          if (busqueda != null) Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppColors.border)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(busqueda.sku, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: AppColors.indigo)),
                const SizedBox(height: 8),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  TokenChip(label: "usado", value: busqueda.vecesUsado, color: AppColors.indigo),
                  TokenChip(label: "reemplazado", value: busqueda.vecesReemplazado, color: AppColors.emerald),
                  TokenChip(label: "rechazado", value: busqueda.vecesRechazado, color: AppColors.red),
                  TokenChip(label: "recomendado", value: busqueda.vecesRecomendado, color: AppColors.amber),
                ]),
              ]),
            ),
          ),
        ])),

        PanelCard(
          title: "Ranking", subtitle: "GET /stats/top",
          trailing: DropdownButton<String>(
            value: campo,
            underline: const SizedBox.shrink(),
            items: camposEstadisticas.map((c) => DropdownMenuItem(
              value: c, child: Text(_etiquetasCampo[c] ?? c, style: const TextStyle(fontSize: 13)),
            )).toList(),
            onChanged: (v) { if (v != null) ctx.read<EstadisticasCubit>().loadTop(campo: v); },
          ),
          child: state is EstadisticasLoading ? const AppShimmer()
              : state is EstadisticasError ? Text("Error: ${state.error}", style: const TextStyle(color: AppColors.red))
              : top.isEmpty ? const AppEmptyState(icon: Icons.query_stats, message:
                  "Sin datos todavía — se llena conforme el bot procesa correcciones y proyectos.\n(¿Se aplicó la migración 0001_knowledge_stats.sql en Supabase?)")
              : Column(children: top.asMap().entries.map((entry) {
                  final i = entry.key;
                  final e = entry.value;
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
                    child: Row(children: [
                      Container(
                        width: 26, height: 26, alignment: Alignment.center,
                        decoration: BoxDecoration(color: AppColors.indigoLight, borderRadius: BorderRadius.circular(8)),
                        child: Text("${i + 1}", style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12, color: AppColors.indigo)),
                      ),
                      const SizedBox(width: 10),
                      Expanded(child: Text(e.sku, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: AppColors.textPrimary))),
                      AppBadge(text: "${e.total()} eventos", bg: AppColors.indigoLight, fg: AppColors.indigo),
                    ]),
                  );
                }).toList()),
        ),
      ]));
    },
  );
}
