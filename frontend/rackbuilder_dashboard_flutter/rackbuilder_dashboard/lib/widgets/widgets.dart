import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../models/models.dart';

// ── Colores ──────────────────────────────────────────────────────────────────
const kBgColor      = Color(0xFFF8FAFC);
const kSurface      = Colors.white;
const kBorder       = Color(0xFFE2E8F0);
const kTextPrimary  = Color(0xFF0F172A);
const kTextSecond   = Color(0xFF64748B);
const kIndigo       = Color(0xFF4F46E5);
const kIndigoLight  = Color(0xFFEEF2FF);
const kAmber        = Color(0xFFD97706);
const kAmberLight   = Color(0xFFFFFBEB);
const kEmerald      = Color(0xFF059669);
const kEmeraldLight = Color(0xFFECFDF5);
const kRed          = Color(0xFFB91C1C);
const kRedLight     = Color(0xFFFEF2F2);

// ── Connection Badge ──────────────────────────────────────────────────────────
class ConnectionBadge extends StatelessWidget {
  final bool connected;
  final String text;
  const ConnectionBadge({super.key, required this.connected, required this.text});

  @override
  Widget build(BuildContext context) {
    final bg   = connected ? kEmeraldLight : kRedLight;
    final fg   = connected ? kEmerald      : kRed;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        _PulseDot(color: fg),
        const SizedBox(width: 6),
        Text(text, style: TextStyle(color: fg, fontWeight: FontWeight.w700, fontSize: 13)),
      ]),
    );
  }
}

class _PulseDot extends StatefulWidget {
  final Color color;
  const _PulseDot({required this.color});
  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat(reverse: true);
    _scale = Tween<double>(begin: 1.0, end: 1.3).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) => ScaleTransition(
    scale: _scale,
    child: Container(width: 9, height: 9, decoration: BoxDecoration(color: widget.color, shape: BoxShape.circle)),
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────────────
class KpiCard extends StatelessWidget {
  final String label;
  final String value;
  final String hint;
  final Color iconBg;
  final Color iconFg;
  final IconData icon;

  const KpiCard({
    super.key,
    required this.label,
    required this.value,
    required this.hint,
    required this.iconBg,
    required this.iconFg,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: kBgColor,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: kBorder),
    ),
    child: Row(children: [
      Container(
        width: 42, height: 42,
        decoration: BoxDecoration(color: iconBg, borderRadius: BorderRadius.circular(12)),
        child: Icon(icon, color: iconFg, size: 18),
      ),
      const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label.toUpperCase(), style: const TextStyle(fontSize: 11, color: kTextSecond, letterSpacing: 0.8)),
        Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kTextPrimary)),
        Text(hint, style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
      ])),
    ]),
  );
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
      Text(label, style: const TextStyle(color: kTextSecond, fontSize: 13)),
      Text('${percent.toStringAsFixed(0)}%', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
    ]),
    const SizedBox(height: 6),
    ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: LinearProgressIndicator(
        value: percent / 100,
        minHeight: 10,
        backgroundColor: const Color(0x2294A3B8),
        valueColor: AlwaysStoppedAnimation<Color>(color),
      ),
    ),
    const SizedBox(height: 4),
    Text(valueLabel, style: const TextStyle(fontSize: 11, color: kTextSecond)),
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
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    margin: const EdgeInsets.only(bottom: 16),
    decoration: BoxDecoration(
      color: kBgColor, borderRadius: BorderRadius.circular(14), border: Border.all(color: kBorder),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: kTextPrimary)),
        if (trailing != null) trailing!
        else Text(subtitle, style: const TextStyle(fontSize: 12, color: kTextSecond)),
      ]),
      if (trailing != null) ...[
        const SizedBox(height: 2),
        Text(subtitle, style: const TextStyle(fontSize: 12, color: kTextSecond)),
      ],
      const SizedBox(height: 14),
      child,
    ]),
  );
}

// ── Model File Card ───────────────────────────────────────────────────────────
class ModelFileCard extends StatelessWidget {
  final StorageFileItem model;
  final bool isOptimizing;
  final VoidCallback? onOptimize;  // null = otro modelo está siendo optimizado

  const ModelFileCard({super.key, required this.model, required this.isOptimizing, required this.onOptimize});

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: kSurface, borderRadius: BorderRadius.circular(16),
      border: Border.all(color: kBorder),
      boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 12, offset: const Offset(0, 4))],
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(model.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: kTextPrimary)),
          const SizedBox(height: 2),
          Text('${model.bucket} / ${model.folder.isEmpty ? "root" : model.folder}',
              style: const TextStyle(fontSize: 12, color: kTextSecond)),
        ])),
        model.isOptimized
          ? Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(color: kEmeraldLight, borderRadius: BorderRadius.circular(999)),
              child: Text('${model.compressionRatio}% reducción',
                  style: const TextStyle(color: kEmerald, fontSize: 11, fontWeight: FontWeight.w700)),
            )
          : Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(999)),
              child: const Text('Sin comprimir',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11, fontWeight: FontWeight.w700)),
            ),
      ]),
      const SizedBox(height: 10),
      Wrap(spacing: 12, runSpacing: 4, children: [
        _detail('Tipo', model.type),
        _detail('Peso', model.formattedSize),
        _detail('Est. Draco', model.formattedCompressed),
      ]),
      const SizedBox(height: 12),
      Row(mainAxisAlignment: MainAxisAlignment.end, children: [
        OutlinedButton(
          onPressed: () {}, // url_launcher
          style: OutlinedButton.styleFrom(
            foregroundColor: kIndigo, side: const BorderSide(color: Color(0xFFC7D2FE)),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
          ),
          child: const Text('Abrir'),
        ),
        const SizedBox(width: 8),
        ElevatedButton(
          onPressed: (isOptimizing || onOptimize == null) ? null : onOptimize,
          style: ElevatedButton.styleFrom(
            backgroundColor: kIndigoLight, foregroundColor: kIndigo,
            elevation: 0,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
          ),
          child: isOptimizing
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Optimizar automáticamente'),
        ),
      ]),
    ]),
  );

  Widget _detail(String label, String val) => Text('$label: $val',
      style: const TextStyle(color: kTextSecond, fontSize: 13));
}

// ── Shimmer Loader ────────────────────────────────────────────────────────────
class ShimmerLoader extends StatelessWidget {
  const ShimmerLoader({super.key});

  @override
  Widget build(BuildContext context) => Shimmer.fromColors(
    baseColor: const Color(0xFFE2E8F0),
    highlightColor: const Color(0xFFF8FAFC),
    child: Column(children: List.generate(3, (i) => Container(
      margin: const EdgeInsets.only(bottom: 12),
      height: 80,
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
    ))),
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String message;
  const EmptyState({super.key, required this.icon, required this.message});

  @override
  Widget build(BuildContext context) => Container(
    height: 200,
    decoration: BoxDecoration(
      border: Border.all(color: kBorder, style: BorderStyle.solid, width: 2),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 32, color: kIndigo),
      const SizedBox(height: 8),
      Text(message, style: const TextStyle(color: kTextSecond, fontSize: 13), textAlign: TextAlign.center),
    ])),
  );
}

// ── Sidebar Nav Button ────────────────────────────────────────────────────────
class NavButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;

  const NavButton({super.key, required this.icon, required this.label, required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
      decoration: BoxDecoration(
        color: active ? kIndigoLight : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: active ? const Color(0xFFC7D2FE) : Colors.transparent),
      ),
      child: Row(children: [
        Icon(icon, size: 17, color: active ? const Color(0xFF4338CA) : const Color(0xFF475569)),
        const SizedBox(width: 10),
        Text(label, style: TextStyle(
          fontWeight: FontWeight.w700, fontSize: 14,
          color: active ? const Color(0xFF4338CA) : const Color(0xFF475569),
        )),
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
    decoration: BoxDecoration(
      color: kSurface, borderRadius: BorderRadius.circular(10), border: Border.all(color: kBorder),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: const TextStyle(color: kTextSecond, fontSize: 12)),
      const SizedBox(height: 4),
      Text(value, style: const TextStyle(color: kTextPrimary, fontWeight: FontWeight.w700, fontSize: 14)),
    ]),
  );
}
