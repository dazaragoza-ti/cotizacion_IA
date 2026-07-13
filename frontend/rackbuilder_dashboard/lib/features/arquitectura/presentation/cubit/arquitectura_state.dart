import "../../domain/error_sistema.dart";

/// Estado simple (no maquina de estados con sealed classes) porque el mapa
/// de arquitectura es contenido estatico -- los errores son una capa de
/// datos en vivo que se superpone encima, no reemplazan la pantalla si
/// fallan al cargar.
class ArquitecturaState {
  final List<ErrorSistema> errores;
  final bool cargando;
  final Map<String, dynamic> metricas;

  const ArquitecturaState({this.errores = const [], this.cargando = false, this.metricas = const {}});

  ArquitecturaState copyWith({List<ErrorSistema>? errores, bool? cargando, Map<String, dynamic>? metricas}) => ArquitecturaState(
    errores: errores ?? this.errores,
    cargando: cargando ?? this.cargando,
    metricas: metricas ?? this.metricas,
  );

  Set<String> get nodosConError => errores.map((e) => e.componente).toSet();

  /// Metrica en vivo de un nodo puntual, o {} si no hay ninguna para ese id.
  Map<String, dynamic> metricaDe(String nodoId) =>
      (metricas[nodoId] as Map<String, dynamic>?) ?? const {};
}
