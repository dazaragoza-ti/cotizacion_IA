import "../entities/storage_entradas_entity.dart";
import "../repositories/alimentar_ia_repository.dart";

class ListarEntradasUsecase {
  final AlimentarIaRepository _repo;
  const ListarEntradasUsecase(this._repo);
  Future<StorageEntradasEntity> call({required String bucket, required String folder}) =>
      _repo.listarEntradas(bucket: bucket, folder: folder);
}
