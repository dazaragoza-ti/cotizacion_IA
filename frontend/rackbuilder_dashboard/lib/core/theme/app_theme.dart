import 'package:flutter/material.dart';

// ── Paleta de colores ─────────────────────────────────────────────────────────
class AppColors {
  AppColors._();
  static const bg          = Color(0xFFF8FAFC);
  static const surface     = Colors.white;
  static const border      = Color(0xFFE2E8F0);
  static const textPrimary = Color(0xFF0F172A);
  static const textSecond  = Color(0xFF64748B);
  static const textHint    = Color(0xFF94A3B8);
  static const indigo      = Color(0xFF4F46E5);
  static const indigoDark  = Color(0xFF4338CA);
  static const indigoLight = Color(0xFFEEF2FF);
  static const indigoBorder= Color(0xFFC7D2FE);
  static const amber       = Color(0xFFD97706);
  static const amberLight  = Color(0xFFFFFBEB);
  static const emerald     = Color(0xFF059669);
  static const emeraldLight= Color(0xFFECFDF5);
  static const red         = Color(0xFFB91C1C);
  static const redLight    = Color(0xFFFEF2F2);
  static const cyan        = Color(0xFF22D3EE);
  static const purple      = Color(0xFF8B5CF6);
  static const slate       = Color(0xFF475569);
  static const slateLight  = Color(0xFFF1F5F9);
}

// ── Breakpoints responsivos ───────────────────────────────────────────────────
class Bp {
  Bp._();
  static bool isMobile(BuildContext ctx)  => MediaQuery.of(ctx).size.width < 600;
  static bool isTablet(BuildContext ctx)  => MediaQuery.of(ctx).size.width < 900 && MediaQuery.of(ctx).size.width >= 600;
  static bool isDesktop(BuildContext ctx) => MediaQuery.of(ctx).size.width >= 900;
  static double width(BuildContext ctx)   => MediaQuery.of(ctx).size.width;
}

// ── Tema Material ─────────────────────────────────────────────────────────────
class AppTheme {
  AppTheme._();

  static ThemeData get light => ThemeData(
    colorScheme: ColorScheme.fromSeed(seedColor: AppColors.indigo),
    fontFamily: 'Inter',
    useMaterial3: true,
    scaffoldBackgroundColor: AppColors.bg,
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.surface,
      foregroundColor: AppColors.textPrimary,
      elevation: 0,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.indigo,
        foregroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.indigo,
        side: const BorderSide(color: AppColors.indigoBorder),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: AppColors.border)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: AppColors.border)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: AppColors.indigo, width: 1.5)),
    ),
  );
}
