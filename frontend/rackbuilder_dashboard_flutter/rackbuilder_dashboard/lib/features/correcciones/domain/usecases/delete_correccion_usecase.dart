import "../repositories/correcciones_repository.dart";
class DeleteCorreccionUsecase {
  final CorreccionesRepository _repo;
  const DeleteCorreccionUsecase(this._repo);
  Future<void> call(int correccionId) => _repo.deleteCorreccion(correccionId);
}
