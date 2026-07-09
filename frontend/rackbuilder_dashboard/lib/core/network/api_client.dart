import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

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
      LogInterceptor(requestBody: false, responseBody: false),
      _ErrorInterceptor(),
    ]);
  }

  String get baseUrl => dio.options.baseUrl;
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
