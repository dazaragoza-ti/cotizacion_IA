import "../repositories/rag_repository.dart";
class SincronizarRagUsecase {
  final RagRepository _repo;
  const SincronizarRagUsecase(this._repo);
  Future<void> call() => _repo.sincronizar();
}
