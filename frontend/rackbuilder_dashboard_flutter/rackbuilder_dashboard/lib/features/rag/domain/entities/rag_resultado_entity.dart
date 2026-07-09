class RagResultadoEntity {
  final String tipo;
  final String fuente;
  final String contenido;
  final double similarity;

  const RagResultadoEntity({required this.tipo, required this.fuente, required this.contenido, required this.similarity});
}
