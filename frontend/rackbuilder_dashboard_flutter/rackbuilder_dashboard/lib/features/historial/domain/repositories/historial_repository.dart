import "../entities/diseno_entity.dart";
abstract class HistorialRepository {
  Future<List<DisenoEntity>> getHistorial({int limit});
  Future<List<DisenoEntity>> getVersionesSesion(String sessionId);
}
