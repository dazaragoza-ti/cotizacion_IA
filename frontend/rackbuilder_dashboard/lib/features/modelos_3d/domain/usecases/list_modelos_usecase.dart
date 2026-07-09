import "../entities/storage_file_entity.dart";
import "../repositories/modelos_repository.dart";

class ListModelosUsecase {
  final ModelosRepository _repo;
  const ListModelosUsecase(this._repo);
  Future<List<StorageFileEntity>> call() => _repo.listModelos();
}
