import "../../../../core/constants/app_constants.dart";

enum StorageBucket { cotizaciones, preciosUnitarios, modelosTerminados }

extension StorageBucketX on StorageBucket {
  String get key => switch (this) {
    StorageBucket.cotizaciones => AppConstants.bucketCotizaciones,
    StorageBucket.preciosUnitarios => AppConstants.bucketPrecios,
    StorageBucket.modelosTerminados => AppConstants.bucketModelos,
  };

  String get label => switch (this) {
    StorageBucket.cotizaciones => "Cotizaciones",
    StorageBucket.preciosUnitarios => "Precios Unitarios",
    StorageBucket.modelosTerminados => "Racks de Ejemplo",
  };

  /// Carpeta raiz dentro del bucket. "modelos" tambien contiene
  /// "modelos 3d de racks" (administrada por el Compresor Draco CAD) --
  /// esto evita mezclarla con los racks de ejemplo terminados.
  List<String> get rootPath => switch (this) {
    StorageBucket.modelosTerminados => const ["modelos 3d terminados"],
    _ => const [],
  };
}
