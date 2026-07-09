import "../entities/pieza_entity.dart";
import "../repositories/catalogo_repository.dart";
class GetCatalogoUsecase {
  final CatalogoRepository _repo;
  const GetCatalogoUsecase(this._repo);
  Future<List<PiezaEntity>> call() => _repo.getPiezas();
}
