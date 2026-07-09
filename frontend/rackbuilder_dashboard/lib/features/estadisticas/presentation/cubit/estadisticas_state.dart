import "package:equatable/equatable.dart";
import "../../domain/entities/estadistica_sku_entity.dart";
import "../../domain/entities/correccion_entity.dart";

abstract class EstadisticasState extends Equatable {
  @override List<Object?> get props => [];
}

class EstadisticasInitial extends EstadisticasState {}
class EstadisticasLoading extends EstadisticasState {}

class EstadisticasLoaded extends EstadisticasState {
  final String campo;
  final List<EstadisticaSkuEntity> top;
  final EstadisticaSkuEntity? busqueda;
  final String? mensajeBusqueda;
  final List<CorreccionEntity> correcciones;
  final bool cargandoCorrecciones;
  EstadisticasLoaded({
    required this.campo,
    required this.top,
    this.busqueda,
    this.mensajeBusqueda,
    this.correcciones = const [],
    this.cargandoCorrecciones = false,
  });

  EstadisticasLoaded copyWith({
    String? campo,
    List<EstadisticaSkuEntity>? top,
    EstadisticaSkuEntity? busqueda,
    String? mensajeBusqueda,
    List<CorreccionEntity>? correcciones,
    bool? cargandoCorrecciones,
  }) => EstadisticasLoaded(
    campo: campo ?? this.campo,
    top: top ?? this.top,
    busqueda: busqueda ?? this.busqueda,
    mensajeBusqueda: mensajeBusqueda ?? this.mensajeBusqueda,
    correcciones: correcciones ?? this.correcciones,
    cargandoCorrecciones: cargandoCorrecciones ?? this.cargandoCorrecciones,
  );

  @override List<Object?> get props =>
      [campo, top, busqueda, mensajeBusqueda, correcciones, cargandoCorrecciones];
}

class EstadisticasError extends EstadisticasState {
  final String error;
  EstadisticasError(this.error);
  @override List<Object?> get props => [error];
}
