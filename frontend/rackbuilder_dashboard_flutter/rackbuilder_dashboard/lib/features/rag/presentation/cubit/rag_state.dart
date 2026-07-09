import "package:equatable/equatable.dart";
import "../../domain/entities/rag_resultado_entity.dart";

class RagState extends Equatable {
  final bool syncing;
  final String syncMessage;
  final bool syncSuccess;
  final bool searching;
  final List<RagResultadoEntity> resultados;
  final String searchError;

  const RagState({this.syncing = false, this.syncMessage = "", this.syncSuccess = false,
      this.searching = false, this.resultados = const [], this.searchError = ""});

  RagState copyWith({bool? syncing, String? syncMessage, bool? syncSuccess,
      bool? searching, List<RagResultadoEntity>? resultados, String? searchError}) => RagState(
    syncing: syncing ?? this.syncing,
    syncMessage: syncMessage ?? this.syncMessage,
    syncSuccess: syncSuccess ?? this.syncSuccess,
    searching: searching ?? this.searching,
    resultados: resultados ?? this.resultados,
    searchError: searchError ?? this.searchError,
  );

  @override List<Object?> get props => [syncing, syncMessage, syncSuccess, searching, resultados, searchError];
}
