import "dart:typed_data";
import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "package:file_picker/file_picker.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/catalogo_cubit.dart";
import "../cubit/catalogo_state.dart";

class CatalogoScreen extends StatefulWidget {
  const CatalogoScreen({super.key});
  @override State<CatalogoScreen> createState() => _CatalogoScreenState();
}

class _CatalogoScreenState extends State<CatalogoScreen> {
  final _skuCtrl     = TextEditingController();
  final _nombreCtrl  = TextEditingController();
  final _pesoCtrl    = TextEditingController();
  final _longCtrl    = TextEditingController();
  final _altCtrl     = TextEditingController();
  final _profCtrl    = TextEditingController();
  String _tipo       = "viga";
  bool _draco        = true;
  String _method     = "edgebreaker";
  Uint8List? _bytes;
  String? _fileName;
  final _tipos = ["viga", "marco", "mensula", "base", "travesano", "otro"];

  @override void dispose() {
    _skuCtrl.dispose(); _nombreCtrl.dispose(); _pesoCtrl.dispose();
    _longCtrl.dispose(); _altCtrl.dispose(); _profCtrl.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    final r = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ["glb", "gltf"], withData: true);
    if (r != null && r.files.single.bytes != null) setState(() { _bytes = r.files.single.bytes; _fileName = r.files.single.name; });
  }

  Future<void> _submit(BuildContext ctx) async {
    if (_skuCtrl.text.trim().isEmpty || _bytes == null) return;
    await ctx.read<CatalogoCubit>().uploadModelo(
      codigoSku: _skuCtrl.text.trim(), nombre: _nombreCtrl.text.trim(), tipo: _tipo,
      pesoMaximo: double.tryParse(_pesoCtrl.text) ?? 0,
      longitud: double.tryParse(_longCtrl.text) ?? 0,
      altura: double.tryParse(_altCtrl.text) ?? 0,
      profundidad: double.tryParse(_profCtrl.text) ?? 0,
      fileBytes: _bytes!, fileName: _fileName!, comprimirDraco: _draco, encoderMethod: _method,
    );
  }

  @override
  Widget build(BuildContext context) => BlocBuilder<CatalogoCubit, CatalogoState>(
    builder: (ctx, state) {
      final piezas   = state is CatalogoLoaded ? state.piezas : [];
      final uploading = state is CatalogoLoaded && state.uploading;
      final message   = state is CatalogoLoaded ? state.message : "";
      final success   = state is CatalogoLoaded && state.success;
      return SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text("Subir Modelo 3D al Catálogo", style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
        const SizedBox(height: 4),
        const Text("Comprime con Draco y registra la pieza en catalogo_piezas.", style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
        const SizedBox(height: 20),
        PanelCard(title: "Datos de la pieza", subtitle: "catalogo_piezas", child: Column(children: [
          ResponsiveRow(children: [_f("SKU *", _skuCtrl, "VIGA-LIG-2400"), _f("Nombre *", _nombreCtrl, "Viga Ligera 2.4m")]),
          const SizedBox(height: 12),
          ResponsiveRow(children: [_dd(), _f("Peso máx. (kg)", _pesoCtrl, "800", num: true)]),
          const SizedBox(height: 12),
          ResponsiveRow(children: [_f("Longitud (m)", _longCtrl, "2.4", num: true), _f("Altura (m)", _altCtrl, "4.0", num: true), _f("Prof. (m)", _profCtrl, "1.0", num: true)]),
        ])),
        PanelCard(title: "Archivo 3D", subtitle: ".glb o .gltf", child: Column(children: [
          GestureDetector(onTap: _pick, child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
            decoration: BoxDecoration(
              color: _bytes != null ? AppColors.indigoLight : AppColors.bg,
              border: Border.all(color: _bytes != null ? AppColors.indigo : AppColors.border, width: 2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(children: [
              Icon(_bytes != null ? Icons.check_circle : Icons.upload_file, color: _bytes != null ? AppColors.indigo : AppColors.textSecond, size: 32),
              const SizedBox(height: 8),
              Text(_bytes != null ? _fileName! : "Toca para seleccionar .glb / .gltf",
                  style: TextStyle(fontWeight: FontWeight.w600, color: _bytes != null ? AppColors.indigo : AppColors.textSecond, fontSize: 13), textAlign: TextAlign.center),
              if (_bytes != null) Text("${(_bytes!.length / 1024).toStringAsFixed(1)} KB", style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
            ]),
          )),
          const SizedBox(height: 12),
          Row(children: [
            Switch(value: _draco, onChanged: (v) => setState(() => _draco = v), activeThumbColor: AppColors.indigo),
            const SizedBox(width: 8),
            const Text("Comprimir con Draco", style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            if (_draco) ...[const SizedBox(width: 16), _chip("edgebreaker"), const SizedBox(width: 6), _chip("sequential")],
          ]),
        ])),
        if (message.isNotEmpty) Container(
          margin: const EdgeInsets.only(bottom: 12), padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: success ? AppColors.emeraldLight : AppColors.redLight,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: success ? AppColors.emerald : AppColors.red),
          ),
          child: Text(message, style: TextStyle(color: success ? AppColors.emerald : AppColors.red, fontWeight: FontWeight.w600, fontSize: 13)),
        ),
        SizedBox(width: double.infinity, child: ElevatedButton.icon(
          onPressed: uploading ? null : () => _submit(ctx),
          icon: uploading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : const Icon(Icons.cloud_upload),
          label: Text(uploading ? "Procesando..." : "Comprimir y subir al catálogo"),
          style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16), textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
        )),
        const SizedBox(height: 24),
        PanelCard(
          title: "Catálogo actual", subtitle: "${piezas.length} piezas",
          trailing: IconButton(icon: const Icon(Icons.refresh, size: 18, color: AppColors.indigo), onPressed: () => ctx.read<CatalogoCubit>().loadCatalogo()),
          child: state is CatalogoLoading ? const AppShimmer()
              : piezas.isEmpty ? const AppEmptyState(icon: Icons.inventory_2_outlined, message: "No hay piezas aún.")
              : Column(children: piezas.map((p) => Container(
                  margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
                  child: Row(children: [
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(p.codigoSku, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: AppColors.indigo)),
                      Text(p.nombre, style: const TextStyle(fontSize: 13, color: AppColors.textPrimary)),
                      Text("${p.tipo} · ${p.pesoMaximoKg} kg · ${p.longitudMetros}m x ${p.alturaMetros}m", style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
                      if (p.hasModelo) const Row(children: [Icon(Icons.check_circle, size: 12, color: AppColors.emerald), SizedBox(width: 4), Text("Modelo 3D disponible", style: TextStyle(fontSize: 10, color: AppColors.emerald, fontWeight: FontWeight.w600))]),
                    ])),
                    GestureDetector(
                      onTap: () async {
                        final ok = await showDialog<bool>(context: context, builder: (c) => AlertDialog(
                          title: const Text("Eliminar pieza"),
                          content: Text("¿Eliminar ${p.codigoSku}?"),
                          actions: [TextButton(onPressed: () => Navigator.pop(c, false), child: const Text("Cancelar")),
                            ElevatedButton(onPressed: () => Navigator.pop(c, true), style: ElevatedButton.styleFrom(backgroundColor: AppColors.red, foregroundColor: Colors.white), child: const Text("Eliminar"))],
                        ));
                        if (ok == true && ctx.mounted) ctx.read<CatalogoCubit>().deletePieza(p.codigoSku);
                      },
                      child: Container(padding: const EdgeInsets.all(6), decoration: BoxDecoration(color: AppColors.redLight, borderRadius: BorderRadius.circular(6)),
                          child: const Icon(Icons.delete_outline, size: 16, color: AppColors.red)),
                    ),
                  ]),
              )).toList()),
        ),
      ]));
    },
  );

  Widget _f(String label, TextEditingController ctrl, String hint, {bool num = false}) => Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textSecond)),
      const SizedBox(height: 4),
      TextField(controller: ctrl, keyboardType: num ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
          style: const TextStyle(fontSize: 13), decoration: InputDecoration(hintText: hint, hintStyle: const TextStyle(color: AppColors.border, fontSize: 13))),
    ],
  );

  Widget _dd() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text("Tipo", style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textSecond)),
    const SizedBox(height: 4),
    DropdownButtonFormField<String>(initialValue: _tipo, onChanged: (v) => setState(() => _tipo = v!),
        items: _tipos.map((o) => DropdownMenuItem(value: o, child: Text(o, style: const TextStyle(fontSize: 13)))).toList()),
  ]);

  Widget _chip(String m) => GestureDetector(
    onTap: () => setState(() => _method = m),
    child: AnimatedContainer(duration: const Duration(milliseconds: 150),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(color: _method == m ? AppColors.indigo : AppColors.surface, borderRadius: BorderRadius.circular(999), border: Border.all(color: _method == m ? AppColors.indigo : AppColors.border)),
      child: Text(m, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _method == m ? Colors.white : AppColors.textSecond)),
    ),
  );
}
