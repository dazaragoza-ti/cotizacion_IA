import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:get_it/get_it.dart';
import '../../features/dashboard/data/datasources/dashboard_remote_datasource.dart';
import '../../features/dashboard/data/repositories/dashboard_repository_impl.dart';
import '../../features/dashboard/domain/repositories/dashboard_repository.dart';
import '../../features/dashboard/domain/usecases/get_metrics_usecase.dart';
import '../../features/dashboard/presentation/cubit/dashboard_cubit.dart';
import '../../features/catalogo/data/datasources/catalogo_remote_datasource.dart';
import '../../features/catalogo/data/repositories/catalogo_repository_impl.dart';
import '../../features/catalogo/domain/repositories/catalogo_repository.dart';
import '../../features/catalogo/domain/usecases/get_catalogo_usecase.dart';
import '../../features/catalogo/domain/usecases/upload_modelo_usecase.dart';
import '../../features/catalogo/domain/usecases/delete_pieza_usecase.dart';
import '../../features/catalogo/presentation/cubit/catalogo_cubit.dart';
import '../../features/historial/data/datasources/historial_remote_datasource.dart';
import '../../features/historial/data/repositories/historial_repository_impl.dart';
import '../../features/historial/domain/repositories/historial_repository.dart';
import '../../features/historial/domain/usecases/get_historial_usecase.dart';
import '../../features/historial/domain/usecases/get_versiones_usecase.dart';
import '../../features/historial/presentation/cubit/historial_cubit.dart';
import '../../features/modelos_3d/data/datasources/modelos_remote_datasource.dart';
import '../../features/modelos_3d/data/repositories/modelos_repository_impl.dart';
import '../../features/modelos_3d/domain/repositories/modelos_repository.dart';
import '../../features/modelos_3d/domain/usecases/list_modelos_usecase.dart';
import '../../features/modelos_3d/domain/usecases/optimize_modelo_usecase.dart';
import '../../features/modelos_3d/presentation/cubit/modelos_cubit.dart';
import '../../features/alimentar_ia/data/datasources/alimentar_ia_remote_datasource.dart';
import '../../features/alimentar_ia/data/repositories/alimentar_ia_repository_impl.dart';
import '../../features/alimentar_ia/domain/repositories/alimentar_ia_repository.dart';
import '../../features/alimentar_ia/domain/usecases/listar_entradas_usecase.dart';
import '../../features/alimentar_ia/domain/usecases/crear_carpeta_usecase.dart';
import '../../features/alimentar_ia/domain/usecases/subir_archivo_usecase.dart';
import '../../features/alimentar_ia/presentation/cubit/alimentar_ia_cubit.dart';
import '../../features/estadisticas/data/datasources/estadisticas_remote_datasource.dart';
import '../../features/estadisticas/data/repositories/estadisticas_repository_impl.dart';
import '../../features/estadisticas/domain/repositories/estadisticas_repository.dart';
import '../../features/estadisticas/domain/usecases/get_top_estadisticas_usecase.dart';
import '../../features/estadisticas/domain/usecases/get_estadistica_sku_usecase.dart';
import '../../features/estadisticas/domain/usecases/get_correcciones_usecase.dart';
import '../../features/estadisticas/presentation/cubit/estadisticas_cubit.dart';
import '../../features/rag/data/datasources/rag_remote_datasource.dart';
import '../../features/rag/data/repositories/rag_repository_impl.dart';
import '../../features/rag/domain/repositories/rag_repository.dart';
import '../../features/rag/domain/usecases/buscar_rag_usecase.dart';
import '../../features/rag/domain/usecases/sincronizar_rag_usecase.dart';
import '../../features/rag/domain/usecases/get_sync_status_usecase.dart';
import '../../features/rag/presentation/cubit/rag_cubit.dart';
import '../../features/arquitectura/data/datasources/arquitectura_remote_datasource.dart';
import '../../features/arquitectura/presentation/cubit/arquitectura_cubit.dart';
import '../network/api_client.dart';

final sl = GetIt.instance;

Future<void> setupServiceLocator() async {
  // Habilita la extension de DevTools de get_it (ver que esta registrado,
  // en que scope, su estado) -- solo en debug, sin costo en produccion.
  if (kDebugMode) sl.debugEventsEnabled = true;

  // ── Core ──────────────────────────────────────────────────────────────────
  sl.registerLazySingleton(() => ApiClient.instance);

  // ── Dashboard ─────────────────────────────────────────────────────────────
  sl.registerLazySingleton<DashboardRemoteDatasource>(
      () => DashboardRemoteDatasourceImpl(sl()));
  // Registrar como implementación concreta para inyectarlo directo en el cubit
  sl.registerLazySingleton<DashboardRepositoryImpl>(
      () => DashboardRepositoryImpl(sl()));
  // También registrar como interfaz (para el use case)
  sl.registerLazySingleton<DashboardRepository>(() => sl<DashboardRepositoryImpl>());
  sl.registerLazySingleton(() => GetMetricsUsecase(sl()));
  // Pasar repo concreto al cubit para evitar el hack (as dynamic)._repo
  sl.registerFactory(() => DashboardCubit(sl(), sl<DashboardRepositoryImpl>(), sl()));

  // ── Catálogo ──────────────────────────────────────────────────────────────
  sl.registerLazySingleton<CatalogoRemoteDatasource>(
      () => CatalogoRemoteDatasourceImpl(sl()));
  sl.registerLazySingleton<CatalogoRepository>(
      () => CatalogoRepositoryImpl(sl()));
  sl.registerLazySingleton(() => GetCatalogoUsecase(sl()));
  sl.registerLazySingleton(() => UploadModeloUsecase(sl()));
  sl.registerLazySingleton(() => DeletePiezaUsecase(sl()));
  sl.registerFactory(() => CatalogoCubit(sl(), sl(), sl()));

  // ── Historial ─────────────────────────────────────────────────────────────
  sl.registerLazySingleton<HistorialRemoteDatasource>(
      () => HistorialRemoteDatasourceImpl(sl()));
  sl.registerLazySingleton<HistorialRepository>(
      () => HistorialRepositoryImpl(sl()));
  sl.registerLazySingleton(() => GetHistorialUsecase(sl()));
  sl.registerLazySingleton(() => GetVersionesUsecase(sl()));
  sl.registerFactory(() => HistorialCubit(sl(), sl()));

  // ── Modelos 3D ────────────────────────────────────────────────────────────
  sl.registerLazySingleton<ModelosRemoteDatasource>(
      () => ModelosRemoteDatasourceImpl(sl()));
  sl.registerLazySingleton<ModelosRepository>(
      () => ModelosRepositoryImpl(sl()));
  sl.registerLazySingleton(() => ListModelosUsecase(sl()));
  sl.registerLazySingleton(() => OptimizeModeloUsecase(sl()));
  sl.registerFactory(() => ModelosCubit(sl(), sl()));

  // ── Alimentar IA ──────────────────────────────────────────────────────────
  sl.registerLazySingleton<AlimentarIaRemoteDatasource>(
      () => AlimentarIaRemoteDatasourceImpl(sl()));
  sl.registerLazySingleton<AlimentarIaRepository>(
      () => AlimentarIaRepositoryImpl(sl()));
  sl.registerLazySingleton(() => ListarEntradasUsecase(sl()));
  sl.registerLazySingleton(() => CrearCarpetaUsecase(sl()));
  sl.registerLazySingleton(() => SubirArchivoUsecase(sl()));
  sl.registerFactory(() => AlimentarIaCubit(sl(), sl(), sl()));

  // -- Estadisticas (Sprint 2: aprendizaje continuo) --------------------------
  sl.registerLazySingleton<EstadisticasRemoteDatasource>(
      () => EstadisticasRemoteDatasourceImpl(sl()));
  sl.registerLazySingleton<EstadisticasRepository>(
      () => EstadisticasRepositoryImpl(sl()));
  sl.registerLazySingleton(() => GetTopEstadisticasUsecase(sl()));
  sl.registerLazySingleton(() => GetEstadisticaSkuUsecase(sl()));
  sl.registerLazySingleton(() => GetCorreccionesUsecase(sl()));
  sl.registerFactory(() => EstadisticasCubit(sl(), sl(), sl()));

  // -- RAG (busqueda semantica + sync) ----------------------------------------
  sl.registerLazySingleton<RagRemoteDatasource>(
      () => RagRemoteDatasourceImpl(sl()));
  sl.registerLazySingleton<RagRepository>(
      () => RagRepositoryImpl(sl()));
  sl.registerLazySingleton(() => BuscarRagUsecase(sl()));
  sl.registerLazySingleton(() => SincronizarRagUsecase(sl()));
  sl.registerLazySingleton(() => GetSyncStatusUsecase(sl()));
  sl.registerFactory(() => RagCubit(sl(), sl(), sl()));

  // -- Arquitectura del Sistema (fallos en vivo sobre el mapa estatico) ------
  sl.registerLazySingleton<ArquitecturaRemoteDatasource>(
      () => ArquitecturaRemoteDatasourceImpl(sl()));
  sl.registerFactory(() => ArquitecturaCubit(sl()));
}
