import "package:equatable/equatable.dart";
import "../../domain/entities/storage_bucket.dart";
import "../../domain/entities/storage_folder_entity.dart";
import "../../domain/entities/storage_file_entity.dart";

abstract class AlimentarIaState extends Equatable {
  @override List<Object?> get props => [];
}

class AlimentarIaInitial extends AlimentarIaState {}
class AlimentarIaLoading extends AlimentarIaState {}

class AlimentarIaLoaded extends AlimentarIaState {
  final StorageBucket bucket;
  final List<String> pathSegments;
  final List<StorageFolderEntity> carpetas;
  final List<StorageFileEntity> archivos;
  final bool uploading;
  final bool creandoCarpeta;
  final String message;
  final bool success;

  AlimentarIaLoaded({
    required this.bucket,
    required this.pathSegments,
    required this.carpetas,
    required this.archivos,
    this.uploading = false,
    this.creandoCarpeta = false,
    this.message = "",
    this.success = false,
  });

  String get folderPath => pathSegments.join("/");

  AlimentarIaLoaded copyWith({
    StorageBucket? bucket,
    List<String>? pathSegments,
    List<StorageFolderEntity>? carpetas,
    List<StorageFileEntity>? archivos,
    bool? uploading,
    bool? creandoCarpeta,
    String? message,
    bool? success,
  }) => AlimentarIaLoaded(
    bucket: bucket ?? this.bucket,
    pathSegments: pathSegments ?? this.pathSegments,
    carpetas: carpetas ?? this.carpetas,
    archivos: archivos ?? this.archivos,
    uploading: uploading ?? false,
    creandoCarpeta: creandoCarpeta ?? false,
    message: message ?? "",
    success: success ?? false,
  );

  @override List<Object?> get props =>
      [bucket, pathSegments, carpetas, archivos, uploading, creandoCarpeta, message, success];
}

class AlimentarIaError extends AlimentarIaState {
  final String error;
  AlimentarIaError(this.error);
  @override List<Object?> get props => [error];
}
