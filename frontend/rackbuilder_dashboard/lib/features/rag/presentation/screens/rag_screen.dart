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
  String? _tipo;
  final _tipos = const ["correccion", "catalogo"];

  @override void dispose() {
    _queryCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BlocBuilder<RagCubit, RagState>(
    builder: (ctx, state) {
      final resultados = state is RagResultados ? state.resultados : const [];
      final sincronizando = state is RagResultados && state.sincronizando;
      final mensaje = state is RagResultados ? state.mensaje : null;

      return SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text("Búsqueda RAG", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
        const SizedBox(height: 4),
        const Text("Busca por similitud semántica en knowledge_chunks (catálogo + correcciones aprendidas).",
            style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
        const SizedBox(height: 20),

        PanelCard(
          title: "Sincronización", subtitle: "POST /rag/sync",
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text("Reindexa catálogo y correcciones al vector store. No es automático en tiempo real.",
                style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
            const SizedBox(height: 10),
            SizedBox(width: double.infinity, child: OutlinedButton.icon(
              onPressed: sincronizando ? null : () => ctx.read<RagCubit>().sincronizar(),
              icon: sincronizando
                  ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.sync, size: 16),
              label: Text(sincronizando ? "Sincronizando..." : "Sincronizar ahora"),
            )),
            if (sincronizando) ...[
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: const LinearProgressIndicator(minHeight: 6, backgroundColor: AppColors.slateLight),
              ),
              const SizedBox(height: 6),
              const Text("Puede tardar uno o dos minutos — corre en segundo plano, no hace falta quedarse en esta pantalla.",
                  style: TextStyle(fontSize: 11, color: AppColors.textHint)),
            ],
            if (mensaje != null) Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(mensaje, style: const TextStyle(fontSize: 12, color: AppColors.textSecond)),
            ),
          ]),
        ),

        PanelCard(title: "Buscar", subtitle: "GET /rag/search", child: Column(children: [
          Row(children: [
            Expanded(child: TextField(
              controller: _queryCtrl,
              decoration: const InputDecoration(hintText: "Ej. rack selectivo carga pesada con pasillo de montacargas", isDense: true),
              onSubmitted: (v) => ctx.read<RagCubit>().buscar(v, tipo: _tipo),
            )),
            const SizedBox(width: 8),
            DropdownButton<String?>(
              value: _tipo,
              hint: const Text("Todos", style: TextStyle(fontSize: 13)),
              underline: const SizedBox.shrink(),
              items: [
                const DropdownMenuItem(value: null, child: Text("Todos", style: TextStyle(fontSize: 13))),
                ..._tipos.map((t) => DropdownMenuItem(value: t, child: Text(t, style: const TextStyle(fontSize: 13)))),
              ],
              onChanged: (v) => setState(() => _tipo = v),
            ),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: () => ctx.read<RagCubit>().buscar(_queryCtrl.text, tipo: _tipo),
              child: const Text("Buscar"),
            ),
          ]),
        ])),

        if (state is RagBuscando) const AppShimmer()
        else if (state is RagError) Text("Error: ${state.error}", style: const TextStyle(color: AppColors.red))
        else if (state is RagResultados && resultados.isEmpty && state.query.isNotEmpty)
          const AppEmptyState(icon: Icons.search_off, message: "Sin resultados para esa búsqueda.")
        else if (resultados.isNotEmpty)
          PanelCard(
            title: "Resultados", subtitle: "${resultados.length} chunk(s)",
            child: Column(children: resultados.map((r) => Container(
              margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  AppBadge(text: r.tipo, bg: AppColors.indigoLight, fg: AppColors.indigo),
                  const SizedBox(width: 6),
                  Text(r.fuente, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
                  const Spacer(),
                  AppBadge(text: "sim ${r.similarity.toStringAsFixed(2)}", bg: AppColors.emeraldLight, fg: AppColors.emerald),
                ]),
                const SizedBox(height: 8),
                Text(r.contenido, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary), maxLines: 6, overflow: TextOverflow.ellipsis),
              ]),
            )).toList()),
          ),
      ]));
    },
  );
}
