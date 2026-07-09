import "../../domain/entities/metrics_entity.dart";
import "../../../../core/constants/app_constants.dart";

class MetricsModel extends MetricsEntity {
  const MetricsModel({required super.proyectos, required super.inputTokens,
      required super.outputTokens, required super.totalTokens,
      required super.avgTokensPerProject, required super.estimatedCost});

  factory MetricsModel.fromRows(List<dynamic> rows) {
    final input  = rows.fold<int>(0, (s, r) => s + ((r["input_tokens"]  as num?)?.toInt() ?? 0));
    final output = rows.fold<int>(0, (s, r) => s + ((r["output_tokens"] as num?)?.toInt() ?? 0));
    final total  = input + output;
    final cost   = (input  / 1000000 * AppConstants.inputPricePerMillion)
                 + (output / 1000000 * AppConstants.outputPricePerMillion);
    return MetricsModel(proyectos: rows.length, inputTokens: input,
        outputTokens: output, totalTokens: total,
        avgTokensPerProject: rows.isNotEmpty ? total / rows.length : 0,
        estimatedCost: cost);
  }
}
