import "dart:ui_web" as ui_web;
import "package:flutter/material.dart";
import "package:flutter_dotenv/flutter_dotenv.dart";
import "package:web/web.dart" as web;
import "../../core/theme/app_theme.dart";

/// URL del visor 3D (GitHub Pages / mismo valor que backend `URL_FRONTEND`).
/// Configurable vía `.env` → `VISOR_3D_URL`. El iframe solo manda `session_id`;
/// las credenciales Supabase viven como defaults en `frontend/index.html`.
String get _urlVisor3D =>
    dotenv.env["VISOR_3D_URL"]?.trim().isNotEmpty == true
        ? dotenv.env["VISOR_3D_URL"]!.trim()
        : "https://dazaragoza-ti.github.io/cotizacion_IA/index.html";

/// Abre un diálogo con el visor 3D en vivo (iframe) para la sesión indicada.
Future<void> mostrarVisor3D(BuildContext context,
    {required String sessionId, required String titulo}) async {
  if (sessionId.trim().isEmpty) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text("No hay session_id para abrir el visor 3D."),
      ));
    }
    return;
  }

  final base = _urlVisor3D;
  final sep = base.contains("?") ? "&" : "?";
  final url = "$base${sep}session_id=${Uri.encodeQueryComponent(sessionId)}";
  final viewType = "visor-3d-$sessionId-${DateTime.now().microsecondsSinceEpoch}";

  ui_web.platformViewRegistry.registerViewFactory(viewType, (int _) {
    final iframe = web.HTMLIFrameElement()
      ..src = url
      ..style.border = "none"
      ..style.width = "100%"
      ..style.height = "100%";
    return iframe;
  });

  if (!context.mounted) return;
  await showDialog(
    context: context,
    builder: (dialogCtx) => Dialog(
      insetPadding: const EdgeInsets.all(24),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: SizedBox(
        width: 480,
        height: 520,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
            child: Row(children: [
              const Icon(Icons.view_in_ar_outlined, size: 18, color: AppColors.indigo),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(titulo,
                      style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 13,
                          color: AppColors.textPrimary),
                      overflow: TextOverflow.ellipsis)),
              IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  onPressed: () => Navigator.of(dialogCtx).pop()),
            ]),
          ),
          const Divider(height: 1),
          Expanded(
            child: ClipRRect(
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
              child: HtmlElementView(viewType: viewType),
            ),
          ),
        ]),
      ),
    ),
  );
}
