import "package:flutter/material.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../cubit/dashboard_state.dart";

class TopbarWidget extends StatelessWidget {
  final DashboardState state;
  const TopbarWidget({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final mobile  = Bp.isMobile(context);
    final connected = state is DashboardConnected;
    final reconnecting = state is DashboardConnecting;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      padding: EdgeInsets.symmetric(horizontal: mobile ? 14 : 20, vertical: mobile ? 10 : 14),
      decoration: BoxDecoration(
        color: AppColors.surface, borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.border),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 18, offset: const Offset(0, 6))],
      ),
      child: Row(children: [
        Container(
          width: mobile ? 36 : 44, height: mobile ? 36 : 44,
          decoration: BoxDecoration(
            gradient: const LinearGradient(colors: [AppColors.indigo, AppColors.indigoAccent]),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(Icons.show_chart, color: Colors.white, size: mobile ? 18 : 22),
        ),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          RichText(text: TextSpan(children: [
            TextSpan(text: "RackBuilder ", style: TextStyle(fontSize: mobile ? 14 : 18, fontWeight: FontWeight.w800, color: AppColors.textPrimary)),
            TextSpan(text: "Dashboard", style: TextStyle(fontSize: mobile ? 14 : 18, fontWeight: FontWeight.w800, color: AppColors.indigo)),
          ])),
          if (!mobile) const Text("Panel de Control, Compresión Draco y Entrenamiento de IA",
              style: TextStyle(fontSize: 12, color: AppColors.textSecond)),
        ])),
        if (reconnecting)
          const Padding(padding: EdgeInsets.only(right: 10),
              child: SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.amber))),
        ConnectionBadge(connected: connected, text: connected ? "Conexión Activa" : "Desconectado"),
      ]),
    );
  }
}
