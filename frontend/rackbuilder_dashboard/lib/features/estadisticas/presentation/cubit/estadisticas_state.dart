import "package:equatable/equatable.dart";
import "../../domain/entities/estadistica_sku_entity.dart";

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
  EstadisticasLoaded({
    required this.campo,
    required this.top,
    this.busqueda,
    this.mensajeBusqueda,
  });
  @override List<Object?> get props => [campo, top, busqueda, mensajeBusqueda];
}

class EstadisticasError extends EstadisticasState {
  final String error;
  EstadisticasError(this.error);
  @override List<Object?> get props => [error];
}
