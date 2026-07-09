import "package:flutter/material.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../../domain/nodo_arquitectura.dart";
import "../widgets/red_arquitectura_painter.dart";

class ArquitecturaScreen extends StatefulWidget {
  const ArquitecturaScreen({super.key});
  @override State<ArquitecturaScreen> createState() => _ArquitecturaScreenState();
}

class _ArquitecturaScreenState extends State<ArquitecturaScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  String? _seleccionado;

  @override void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(seconds: 4))..repeat();
  }

  @override void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  NodoArquitectura? get _nodo => _seleccionado == null
      ? null
      : ArquitecturaData.nodos.where((n) => n.id == _seleccionado).firstOrNull;

  void _onTapDown(TapDownDetails details, Map<String, Offset> posiciones) {
    const radioToque = 32.0;
    String? masCercano;
    double mejorDist = double.infinity;
    for (final entry in posiciones.entries) {
      final d = (entry.value - details.localPosition).distance;
      if (d < radioToque && d < mejorDist) { mejorDist = d; masCercano = entry.key; }
    }
    setState(() => _seleccionado = masCercano);
  }

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text("Arquitectura del sistema", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
    const SizedBox(height: 4),
    const Text("Cómo fluye una solicitud a través de los motores reales del proyecto. Toca un nodo para ver su detalle.",
        style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
    const SizedBox(height: 8),
    Wrap(spacing: 12, runSpacing: 6, children: [
      _leyenda(AppColors.emerald, "Implementado"),
      _leyenda(AppColors.amber, "Parcial / no-op sin configurar"),
      _leyenda(AppColors.textHint, "Descartado a propósito"),
    ]),
    const SizedBox(height: 16),
    PanelCard(
      title: "Mapa de motores", subtitle: "${ArquitecturaData.nodos.length} componentes",
      child: LayoutBuilder(builder: (context, constraints) {
        final ancho = constraints.maxWidth.clamp(600, 1400).toDouble();
        const alto = 460.0;
        final posiciones = {
          for (final n in ArquitecturaData.nodos)
            n.id: Offset(n.posicion.dx * ancho, n.posicion.dy * alto),
        };
        return SizedBox(
          width: ancho, height: alto,
          child: AnimatedBuilder(
            animation: _ctrl,
            builder: (context, _) => GestureDetector(
              onTapDown: (d) => _onTapDown(d, posiciones),
              child: CustomPaint(
                size: Size(ancho, alto),
                painter: RedArquitecturaPainter(pulso: _ctrl.value, nodoSeleccionado: _seleccionado, posicionesAbs: posiciones),
              ),
            ),
          ),
        );
      }),
    ),
    if (_nodo != null) PanelCard(
      title: _nodo!.label.replaceAll("\n", " "),
      subtitle: switch (_nodo!.estado) {
        EstadoNodo.implementado => "Implementado",
        EstadoNodo.parcial => "Parcial",
        EstadoNodo.noImplementado => "Descartado a propósito",
      },
      child: Text(_nodo!.descripcion, style: const TextStyle(fontSize: 13, color: AppColors.textPrimary, height: 1.4)),
    )
    else const AppEmptyState(icon: Icons.touch_app_outlined, message: "Toca cualquier círculo del mapa para ver qué hace ese componente."),
  ]);

  Widget _leyenda(Color color, String texto) => Row(mainAxisSize: MainAxisSize.min, children: [
    Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
    const SizedBox(width: 6),
    Text(texto, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
  ]);
}
