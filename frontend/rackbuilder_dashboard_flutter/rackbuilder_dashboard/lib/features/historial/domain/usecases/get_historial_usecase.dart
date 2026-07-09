import "../entities/diseno_entity.dart";
import "../repositories/historial_repository.dart";
class GetHistorialUsecase {
  final HistorialRepository _repo;
  const GetHistorialUsecase(this._repo);
  Future<List<DisenoEntity>> call({int limit = 50}) => _repo.getHistorial(limit: limit);
}
