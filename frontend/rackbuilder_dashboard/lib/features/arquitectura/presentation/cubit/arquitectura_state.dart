import "../../domain/error_sistema.dart";

/// Estado simple (no maquina de estados con sealed classes) porque el mapa
/// de arquitectura es contenido estatico -- los errores son una capa de
/// datos en vivo que se superpone encima, no reemplazan la pantalla si
/// fallan al cargar.
class ArquitecturaState {
  final List<ErrorSistema> errores;
  final bool cargando;
  final Map<String, dynamic> metricas;
  final bool enVivoConectado;
  final Map<String, String> pasosEnCurso;
  final String? mensajeError;

  const ArquitecturaState({
    this.errores = const [],
    this.cargando = false,
    this.metricas = const {},
    this.enVivoConectado = false,
    this.pasosEnCurso = const {},
    this.mensajeError,
  });

  ArquitecturaState copyWith({
    List<ErrorSistema>? errores,
    bool? cargando,
    Map<String, dynamic>? metricas,
    bool? enVivoConectado,
    Map<String, String>? pasosEnCurso,
    String? mensajeError,
    bool clearMensaje = false,
  }) =>
      ArquitecturaState(
        errores: errores ?? this.errores,
        cargando: cargando ?? this.cargando,
        metricas: metricas ?? this.metricas,
        enVivoConectado: enVivoConectado ?? this.enVivoConectado,
        pasosEnCurso: pasosEnCurso ?? this.pasosEnCurso,
        mensajeError: clearMensaje ? null : (mensajeError ?? this.mensajeError),
      );

  Set<String> get nodosConError => errores.map((e) => e.componente).toSet();

  /// Metrica en vivo de un nodo puntual, o {} si no hay ninguna para ese id.
  Map<String, dynamic> metricaDe(String nodoId) =>
      (metricas[nodoId] as Map<String, dynamic>?) ?? const {};

  /// Nodos por los que esta pasando AHORA MISMO una solicitud real en curso
  /// (a diferencia de nodosConError/metricas, que son agregados historicos).
  Set<String> get nodosActivos => pasosEnCurso.keys.toSet();
}
