class CorreccionEntity {
  final int id;
  final String sessionId;
  final String? tipoRack;
  final String? proyectoClave;
  final String descripcionError;
  final String instruccionCorrectiva;
  final int vecesRepetida;
  final String origen; // "manual" | "automatico"
  final String createdAt;

  const CorreccionEntity({required this.id, required this.sessionId, this.tipoRack,
      this.proyectoClave, required this.descripcionError, required this.instruccionCorrectiva,
      required this.vecesRepetida, required this.origen, required this.createdAt});

  bool get esAutomatica => origen == "automatico";
}
