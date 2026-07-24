import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/formatters.dart';

export '../../core/theme/app_theme.dart' show AppColors, Bp;

// ── Connection Badge ──────────────────────────────────────────────────────────
class ConnectionBadge extends StatelessWidget {
  final bool connected;
  final bool checking;
  final String text;
  final String? shortText;
  const ConnectionBadge({
    super.key,
    required this.connected,
    required this.text,
    this.checking = false,
    this.shortText,
  });

  @override
  Widget build(BuildContext context) {
    final Color bg;
    final Color fg;
    if (checking) {
      bg = const Color(0xFFFFF7ED);
      fg = AppColors.amber;
    } else if (connected) {
      bg = AppColors.emeraldLight;
      fg = AppColors.emerald;
    } else {
      bg = AppColors.redLight;
      fg = AppColors.red;
    }
    final mobile = Bp.isMobile(context);
    final label = checking
        ? (mobile ? '…' : 'Checking')
        : (mobile ? (shortText ?? (connected ? 'Online' : 'Off')) : text);
    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      padding: EdgeInsets.symmetric(horizontal: mobile ? 8 : 12, vertical: mobile ? 5 : 7),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        PulseDot(color: fg),
        const SizedBox(width: 6),
        Text(label, style: TextStyle(color: fg, fontWeight: FontWeight.w700, fontSize: mobile ? 11 : 13)),
      ]),
    );
  }
}

/// SnackBar de error flotante — mensaje útil, no tragar excepciones en silencio.
void showAppError(BuildContext context, String message) {
  if (!context.mounted) return;
  final trimmed = message.trim();
  if (trimmed.isEmpty) return;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
    content: Text(trimmed),
    backgroundColor: AppColors.red,
    behavior: SnackBarBehavior.floating,
    duration: const Duration(seconds: 4),
  ));
}

/// SnackBar informativo (warnings, avisos no fatales).
void showAppWarning(BuildContext context, String message) {
  if (!context.mounted) return;
  final trimmed = message.trim();
  if (trimmed.isEmpty) return;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
    content: Text(trimmed),
    backgroundColor: AppColors.amber,
    behavior: SnackBarBehavior.floating,
    duration: const Duration(seconds: 3),
  ));
}

// ── Pulse Dot ─────────────────────────────────────────────────────────────────
class PulseDot extends StatefulWidget {
  final Color color;
  const PulseDot({super.key, required this.color});
  @override State<PulseDot> createState() => _PulseDotState();
}
class _PulseDotState extends State<PulseDot> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _scale;
  @override void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat(reverse: true);
    _scale = Tween(begin: 1.0, end: 1.3).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }
  @override void dispose() { _ctrl.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) => ScaleTransition(
    scale: _scale,
    child: Container(width: 9, height: 9, decoration: BoxDecoration(color: widget.color, shape: BoxShape.circle)),
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────
class KpiCard extends StatelessWidget {
  final String label;
  final String value;
  final String hint;
  final Color iconBg;
  final Color iconFg;
  final IconData icon;
  const KpiCard({super.key, required this.label, required this.value, required this.hint,
      required this.iconBg, required this.iconFg, required this.icon});

  @override
  Widget build(BuildContext context) {
    final mobile = Bp.isMobile(context);
    return Container(
      padding: EdgeInsets.all(mobile ? 12 : 16),
      decoration: BoxDecoration(color: AppColors.bg, borderRadius: BorderRadius.circular(14), border: Border.all(color: AppColors.border)),
      child: Row(children: [
        Container(
          width: mobile ? 36 : 42, height: mobile ? 36 : 42,
          decoration: BoxDecoration(color: iconBg, borderRadius: BorderRadius.circular(12)),
          child: Icon(icon, color: iconFg, size: mobile ? 16 : 18),
        ),
        const SizedBox(width: 10),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label.toUpperCase(), style: TextStyle(fontSize: mobile ? 9 : 11, color: AppColors.textSecond, letterSpacing: 0.8)),
          Text(value, style: TextStyle(fontSize: mobile ? 16 : 20, fontWeight: FontWeight.w800, color: AppColors.textPrimary)),
          Text(hint, style: const TextStyle(fontSize: 10, color: AppColors.textHint)),
        ])),
      ]),
    );
  }
}

// ── Token Bar ─────────────────────────────────────────────────────────────────
class TokenBar extends StatelessWidget {
  final String label;
  final String valueLabel;
  final double percent;
  final Color color;
  const TokenBar({super.key, required this.label, required this.valueLabel, required this.percent, required this.color});

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      Text(label, style: const TextStyle(color: AppColors.textSecond, fontSize: 13)),
      Text('${percent.toStringAsFixed(0)}%', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
    ]),
    const SizedBox(height: 6),
    ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: LinearProgressIndicator(
        value: percent / 100, minHeight: 10,
        backgroundColor: const Color(0x2294A3B8),
        valueColor: AlwaysStoppedAnimation<Color>(color),
      ),
    ),
    const SizedBox(height: 4),
    Text(valueLabel, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
  ]);
}

// ── Panel Card ────────────────────────────────────────────────────────────────
class PanelCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget child;
  final Widget? trailing;
  const PanelCard({super.key, required this.title, required this.subtitle, required this.child, this.trailing});

  @override
  Widget build(BuildContext context) {
    final mobile = Bp.isMobile(context);
    return Container(
      padding: EdgeInsets.all(mobile ? 12 : 16),
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(color: AppColors.bg, borderRadius: BorderRadius.circular(14), border: Border.all(color: AppColors.border)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Expanded(child: Text(title, style: TextStyle(fontWeight: FontWeight.w700, fontSize: mobile ? 13 : 15, color: AppColors.textPrimary), overflow: TextOverflow.ellipsis)),
          const SizedBox(width: 8),
          if (trailing != null) trailing!
          else Text(subtitle, style: const TextStyle(fontSize: 12, color: AppColors.textSecond)),
        ]),
        if (trailing != null) ...[const SizedBox(height: 2), Text(subtitle, style: const TextStyle(fontSize: 12, color: AppColors.textSecond))],
        const SizedBox(height: 12),
        child,
      ]),
    );
  }
}

// ── Nav Button ────────────────────────────────────────────────────────────────
class NavButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;
  final bool iconOnly;
  const NavButton({super.key, required this.icon, required this.label, required this.active, required this.onTap, this.iconOnly = false});

  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      margin: iconOnly ? EdgeInsets.zero : const EdgeInsets.only(bottom: 6),
      padding: iconOnly
          ? const EdgeInsets.symmetric(vertical: 6)
          : const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
      decoration: iconOnly ? null : BoxDecoration(
        color: active ? AppColors.indigoLight : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: active ? AppColors.indigoBorder : Colors.transparent),
      ),
      child: iconOnly
          ? Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(icon, size: 22, color: active ? AppColors.indigo : AppColors.textHint),
              const SizedBox(height: 3),
              Text(label.split(' ').first, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: active ? AppColors.indigo : AppColors.textHint)),
            ])
          : Row(children: [
              Icon(icon, size: 17, color: active ? AppColors.indigoDark : AppColors.slate),
              const SizedBox(width: 10),
              Text(label, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: active ? AppColors.indigoDark : AppColors.slate)),
            ]),
    ),
  );
}

// ── Summary Item ──────────────────────────────────────────────────────────────
class SummaryItem extends StatelessWidget {
  final String label;
  final String value;
  const SummaryItem({super.key, required this.label, required this.value});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppColors.border)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: const TextStyle(color: AppColors.textSecond, fontSize: 12)),
      const SizedBox(height: 4),
      Text(value, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w700, fontSize: 14)),
    ]),
  );
}

// ── Shimmer Loader ────────────────────────────────────────────────────────────
class AppShimmer extends StatelessWidget {
  const AppShimmer({super.key});
  @override
  Widget build(BuildContext context) => Shimmer.fromColors(
    baseColor: const Color(0xFFE2E8F0),
    highlightColor: AppColors.bg,
    child: Column(children: List.generate(3, (i) => Container(
      margin: const EdgeInsets.only(bottom: 12), height: 80,
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
    ))),
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────
class AppEmptyState extends StatelessWidget {
  final IconData icon;
  final String message;
  const AppEmptyState({super.key, required this.icon, required this.message});
  @override
  Widget build(BuildContext context) => Container(
    height: 180,
    decoration: BoxDecoration(border: Border.all(color: AppColors.border, width: 2), borderRadius: BorderRadius.circular(14)),
    child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 28, color: AppColors.indigo),
      const SizedBox(height: 8),
      Padding(padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(message, style: const TextStyle(color: AppColors.textSecond, fontSize: 13), textAlign: TextAlign.center)),
    ])),
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────
class AppBadge extends StatelessWidget {
  final String text;
  final Color bg;
  final Color fg;
  const AppBadge({super.key, required this.text, required this.bg, required this.fg});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
    child: Text(text, style: TextStyle(color: fg, fontSize: 10, fontWeight: FontWeight.w700)),
  );
}

// ── Responsive Row ────────────────────────────────────────────────────────────
class ResponsiveRow extends StatelessWidget {
  final List<Widget> children;
  final double breakpoint;
  final double spacing;
  const ResponsiveRow({super.key, required this.children, this.breakpoint = 600, this.spacing = 12});

  @override
  Widget build(BuildContext context) {
    if (Bp.width(context) >= breakpoint) {
      return Row(crossAxisAlignment: CrossAxisAlignment.start, children: children
          .asMap().entries.map((e) => Expanded(child: e.key < children.length - 1
              ? Padding(padding: EdgeInsets.only(right: spacing), child: e.value)
              : e.value)).toList());
    }
    return Column(children: children.map((c) =>
        Padding(padding: EdgeInsets.only(bottom: spacing), child: c)).toList());
  }
}

// ── Token Chip ────────────────────────────────────────────────────────────────
class TokenChip extends StatelessWidget {
  final String label;
  final int value;
  final Color color;
  const TokenChip({super.key, required this.label, required this.value, required this.color});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
    decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(999)),
    child: Text('$label: ${Formatters.thousands(value)}',
        style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
  );
}

// ── Confirm Dialog ────────────────────────────────────────────────────────────
/// Diálogo de confirmación estándar para acciones destructivas (eliminar,
/// descartar, etc.) — antes cada pantalla armaba su propio AlertDialog inline
/// con estilos ligeramente distintos (ver catalogo_screen.dart).
Future<bool> confirmarAccion(
  BuildContext context, {
  required String titulo,
  required String mensaje,
  String textoConfirmar = "Eliminar",
  String textoCancelar = "Cancelar",
  bool destructivo = true,
}) async {
  final ok = await showDialog<bool>(context: context, builder: (c) => AlertDialog(
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    title: Text(titulo, style: const TextStyle(fontWeight: FontWeight.w700)),
    content: Text(mensaje),
    actions: [
      TextButton(onPressed: () => Navigator.pop(c, false), child: Text(textoCancelar)),
      ElevatedButton(
        onPressed: () => Navigator.pop(c, true),
        style: ElevatedButton.styleFrom(
          backgroundColor: destructivo ? AppColors.red : AppColors.indigo,
          foregroundColor: Colors.white,
        ),
        child: Text(textoConfirmar),
      ),
    ],
  ));
  return ok == true;
}
