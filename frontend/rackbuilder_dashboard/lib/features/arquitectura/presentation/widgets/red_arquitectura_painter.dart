import "dart:math" as math;
import "package:flutter/material.dart";
import "../../domain/nodo_arquitectura.dart";
import "../../../../core/theme/app_theme.dart";

Color colorDeEstado(EstadoNodo e) => switch (e) {
  EstadoNodo.implementado => AppColors.emerald,
  EstadoNodo.parcial => AppColors.amber,
  EstadoNodo.noImplementado => AppColors.textHint,
};

class RedArquitecturaPainter extends CustomPainter {
  final double pulso; // 0..1, avanza con la animacion
  final String? nodoSeleccionado;
  final Map<String, Offset> posicionesAbs;
  final Set<String> nodosConError;
  final Set<String> nodosActivos; // por aqui esta pasando una solicitud real AHORA

  RedArquitecturaPainter({
    required this.pulso,
    required this.nodoSeleccionado,
    required this.posicionesAbs,
    this.nodosConError = const {},
    this.nodosActivos = const {},
  });

  Offset _pos(String id) => posicionesAbs[id] ?? Offset.zero;

  @override
  void paint(Canvas canvas, Size size) {
    for (int i = 0; i < ArquitecturaData.conexiones.length; i++) {
      final c = ArquitecturaData.conexiones[i];
      final a = _pos(c.desde);
      final b = _pos(c.hacia);
      if (a == Offset.zero || b == Offset.zero) continue;

      final resaltada = nodoSeleccionado != null && (nodoSeleccionado == c.desde || nodoSeleccionado == c.hacia);
      final colorLinea = c.observabilidad
          ? AppColors.purple
          : (c.offline ? AppColors.textHint : AppColors.indigo);
      final lineaPaint = Paint()
        ..color = colorLinea.withValues(alpha: resaltada ? 0.9 : (c.observabilidad || c.offline ? 0.3 : 0.35))
        ..strokeWidth = resaltada ? 2.6 : 1.6
        ..style = PaintingStyle.stroke;

      if (c.observabilidad || c.offline) {
        // offline: misma linea punteada que observabilidad, pero neutra y sin
        // pulso -- no representa datos fluyendo en vivo, sino una accion
        // manual de un desarrollador (ej. Corrector 3D).
        _dibujarLineaPunteada(canvas, a, b, lineaPaint, dash: 5, gap: 4);
      } else {
        canvas.drawLine(a, b, lineaPaint);
        // Pulso viajando por la conexion -- efecto "red neuronal" activa.
        final t = (pulso + i * 0.13) % 1.0;
        final punto = Offset.lerp(a, b, t)!;
        canvas.drawCircle(punto, resaltada ? 4.5 : 3.0,
            Paint()..color = (c.observabilidad ? AppColors.purple : AppColors.indigo).withValues(alpha: 0.9));
      }
    }

    for (final n in ArquitecturaData.nodos) {
      final pos = _pos(n.id);
      if (pos == Offset.zero) continue;
      final seleccionado = nodoSeleccionado == n.id;
      final conError = nodosConError.contains(n.id);
      final activo = nodosActivos.contains(n.id);
      final color = conError ? AppColors.red : colorDeEstado(n.estado);
      final radio = seleccionado ? 30.0 : 26.0;
      final noImplementado = n.estado == EstadoNodo.noImplementado;

      if (activo) {
        // Onda expansiva: una peticion real esta pasando por este nodo AHORA
        // (eventos_pipeline via Realtime), distinto del pulso decorativo de
        // las conexiones y de la insignia roja de error.
        final radioOnda = radio + 4 + 14 * pulso;
        canvas.drawCircle(pos, radioOnda, Paint()
          ..color = AppColors.cyan.withValues(alpha: (1 - pulso) * 0.6)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5);
      }

      canvas.drawCircle(pos, radio + 6,
          Paint()..color = color.withValues(alpha: seleccionado ? 0.22 : (conError ? 0.18 : 0.10)));
      canvas.drawCircle(pos, radio, Paint()..color = AppColors.surface);

      final bordePaint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = (conError || seleccionado) ? 3 : 2;
      if (noImplementado) {
        _dibujarCirculoPunteado(canvas, pos, radio, bordePaint);
      } else {
        canvas.drawCircle(pos, radio, bordePaint);
      }

      if (conError) {
        // Insignia de alerta -- el pulso de la animacion la hace "latir"
        // para que sea imposible no notarla al abrir la pantalla.
        final escala = 1.0 + 0.08 * math.sin(pulso * 2 * math.pi);
        final centroInsignia = pos + Offset(radio * 0.72, -radio * 0.72);
        canvas.drawCircle(centroInsignia, 8 * escala, Paint()..color = AppColors.red);
        canvas.drawCircle(centroInsignia, 8 * escala, Paint()
          ..color = AppColors.surface
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
        final signo = TextPainter(
          text: const TextSpan(text: "!", style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Colors.white)),
          textDirection: TextDirection.ltr,
        )..layout();
        signo.paint(canvas, centroInsignia - Offset(signo.width / 2, signo.height / 2));
      }

      final painter = TextPainter(
        text: TextSpan(text: String.fromCharCode(n.icon.codePoint),
            style: TextStyle(fontSize: 20, fontFamily: n.icon.fontFamily, package: n.icon.fontPackage,
                color: color.withValues(alpha: noImplementado ? 0.6 : 1))),
        textDirection: TextDirection.ltr,
      )..layout();
      painter.paint(canvas, pos - Offset(painter.width / 2, painter.height / 2));

      final label = TextPainter(
        text: TextSpan(text: n.label, style: TextStyle(
            fontSize: 10, fontWeight: FontWeight.w700,
            color: noImplementado ? AppColors.textHint : AppColors.textPrimary, height: 1.1)),
        textAlign: TextAlign.center,
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: 90);
      label.paint(canvas, pos + Offset(-label.width / 2, radio + 6));
    }
  }

  void _dibujarLineaPunteada(Canvas canvas, Offset a, Offset b, Paint paint, {required double dash, required double gap}) {
    final total = (b - a).distance;
    if (total == 0) return;
    final dir = (b - a) / total;
    double recorrido = 0;
    while (recorrido < total) {
      final ini = a + dir * recorrido;
      final fin = a + dir * math.min(recorrido + dash, total);
      canvas.drawLine(ini, fin, paint);
      recorrido += dash + gap;
    }
  }

  void _dibujarCirculoPunteado(Canvas canvas, Offset centro, double radio, Paint paint) {
    const pasoAngular = 0.22; // radianes por segmento
    for (double ang = 0; ang < 2 * math.pi; ang += pasoAngular * 2) {
      final p1 = centro + Offset(math.cos(ang), math.sin(ang)) * radio;
      final p2 = centro + Offset(math.cos(ang + pasoAngular), math.sin(ang + pasoAngular)) * radio;
      canvas.drawLine(p1, p2, paint);
    }
  }

  @override
  bool shouldRepaint(covariant RedArquitecturaPainter oldDelegate) =>
      oldDelegate.pulso != pulso ||
      oldDelegate.nodoSeleccionado != nodoSeleccionado ||
      oldDelegate.nodosConError != nodosConError ||
      oldDelegate.nodosActivos != nodosActivos;
}
