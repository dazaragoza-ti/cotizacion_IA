import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../services/dashboard_service.dart';
import '../widgets/widgets.dart';
import 'upload_modelo_screen.dart';
import 'historial_screen.dart';

// Fix 9: cada módulo es su propio widget — dashboard_screen solo orquesta
enum DashModule { analiticas, alimentar, draco, catalogo, historial }

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _svc = DashboardService.instance;

  DashModule _activeModule = DashModule.analiticas;
  bool _connected = false;
  String _connectionText = 'Desconectado';

  DashboardMetrics _metrics = DashboardMetrics.empty();
  List<StorageFileItem> _aiDocuments = [];
  List<StorageFileItem> _dracoModels = [];

  bool _loadingMetrics = false;
  bool _loadingStorage = false;
  String? _optimizingPath;
  String _optimizeMessage = '';
  String _supabaseUrl = '';
  String _supabaseKey = '';

  // Fix 10: reconexión automática
  bool _reconnecting = false;

  @override
  void initState() {
    super.initState();
    _autoConnect();
  }

  Future<void> _autoConnect() async {
    final prefs = await SharedPreferences.getInstance();
    final savedUrl = prefs.getString('sb_url') ?? '';
    final savedKey = prefs.getString('sb_key') ?? '';
    if (savedUrl.isNotEmpty && savedKey.isNotEmpty) {
      _supabaseUrl = savedUrl; _supabaseKey = savedKey;
      await _connect();
    } else {
      final config = await _svc.fetchConfigFromBackend();
      if (config != null) {
        _supabaseUrl = config['url']!; _supabaseKey = config['key']!;
        await _connect();
      }
    }
  }

  Future<void> _connect() async {
    try {
      _svc.setConnection(_supabaseUrl, _supabaseKey);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('sb_url', _supabaseUrl);
      await prefs.setString('sb_key', _supabaseKey);
      if (mounted) setState(() { _connected = true; _connectionText = 'Conexión Activa'; _reconnecting = false; });
      await Future.wait([_loadMetrics(), _loadStorage()]);
    } catch (e) {
      if (mounted) setState(() { _connected = false; _connectionText = 'Desconectado'; });
      // Fix 10: reintento automático tras 5 segundos
      _scheduleReconnect();
    }
  }

  // Fix 10: reconexión con backoff
  void _scheduleReconnect() {
    if (_reconnecting) return;
    _reconnecting = true;
    Future.delayed(const Duration(seconds: 5), () async {
      if (!mounted || _connected) return;
      setState(() => _connectionText = 'Reconectando...');
      await _connect();
    });
  }

  Future<void> _loadMetrics() async {
    if (mounted) setState(() => _loadingMetrics = true);
    try {
      final m = await _svc.getMetrics();
      if (mounted) setState(() => _metrics = m);
    } catch (e) {
      if (mounted) setState(() => _metrics = DashboardMetrics.empty());
      _scheduleReconnect();
    } finally {
      if (mounted) setState(() => _loadingMetrics = false);
    }
  }

  Future<void> _loadStorage() async {
    if (_loadingStorage) return;
    if (mounted) setState(() => _loadingStorage = true);
    try {
      final results = await Future.wait([
        _svc.listStorageFiles('cotizaciones', 'Racks'),
        _svc.listStorageFiles('precios unitarios', 'productos'),
        _svc.listStorageFiles('modelos', 'modelos 3d de racks'),
        _svc.listStorageFiles('modelos', ''),
      ]);
      final aiDocs = [...results[0], ...results[1]]..sort((a, b) => a.name.compareTo(b.name));
      final unique = <String, StorageFileItem>{};
      for (final m in [...results[2], ...results[3]]) { unique[m.path] = m; }
      final dracoList = unique.values.toList()..sort((a, b) => a.name.compareTo(b.name));
      if (mounted) setState(() { _aiDocuments = aiDocs; _dracoModels = dracoList; });
    } catch (e) {
      debugPrint('loadStorage error: $e');
    } finally {
      if (mounted) setState(() => _loadingStorage = false);
    }
  }

  Future<void> _switchModule(DashModule m) async {
    setState(() => _activeModule = m);
    if (m == DashModule.draco || m == DashModule.alimentar) await _loadStorage();
  }

  Future<void> _optimizeModel(StorageFileItem model) async {
    setState(() { _optimizingPath = model.path; _optimizeMessage = 'Optimizando ${model.name}...'; });
    try {
      final result = await _svc.optimizeStorageFile(model.bucket, model.path);
      final orig = (result['original_size'] as num).toInt();
      final comp = (result['compressed_size'] as num).toInt();
      final pct = orig > 0 ? ((orig - comp) / orig * 100).toStringAsFixed(1) : '0';
      setState(() {
        _dracoModels = _dracoModels.map((m) => m.path == model.path
            ? m.withOptimizationResult(originalSize: orig, compressedSizeResult: comp)
            : m).toList();
        _optimizeMessage = '${model.name}: ${_fmtBytes(orig)} → ${_fmtBytes(comp)} ($pct% reducción)';
      });
    } catch (e) {
      setState(() => _optimizeMessage = 'Error: $e');
    } finally {
      setState(() => _optimizingPath = null);
    }
  }

  String _fmtBytes(int b) {
    if (b == 0) return '0 B';
    const s = ['B', 'KB', 'MB', 'GB'];
    var i = 0; double val = b.toDouble();
    while (val >= 1024 && i < s.length - 1) { val /= 1024; i++; }
    return '${val.toStringAsFixed(2)} ${s[i]}';
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width > 900;
    return Scaffold(
      backgroundColor: kBgColor,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(children: [
            _buildTopbar(),
            const SizedBox(height: 14),
            Expanded(child: isWide ? _buildWideLayout() : _buildNarrowLayout()),
          ]),
        ),
      ),
    );
  }

  Widget _buildTopbar() => Container(
    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
    decoration: BoxDecoration(
      color: kSurface, borderRadius: BorderRadius.circular(18),
      border: Border.all(color: kBorder),
      boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 18, offset: const Offset(0, 6))],
    ),
    child: Row(children: [
      Container(
        width: 44, height: 44,
        decoration: BoxDecoration(
          gradient: const LinearGradient(colors: [Color(0xFF4F46E5), Color(0xFF6366F1)], begin: Alignment.topLeft, end: Alignment.bottomRight),
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Icon(Icons.show_chart, color: Colors.white, size: 22),
      ),
      const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        RichText(text: const TextSpan(children: [
          TextSpan(text: 'RackBuilder ', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: kTextPrimary)),
          TextSpan(text: 'Dashboard', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: kIndigo)),
        ])),
        const Text('Panel de Control, Compresión Draco y Entrenamiento de IA',
            style: TextStyle(fontSize: 12, color: kTextSecond)),
      ])),
      if (_reconnecting && !_connected)
        const Padding(
          padding: EdgeInsets.only(right: 10),
          child: SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: kAmber)),
        ),
      ConnectionBadge(connected: _connected, text: _connectionText),
    ]),
  );

  Widget _buildWideLayout() => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
    SizedBox(width: 260, child: _buildSidebar()),
    const SizedBox(width: 14),
    Expanded(child: _buildContentPanel()),
  ]);

  Widget _buildNarrowLayout() => Column(children: [
    _buildSidebar(),
    const SizedBox(height: 14),
    Expanded(child: _buildContentPanel()),
  ]);

  Widget _buildSidebar() => Column(mainAxisSize: MainAxisSize.min, children: [
    Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: kSurface, borderRadius: BorderRadius.circular(16), border: Border.all(color: kBorder),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 16)],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('HERRAMIENTAS', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: Color(0xFF94A3B8), letterSpacing: 1.5)),
        const SizedBox(height: 10),
        NavButton(icon: Icons.bar_chart,      label: 'Métricas y Tokens',    active: _activeModule == DashModule.analiticas, onTap: () => _switchModule(DashModule.analiticas)),
        NavButton(icon: Icons.psychology,     label: 'Alimentar IA',          active: _activeModule == DashModule.alimentar,  onTap: () => _switchModule(DashModule.alimentar)),
        NavButton(icon: Icons.compress,       label: 'Optimizar Draco CAD',   active: _activeModule == DashModule.draco,      onTap: () => _switchModule(DashModule.draco)),
        NavButton(icon: Icons.cloud_upload,   label: 'Subir al Catálogo',     active: _activeModule == DashModule.catalogo,   onTap: () => _switchModule(DashModule.catalogo)),
        NavButton(icon: Icons.history,        label: 'Historial de Diseños',  active: _activeModule == DashModule.historial,  onTap: () => _switchModule(DashModule.historial)),
      ]),
    ),
    const SizedBox(height: 12),
    Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(16), border: Border.all(color: kBorder)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('ESTADO DE SINCRONIZACIÓN', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: Color(0xFF94A3B8), letterSpacing: 1.5)),
        const SizedBox(height: 10),
        Row(children: [
          _PulseDot(color: _connected ? kEmerald : kRed),
          const SizedBox(width: 8),
          Text(_connectionText, style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF475569))),
        ]),
        if (!_connected) ...[
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _autoConnect,
              icon: const Icon(Icons.refresh, size: 14),
              label: const Text('Reconectar', style: TextStyle(fontSize: 12)),
              style: OutlinedButton.styleFrom(
                foregroundColor: kIndigo,
                side: const BorderSide(color: Color(0xFFC7D2FE)),
                padding: const EdgeInsets.symmetric(vertical: 8),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
            ),
          ),
        ],
      ]),
    ),
  ]);

  Widget _buildContentPanel() => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: kSurface, borderRadius: BorderRadius.circular(18), border: Border.all(color: kBorder),
      boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 18)],
    ),
    child: SingleChildScrollView(child: AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: switch (_activeModule) {
        DashModule.analiticas => _AnaliticasModule(
            key: const ValueKey('analiticas'),
            metrics: _metrics, loading: _loadingMetrics,
            onRefresh: () => Future.wait([_loadMetrics(), _loadStorage()])),
        DashModule.alimentar  => _AlimentarModule(
            key: const ValueKey('alimentar'),
            documents: _aiDocuments, loading: _loadingStorage),
        DashModule.draco      => _DracoModule(
            key: const ValueKey('draco'),
            models: _dracoModels, loading: _loadingStorage,
            optimizingPath: _optimizingPath,
            optimizeMessage: _optimizeMessage,
            onOptimize: _optimizeModel,
            onReload: _loadStorage),
        DashModule.catalogo   => const UploadModeloScreen(key: ValueKey('catalogo')),
        DashModule.historial  => const HistorialScreen(key: ValueKey('historial')),
      },
    )),
  );
}

// ── Fix 9: Módulos como widgets independientes ───────────────────────────────

class _AnaliticasModule extends StatelessWidget {
  final DashboardMetrics metrics;
  final bool loading;
  final Future<void> Function() onRefresh;
  const _AnaliticasModule({super.key, required this.metrics, required this.loading, required this.onRefresh});

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Métricas Globales de Proyectos', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: kTextPrimary)),
        SizedBox(height: 2),
        Text('Monitoreo en tiempo real de diseños y costo de APIs.', style: TextStyle(fontSize: 12, color: kTextSecond)),
      ]),
      ElevatedButton.icon(
        onPressed: onRefresh,
        icon: const Icon(Icons.refresh, size: 16),
        label: const Text('Actualizar'),
        style: ElevatedButton.styleFrom(backgroundColor: kIndigo, foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
      ),
    ]),
    const SizedBox(height: 16),
    loading ? const ShimmerLoader() : _KpiGrid(metrics: metrics),
    const SizedBox(height: 14),
    LayoutBuilder(builder: (ctx, c) {
      final wide = c.maxWidth > 600;
      final tokenPanel = PanelCard(
        title: 'Uso de tokens', subtitle: 'Resumen del flujo actual',
        child: Column(children: [
          TokenBar(label: 'Input tokens', valueLabel: '${metrics.inputTokens.toLocaleString()} tokens',
              percent: metrics.totalTokens > 0 ? metrics.inputTokens / metrics.totalTokens * 100 : 0,
              color: const Color(0xFF22D3EE)),
          const SizedBox(height: 12),
          TokenBar(label: 'Output tokens', valueLabel: '${metrics.outputTokens.toLocaleString()} tokens',
              percent: metrics.totalTokens > 0 ? metrics.outputTokens / metrics.totalTokens * 100 : 0,
              color: const Color(0xFF8B5CF6)),
          const SizedBox(height: 14),
          Wrap(spacing: 10, runSpacing: 10, children: [
            SummaryItem(label: 'Tokens totales',     value: metrics.totalTokens.toLocaleString()),
            SummaryItem(label: 'Prom. por proyecto', value: metrics.avgTokensPerProject.round().toLocaleString()),
            SummaryItem(label: 'Costo estimado',     value: '\$${metrics.estimatedCost.toStringAsFixed(2)}'),
          ]),
        ]),
      );
      final activityPanel = PanelCard(
        title: 'Actividad reciente', subtitle: 'Desde Supabase',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: metrics.proyectos == 0
            ? [const Text('Conectando a Supabase...', style: TextStyle(color: kTextSecond, fontSize: 13))]
            : [
                Text('${metrics.proyectos} proyectos cargados desde Supabase', style: const TextStyle(fontSize: 13, color: kTextSecond)),
                const SizedBox(height: 6),
                Text('Total de tokens: ${metrics.totalTokens.toLocaleString()}', style: const TextStyle(fontSize: 13, color: kTextSecond)),
                const SizedBox(height: 6),
                Text('Promedio por diseño: ${metrics.avgTokensPerProject.round().toLocaleString()} tokens', style: const TextStyle(fontSize: 13, color: kTextSecond)),
              ]),
      );
      return wide
          ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(flex: 2, child: tokenPanel),
              const SizedBox(width: 12),
              Expanded(child: activityPanel),
            ])
          : Column(children: [tokenPanel, activityPanel]);
    }),
  ]);
}

class _KpiGrid extends StatelessWidget {
  final DashboardMetrics metrics;
  const _KpiGrid({required this.metrics});
  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (ctx, c) {
    final wide = c.maxWidth > 500;
    final cards = [
      KpiCard(label: 'Proyectos', value: metrics.proyectos.toString(), hint: 'Registros en disenos_racks',
          iconBg: kIndigoLight, iconFg: const Color(0xFF4338CA), icon: Icons.folder_open),
      KpiCard(label: 'Tokens', value: metrics.totalTokens.toLocaleString(), hint: 'Entrada + salida',
          iconBg: kAmberLight, iconFg: kAmber, icon: Icons.bar_chart),
      KpiCard(label: 'Costo estimado', value: '\$${metrics.estimatedCost.toStringAsFixed(2)}', hint: 'Basado en uso real',
          iconBg: kEmeraldLight, iconFg: kEmerald, icon: Icons.attach_money),
    ];
    return wide
        ? Row(children: cards.map((c) => Expanded(child: Padding(padding: const EdgeInsets.only(right: 10), child: c))).toList())
        : Column(children: cards.map((c) => Padding(padding: const EdgeInsets.only(bottom: 10), child: c)).toList());
  });
}

class _AlimentarModule extends StatelessWidget {
  final List<StorageFileItem> documents;
  final bool loading;
  const _AlimentarModule({super.key, required this.documents, required this.loading});

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text('Alimentar Inteligencia Artificial', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: kTextPrimary)),
    const SizedBox(height: 4),
    const Text('Documentos de cotizaciones y precios en Supabase Storage.', style: TextStyle(fontSize: 12, color: kTextSecond)),
    const SizedBox(height: 16),
    if (loading) const ShimmerLoader()
    else if (documents.isEmpty)
      const EmptyState(icon: Icons.cloud_upload, message: 'No hay documentos disponibles en los buckets indicados.')
    else
      ...documents.map((doc) => Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(14), border: Border.all(color: kBorder)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(doc.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: kTextPrimary)),
          const SizedBox(height: 4),
          Text('${doc.bucket} / ${doc.folder}', style: const TextStyle(fontSize: 12, color: kTextSecond)),
          Text(doc.type, style: const TextStyle(fontSize: 12, color: kTextSecond)),
        ]),
      )),
  ]);
}

class _DracoModule extends StatelessWidget {
  final List<StorageFileItem> models;
  final bool loading;
  final String? optimizingPath;
  final String optimizeMessage;
  final Future<void> Function(StorageFileItem) onOptimize;
  final Future<void> Function() onReload;

  const _DracoModule({super.key, required this.models, required this.loading,
      required this.optimizingPath, required this.optimizeMessage,
      required this.onOptimize, required this.onReload});

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Compresor Draco CAD', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: kTextPrimary)),
        SizedBox(height: 2),
        Text('Modelos 3D en el bucket de Supabase.', style: TextStyle(fontSize: 12, color: kTextSecond)),
      ]),
      OutlinedButton.icon(
        onPressed: onReload,
        icon: const Icon(Icons.refresh, size: 16),
        label: const Text('Forzar recarga'),
        style: OutlinedButton.styleFrom(foregroundColor: kIndigo, side: const BorderSide(color: Color(0xFFC7D2FE)),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
      ),
    ]),
    const SizedBox(height: 16),
    if (optimizeMessage.isNotEmpty)
      Container(
        margin: const EdgeInsets.only(bottom: 12), padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: kIndigoLight, borderRadius: BorderRadius.circular(10)),
        child: Text(optimizeMessage, style: const TextStyle(color: Color(0xFF1E3A8A), fontSize: 13)),
      ),
    if (loading) const ShimmerLoader()
    else if (models.isEmpty)
      const EmptyState(icon: Icons.description_outlined, message: 'No hay modelos 3D disponibles en el bucket indicado.')
    else
      ...models.map((m) => ModelFileCard(
          model: m,
          isOptimizing: optimizingPath == m.path,
          onOptimize: optimizingPath != null ? null : () => onOptimize(m))),
  ]);
}

// ── Helpers ──────────────────────────────────────────────────────────────────
extension _IntFormat on int {
  String toLocaleString() {
    final str = toString();
    final buffer = StringBuffer();
    for (var i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) buffer.write(',');
      buffer.write(str[i]);
    }
    return buffer.toString();
  }
}

class _PulseDot extends StatefulWidget {
  final Color color;
  const _PulseDot({required this.color});
  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _scale;
  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat(reverse: true);
    _scale = Tween<double>(begin: 1.0, end: 1.3).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }
  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => ScaleTransition(
    scale: _scale,
    child: Container(width: 9, height: 9, decoration: BoxDecoration(color: widget.color, shape: BoxShape.circle)),
  );
}
