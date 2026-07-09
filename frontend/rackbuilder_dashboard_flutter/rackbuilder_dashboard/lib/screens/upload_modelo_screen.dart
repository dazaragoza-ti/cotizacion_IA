import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../services/dashboard_service.dart';
import '../widgets/widgets.dart';

class UploadModeloScreen extends StatefulWidget {
  const UploadModeloScreen({super.key});

  @override
  State<UploadModeloScreen> createState() => _UploadModeloScreenState();
}

class _UploadModeloScreenState extends State<UploadModeloScreen> {
  final _svc = DashboardService.instance;

  // Form fields
  final _skuCtrl        = TextEditingController();
  final _nombreCtrl     = TextEditingController();
  final _pesoCtrl       = TextEditingController();
  final _longitudCtrl   = TextEditingController();
  final _alturaCtrl     = TextEditingController();
  final _profCtrl       = TextEditingController();
  String _tipo          = 'viga';
  bool _comprimirDraco  = true;
  String _encoderMethod = 'edgebreaker';

  // File
  Uint8List? _fileBytes;
  String?    _fileName;

  // State
  bool   _uploading = false;
  String _statusMsg = '';
  bool   _success   = false;
  Map<String, dynamic>? _lastResult;

  // Catálogo existente
  List<dynamic> _catalogo = [];
  bool _loadingCatalogo = false;

  final List<String> _tipos = ['viga', 'marco', 'mensula', 'base', 'travesaño', 'otro'];

  @override
  void initState() {
    super.initState();
    _loadCatalogo();
  }

  @override
  void dispose() {
    _skuCtrl.dispose(); _nombreCtrl.dispose(); _pesoCtrl.dispose();
    _longitudCtrl.dispose(); _alturaCtrl.dispose(); _profCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadCatalogo() async {
    setState(() => _loadingCatalogo = true);
    try {
      final data = await _svc.fetchCatalogo();
      setState(() => _catalogo = data);
    } catch (e) {
      debugPrint('loadCatalogo error: $e');
    } finally {
      setState(() => _loadingCatalogo = false);
    }
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['glb', 'gltf'],
      withData: true,
    );
    if (result != null && result.files.single.bytes != null) {
      setState(() {
        _fileBytes = result.files.single.bytes;
        _fileName  = result.files.single.name;
        _statusMsg = '';
      });
    }
  }

  Future<void> _submit() async {
    if (_skuCtrl.text.trim().isEmpty || _nombreCtrl.text.trim().isEmpty) {
      setState(() { _statusMsg = 'SKU y Nombre son obligatorios.'; _success = false; });
      return;
    }
    if (_fileBytes == null || _fileName == null) {
      setState(() { _statusMsg = 'Selecciona un archivo .glb o .gltf.'; _success = false; });
      return;
    }

    setState(() { _uploading = true; _statusMsg = 'Subiendo y procesando...'; _success = false; });

    try {
      final result = await _svc.uploadModeloCatalogo(
        codigoSku:      _skuCtrl.text.trim(),
        nombre:         _nombreCtrl.text.trim(),
        tipo:           _tipo,
        pesoMaximo:     double.tryParse(_pesoCtrl.text) ?? 0,
        longitud:       double.tryParse(_longitudCtrl.text) ?? 0,
        altura:         double.tryParse(_alturaCtrl.text) ?? 0,
        profundidad:    double.tryParse(_profCtrl.text) ?? 0,
        fileBytes:      _fileBytes!,
        fileName:       _fileName!,
        comprimirDraco: _comprimirDraco,
        encoderMethod:  _encoderMethod,
      );

      setState(() {
        _lastResult = result;
        _success    = true;
        _statusMsg  = '¡Pieza registrada correctamente!';
      });
      _loadCatalogo();
    } catch (e) {
      setState(() { _statusMsg = 'Error: $e'; _success = false; });
    } finally {
      setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: const EdgeInsets.all(4),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      // Header
      const Text('Subir Modelo 3D al Catálogo',
          style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: kTextPrimary)),
      const SizedBox(height: 4),
      const Text('Comprime con Draco, sube a Supabase Storage y registra la pieza en el catálogo.',
          style: TextStyle(fontSize: 12, color: kTextSecond)),
      const SizedBox(height: 20),

      // Formulario
      PanelCard(
        title: 'Datos de la pieza',
        subtitle: 'Información para catalogo_piezas',
        child: Column(children: [
          _row([
            _field('Código SKU *', _skuCtrl, hint: 'ej: VIGA-LIG-2400'),
            _field('Nombre *', _nombreCtrl, hint: 'ej: Viga Ligera 2.4m'),
          ]),
          const SizedBox(height: 12),
          _row([
            _dropdown('Tipo', _tipo, _tipos, (v) => setState(() => _tipo = v!)),
            _field('Peso máx. (kg)', _pesoCtrl, hint: '800', isNumber: true),
          ]),
          const SizedBox(height: 12),
          _row([
            _field('Longitud (m)', _longitudCtrl, hint: '2.4', isNumber: true),
            _field('Altura (m)', _alturaCtrl, hint: '4.0', isNumber: true),
            _field('Profundidad (m)', _profCtrl, hint: '1.0', isNumber: true),
          ]),
        ]),
      ),

      // Archivo
      PanelCard(
        title: 'Archivo 3D',
        subtitle: '.glb o .gltf',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          GestureDetector(
            onTap: _pickFile,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 16),
              decoration: BoxDecoration(
                color: _fileBytes != null ? kIndigoLight : kBgColor,
                border: Border.all(
                  color: _fileBytes != null ? kIndigo : kBorder,
                  style: BorderStyle.solid, width: 2,
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(children: [
                Icon(_fileBytes != null ? Icons.check_circle : Icons.upload_file,
                    color: _fileBytes != null ? kIndigo : kTextSecond, size: 32),
                const SizedBox(height: 8),
                Text(
                  _fileBytes != null
                      ? _fileName!
                      : 'Toca para seleccionar archivo .glb / .gltf',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: _fileBytes != null ? kIndigo : kTextSecond,
                    fontSize: 13,
                  ),
                  textAlign: TextAlign.center,
                ),
                if (_fileBytes != null)
                  Text('${(_fileBytes!.length / 1024).toStringAsFixed(1)} KB',
                      style: const TextStyle(fontSize: 11, color: kTextSecond)),
              ]),
            ),
          ),
          const SizedBox(height: 16),

          // Opciones Draco
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _comprimirDraco ? kIndigoLight : kBgColor,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: _comprimirDraco ? const Color(0xFFC7D2FE) : kBorder),
            ),
            child: Column(children: [
              Row(children: [
                Switch(
                  value: _comprimirDraco,
                  onChanged: (v) => setState(() => _comprimirDraco = v),
                  activeThumbColor: kIndigo,
                ),
                const SizedBox(width: 8),
                const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Comprimir con Draco', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: kTextPrimary)),
                  Text('Reduce el tamaño del modelo ~78% antes de subir', style: TextStyle(fontSize: 11, color: kTextSecond)),
                ])),
              ]),
              if (_comprimirDraco) ...[
                const SizedBox(height: 10),
                Row(children: [
                  const Text('Método: ', style: TextStyle(fontSize: 13, color: kTextSecond)),
                  const SizedBox(width: 8),
                  _chipMethod('edgebreaker'),
                  const SizedBox(width: 6),
                  _chipMethod('sequential'),
                ]),
              ],
            ]),
          ),
        ]),
      ),

      // Status
      if (_statusMsg.isNotEmpty)
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: _success ? kEmeraldLight : (_uploading ? kIndigoLight : kRedLight),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: _success ? kEmerald : (_uploading ? kIndigo : kRed)),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              if (_uploading) const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
              if (!_uploading) Icon(_success ? Icons.check_circle : Icons.error_outline,
                  size: 18, color: _success ? kEmerald : kRed),
              const SizedBox(width: 8),
              Expanded(child: Text(_statusMsg, style: TextStyle(
                fontWeight: FontWeight.w600, fontSize: 13,
                color: _success ? kEmerald : (_uploading ? kIndigo : kRed),
              ))),
            ]),
            if (_success && _lastResult != null) ...[
              const SizedBox(height: 8),
              _resultRow('SKU', _lastResult!['codigo_sku']),
              _resultRow('Ruta', _lastResult!['storage_path']),
              _resultRow('Tamaño original', '${(_lastResult!['original_size'] / 1024).toStringAsFixed(1)} KB'),
              _resultRow('Tamaño final', '${(_lastResult!['final_size'] / 1024).toStringAsFixed(1)} KB'),
              _resultRow('Reducción', '${_lastResult!['reduction_percent']}%'),
            ],
          ]),
        ),

      // Botón submit
      SizedBox(
        width: double.infinity,
        child: ElevatedButton.icon(
          onPressed: _uploading ? null : _submit,
          icon: _uploading
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : const Icon(Icons.cloud_upload),
          label: Text(_uploading ? 'Procesando...' : 'Comprimir y subir al catálogo'),
          style: ElevatedButton.styleFrom(
            backgroundColor: kIndigo, foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 16),
            textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        ),
      ),

      const SizedBox(height: 24),

      // Catálogo existente
      PanelCard(
        title: 'Catálogo actual',
        subtitle: '${_catalogo.length} piezas registradas',
        trailing: IconButton(icon: const Icon(Icons.refresh, size: 18, color: kIndigo), onPressed: _loadCatalogo),
        child: _loadingCatalogo
            ? const ShimmerLoader()
            : _catalogo.isEmpty
                ? const EmptyState(icon: Icons.inventory_2_outlined, message: 'No hay piezas en el catálogo aún.')
                : Column(children: _catalogo.map((p) => _catalogoItem(p as Map<String, dynamic>)).toList()),
      ),
    ]),
  );

  // ── Helpers UI ───────────────────────────────────────────────────────────────

  Widget _row(List<Widget> children) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: children.map((w) => Expanded(child: Padding(padding: const EdgeInsets.only(right: 8), child: w))).toList(),
  );

  Widget _field(String label, TextEditingController ctrl, {String hint = '', bool isNumber = false}) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kTextSecond)),
      const SizedBox(height: 4),
      TextField(
        controller: ctrl,
        keyboardType: isNumber ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
        style: const TextStyle(fontSize: 13),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: const TextStyle(color: Color(0xFFCBD5E1), fontSize: 13),
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBorder)),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBorder)),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kIndigo, width: 1.5)),
          filled: true, fillColor: kSurface,
        ),
      ),
    ],
  );

  Widget _dropdown(String label, String value, List<String> options, ValueChanged<String?> onChanged) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kTextSecond)),
      const SizedBox(height: 4),
      DropdownButtonFormField<String>(
        initialValue: value,
        onChanged: onChanged,
        items: options.map((o) => DropdownMenuItem(value: o, child: Text(o, style: const TextStyle(fontSize: 13)))).toList(),
        decoration: InputDecoration(
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBorder)),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: kBorder)),
          filled: true, fillColor: kSurface,
        ),
      ),
    ],
  );

  Widget _chipMethod(String method) => GestureDetector(
    onTap: () => setState(() => _encoderMethod = method),
    child: AnimatedContainer(
      duration: const Duration(milliseconds: 150),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: _encoderMethod == method ? kIndigo : kSurface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: _encoderMethod == method ? kIndigo : kBorder),
      ),
      child: Text(method, style: TextStyle(
        fontSize: 12, fontWeight: FontWeight.w600,
        color: _encoderMethod == method ? Colors.white : kTextSecond,
      )),
    ),
  );

  Widget _resultRow(String label, dynamic value) => Padding(
    padding: const EdgeInsets.only(bottom: 3),
    child: Row(children: [
      Text('$label: ', style: const TextStyle(fontSize: 12, color: kTextSecond)),
      Text('$value', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kTextPrimary)),
    ]),
  );

  Future<void> _eliminarPieza(String sku) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Eliminar pieza'),
        content: Text('¿Eliminar "$sku" del catálogo y de Supabase Storage?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: kRed, foregroundColor: Colors.white),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
    if (confirmar != true) return;
    try {
      await _svc.eliminarPiezaCatalogo(sku);
      setState(() => _statusMsg = 'Pieza "$sku" eliminada.');
      _loadCatalogo();
    } catch (e) {
      setState(() => _statusMsg = 'Error eliminando: $e');
    }
  }

  Widget _catalogoItem(Map<String, dynamic> p) => Container(
    margin: const EdgeInsets.only(bottom: 10),
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: kSurface, borderRadius: BorderRadius.circular(12), border: Border.all(color: kBorder),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(p['codigo_sku'] ?? '', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: kIndigo)),
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(color: kIndigoLight, borderRadius: BorderRadius.circular(999)),
            child: Text(p['tipo'] ?? '', style: const TextStyle(fontSize: 11, color: kIndigo, fontWeight: FontWeight.w600)),
          ),
          const SizedBox(width: 6),
          // Fix 6: botón eliminar atómico
          GestureDetector(
            onTap: () => _eliminarPieza(p['codigo_sku'] as String),
            child: Container(
              padding: const EdgeInsets.all(5),
              decoration: BoxDecoration(color: const Color(0xFFFEF2F2), borderRadius: BorderRadius.circular(6)),
              child: const Icon(Icons.delete_outline, size: 15, color: kRed),
            ),
          ),
        ]),
      ]),
      const SizedBox(height: 4),
      Text(p['nombre'] ?? '', style: const TextStyle(fontSize: 13, color: kTextPrimary)),
      const SizedBox(height: 6),
      Wrap(spacing: 12, runSpacing: 4, children: [
        _catalogoDetail('Peso máx.', '${p['peso_maximo_soportado_kg']} kg'),
        _catalogoDetail('Longitud', '${p['longitud_metros']} m'),
        _catalogoDetail('Altura', '${p['altura_metros']} m'),
        _catalogoDetail('Profundidad', '${p['profundidad_metros']} m'),
      ]),
      if (p['url_modelo_glb'] != null && (p['url_modelo_glb'] as String).isNotEmpty) ...[
        const SizedBox(height: 6),
        Row(children: [
          const Icon(Icons.check_circle, size: 14, color: kEmerald),
          const SizedBox(width: 4),
          const Text('Modelo 3D disponible', style: TextStyle(fontSize: 11, color: kEmerald, fontWeight: FontWeight.w600)),
        ]),
      ],
    ]),
  );

  Widget _catalogoDetail(String label, String value) =>
      Text('$label: $value', style: const TextStyle(fontSize: 12, color: kTextSecond));
}
