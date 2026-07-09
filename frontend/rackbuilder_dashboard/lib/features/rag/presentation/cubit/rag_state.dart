import "package:equatable/equatable.dart";
import "../../domain/entities/rag_resultado_entity.dart";

abstract class RagState extends Equatable {
  @override List<Object?> get props => [];
}

class RagInitial extends RagState {}
class RagBuscando extends RagState {}

class RagResultados extends RagState {
  final String query;
  final List<RagResultadoEntity> resultados;
  final bool sincronizando;
  final String? mensaje;
  RagResultados({required this.query, required this.resultados, this.sincronizando = false, this.mensaje});
  @override List<Object?> get props => [query, resultados, sincronizando, mensaje];
}

class RagError extends RagState {
  final String error;
  RagError(this.error);
  @override List<Object?> get props => [error];
}
