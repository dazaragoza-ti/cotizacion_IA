import 'package:equatable/equatable.dart';

class MetricsEntity extends Equatable {
  final int proyectos;
  final int inputTokens;
  final int outputTokens;
  final int totalTokens;
  final double avgTokensPerProject;
  final double estimatedCost;

  const MetricsEntity({required this.proyectos, required this.inputTokens,
      required this.outputTokens, required this.totalTokens,
      required this.avgTokensPerProject, required this.estimatedCost});

  factory MetricsEntity.empty() => const MetricsEntity(
      proyectos: 0, inputTokens: 0, outputTokens: 0,
      totalTokens: 0, avgTokensPerProject: 0, estimatedCost: 0);

  @override List<Object?> get props =>
      [proyectos, inputTokens, outputTokens, totalTokens, estimatedCost];
}
