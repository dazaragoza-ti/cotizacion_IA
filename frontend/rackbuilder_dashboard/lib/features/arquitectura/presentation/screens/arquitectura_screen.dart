import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../../domain/nodo_arquitectura.dart";
import "../../domain/error_sistema.dart";
import "../cubit/arquitectura_cubit.dart";
import "../cubit/arquitectura_state.dart";
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
    context.read<ArquitecturaCubit>().iniciarPolling();
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
  Widget build(BuildContext context) => BlocBuilder<ArquitecturaCubit, ArquitecturaState>(
    builder: (context, state) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Text("Arquitectura del sistema", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
        const SizedBox(width: 10),
        _indicadorEnVivo(state.enVivoConectado),
      ]),
      const SizedBox(height: 4),
      const Text("Cómo fluye una solicitud a través de los motores reales del proyecto. Toca un nodo para ver su detalle.",
          style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
      const SizedBox(height: 8),
      if (state.errores.isNotEmpty) ...[
        _panelFallos(context, state.errores),
        const SizedBox(height: 12),
      ],
      if (state.pasosEnCurso.isNotEmpty) ...[
        _panelEnCurso(state.pasosEnCurso),
        const SizedBox(height: 12),
      ],
      Wrap(spacing: 12, runSpacing: 6, children: [
        _leyenda(AppColors.emerald, "Implementado"),
        _leyenda(AppColors.amber, "Parcial / no-op sin configurar"),
        _leyendaBorde(AppColors.textHint, "Descartado o futuro (borde punteado)"),
        _leyenda(AppColors.red, "Fallo reciente (ver detalle abajo)"),
        _leyendaLinea(AppColors.indigo, "Flujo de datos"),
        _leyendaLinea(AppColors.purple, "Observabilidad (LangSmith), punteado"),
        _leyendaAnillo(AppColors.cyan, "Solicitud real en curso ahora mismo"),
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
                  painter: RedArquitecturaPainter(
                    pulso: _ctrl.value,
                    nodoSeleccionado: _seleccionado,
                    posicionesAbs: posiciones,
                    nodosConError: state.nodosConError,
                    nodosActivos: state.nodosActivos,
                  ),
                ),
              ),
            ),
          );
        }),
      ),
      if (_nodo != null) _panelDetalleNodo(_nodo!, state.metricaDe(_nodo!.id), state.pasosEnCurso[_nodo!.id])
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
    ]),
  );

  Widget _panelFallos(BuildContext context, List<ErrorSistema> errores) => PanelCard(
    title: "Fallos recientes",
    subtitle: "${errores.length} sin resolver",
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final e in errores) Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.error_outline, size: 16, color: AppColors.red),
          const SizedBox(width: 8),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              AppBadge(text: e.componente, bg: AppColors.redLight, fg: AppColors.red),
              const SizedBox(width: 6),
              if (e.endpoint != null) Expanded(child: Text(e.endpoint!,
                  style: const TextStyle(fontSize: 11, color: AppColors.textHint), overflow: TextOverflow.ellipsis)),
            ]),
            const SizedBox(height: 4),
            Text(e.mensaje, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary), maxLines: 2, overflow: TextOverflow.ellipsis),
          ])),
          const SizedBox(width: 8),
          TextButton(
            onPressed: () => context.read<ArquitecturaCubit>().resolverError(e.id),
            child: const Text("Marcar resuelto", style: TextStyle(fontSize: 11)),
          ),
        ]),
      ),
    ]),
  );

  Widget _panelEnCurso(Map<String, String> pasosEnCurso) => PanelCard(
    title: "Ahora mismo",
    subtitle: "${pasosEnCurso.length} nodo(s) procesando una solicitud real",
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final entry in pasosEnCurso.entries) Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const SizedBox(
            width: 12, height: 12,
            child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.cyan),
          ),
          const SizedBox(width: 8),
          AppBadge(
            text: ArquitecturaData.nodos.where((n) => n.id == entry.key).firstOrNull?.label.replaceAll("\n", " ") ?? entry.key,
            bg: AppColors.indigoLight, fg: AppColors.indigo,
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(entry.value, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary))),
        ]),
      ),
    ]),
  );

  Widget _panelDetalleNodo(NodoArquitectura nodo, Map<String, dynamic> metrica, String? pasoEnCurso) => PanelCard(
    title: nodo.label.replaceAll("\n", " "),
    subtitle: switch (nodo.estado) {
      EstadoNodo.implementado => "Implementado",
      EstadoNodo.parcial => "Parcial",
      EstadoNodo.noImplementado => "Descartado a propósito / futuro",
    },
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(nodo.descripcion, style: const TextStyle(fontSize: 13, color: AppColors.textPrimary, height: 1.4)),
      if (pasoEnCurso != null) ...[
        const SizedBox(height: 10),
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const SizedBox(
            width: 12, height: 12,
            child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.cyan),
          ),
          const SizedBox(width: 8),
          Expanded(child: Text("Ahora mismo: $pasoEnCurso",
              style: const TextStyle(fontSize: 12, color: AppColors.indigo, fontWeight: FontWeight.w700))),
        ]),
      ],
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
      if (_textoEnVivo(nodo.id, metrica) case final texto?) ...[
        const SizedBox(height: 12),
        const Divider(height: 1),
        const SizedBox(height: 10),
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.bolt, size: 14, color: AppColors.emerald),
          const SizedBox(width: 6),
          Expanded(child: Text(texto, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary, fontWeight: FontWeight.w600))),
        ]),
      ],
    ]),
  );

  String? _textoEnVivo(String nodoId, Map<String, dynamic> m) {
    if (m.isEmpty) return null;
    switch (nodoId) {
      case "fastapi":
        return "En vivo: backend ${m["estado"]?.toString() ?? "desconocido"}.";
      case "supabase":
        return "En vivo: ${m["estado"]?.toString() ?? "desconocido"}.";
      case "langsmith":
        return "En vivo: ${m["configurado"] == true ? "configurado, trazando" : "no configurado (no-op)"}.";
      case "rag":
        final chunks = m["chunks_indexados"];
        return chunks == null ? null : "En vivo: $chunks chunks indexados en knowledge_chunks.";
      case "graph":
        final relaciones = m["relaciones_activas"];
        return relaciones == null ? null : "En vivo: $relaciones relaciones activas en el grafo.";
      case "claude":
        final disenos = m["disenos_generados"];
        if (disenos == null) return null;
        final tokens = m["tokens_totales"] ?? 0;
        final costo = m["costo_usd"] ?? 0;
        return "En vivo: $disenos diseños generados, $tokens tokens, costo USD $costo.";
      case "promotion":
        final reglas = m["reglas_activas"];
        return reglas == null ? null : "En vivo: $reglas reglas activas en reglas_armado.";
      default:
        return null;
    }
  }

  Widget _filaEntradaSalida(String etiqueta, String texto) => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
    SizedBox(width: 60, child: Text(etiqueta, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.textSecond))),
    Expanded(child: Text(texto, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary, height: 1.3))),
  ]);

  Widget _panelFlujo({required String titulo, required String subtitulo, required List<PasoFlujo> pasos}) {
    // Sin nodo seleccionado: se ven todos los pasos. Con un nodo seleccionado,
    // solo quedan los pasos donde ese nodo participa (protagonista o
    // relacionado) -- antes tocar Supabase o LangSmith no filtraba nada y
    // parecia que no tenian relacion con ningun flujo.
    final seleccionado = _seleccionado;
    final pasosFiltrados = seleccionado == null
        ? pasos
        : pasos.where((p) => p.coincideCon(seleccionado)).toList();
    return PanelCard(
      title: titulo,
      subtitle: subtitulo,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (seleccionado != null && pasosFiltrados.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text("Este nodo no participa directamente en este flujo.",
                style: TextStyle(fontSize: 12, color: AppColors.textHint, fontStyle: FontStyle.italic)),
          )
        else
          for (final paso in pasosFiltrados) _filaPaso(paso),
      ]),
    );
  }

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

  Widget _indicadorEnVivo(bool conectado) => Tooltip(
    message: conectado
        ? "Supabase Realtime conectado: el mapa se actualiza al instante cuando cambian los datos."
        : "Realtime no conectado -- se refresca por polling cada 30s.",
    child: Row(mainAxisSize: MainAxisSize.min, children: [
      Container(
        width: 8, height: 8,
        decoration: BoxDecoration(
          color: conectado ? AppColors.emerald : AppColors.textHint,
          shape: BoxShape.circle,
        ),
      ),
      const SizedBox(width: 4),
      Text(conectado ? "En vivo" : "Polling",
          style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700,
              color: conectado ? AppColors.emerald : AppColors.textHint)),
    ]),
  );

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

  Widget _leyendaAnillo(Color color, String texto) => Row(mainAxisSize: MainAxisSize.min, children: [
    Container(
      width: 12, height: 12,
      decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: color, width: 1.6)),
    ),
    const SizedBox(width: 6),
    Text(texto, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
  ]);
}
