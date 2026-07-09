import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../../../../shared/widgets/model_3d_preview_dialog.dart";
import "../cubit/modelos_cubit.dart";
import "../cubit/modelos_state.dart";
import "../../domain/entities/storage_file_entity.dart";

class ModelosScreen extends StatelessWidget {
  const ModelosScreen({super.key});

  @override
  Widget build(BuildContext context) => BlocBuilder<ModelosCubit, ModelosState>(
    builder: (ctx, state) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      ResponsiveRow(children: [
        const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text("Compresor Draco CAD", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
          Text("Modelos 3D en el bucket de Supabase.", style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
        ]),
        Align(alignment: Alignment.centerRight, child: OutlinedButton.icon(
          onPressed: () => ctx.read<ModelosCubit>().loadModelos(),
          icon: const Icon(Icons.refresh, size: 16),
          label: const Text("Recargar"),
        )),
      ]),
      const SizedBox(height: 16),
      if (state is ModelosLoaded && state.message.isNotEmpty)
        Container(
          margin: const EdgeInsets.only(bottom: 12), padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: AppColors.indigoLight, borderRadius: BorderRadius.circular(10)),
          child: Text(state.message, style: const TextStyle(color: Color(0xFF1E3A8A), fontSize: 13)),
        ),
      if (state is ModelosLoading) const AppShimmer()
      else if (state is ModelosLoaded && state.modelos.isEmpty)
        const AppEmptyState(icon: Icons.description_outlined, message: "No hay modelos 3D disponibles.")
      else if (state is ModelosLoaded)
        ...state.modelos.map((m) => _ModelCard(
          model: m,
          isOptimizing: state.optimizingPath == m.path,
          anyOptimizing: state.optimizingPath != null,
          onOptimize: () => ctx.read<ModelosCubit>().optimizeModelo(m),
        ))
      else if (state is ModelosError)
        AppEmptyState(icon: Icons.error_outline, message: state.error)
      else
        const AppEmptyState(icon: Icons.compress, message: "Toca Recargar para ver los modelos."),
    ]),
  );
}

class _ModelCard extends StatelessWidget {
  final StorageFileEntity model;
  final bool isOptimizing;
  final bool anyOptimizing;
  final VoidCallback onOptimize;
  const _ModelCard({required this.model, required this.isOptimizing, required this.anyOptimizing, required this.onOptimize});

  @override
  Widget build(BuildContext context) {
    final mobile = Bp.isMobile(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: EdgeInsets.all(mobile ? 12 : 16),
      decoration: BoxDecoration(
        color: AppColors.surface, borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 12, offset: const Offset(0, 4))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: () => mostrarPreview3D(context, url: model.url, nombre: model.name),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(Icons.view_in_ar_outlined, size: mobile ? 18 : 20, color: AppColors.indigo),
            const SizedBox(width: 8),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(model.name, style: TextStyle(fontWeight: FontWeight.w700, fontSize: mobile ? 13 : 14, color: AppColors.textPrimary)),
              const SizedBox(height: 2),
              Text("${model.bucket} / ${model.folder.isEmpty ? "root" : model.folder}",
                  style: const TextStyle(fontSize: 11, color: AppColors.textSecond), overflow: TextOverflow.ellipsis),
            ])),
            const SizedBox(width: 8),
            model.isOptimized
                ? AppBadge(text: "${model.compressionRatio}% reducción", bg: AppColors.emeraldLight, fg: AppColors.emerald)
                : const AppBadge(text: "Sin comprimir", bg: AppColors.slateLight, fg: AppColors.textHint),
          ]),
        ),
        const SizedBox(height: 10),
        Wrap(spacing: 10, runSpacing: 4, children: [
          Text("Tipo: ${model.type}", style: const TextStyle(color: AppColors.textSecond, fontSize: 12)),
          Text("Peso: ${model.formattedSize}", style: const TextStyle(color: AppColors.textSecond, fontSize: 12)),
          if (model.isOptimized) Text("Comprimido: ${model.formattedCompressed}", style: const TextStyle(color: AppColors.textSecond, fontSize: 12)),
        ]),
        const SizedBox(height: 12),
        mobile
            ? SizedBox(width: double.infinity, child: ElevatedButton(
                onPressed: (isOptimizing || anyOptimizing) ? null : onOptimize,
                child: isOptimizing ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text("Optimizar con Draco"),
              ))
            : Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                ElevatedButton(
                  onPressed: (isOptimizing || anyOptimizing) ? null : onOptimize,
                  style: ElevatedButton.styleFrom(backgroundColor: AppColors.indigoLight, foregroundColor: AppColors.indigo, elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999))),
                  child: isOptimizing ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text("Optimizar automáticamente"),
                ),
              ]),
      ]),
    );
  }
}
