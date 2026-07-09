import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../core/utils/formatters.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/historial_cubit.dart";
import "../cubit/historial_state.dart";
import "../../domain/entities/diseno_entity.dart";

class HistorialScreen extends StatelessWidget {
  const HistorialScreen({super.key});

  @override
  Widget build(BuildContext context) => BlocBuilder<HistorialCubit, HistorialState>(
    builder: (ctx, state) {
      final mobile = Bp.isMobile(context);
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text("Historial de Diseños", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
            Text("Sesiones y versiones generadas por el bot.", style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
          ]),
          IconButton(icon: const Icon(Icons.refresh, color: AppColors.indigo), onPressed: () => ctx.read<HistorialCubit>().loadHistorial()),
        ]),
        const SizedBox(height: 16),
        if (state is HistorialLoading) const AppShimmer()
        else if (state is HistorialLoaded)
          mobile
              ? _MobileHistorial(state: state, onSelect: (id) => ctx.read<HistorialCubit>().selectSesion(id))
              : _DesktopHistorial(state: state, onSelect: (id) => ctx.read<HistorialCubit>().selectSesion(id))
        else if (state is HistorialError)
          AppEmptyState(icon: Icons.error_outline, message: state.error)
        else
          const AppEmptyState(icon: Icons.history, message: "Toca el botón de recarga para cargar el historial."),
      ]);
    },
  );
}

class _DesktopHistorial extends StatelessWidget {
  final HistorialLoaded state;
  final void Function(String) onSelect;
  const _DesktopHistorial({required this.state, required this.onSelect});

  @override
  Widget build(BuildContext context) => state.disenos.isEmpty
      ? const AppEmptyState(icon: Icons.history, message: "No hay diseños registrados aún.")
      : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(flex: 2, child: PanelCard(title: "Sesiones", subtitle: "${state.disenos.length} registros",
              child: Column(children: state.disenos.map((d) => _SesionTile(d: d, selected: d.sessionId == state.selectedSessionId, onTap: () => onSelect(d.sessionId))).toList()))),
          const SizedBox(width: 14),
          Expanded(flex: 3, child: state.selectedSessionId == null
              ? Container(height: 200, decoration: BoxDecoration(border: Border.all(color: AppColors.border, width: 2), borderRadius: BorderRadius.circular(14)),
                  child: const Center(child: Text("Selecciona una sesión", style: TextStyle(color: AppColors.textSecond, fontSize: 13))))
              : state.loadingVersiones ? const AppShimmer()
              : PanelCard(title: "Versiones", subtitle: "Sesión: ...${state.selectedSessionId!.substring(state.selectedSessionId!.length > 8 ? state.selectedSessionId!.length - 8 : 0)}",
                  child: Column(children: state.versiones.map((v) => _VersionTile(v: v)).toList()))),
        ]);
}

class _MobileHistorial extends StatelessWidget {
  final HistorialLoaded state;
  final void Function(String) onSelect;
  const _MobileHistorial({required this.state, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    if (state.selectedSessionId != null) {
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        TextButton.icon(onPressed: () => onSelect(""), icon: const Icon(Icons.arrow_back, size: 16), label: const Text("Volver a sesiones")),
        if (state.loadingVersiones) const AppShimmer()
        else ...state.versiones.map((v) => _VersionTile(v: v)),
      ]);
    }
    return Column(children: state.disenos.map((d) =>
        _SesionTile(d: d, selected: false, onTap: () => onSelect(d.sessionId))).toList());
  }
}

class _SesionTile extends StatelessWidget {
  final DisenoEntity d;
  final bool selected;
  final VoidCallback onTap;
  const _SesionTile({required this.d, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: AnimatedContainer(
      duration: const Duration(milliseconds: 150),
      margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: selected ? AppColors.indigoLight : AppColors.surface,
          borderRadius: BorderRadius.circular(10), border: Border.all(color: selected ? AppColors.indigo : AppColors.border)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Expanded(child: Text(d.vendedorId, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: selected ? AppColors.indigo : AppColors.textPrimary), overflow: TextOverflow.ellipsis)),
          AppBadge(text: "v${d.versionActual}", bg: selected ? AppColors.indigo : AppColors.indigoLight, fg: selected ? Colors.white : AppColors.indigo),
        ]),
        const SizedBox(height: 4),
        Text(d.solicitudOriginal, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
        const SizedBox(height: 4),
        Row(children: [const Icon(Icons.token, size: 11, color: AppColors.textHint), const SizedBox(width: 3),
            Text("${Formatters.thousands(d.totalTokens)} tokens", style: const TextStyle(fontSize: 10, color: AppColors.textHint))]),
      ]),
    ),
  );
}

class _VersionTile extends StatelessWidget {
  final DisenoEntity v;
  const _VersionTile({required this.v});

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppColors.border)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Container(width: 28, height: 28, decoration: const BoxDecoration(color: AppColors.indigoLight, shape: BoxShape.circle),
            child: Center(child: Text("${v.versionActual}", style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12, color: AppColors.indigo)))),
        const SizedBox(width: 10),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(v.solicitudOriginal, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: AppColors.textPrimary), maxLines: 2, overflow: TextOverflow.ellipsis),
          Text(Formatters.date(v.createdAt), style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
        ])),
      ]),
      if (v.historialComentarios.isNotEmpty) ...[
        const SizedBox(height: 8),
        ...v.historialComentarios.map((c) => Padding(padding: const EdgeInsets.only(bottom: 3, left: 8),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text("• ", style: TextStyle(color: AppColors.indigo, fontSize: 11)),
                Expanded(child: Text(c, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)))]))),
      ],
      if (v.inputTokens > 0 || v.outputTokens > 0) ...[
        const SizedBox(height: 8),
        Row(children: [TokenChip(label: "In", value: v.inputTokens, color: AppColors.cyan), const SizedBox(width: 6), TokenChip(label: "Out", value: v.outputTokens, color: AppColors.purple)]),
      ],
    ]),
  );
}
