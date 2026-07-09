import "package:flutter/material.dart";
import "package:model_viewer_plus/model_viewer_plus.dart";
import "../../core/theme/app_theme.dart";

const _extensionesModelo3D = {".glb", ".gltf"};

bool esArchivoModelo3D(String nombreOUrl) {
  final limpio = nombreOUrl.split("?").first.toLowerCase();
  return _extensionesModelo3D.any((ext) => limpio.endsWith(ext));
}

/// Abre una pestana chica (dialog) con una vista previa 3D interactiva
/// (rotar/zoom) del archivo GLB/GLTF indicado, sin salir del dashboard.
Future<void> mostrarPreview3D(BuildContext context, {required String url, required String nombre}) {
  return showDialog(
    context: context,
    builder: (dialogCtx) => Dialog(
      insetPadding: const EdgeInsets.all(24),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: SizedBox(
        width: 440,
        height: 480,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
            child: Row(children: [
              const Icon(Icons.view_in_ar_outlined, size: 18, color: AppColors.indigo),
              const SizedBox(width: 8),
              Expanded(child: Text(nombre, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: AppColors.textPrimary), overflow: TextOverflow.ellipsis)),
              IconButton(icon: const Icon(Icons.close, size: 20), onPressed: () => Navigator.of(dialogCtx).pop()),
            ]),
          ),
          const Divider(height: 1),
          Expanded(
            child: ClipRRect(
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
              child: ModelViewer(
                src: url,
                alt: nombre,
                autoRotate: true,
                cameraControls: true,
                backgroundColor: AppColors.bg,
              ),
            ),
          ),
        ]),
      ),
    ),
  );
}
