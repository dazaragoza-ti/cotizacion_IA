import "../repositories/modelos_repository.dart";

class OptimizeModeloUsecase {
  final ModelosRepository _repo;
  const OptimizeModeloUsecase(this._repo);
  Future<Map<String, dynamic>> call(String bucket, String path) =>
      _repo.optimizeModelo(bucket, path);
}
