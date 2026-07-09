import "package:equatable/equatable.dart";
import "../../domain/entities/correccion_entity.dart";
abstract class CorreccionesState extends Equatable {
  @override List<Object?> get props => [];
}
class CorreccionesInitial extends CorreccionesState {}
class CorreccionesLoading extends CorreccionesState {}
class CorreccionesLoaded  extends CorreccionesState {
  final List<CorreccionEntity> correcciones;
  final int? eliminandoId;
  CorreccionesLoaded({required this.correcciones, this.eliminandoId});
  @override List<Object?> get props => [correcciones, eliminandoId];
}
class CorreccionesError extends CorreccionesState {
  final String error;
  CorreccionesError(this.error);
  @override List<Object?> get props => [error];
}
