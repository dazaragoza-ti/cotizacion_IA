/// Constantes globales de la aplicación
class AppConstants {
  AppConstants._();

  // Precios Claude Sonnet 4.6 (USD por millón de tokens)
  static const double inputPricePerMillion  = 3.00;
  static const double outputPricePerMillion = 15.00;

  // Buckets de Supabase Storage
  static const String bucketCotizaciones  = 'cotizaciones';
  static const String bucketPrecios       = 'precios unitarios';
  static const String bucketModelos       = 'modelos';

  // Carpetas dentro de cada bucket
  static const String folderRacks         = 'Racks';
  static const String folderProductos     = 'productos';
  static const String folderModelos3D     = 'modelos 3d de racks';
  static const String folderCatalogo      = 'catalogo';
}

/// Endpoints del backend FastAPI
class ApiEndpoints {
  ApiEndpoints._();
  static const String configSupabase      = '/config/supabase';
  static const String storageFiles        = '/storage/files';
  static const String storageOptimize     = '/storage/files/optimize';
  static const String storageReplace      = '/storage/files/replace';
  static const String catalogoPiezas      = '/catalogo/piezas';
  static const String catalogoUpload      = '/catalogo/upload-modelo';
  static const String disenosHistorial    = '/disenos/historial';
  static const String disenos             = '/disenos/sesion';
  static const String storageEntradas     = '/storage/entradas';
  static const String storageCarpeta      = '/storage/carpeta';
  static const String storageSubirArchivo = '/storage/subir-archivo';
  static const String statsTop            = '/stats/top';
  static const String statsSku            = '/stats/sku';
  static const String ragSearch           = '/rag/search';
  static const String ragSync             = '/rag/sync';
  static const String ragSyncStatus       = '/rag/sync/status';
  static const String correcciones        = '/correcciones';
}
