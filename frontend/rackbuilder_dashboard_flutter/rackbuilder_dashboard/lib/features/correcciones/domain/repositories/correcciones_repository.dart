import "../entities/correccion_entity.dart";
abstract class CorreccionesRepository {
  Future<List<CorreccionEntity>> getCorrecciones({int limit});
  Future<void> deleteCorreccion(int correccionId);
}
