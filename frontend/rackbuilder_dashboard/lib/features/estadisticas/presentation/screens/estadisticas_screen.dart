import "package:flutter/material.dart";
import "package:flutter_bloc/flutter_bloc.dart";
import "../../../../shared/widgets/app_widgets.dart";
import "../../domain/entities/correccion_entity.dart";
import "../../data/datasources/estadisticas_remote_datasource.dart" show camposEstadisticas;
import "../cubit/estadisticas_cubit.dart";
import "../cubit/estadisticas_state.dart";

const Map<String, String> _etiquetasCampo = {
  "veces_usado": "Más usados",
  "veces_reemplazado": "Más reemplazados",
  "veces_rechazado": "Más rechazados",
  "veces_recomendado": "Más recomendados",
};

// Una frase clara por opcion -- antes el dropdown solo mostraba la etiqueta
// y el usuario tenia que adivinar que significaba cada contador.
const Map<String, String> _explicacionCampo = {
  "veces_usado": "Piezas que Claude eligió más veces al diseñar un rack nuevo.",
  "veces_reemplazado": "Piezas que dejaron de usarse porque se sustituyeron por otra — "
      "útil para ver qué tan seguido cambia el catálogo en la práctica.",
  "veces_rechazado": "Piezas que el sistema propuso pero el cliente/vendedor terminó "
      "corrigiendo o rechazando — si una pieza se rechaza mucho, algo en su regla "
      "de selección puede estar mal.",
  "veces_recomendado": "Piezas que el sistema sugirió como mejor alternativa a otra.",
};

class EstadisticasScreen extends StatefulWidget {
  const EstadisticasScreen({super.key});
  @override State<EstadisticasScreen> createState() => _EstadisticasScreenState();
}

class _EstadisticasScreenState extends State<EstadisticasScreen> {
  final _buscarCtrl = TextEditingController();

  @override void dispose() {
    _buscarCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BlocConsumer<EstadisticasCubit, EstadisticasState>(
    listenWhen: (prev, next) =>
        next is EstadisticasLoaded &&
        next.warning != null &&
        next.warning != (prev is EstadisticasLoaded ? prev.warning : null),
    listener: (ctx, state) {
      if (state is EstadisticasLoaded && state.warning != null) {
        showAppWarning(ctx, state.warning!);
      }
    },
    builder: (ctx, state) {
      final campo = state is EstadisticasLoaded ? state.campo : camposEstadisticas.first;
      final top = state is EstadisticasLoaded ? state.top : const [];
      final busqueda = state is EstadisticasLoaded ? state.busqueda : null;
      final mensajeBusqueda = state is EstadisticasLoaded ? state.mensajeBusqueda : null;
      final correcciones = state is EstadisticasLoaded ? state.correcciones : const <CorreccionEntity>[];
      final cargandoCorrecciones = state is EstadisticasLoaded && state.cargandoCorrecciones;

      return SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text("Aprendizaje continuo",
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.textPrimary)),
        const SizedBox(height: 4),
        const Text(
          "Aquí ves lo que el sistema ha aprendido de las correcciones que hace el equipo día a día.",
          style: TextStyle(fontSize: 12, color: AppColors.textSecond),
        ),
        const SizedBox(height: 20),

        _panelComoFunciona(),
        const SizedBox(height: 16),

        PanelCard(
          title: "Correcciones aprendidas",
          subtitle: correcciones.isEmpty ? "Aún sin correcciones registradas" : "${correcciones.length} registradas",
          child: cargandoCorrecciones ? const AppShimmer()
              : correcciones.isEmpty
                  ? const AppEmptyState(icon: Icons.school_outlined, message:
                      "Todavía no hay correcciones registradas. En cuanto alguien ajuste un "
                      "diseño (por Telegram o el dashboard), aparecerán aquí.")
                  : Column(children: correcciones.map((c) => _filaCorreccion(c)).toList()),
        ),
        const SizedBox(height: 16),

        PanelCard(title: "Buscar una pieza por código", subtitle: "Historial completo de un SKU", child: Column(children: [
          const Text(
            "Escribe el código de una pieza del catálogo (ej. LRS7355) para ver su historial completo.",
            style: TextStyle(fontSize: 12, color: AppColors.textSecond),
          ),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: TextField(
              controller: _buscarCtrl,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(hintText: "Ej. LRS7355", isDense: true),
              onSubmitted: (v) => ctx.read<EstadisticasCubit>().buscarSku(v),
            )),
            const SizedBox(width: 8),
            ElevatedButton(

              onPressed: () => ctx.read<EstadisticasCubit>().buscarSku(_buscarCtrl.text),
              child: const Text("Buscar"),
            ),
          ]),
          if (mensajeBusqueda != null) Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text(mensajeBusqueda, style: const TextStyle(color: AppColors.textSecond, fontSize: 12)),
          ),
          if (busqueda != null) Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppColors.border)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(busqueda.sku, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: AppColors.indigo)),
                const SizedBox(height: 10),
                _filaContador("Usada", busqueda.vecesUsado, AppColors.indigo, _explicacionCampo["veces_usado"]!),
                _filaContador("Reemplazada", busqueda.vecesReemplazado, AppColors.emerald, _explicacionCampo["veces_reemplazado"]!),
                _filaContador("Rechazada", busqueda.vecesRechazado, AppColors.red, _explicacionCampo["veces_rechazado"]!),
                _filaContador("Recomendada", busqueda.vecesRecomendado, AppColors.amber, _explicacionCampo["veces_recomendado"]!),
              ]),
            ),
          ),
        ])),
        const SizedBox(height: 16),

        PanelCard(
          title: "Ranking de piezas", subtitle: _explicacionCampo[campo] ?? "",
          trailing: DropdownButton<String>(
            value: campo,
            underline: const SizedBox.shrink(),
            items: camposEstadisticas.map((c) => DropdownMenuItem(
              value: c, child: Text(_etiquetasCampo[c] ?? c, style: const TextStyle(fontSize: 13)),
            )).toList(),
            onChanged: (v) { if (v != null) ctx.read<EstadisticasCubit>().loadTop(campo: v); },
          ),
          child: state is EstadisticasLoading ? const AppShimmer()
              : state is EstadisticasError ? Text("Error: ${state.error}", style: const TextStyle(color: AppColors.red))
              : top.isEmpty ? const AppEmptyState(icon: Icons.query_stats, message:
                  "Sin datos todavía — se llena conforme el equipo diseña racks y hace correcciones.")
              : Column(children: top.asMap().entries.map((entry) {
                  final i = entry.key;
                  final e = entry.value;
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
                    child: Row(children: [
                      Container(
                        width: 26, height: 26, alignment: Alignment.center,
                        decoration: BoxDecoration(color: AppColors.indigoLight, borderRadius: BorderRadius.circular(8)),
                        child: Text("${i + 1}", style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12, color: AppColors.indigo)),
                      ),
                      const SizedBox(width: 10),
                      Expanded(child: Text(e.sku, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: AppColors.textPrimary))),
                      AppBadge(text: "${e.total()} eventos", bg: AppColors.indigoLight, fg: AppColors.indigo),
                    ]),
                  );
                }).toList()),
        ),
      ]));
    },
  );

  Widget _panelComoFunciona() => PanelCard(
    title: "¿Cómo aprende el sistema?", subtitle: "En 3 pasos",
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _pasoComoFunciona(1, "Alguien corrige un diseño",
          "Cuando un vendedor o ingeniero ajusta un rack (cambia una pieza, marca que dos piezas "
          "no deben ir juntas, etc.), el sistema guarda ese ajuste como una \"corrección\"."),
      _pasoComoFunciona(2, "La corrección se refuerza si se repite",
          "Si la misma corrección aparece varias veces en proyectos distintos, el sistema le sube "
          "la confianza — ya no es un caso aislado, es un patrón real."),
      _pasoComoFunciona(3, "Al repetirse mucho, se vuelve una regla automática",
          "Al llegar a 50 repeticiones, la corrección deja de depender de que el sistema \"se acuerde\" "
          "cada vez — se convierte en una regla fija que se aplica siempre, sola."),
      const SizedBox(height: 6),
      const Divider(height: 1),
      const SizedBox(height: 10),
      Wrap(spacing: 14, runSpacing: 8, children: [
        _leyendaEstado(EstadoAprendizaje.nueva, "Nueva (menos de 5 veces)"),
        _leyendaEstado(EstadoAprendizaje.importante, "Importante (5 o más)"),
        _leyendaEstado(EstadoAprendizaje.candidata, "Candidata (20 o más)"),
        _leyendaEstado(EstadoAprendizaje.permanente, "Regla permanente (50 o más)"),
      ]),
    ]),
  );

  Widget _pasoComoFunciona(int numero, String titulo, String detalle) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(
        width: 22, height: 22, alignment: Alignment.center,
        decoration: const BoxDecoration(color: AppColors.indigoLight, shape: BoxShape.circle),
        child: Text("$numero", style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.indigo)),
      ),
      const SizedBox(width: 10),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(titulo, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
        const SizedBox(height: 2),
        Text(detalle, style: const TextStyle(fontSize: 12, color: AppColors.textSecond, height: 1.35)),
      ])),
    ]),
  );

  (Color, String) _colorYEtiquetaEstado(EstadoAprendizaje estado) => switch (estado) {
    EstadoAprendizaje.nueva => (AppColors.textHint, "Nueva"),
    EstadoAprendizaje.importante => (AppColors.amber, "Importante"),
    EstadoAprendizaje.candidata => (AppColors.purple, "Candidata"),
    EstadoAprendizaje.permanente => (AppColors.emerald, "Regla permanente"),
  };

  Widget _leyendaEstado(EstadoAprendizaje estado, String texto) {
    final (color, _) = _colorYEtiquetaEstado(estado);
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
      const SizedBox(width: 6),
      Text(texto, style: const TextStyle(fontSize: 11, color: AppColors.textSecond)),
    ]);
  }

  Widget _filaCorreccion(CorreccionEntity c) {
    final (color, etiqueta) = _colorYEtiquetaEstado(c.estado);
    return Container(
      margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(c.descripcionError, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.textPrimary))),
          const SizedBox(width: 8),
          AppBadge(text: etiqueta, bg: color.withValues(alpha: 0.12), fg: color),
        ]),
        if (c.instruccionCorrectiva.isNotEmpty && c.instruccionCorrectiva != c.descripcionError) ...[
          const SizedBox(height: 4),
          Text(c.instruccionCorrectiva, style: const TextStyle(fontSize: 12, color: AppColors.textSecond)),
        ],
        const SizedBox(height: 8),
        Wrap(spacing: 6, runSpacing: 4, children: [
          if (c.piezaAfectada != null) AppBadge(text: c.piezaAfectada!, bg: AppColors.indigoLight, fg: AppColors.indigo),
          if (c.tipoRack != null) AppBadge(text: c.tipoRack!, bg: AppColors.slateLight, fg: AppColors.textSecond),
        ]),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: c.progreso.clamp(0.0, 1.0), minHeight: 6,
            backgroundColor: AppColors.slateLight,
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          c.estado == EstadoAprendizaje.permanente
              ? "Ya es una regla automática — se aplica siempre, sin depender de que se repita."
              : "Se ha repetido ${c.vecesRepetida} ${c.vecesRepetida == 1 ? "vez" : "veces"} · "
                "faltan ${c.faltanParaSiguiente} para el siguiente nivel",
          style: const TextStyle(fontSize: 11, color: AppColors.textHint),
        ),
      ]),
    );
  }

  Widget _filaContador(String etiqueta, int valor, Color color, String explicacion) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(
        width: 34, height: 34, alignment: Alignment.center,
        decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(8)),
        child: Text("$valor", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: color)),
      ),
      const SizedBox(width: 10),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(etiqueta, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
        Text(explicacion, style: const TextStyle(fontSize: 11, color: AppColors.textSecond, height: 1.3)),
      ])),
    ]),
  );
}
