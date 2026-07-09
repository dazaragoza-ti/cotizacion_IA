class DisenoEntity {
  final String id;
  final String vendedorId;
  final String sessionId;
  final String solicitudOriginal;
  final int versionActual;
  final List<String> historialComentarios;
  final int inputTokens;
  final int outputTokens;
  final String createdAt;

  const DisenoEntity({required this.id, required this.vendedorId, required this.sessionId,
      required this.solicitudOriginal, required this.versionActual,
      required this.historialComentarios, required this.inputTokens,
      required this.outputTokens, required this.createdAt});

  int get totalTokens => inputTokens + outputTokens;
}
