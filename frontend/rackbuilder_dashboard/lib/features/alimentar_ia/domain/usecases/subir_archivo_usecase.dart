import "../repositories/alimentar_ia_repository.dart";

class SubirArchivoUsecase {
  final AlimentarIaRepository _repo;
  const SubirArchivoUsecase(this._repo);
  Future<String> call({
    required String bucket,
    required String folder,
    required List<int> fileBytes,
    required String fileName,
  }) => _repo.subirArchivo(bucket: bucket, folder: folder, fileBytes: fileBytes, fileName: fileName);
}
