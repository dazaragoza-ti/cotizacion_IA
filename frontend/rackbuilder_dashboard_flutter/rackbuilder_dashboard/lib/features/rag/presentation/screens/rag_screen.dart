import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/rag_cubit.dart";
import "../cubit/rag_state.dart";

class RagScreen extends StatefulWidget {
  const RagScreen({super.key});
  @override State<RagScreen> createState() => _RagScreenState();
}

class _RagScreenState extends State<RagScreen> {
  final _queryCtrl = TextEditingController();
  String? _tipoFiltro;
  final _tipos = const ["catalogo", "correccion"];

  @override void dispose() { _queryCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => BlocBuilder<RagCubit, RagState>(
    builder: (ctx, state) => SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text("Base de Conocimiento (RAG)", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
      const SizedBox(height: 4),
      const Text("Reindexa catálogo + correcciones al vector store, y prueba búsquedas semánticas.", style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
      const SizedBox(height: 20),

      PanelCard(title: "Sincronización", subtitle: "POST /rag/sync", child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text("La indexación NO es automática: hay que sincronizar tras cambios de catálogo o correcciones nuevas.",
            style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
        const SizedBox(height: 12),
        if (state.syncMessage.isNotEmpty) Container(
          margin: const EdgeInsets.only(bottom: 12), padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: state.syncSuccess ? AppColors.emeraldLight : (state.syncing ? AppColors.bg : AppColors.redLight),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: state.syncSuccess ? AppColors.emerald : (state.syncing ? AppColors.border : AppColors.red)),
          ),
          child: Text(state.syncMessage, style: TextStyle(
              color: state.syncSuccess ? AppColors.emerald : (state.syncing ? AppColors.textSecond : AppColors.red),
              fontWeight: FontWeight.w600, fontSize: 13)),
        ),
        SizedBox(width: double.infinity, child: ElevatedButton.icon(
          onPressed: state.syncing ? null : () => ctx.read<RagCubit>().sincronizar(),
          icon: state.syncing ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.sync),
          label: Text(state.syncing ? "Sincronizando..." : "Sincronizar RAG"),
          style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14), textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
        )),
      ])),

      PanelCard(title: "Búsqueda semántica", subtitle: "GET /rag/search", child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: TextField(
            controller: _queryCtrl,
            style: const TextStyle(fontSize: 13),
            decoration: const InputDecoration(hintText: "Ej: viga ligera de 2.4m", hintStyle: TextStyle(color: AppColors.border, fontSize: 13)),
            onSubmitted: (q) => ctx.read<RagCubit>().buscar(q, tipo: _tipoFiltro),
          )),
          const SizedBox(width: 8),
          SizedBox(width: 130, child: DropdownButtonFormField<String?>(
            initialValue: _tipoFiltro,
            hint: const Text("Todos", style: TextStyle(fontSize: 12)),
            onChanged: (v) => setState(() => _tipoFiltro = v),
            items: [const DropdownMenuItem(value: null, child: Text("Todos", style: TextStyle(fontSize: 12))),
                ..._tipos.map((t) => DropdownMenuItem(value: t, child: Text(t, style: const TextStyle(fontSize: 12))))],
          )),
        ]),
        const SizedBox(height: 10),
        SizedBox(width: double.infinity, child: OutlinedButton.icon(
          onPressed: state.searching ? null : () => ctx.read<RagCubit>().buscar(_queryCtrl.text, tipo: _tipoFiltro),
          icon: state.searching ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.search, size: 18),
          label: Text(state.searching ? "Buscando..." : "Buscar"),
        )),
        if (state.searchError.isNotEmpty) ...[
          const SizedBox(height: 10),
          Text("Error: ${state.searchError}", style: const TextStyle(color: AppColors.red, fontSize: 12)),
        ],
        const SizedBox(height: 16),
        if (state.searching) const AppShimmer()
        else if (state.resultados.isEmpty)
          const AppEmptyState(icon: Icons.manage_search, message: "Sin resultados aún. Escribe una búsqueda arriba.")
        else Column(children: state.resultados.map((r) => Container(
            margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                AppBadge(text: r.tipo, bg: AppColors.indigoLight, fg: AppColors.indigo),
                const SizedBox(width: 6),
                AppBadge(text: r.fuente, bg: AppColors.bg, fg: AppColors.textSecond),
                const Spacer(),
                Text("${(r.similarity * 100).toStringAsFixed(1)}% similar", style: const TextStyle(fontSize: 10, color: AppColors.textHint, fontWeight: FontWeight.w600)),
              ]),
              const SizedBox(height: 8),
              Text(r.contenido, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary), maxLines: 4, overflow: TextOverflow.ellipsis),
            ]),
        )).toList()),
      ])),
    ])),
  );
}
