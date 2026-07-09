import "../../../../core/constants/app_constants.dart";

enum StorageBucket { cotizaciones, preciosUnitarios }

extension StorageBucketX on StorageBucket {
  String get key => switch (this) {
    StorageBucket.cotizaciones => AppConstants.bucketCotizaciones,
    StorageBucket.preciosUnitarios => AppConstants.bucketPrecios,
  };

  String get label => switch (this) {
    StorageBucket.cotizaciones => "Cotizaciones",
    StorageBucket.preciosUnitarios => "Precios Unitarios",
  };
}
