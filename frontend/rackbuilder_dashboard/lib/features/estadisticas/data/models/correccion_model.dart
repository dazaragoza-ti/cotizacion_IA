import "../../domain/entities/correccion_entity.dart";

class CorreccionModel extends CorreccionEntity {
  const CorreccionModel({
    required super.id,
    super.tipoRack,
    super.piezaAfectada,
    required super.descripcionError,
    required super.instruccionCorrectiva,
    required super.vecesRepetida,
    super.createdAt,
  });

  factory CorreccionModel.fromJson(Map<String, dynamic> j) => CorreccionModel(
    id: (j["id"] as num?)?.toInt() ?? 0,
    tipoRack: j["tipo_rack"] as String?,
    piezaAfectada: j["pieza_afectada"] as String?,
    descripcionError: j["descripcion_error"] as String? ?? "",
    instruccionCorrectiva: j["instruccion_correctiva"] as String? ?? "",
    vecesRepetida: (j["veces_repetida"] as num?)?.toInt() ?? 1,
    createdAt: j["created_at"] as String?,
  );
}
