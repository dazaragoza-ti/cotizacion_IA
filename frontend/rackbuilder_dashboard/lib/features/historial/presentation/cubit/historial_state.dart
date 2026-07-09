import "package:equatable/equatable.dart";
import "../../domain/entities/diseno_entity.dart";
abstract class HistorialState extends Equatable {
  @override List<Object?> get props => [];
}
class HistorialInitial extends HistorialState {}
class HistorialLoading extends HistorialState {}
class HistorialLoaded  extends HistorialState {
  final List<DisenoEntity> disenos;
  final String? selectedSessionId;
  final List<DisenoEntity> versiones;
  final bool loadingVersiones;
  HistorialLoaded({required this.disenos, this.selectedSessionId, this.versiones = const [], this.loadingVersiones = false});
  @override List<Object?> get props => [disenos, selectedSessionId, versiones, loadingVersiones];
}
class HistorialError extends HistorialState {
  final String error;
  HistorialError(this.error);
  @override List<Object?> get props => [error];
}
