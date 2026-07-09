import "package:equatable/equatable.dart";
import "../../domain/entities/pieza_entity.dart";

abstract class CatalogoState extends Equatable {
  @override List<Object?> get props => [];
}
class CatalogoInitial  extends CatalogoState {}
class CatalogoLoading  extends CatalogoState {}
class CatalogoLoaded   extends CatalogoState {
  final List<PiezaEntity> piezas;
  final bool uploading;
  final String message;
  final bool success;
  CatalogoLoaded({required this.piezas, this.uploading = false, this.message = "", this.success = false});
  @override List<Object?> get props => [piezas, uploading, message, success];
}
class CatalogoError extends CatalogoState {
  final String error;
  CatalogoError(this.error);
  @override List<Object?> get props => [error];
}
