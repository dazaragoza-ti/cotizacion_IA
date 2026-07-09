/// Estado de una correccion segun cuantas veces se ha repetido -- mismos
/// umbrales que app/engineering/promotion.py (5/20/50) para que la UI cuente
/// exactamente la misma historia que el backend.
enum EstadoAprendizaje { nueva, importante, candidata, permanente }

class CorreccionEntity {
  final int id;
  final String? tipoRack;
  final String? piezaAfectada;
  final String descripcionError;
  final String instruccionCorrectiva;
  final int vecesRepetida;
  final String? createdAt;

  const CorreccionEntity({
    required this.id,
    this.tipoRack,
    this.piezaAfectada,
    required this.descripcionError,
    required this.instruccionCorrectiva,
    required this.vecesRepetida,
    this.createdAt,
  });

  static const umbralImportante = 5;
  static const umbralCandidata = 20;
  static const umbralPermanente = 50;

  EstadoAprendizaje get estado {
    if (vecesRepetida >= umbralPermanente) return EstadoAprendizaje.permanente;
    if (vecesRepetida >= umbralCandidata) return EstadoAprendizaje.candidata;
    if (vecesRepetida >= umbralImportante) return EstadoAprendizaje.importante;
    return EstadoAprendizaje.nueva;
  }

  /// Cuantas repeticiones faltan para el siguiente escalon (0 si ya es permanente).
  int get faltanParaSiguiente {
    if (vecesRepetida >= umbralPermanente) return 0;
    if (vecesRepetida >= umbralCandidata) return umbralPermanente - vecesRepetida;
    if (vecesRepetida >= umbralImportante) return umbralCandidata - vecesRepetida;
    return umbralImportante - vecesRepetida;
  }

  /// Progreso 0..1 dentro del escalon actual, para una barra visual.
  double get progreso {
    if (vecesRepetida >= umbralPermanente) return 1.0;
    if (vecesRepetida >= umbralCandidata) {
      return (vecesRepetida - umbralCandidata) / (umbralPermanente - umbralCandidata);
    }
    if (vecesRepetida >= umbralImportante) {
      return (vecesRepetida - umbralImportante) / (umbralCandidata - umbralImportante);
    }
    return vecesRepetida / umbralImportante;
  }
}
