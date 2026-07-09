import "package:flutter/material.dart";
import "package:flutter_dotenv/flutter_dotenv.dart";
import "core/di/service_locator.dart";
import "core/theme/app_theme.dart";
import "features/dashboard/presentation/screens/dashboard_screen.dart";

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: ".env");
  await setupServiceLocator();
  runApp(const RackBuilderApp());
}

class RackBuilderApp extends StatelessWidget {
  const RackBuilderApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: "RackBuilder Dashboard",
    debugShowCheckedModeBanner: false,
    theme: AppTheme.light,
    home: const DashboardScreen(),
  );
}
