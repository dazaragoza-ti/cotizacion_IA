import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../core/utils/formatters.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/correcciones_cubit.dart";
import "../cubit/correcciones_state.dart";
import "../../domain/entities/correccion_entity.dart";

class CorreccionesScreen extends StatelessWidget {
  const CorreccionesScreen({super.key});

  @override
  Widget build(BuildContext context) => BlocBuilder<CorreccionesCubit, CorreccionesState>(
    builder: (ctx, state) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text("Aprendizaje Continuo", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
          Text("Correcciones capturadas por el agente (se aplican automáticamente, sin aprobación humana).", style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
        ]),
        IconButton(icon: const Icon(Icons.refresh, color: AppColors.indigo), onPressed: () => ctx.read<CorreccionesCubit>().loadCorrecciones()),
      ]),
      const SizedBox(height: 16),
      if (state is CorreccionesLoading) const AppShimmer()
      else if (state is CorreccionesLoaded)
        state.correcciones.isEmpty
            ? const AppEmptyState(icon: Icons.psychology_alt_outlined, message: "No hay correcciones registradas aún.")
            : PanelCard(title: "Correcciones", subtitle: "${state.correcciones.length} registros · ordenadas por más repetidas",
                child: Column(children: state.correcciones.map((c) => _CorreccionTile(
                    c: c, eliminando: state.eliminandoId == c.id,
                    onDelete: () => _confirmarEliminar(context, ctx, c))).toList()))
      else if (state is CorreccionesError)
        AppEmptyState(icon: Icons.error_outline, message: state.error)
      else
        const AppEmptyState(icon: Icons.psychology_alt_outlined, message: "Toca el botón de recarga para cargar las correcciones."),
    ]),
  );

  Future<void> _confirmarEliminar(BuildContext context, BuildContext cubitCtx, CorreccionEntity c) async {
    final ok = await showDialog<bool>(context: context, builder: (dialogCtx) => AlertDialog(
      title: const Text("Eliminar corrección"),
      content: Text("¿Eliminar esta corrección? Dejará de aplicarse en el contexto del agente.\n\n${c.descripcionError}"),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogCtx, false), child: const Text("Cancelar")),
        ElevatedButton(onPressed: () => Navigator.pop(dialogCtx, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.red, foregroundColor: Colors.white), child: const Text("Eliminar")),
      ],
    ));
    if (ok == true && cubitCtx.mounted) cubitCtx.read<CorreccionesCubit>().eliminarCorreccion(c.id);
  }
}

class _CorreccionTile extends StatelessWidget {
  final CorreccionEntity c;
  final bool eliminando;
  final VoidCallback onDelete;
  const _CorreccionTile({required this.c, required this.eliminando, required this.onDelete});

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        AppBadge(text: "x${c.vecesRepetida}", bg: c.vecesRepetida > 1 ? AppColors.indigo : AppColors.indigoLight,
            fg: c.vecesRepetida > 1 ? Colors.white : AppColors.indigo),
        const SizedBox(width: 6),
        AppBadge(text: c.esAutomatica ? "Automática" : "Manual",
            bg: c.esAutomatica ? const Color(0x1AF59E0B) : AppColors.emeraldLight,
            fg: c.esAutomatica ? const Color(0xFFB45309) : AppColors.emerald),
        if (c.tipoRack != null) ...[const SizedBox(width: 6), AppBadge(text: c.tipoRack!, bg: AppColors.bg, fg: AppColors.textSecond)],
        const Spacer(),
        Text(Formatters.date(c.createdAt), style: const TextStyle(fontSize: 10, color: AppColors.textHint)),
        const SizedBox(width: 8),
        GestureDetector(
          onTap: eliminando ? null : onDelete,
          child: Container(padding: const EdgeInsets.all(6), decoration: BoxDecoration(color: AppColors.redLight, borderRadius: BorderRadius.circular(6)),
              child: eliminando
                  ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.red))
                  : const Icon(Icons.delete_outline, size: 16, color: AppColors.red)),
        ),
      ]),
      const SizedBox(height: 8),
      Text(c.descripcionError, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
      if (c.instruccionCorrectiva.isNotEmpty && c.instruccionCorrectiva != c.descripcionError) ...[
        const SizedBox(height: 4),
        Text(c.instruccionCorrectiva, style: const TextStyle(fontSize: 12, color: AppColors.textSecond)),
      ],
      if (c.proyectoClave != null) ...[
        const SizedBox(height: 4),
        Text("Clave: ${c.proyectoClave}", style: const TextStyle(fontSize: 10, color: AppColors.textHint, fontFamily: "monospace")),
      ],
    ]),
  );
}
