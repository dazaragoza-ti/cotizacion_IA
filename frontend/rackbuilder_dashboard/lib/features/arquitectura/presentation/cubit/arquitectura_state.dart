import "../../domain/error_sistema.dart";

/// Estado simple (no maquina de estados con sealed classes) porque el mapa
/// de arquitectura es contenido estatico -- los errores son una capa de
/// datos en vivo que se superpone encima, no reemplazan la pantalla si
/// fallan al cargar.
class ArquitecturaState {
  final List<ErrorSistema> errores;
  final bool cargando;

  const ArquitecturaState({this.errores = const [], this.cargando = false});

  ArquitecturaState copyWith({List<ErrorSistema>? errores, bool? cargando}) => ArquitecturaState(
    errores: errores ?? this.errores,
    cargando: cargando ?? this.cargando,
  );

  Set<String> get nodosConError => errores.map((e) => e.componente).toSet();
}
