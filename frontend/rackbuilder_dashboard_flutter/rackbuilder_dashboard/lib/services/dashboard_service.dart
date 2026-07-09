import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/models.dart';

class DashboardService {
  static DashboardService? _instance;
  static DashboardService get instance => _instance ??= DashboardService._();
  DashboardService._();

  SupabaseClient? _supabase;
  String _supabaseUrl = 'https://ltetbljizxngcwszyzmn.supabase.co';
  String _supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0ZXRibGppenhuZ2N3c3p5em1uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIzMTc0MzMsImV4cCI6MjA5Nzg5MzQzM30.ThZMYsYyHv0eC2PxSV-NmqJySwSY3Y32tK8QrHEivaw';
  String backendUrl = 'http://localhost:8000';

  bool get isConnected => _supabase != null;

  void setConnection(String url, String key) {
    final trimUrl = url.trim();
    final trimKey = key.trim();
    if (trimUrl.isEmpty || trimKey.isEmpty) {
      throw Exception('Falta la URL o la anon key de Supabase');
    }
    if (_supabase != null && _supabaseUrl == trimUrl && _supabaseKey == trimKey) return;
    _supabaseUrl = trimUrl;
    _supabaseKey = trimKey;
    _supabase = SupabaseClient(trimUrl, trimKey);
  }

  /// Pide credenciales al backend (las lee del .env del servidor)
  Future<Map<String, String>?> fetchConfigFromBackend() async {
    try {
      final res = await http.get(Uri.parse('$backendUrl/config/supabase'));
      if (res.statusCode != 200) return null;
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      final url = data['url'] as String?;
      final key = data['key'] as String?;
      if (url != null && key != null && url.isNotEmpty && key.isNotEmpty) {
        return {'url': url, 'key': key};
      }
    } catch (_) {}
    return null;
  }

  Future<DashboardMetrics> getMetrics() async {
    if (_supabase == null) throw Exception('Sin conexión a Supabase');
    final res = await _supabase!
        .from('disenos_racks')
        .select('input_tokens, output_tokens');

    final rows = (res as List<dynamic>);
    final input = rows.fold<int>(0, (s, r) => s + ((r['input_tokens'] as num?)?.toInt() ?? 0));
    final output = rows.fold<int>(0, (s, r) => s + ((r['output_tokens'] as num?)?.toInt() ?? 0));
    final total = input + output;
    // Claude Sonnet 4.6: $3.00 / 1M input tokens, $15.00 / 1M output tokens
    const double inputPricePerMillion  = 3.00;
    const double outputPricePerMillion = 15.00;
    final estimatedCost = (input  / 1000000 * inputPricePerMillion)
                        + (output / 1000000 * outputPricePerMillion);

    return DashboardMetrics(
      proyectos: rows.length,
      inputTokens: input,
      outputTokens: output,
      totalTokens: total,
      avgTokensPerProject: rows.isNotEmpty ? total / rows.length : 0,
      estimatedCost: estimatedCost,
    );
  }

  Future<List<StorageFileItem>> listStorageFiles(String bucket, String folder) async {
    if (bucket.isEmpty) return [];
    final uri = Uri.parse('$backendUrl/storage/files').replace(
      queryParameters: {'bucket': bucket, 'folder': folder},
    );
    final res = await http.get(uri);
    if (res.statusCode != 200) throw Exception(res.body);
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    final files = (data['files'] as List<dynamic>? ?? [])
        .map((f) => StorageFileItem.fromJson(f as Map<String, dynamic>))
        .where((f) => f.name.toLowerCase().endsWith('.glb') || f.name.toLowerCase().endsWith('.gltf'))
        .toList()
      ..sort((a, b) => a.name.compareTo(b.name));
    return files;
  }

  Future<Map<String, dynamic>> optimizeStorageFile(String bucket, String path) async {
    final req = http.MultipartRequest('POST', Uri.parse('$backendUrl/storage/files/optimize'))
      ..fields['bucket'] = bucket
      ..fields['path'] = path;
    final streamed = await req.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) throw Exception(body);
    return jsonDecode(body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> replaceStorageFile(String bucket, String path, List<int> bytes, String filename) async {
    final req = http.MultipartRequest('POST', Uri.parse('$backendUrl/storage/files/replace'))
      ..fields['bucket'] = bucket
      ..fields['path'] = path
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final streamed = await req.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) throw Exception(body);
    return jsonDecode(body) as Map<String, dynamic>;
  }

  /// Lista todas las piezas del catálogo
  Future<List<dynamic>> fetchCatalogo() async {
    final res = await http.get(Uri.parse('$backendUrl/catalogo/piezas'));
    if (res.statusCode != 200) throw Exception(res.body);
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return data['piezas'] as List<dynamic>? ?? [];
  }

  /// Sube modelo, lo comprime con Draco y registra en catalogo_piezas
  Future<Map<String, dynamic>> uploadModeloCatalogo({
    required String codigoSku,
    required String nombre,
    required String tipo,
    required double pesoMaximo,
    required double longitud,
    required double altura,
    required double profundidad,
    required List<int> fileBytes,
    required String fileName,
    required bool comprimirDraco,
    required String encoderMethod,
  }) async {
    final req = http.MultipartRequest('POST', Uri.parse('$backendUrl/catalogo/upload-modelo'))
      ..fields['codigo_sku']               = codigoSku
      ..fields['nombre']                   = nombre
      ..fields['tipo']                     = tipo
      ..fields['peso_maximo_soportado_kg'] = pesoMaximo.toString()
      ..fields['longitud_metros']          = longitud.toString()
      ..fields['altura_metros']            = altura.toString()
      ..fields['profundidad_metros']       = profundidad.toString()
      ..fields['comprimir_draco']          = comprimirDraco.toString()
      ..fields['encoder_method']           = encoderMethod
      ..files.add(http.MultipartFile.fromBytes('file', fileBytes, filename: fileName));

    final streamed = await req.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) throw Exception(body);
    return jsonDecode(body) as Map<String, dynamic>;
  }


  Future<List<dynamic>> fetchHistorial({int limit = 50}) async {
    final res = await http.get(Uri.parse('$backendUrl/disenos/historial?limit=$limit'));
    if (res.statusCode != 200) throw Exception(res.body);
    return (jsonDecode(res.body) as Map<String, dynamic>)['disenos'] as List<dynamic>;
  }

  Future<List<dynamic>> fetchVersionesSesion(String sessionId) async {
    final res = await http.get(Uri.parse('$backendUrl/disenos/sesion/$sessionId'));
    if (res.statusCode != 200) throw Exception(res.body);
    return (jsonDecode(res.body) as Map<String, dynamic>)['versiones'] as List<dynamic>;
  }

  Future<void> eliminarPiezaCatalogo(String codigoSku) async {
    final res = await http.delete(Uri.parse('$backendUrl/catalogo/piezas/$codigoSku'));
    if (res.statusCode != 200) throw Exception(res.body);
  }

}