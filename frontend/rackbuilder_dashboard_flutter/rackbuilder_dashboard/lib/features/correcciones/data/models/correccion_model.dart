import "../../domain/entities/correccion_entity.dart";
class CorreccionModel extends CorreccionEntity {
  const CorreccionModel({required super.id, required super.sessionId, super.tipoRack,
      super.proyectoClave, required super.descripcionError, required super.instruccionCorrectiva,
      required super.vecesRepetida, required super.origen, required super.createdAt});

  factory CorreccionModel.fromJson(Map<String, dynamic> j) => CorreccionModel(
    id: (j["id"] as num?)?.toInt() ?? 0,
    sessionId: j["session_id"] as String? ?? "",
    tipoRack: j["tipo_rack"] as String?,
    proyectoClave: j["proyecto_clave"] as String?,
    descripcionError: j["descripcion_error"] as String? ?? "",
    instruccionCorrectiva: j["instruccion_correctiva"] as String? ?? "",
    vecesRepetida: (j["veces_repetida"] as num?)?.toInt() ?? 1,
    origen: j["origen"] as String? ?? "manual",
    createdAt: j["created_at"] as String? ?? "",
  );
}
