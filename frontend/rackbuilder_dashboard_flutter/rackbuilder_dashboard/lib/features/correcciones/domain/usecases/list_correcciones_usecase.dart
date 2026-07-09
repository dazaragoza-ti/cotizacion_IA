import "../entities/correccion_entity.dart";
import "../repositories/correcciones_repository.dart";
class ListCorreccionesUsecase {
  final CorreccionesRepository _repo;
  const ListCorreccionesUsecase(this._repo);
  Future<List<CorreccionEntity>> call({int limit = 100}) => _repo.getCorrecciones(limit: limit);
}
