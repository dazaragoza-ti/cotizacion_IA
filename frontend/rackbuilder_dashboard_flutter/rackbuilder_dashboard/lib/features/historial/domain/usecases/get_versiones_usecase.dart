import "../entities/diseno_entity.dart";
import "../repositories/historial_repository.dart";
class GetVersionesUsecase {
  final HistorialRepository _repo;
  const GetVersionesUsecase(this._repo);
  Future<List<DisenoEntity>> call(String sessionId) => _repo.getVersionesSesion(sessionId);
}
