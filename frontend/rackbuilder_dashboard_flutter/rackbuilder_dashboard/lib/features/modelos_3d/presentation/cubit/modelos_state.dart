import "package:equatable/equatable.dart";
import "../../domain/entities/storage_file_entity.dart";

abstract class ModelosState extends Equatable {
  @override List<Object?> get props => [];
}
class ModelosInitial  extends ModelosState {}
class ModelosLoading  extends ModelosState {}
class ModelosLoaded   extends ModelosState {
  final List<StorageFileEntity> modelos;
  final String? optimizingPath;
  final String message;
  ModelosLoaded({required this.modelos, this.optimizingPath, this.message = ""});
  @override List<Object?> get props => [modelos, optimizingPath, message];
}
class ModelosError extends ModelosState {
  final String error;
  ModelosError(this.error);
  @override List<Object?> get props => [error];
}
