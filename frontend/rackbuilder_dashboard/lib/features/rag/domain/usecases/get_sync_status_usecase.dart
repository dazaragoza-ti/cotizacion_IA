import "../repositories/rag_repository.dart";

class GetSyncStatusUsecase {
  final RagRepository _repo;
  const GetSyncStatusUsecase(this._repo);
  Future<bool> call() => _repo.syncEnProgreso();
}
