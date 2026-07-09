import "dart:ui_web" as ui_web;
import "package:flutter/material.dart";
import "package:shared_preferences/shared_preferences.dart";
import "package:web/web.dart" as web;
import "../../core/theme/app_theme.dart";

// Mismo visor web (GitHub Pages) que usa el bot de Telegram
// (ver backend/app/config.py: URL_FRONTEND) -- lee sb_url/sb_key/session_id
// y arma el render 3D en vivo desde Supabase, no hay un archivo GLB estatico
// por version para incrustar directamente.
const _urlVisor3D = "https://dazaragoza-ti.github.io/cotizacion_IA/index.html";

/// Abre una pestana chica con el visor 3D en vivo (iframe) para la sesion de
/// diseno indicada. Si todavia no hay credenciales de Supabase cacheadas
/// (el dashboard no se conecto aun), avisa en vez de mostrar un iframe roto.
Future<void> mostrarVisor3D(BuildContext context, {required String sessionId, required String titulo}) async {
  final prefs = await SharedPreferences.getInstance();
  final sbUrl = prefs.getString("sb_url") ?? "";
  final sbKey = prefs.getString("sb_key") ?? "";
  if (sbUrl.isEmpty || sbKey.isEmpty || !context.mounted) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text("Aun no hay credenciales de Supabase cacheadas -- recarga el dashboard e intenta de nuevo."),
      ));
    }
    return;
  }

  final url = "$_urlVisor3D?sb_url=${Uri.encodeQueryComponent(sbUrl)}"
      "&sb_key=${Uri.encodeQueryComponent(sbKey)}"
      "&session_id=${Uri.encodeQueryComponent(sessionId)}";
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
              Expanded(child: Text(titulo, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: AppColors.textPrimary), overflow: TextOverflow.ellipsis)),
              IconButton(icon: const Icon(Icons.close, size: 20), onPressed: () => Navigator.of(dialogCtx).pop()),
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
