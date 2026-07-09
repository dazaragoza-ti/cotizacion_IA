import "../repositories/alimentar_ia_repository.dart";

class CrearCarpetaUsecase {
  final AlimentarIaRepository _repo;
  const CrearCarpetaUsecase(this._repo);
  Future<void> call({required String bucket, required String folderPath}) =>
      _repo.crearCarpeta(bucket: bucket, folderPath: folderPath);
}
