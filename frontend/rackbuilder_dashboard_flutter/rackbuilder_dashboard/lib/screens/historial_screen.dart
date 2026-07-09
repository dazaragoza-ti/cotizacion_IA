import 'package:flutter/material.dart';
import '../services/dashboard_service.dart';
import '../widgets/widgets.dart';

class HistorialScreen extends StatefulWidget {
  const HistorialScreen({super.key});
  @override
  State<HistorialScreen> createState() => _HistorialScreenState();
}

class _HistorialScreenState extends State<HistorialScreen> {
  final _svc = DashboardService.instance;
  List<dynamic> _disenos = [];
  bool _loading = false;
  String? _selectedSessionId;
  List<dynamic> _versiones = [];
  bool _loadingVersiones = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await _svc.fetchHistorial();
      setState(() => _disenos = data);
    } catch (e) {
      debugPrint('historial error: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _loadVersiones(String sessionId) async {
    setState(() { _selectedSessionId = sessionId; _loadingVersiones = true; });
    try {
      final data = await _svc.fetchVersionesSesion(sessionId);
      setState(() => _versiones = data);
    } catch (e) {
      debugPrint('versiones error: $e');
    } finally {
      setState(() => _loadingVersiones = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Historial de Diseños', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: kTextPrimary)),
          SizedBox(height: 2),
          Text('Todas las sesiones y versiones generadas por el bot.', style: TextStyle(fontSize: 12, color: kTextSecond)),
        ]),
        IconButton(icon: const Icon(Icons.refresh, color: kIndigo), onPressed: _load),
      ]),
      const SizedBox(height: 16),
      if (_loading)
        const ShimmerLoader()
      else if (_disenos.isEmpty)
        const EmptyState(icon: Icons.history, message: 'No hay diseños registrados aún.')
      else
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Lista de sesiones
          Expanded(
            flex: 2,
            child: PanelCard(
              title: 'Sesiones',
              subtitle: '${_disenos.length} registros',
              child: Column(
                children: _disenos.map((d) => _sesionTile(d as Map<String, dynamic>)).toList(),
              ),
            ),
          ),
          const SizedBox(width: 14),
          // Panel de versiones
          Expanded(
            flex: 3,
            child: _selectedSessionId == null
                ? Container(
                    height: 200,
                    decoration: BoxDecoration(
                      border: Border.all(color: kBorder, width: 2, style: BorderStyle.solid),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Center(
                      child: Text('Selecciona una sesión para ver sus versiones',
                          style: TextStyle(color: kTextSecond, fontSize: 13)),
                    ),
                  )
                : PanelCard(
                    title: 'Versiones',
                    subtitle: 'Sesión: ...${_selectedSessionId!.substring(_selectedSessionId!.length > 8 ? _selectedSessionId!.length - 8 : 0)}',
                    child: _loadingVersiones
                        ? const ShimmerLoader()
                        : Column(
                            children: _versiones.map((v) => _versionTile(v as Map<String, dynamic>)).toList(),
                          ),
                  ),
          ),
        ]),
    ],
  );

  Widget _sesionTile(Map<String, dynamic> d) {
    final isSelected = d['session_id'] == _selectedSessionId;
    final tokens = ((d['input_tokens'] as num?)?.toInt() ?? 0) +
        ((d['output_tokens'] as num?)?.toInt() ?? 0);
    return GestureDetector(
      onTap: () => _loadVersiones(d['session_id'] as String),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected ? kIndigoLight : kSurface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: isSelected ? kIndigo : kBorder),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Expanded(
              child: Text(
                d['vendedor_id'] as String? ?? 'Desconocido',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13,
                    color: isSelected ? kIndigo : kTextPrimary),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                color: isSelected ? kIndigo : const Color(0xFFEEF2FF),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text('v${d['version_actual']}',
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700,
                      color: isSelected ? Colors.white : kIndigo)),
            ),
          ]),
          const SizedBox(height: 4),
          Text(
            d['solicitud_original'] as String? ?? '',
            maxLines: 2, overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 11, color: kTextSecond),
          ),
          const SizedBox(height: 4),
          Row(children: [
            const Icon(Icons.token, size: 11, color: Color(0xFF94A3B8)),
            const SizedBox(width: 3),
            Text('$tokens tokens',
                style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8))),
          ]),
        ]),
      ),
    );
  }

  Widget _versionTile(Map<String, dynamic> v) {
    final historial = (v['historial_comentarios'] as List<dynamic>?) ?? [];
    final inputTk = (v['input_tokens'] as num?)?.toInt() ?? 0;
    final outputTk = (v['output_tokens'] as num?)?.toInt() ?? 0;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: kSurface, borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kBorder),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 28, height: 28,
            decoration: BoxDecoration(color: kIndigoLight, shape: BoxShape.circle),
            child: Center(
              child: Text('${v['version_actual']}',
                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12, color: kIndigo)),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(
              v['solicitud_original'] as String? ?? '',
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: kTextPrimary),
              maxLines: 2, overflow: TextOverflow.ellipsis,
            ),
            Text(
              _formatDate(v['created_at'] as String?),
              style: const TextStyle(fontSize: 11, color: kTextSecond),
            ),
          ])),
        ]),
        if (historial.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Text('Cambios:', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: kTextSecond)),
          const SizedBox(height: 4),
          ...historial.map((c) => Padding(
            padding: const EdgeInsets.only(bottom: 3, left: 8),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('• ', style: TextStyle(color: kIndigo, fontSize: 11)),
              Expanded(child: Text('$c', style: const TextStyle(fontSize: 11, color: kTextSecond))),
            ]),
          )),
        ],
        if (inputTk > 0 || outputTk > 0) ...[
          const SizedBox(height: 8),
          Row(children: [
            _tokenChip('In', inputTk, const Color(0xFF22D3EE)),
            const SizedBox(width: 6),
            _tokenChip('Out', outputTk, const Color(0xFF8B5CF6)),
          ]),
        ],
      ]),
    );
  }

  Widget _tokenChip(String label, int val, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(999),
    ),
    child: Text('$label: $val', style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
  );

  String _formatDate(String? iso) {
    if (iso == null) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.day}/${dt.month}/${dt.year} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) { return iso; }
  }
}
