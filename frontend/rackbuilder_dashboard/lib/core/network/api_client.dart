import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../constants/app_constants.dart';

/// Cliente HTTP centralizado con Dio — interceptores, timeouts y manejo de errores
class ApiClient {
  static ApiClient? _instance;
  static ApiClient get instance => _instance ??= ApiClient._();
  ApiClient._() { _init(); }

  late final Dio dio;

  void _init() {
    final baseUrl = dotenv.env['BACKEND_URL'] ?? 'http://localhost:8000';
    dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 60),
      headers: {'Content-Type': 'application/json'},
    ));

    dio.interceptors.addAll([
      _RetryInterceptor(dio),
      LogInterceptor(requestBody: false, responseBody: false),
      _ErrorInterceptor(),
    ]);
  }

  String get baseUrl => dio.options.baseUrl;

  /// Health check del backend FastAPI (`GET /`).
  /// Lanza [DioException] si el servidor no responde o no está sano.
  Future<bool> checkHealth() async {
    final res = await dio.get(ApiEndpoints.health);
    final status = res.data is Map ? res.data['status'] : null;
    return res.statusCode == 200 && (status == null || status == 'healthy');
  }
}

/// Reintenta con backoff ante errores transitorios (timeouts, sin conexion,
/// 5xx del backend) -- antes cualquier caida momentanea de red terminaba
/// directo en un DashboardError visible al usuario, sin ningun reintento.
class _RetryInterceptor extends Interceptor {
  final Dio _dio;
  static const int maxReintentos = 2;
  _RetryInterceptor(this._dio);

  bool _esReintentable(DioException err) {
    const tiposTransitorios = {
      DioExceptionType.connectionTimeout,
      DioExceptionType.receiveTimeout,
      DioExceptionType.sendTimeout,
      DioExceptionType.connectionError,
    };
    if (tiposTransitorios.contains(err.type)) return true;
    final status = err.response?.statusCode;
    return status != null && status >= 500;
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    final intento = (err.requestOptions.extra['_retryIntento'] as int?) ?? 0;
    if (!_esReintentable(err) || intento >= maxReintentos) {
      handler.next(err);
      return;
    }
    await Future.delayed(Duration(milliseconds: 400 * (intento + 1)));
    final opciones = err.requestOptions;
    opciones.extra['_retryIntento'] = intento + 1;
    try {
      final respuesta = await _dio.fetch(opciones);
      handler.resolve(respuesta);
    } catch (_) {
      handler.next(err);
    }
  }
}

class _ErrorInterceptor extends Interceptor {
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final msg = err.response?.data?['detail'] ?? err.message ?? 'Error desconocido';
    handler.next(DioException(
      requestOptions: err.requestOptions,
      response: err.response,
      error: msg,
      type: err.type,
    ));
  }
}
