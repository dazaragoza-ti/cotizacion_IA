import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "package:file_picker/file_picker.dart";
import "package:url_launcher/url_launcher.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../../../../shared/widgets/model_3d_preview_dialog.dart";
import "../../domain/entities/storage_bucket.dart";
import "../cubit/alimentar_ia_cubit.dart";
import "../cubit/alimentar_ia_state.dart";

class AlimentarIaScreen extends StatefulWidget {
  const AlimentarIaScreen({super.key});
  @override State<AlimentarIaScreen> createState() => _AlimentarIaScreenState();
}

class _AlimentarIaScreenState extends State<AlimentarIaScreen> {
  Future<void> _subirArchivo(BuildContext ctx) async {
    final r = await FilePicker.pickFiles(withData: true);
    if (r == null || r.files.single.bytes == null) return;
    if (!ctx.mounted) return;
    await ctx.read<AlimentarIaCubit>().subirArchivo(
        bytes: r.files.single.bytes!, fileName: r.files.single.name);
  }

  Future<void> _nuevaCarpeta(BuildContext ctx) async {
    final controller = TextEditingController();
    final nombre = await showDialog<String>(context: context, builder: (dialogCtx) => AlertDialog(
      title: const Text("Nueva subcarpeta"),
      content: TextField(
        controller: controller, autofocus: true,
        decoration: const InputDecoration(hintText: "ej: Cliente_Acme_2026"),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(dialogCtx), child: const Text("Cancelar")),
        ElevatedButton(onPressed: () => Navigator.pop(dialogCtx, controller.text.trim()), child: const Text("Crear")),
      ],
    ));
    if (nombre != null && nombre.isNotEmpty && ctx.mounted) {
      await ctx.read<AlimentarIaCubit>().crearCarpeta(nombre);
    }
  }

  Future<void> _abrirArchivo(BuildContext context, String url, String nombre) async {
    if (url.isEmpty) return;
    if (esArchivoModelo3D(nombre)) {
      await mostrarPreview3D(context, url: url, nombre: nombre);
      return;
    }
    final uri = Uri.tryParse(url);
    if (uri != null) await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) => BlocConsumer<AlimentarIaCubit, AlimentarIaState>(
    listener: (ctx, state) {
      if (state is AlimentarIaLoaded && state.message.isNotEmpty) {
        ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
          content: Text(state.message),
          backgroundColor: state.success ? AppColors.emerald : AppColors.red,
          behavior: SnackBarBehavior.floating, duration: const Duration(seconds: 2),
        ));
      }
    },
    builder: (ctx, state) {
      final loaded = state is AlimentarIaLoaded ? state : null;
      final bucket = loaded?.bucket ?? StorageBucket.cotizaciones;
      final segments = loaded?.pathSegments ?? const <String>[];
      final carpetas = loaded?.carpetas ?? const [];
      final archivos = loaded?.archivos ?? const [];
      final uploading = loaded?.uploading ?? false;

      return SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text("Alimentar Inteligencia Artificial",
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
        const SizedBox(height: 4),
        const Text(
          "Explora y organiza los documentos de cotizaciones y precios unitarios en Supabase Storage. "
          "Crea subcarpetas para mantener todo ordenado por cliente, proyecto o fecha.",
          style: TextStyle(fontSize: 12, color: AppColors.textSecond),
        ),
        const SizedBox(height: 20),

        // Selector de bucket
        Row(children: StorageBucket.values.map((b) => Padding(
          padding: const EdgeInsets.only(right: 8),
          child: GestureDetector(
            onTap: () => ctx.read<AlimentarIaCubit>().cambiarBucket(b),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: bucket == b ? AppColors.indigo : AppColors.surface,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: bucket == b ? AppColors.indigo : AppColors.border),
              ),
              child: Text(b.label, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700,
                  color: bucket == b ? Colors.white : AppColors.textSecond)),
            ),
          ),
        )).toList()),
        const SizedBox(height: 16),

        PanelCard(
          title: "Explorador", subtitle: "${carpetas.length} carpetas · ${archivos.length} archivos",
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            IconButton(icon: const Icon(Icons.create_new_folder_outlined, size: 20, color: AppColors.indigo),
                tooltip: "Nueva subcarpeta", onPressed: () => _nuevaCarpeta(ctx)),
            IconButton(icon: const Icon(Icons.refresh, size: 18, color: AppColors.indigo),
                onPressed: () => ctx.read<AlimentarIaCubit>().navegarA(segments.length - 1)),
          ]),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            // Breadcrumb
            Wrap(crossAxisAlignment: WrapCrossAlignment.center, children: [
              _crumb("Inicio", active: segments.isEmpty, onTap: () => ctx.read<AlimentarIaCubit>().navegarA(-1)),
              for (int i = 0; i < segments.length; i++) ...[
                const Padding(padding: EdgeInsets.symmetric(horizontal: 4), child: Icon(Icons.chevron_right, size: 14, color: AppColors.textHint)),
                _crumb(segments[i], active: i == segments.length - 1, onTap: () => ctx.read<AlimentarIaCubit>().navegarA(i)),
              ],
            ]),
            const SizedBox(height: 14),

            // Botón de subir archivo
            SizedBox(width: double.infinity, child: OutlinedButton.icon(
              onPressed: uploading ? null : () => _subirArchivo(ctx),
              icon: uploading
                  ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.upload_file, size: 16),
              label: Text(uploading ? "Subiendo..." : "Subir archivo a esta carpeta"),
            )),
            const SizedBox(height: 14),

            if (state is AlimentarIaLoading) const AppShimmer()
            else if (state is AlimentarIaError) AppEmptyState(icon: Icons.error_outline, message: state.error)
            else if (carpetas.isEmpty && archivos.isEmpty)
              const AppEmptyState(icon: Icons.folder_open_outlined, message: "Esta carpeta está vacía. Crea una subcarpeta o sube un archivo.")
            else ...[
              ...carpetas.map((f) => _EntradaTile(
                icon: Icons.folder, iconColor: AppColors.amber, title: f.name, subtitle: "Carpeta",
                onTap: () => ctx.read<AlimentarIaCubit>().abrirCarpeta(f.name),
              )),
              ...archivos.map((a) => _EntradaTile(
                icon: esArchivoModelo3D(a.name) ? Icons.view_in_ar_outlined : Icons.insert_drive_file_outlined,
                iconColor: AppColors.indigo,
                title: a.name, subtitle: "${a.type} · ${a.sizeLabel}",
                onTap: () => _abrirArchivo(ctx, a.url, a.name),
              )),
            ],
          ]),
        ),
      ]));
    },
  );

  Widget _crumb(String label, {required bool active, required VoidCallback onTap}) => GestureDetector(
    onTap: active ? null : onTap,
    child: Text(label, style: TextStyle(
      fontSize: 12, fontWeight: active ? FontWeight.w800 : FontWeight.w600,
      color: active ? AppColors.textPrimary : AppColors.indigo,
      decoration: active ? TextDecoration.none : TextDecoration.underline,
    )),
  );
}

class _EntradaTile extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  const _EntradaTile({required this.icon, required this.iconColor, required this.title, required this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: Container(
      margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppColors.border)),
      child: Row(children: [
        Icon(icon, size: 20, color: iconColor),
        const SizedBox(width: 10),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary), overflow: TextOverflow.ellipsis),
          Text(subtitle, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
        ])),
        const Icon(Icons.chevron_right, size: 16, color: AppColors.textHint),
      ]),
    ),
  );
}
