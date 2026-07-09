class ErrorSistema {
  final String id;
  final String componente;
  final String mensaje;
  final String? endpoint;
  final String createdAt;

  const ErrorSistema({
    required this.id,
    required this.componente,
    required this.mensaje,
    this.endpoint,
    required this.createdAt,
  });

  factory ErrorSistema.fromJson(Map<String, dynamic> j) => ErrorSistema(
    id: j["id"]?.toString() ?? "",
    componente: j["componente"] as String? ?? "fastapi",
    mensaje: j["mensaje"] as String? ?? "",
    endpoint: j["endpoint"] as String?,
    createdAt: j["created_at"] as String? ?? "",
  );
}
