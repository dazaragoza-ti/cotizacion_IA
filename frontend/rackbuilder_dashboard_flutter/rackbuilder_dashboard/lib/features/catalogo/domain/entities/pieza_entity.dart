class PiezaEntity {
  final String codigoSku;
  final String nombre;
  final String tipo;
  final double pesoMaximoKg;
  final double longitudMetros;
  final double alturaMetros;
  final double profundidadMetros;
  final String? urlModeloGlb;

  const PiezaEntity({required this.codigoSku, required this.nombre, required this.tipo,
      required this.pesoMaximoKg, required this.longitudMetros, required this.alturaMetros,
      required this.profundidadMetros, this.urlModeloGlb});

  bool get hasModelo => urlModeloGlb != null && urlModeloGlb!.isNotEmpty;
}
