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
      _leyendaBorde(AppColors.textHint, "Descartado o futuro (borde punteado)"),
      _leyendaLinea(AppColors.indigo, "Flujo de datos"),
      _leyendaLinea(AppColors.purple, "Observabilidad (LangSmith), punteado"),
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
    if (_nodo != null) _panelDetalleNodo(_nodo!)
    else const AppEmptyState(icon: Icons.touch_app_outlined, message: "Toca cualquier círculo del mapa para ver qué hace ese componente."),
    const SizedBox(height: 16),
    _panelFlujo(
      titulo: "Flujo 1 — Cómo se genera un diseño",
      subtitulo: "Del mensaje del cliente a los archivos entregados",
      pasos: ArquitecturaData.flujoGeneracion,
    ),
    const SizedBox(height: 16),
    _panelFlujo(
      titulo: "Flujo 2 — Cómo aprende el sistema",
      subtitulo: "De una corrección manual a una regla reutilizable",
      pasos: ArquitecturaData.flujoAprendizaje,
    ),
  ]);

  Widget _panelDetalleNodo(NodoArquitectura nodo) => PanelCard(
    title: nodo.label.replaceAll("\n", " "),
    subtitle: switch (nodo.estado) {
      EstadoNodo.implementado => "Implementado",
      EstadoNodo.parcial => "Parcial",
      EstadoNodo.noImplementado => "Descartado a propósito / futuro",
    },
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(nodo.descripcion, style: const TextStyle(fontSize: 13, color: AppColors.textPrimary, height: 1.4)),
      if (nodo.capituloManual != null) ...[
        const SizedBox(height: 10),
        Row(children: [
          const Icon(Icons.menu_book_outlined, size: 14, color: AppColors.textHint),
          const SizedBox(width: 6),
          Text(nodo.capituloManual!, style: const TextStyle(fontSize: 11, color: AppColors.textHint, fontStyle: FontStyle.italic)),
        ]),
      ],
      if (nodo.entradas.isNotEmpty && nodo.entradas != "-") ...[
        const SizedBox(height: 10),
        _filaEntradaSalida("Recibe", nodo.entradas),
      ],
      if (nodo.salidas.isNotEmpty && nodo.salidas != "-") ...[
        const SizedBox(height: 6),
        _filaEntradaSalida("Entrega", nodo.salidas),
      ],
    ]),
  );

  Widget _filaEntradaSalida(String etiqueta, String texto) => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
    SizedBox(width: 60, child: Text(etiqueta, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.textSecond))),
    Expanded(child: Text(texto, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary, height: 1.3))),
  ]);

  Widget _panelFlujo({required String titulo, required String subtitulo, required List<PasoFlujo> pasos}) => PanelCard(
    title: titulo,
    subtitle: subtitulo,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final paso in pasos) _filaPaso(paso),
    ]),
  );

  Widget _filaPaso(PasoFlujo paso) {
    final activo = _seleccionado == paso.nodoId;
    return InkWell(
      onTap: () => setState(() => _seleccionado = paso.nodoId),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 22, height: 22,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: activo ? AppColors.indigo : AppColors.indigo.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: Text("${paso.numero}", style: TextStyle(
                fontSize: 11, fontWeight: FontWeight.w800,
                color: activo ? Colors.white : AppColors.indigo)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(paso.titulo, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
              const SizedBox(height: 2),
              Text(paso.detalle, style: const TextStyle(fontSize: 12, color: AppColors.textSecond, height: 1.35)),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _leyenda(Color color, String texto) => Row(mainAxisSize: MainAxisSize.min, children: [
    Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
    const SizedBox(width: 6),
    Text(texto, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
  ]);

  Widget _leyendaBorde(Color color, String texto) => Row(mainAxisSize: MainAxisSize.min, children: [
    Container(
      width: 10, height: 10,
      decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: color, width: 1.4)),
    ),
    const SizedBox(width: 6),
    Text(texto, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
  ]);

  Widget _leyendaLinea(Color color, String texto) => Row(mainAxisSize: MainAxisSize.min, children: [
    Container(width: 14, height: 2, color: color),
    const SizedBox(width: 6),
    Text(texto, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
  ]);
}
