import "../repositories/catalogo_repository.dart";
class DeletePiezaUsecase {
  final CatalogoRepository _repo;
  const DeletePiezaUsecase(this._repo);
  Future<void> call(String sku) => _repo.deletePieza(sku);
}
