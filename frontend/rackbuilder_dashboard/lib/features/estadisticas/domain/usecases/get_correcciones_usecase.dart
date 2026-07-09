import "../entities/correccion_entity.dart";
import "../repositories/estadisticas_repository.dart";

class GetCorreccionesUsecase {
  final EstadisticasRepository _repo;
  const GetCorreccionesUsecase(this._repo);
  Future<List<CorreccionEntity>> call({int limit = 100}) => _repo.getCorrecciones(limit: limit);
}
