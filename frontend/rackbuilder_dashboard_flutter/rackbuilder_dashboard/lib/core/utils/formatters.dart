/// Funciones de formateo reutilizables
class Formatters {
  Formatters._();

  static String bytes(int b) {
    if (b == 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    var val = b.toDouble(); var i = 0;
    while (val >= 1024 && i < sizes.length - 1) { val /= 1024; i++; }
    return '${val.toStringAsFixed(2)} ${sizes[i]}';
  }

  static String thousands(int n) {
    final str = n.toString();
    final buf = StringBuffer();
    for (var i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) buf.write(',');
      buf.write(str[i]);
    }
    return buf.toString();
  }

  static String date(String? iso) {
    if (iso == null) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.day}/${dt.month}/${dt.year} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) { return iso; }
  }

  static String currency(double amount) => '\$${amount.toStringAsFixed(2)}';
}
