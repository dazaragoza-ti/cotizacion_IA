"""
Agente de ensamble rápido (modo "rack"): valida geometría y calcula
posiciones 3D usando el catálogo de piezas real.
"""
import json
from ..clients import supabase, anthropic_client
from ..ai.tracing import anotar_run, traceable
from .catalogo_service import consultar_catalogo_piezas
from .reglas_service import obtener_ultimo_diseno, consultar_reglas_armado, consultar_correcciones_relevantes


def validar_diseno(datos_ensamble: dict, catalogo_disponible: list) -> list[str]:
    """
    Valida el JSON que devuelve Claude (guardar_diseno_3d) contra invariantes
    geométricas y de catálogo, ANTES de guardarlo en disenos_racks.
    No depende de parsear el texto libre de reglas_armado (eso requeriría un
    motor de reglas); en su lugar codifica en Python los chequeos estructurales
    que esas reglas representan. Devuelve una lista de errores; vacía = válido.
    """
    TOL = 0.05  # tolerancia en metros para comparar coordenadas (5 cm)
    errores: list[str] = []

    # --- Índice de catálogo: soporta tanto 'sku' (fallback) como 'codigo_sku' (Supabase) ---
    catalogo_por_sku = {}
    for pieza in catalogo_disponible:
        sku = pieza.get("codigo_sku") or pieza.get("sku")
        if sku:
            catalogo_por_sku[sku] = pieza

    marcos = datos_ensamble.get("marcos", []) or []
    vigas = datos_ensamble.get("vigas", []) or []
    mensulas = datos_ensamble.get("mensulas", []) or []
    numero_niveles = datos_ensamble.get("numero_niveles")
    peso_por_nivel = datos_ensamble.get("peso_maximo_por_nivel_kg")

    # --- 1. Todos los SKUs referenciados deben existir en el catálogo real ---
    for grupo, nombre_grupo in ((marcos, "marcos"), (vigas, "vigas"), (mensulas, "mensulas")):
        for item in grupo:
            sku = item.get("sku")
            if not sku:
                errores.append(f"Un elemento de '{nombre_grupo}' no tiene SKU.")
            elif sku not in catalogo_por_sku:
                errores.append(f"SKU inexistente en catálogo: '{sku}' (grupo: {nombre_grupo}).")

    # --- 2. Capacidad de carga: el peso por nivel no debe exceder lo que soportan vigas/ménsulas usadas ---
    if peso_por_nivel is not None:
        for grupo, nombre_grupo in ((vigas, "vigas"), (mensulas, "mensulas")):
            for item in grupo:
                sku = item.get("sku")
                pieza = catalogo_por_sku.get(sku)
                if pieza:
                    capacidad = pieza.get("peso_maximo_soportado_kg")
                    if capacidad is not None and peso_por_nivel > capacidad:
                        errores.append(
                            f"Sobrecarga: se pide {peso_por_nivel}kg/nivel pero '{sku}' "
                            f"({nombre_grupo}) solo soporta {capacidad}kg."
                        )

    # --- 3. Marcos: deben venir en pares simétricos en X (izquierdo/derecho) ---
    if len(marcos) >= 2:
        xs_marcos = [m.get("posicion", {}).get("x") for m in marcos if m.get("posicion")]
        xs_validos = [x for x in xs_marcos if x is not None]
        if xs_validos:
            x_min, x_max = min(xs_validos), max(xs_validos)
            if abs(x_min + x_max) > TOL:
                errores.append(
                    f"Los marcos no son simétricos respecto al centro (X): "
                    f"min={x_min}, max={x_max}."
                )
    elif len(marcos) == 1:
        # Válido solo para el módulo pre-armado de 1 nivel; si hay más de 1 nivel, falta el segundo marco.
        if numero_niveles and numero_niveles > 1:
            errores.append("Se esperaban al menos 2 marcos laterales para una estructura de varios niveles.")

    # --- 4. Niveles: la cantidad de niveles distintos en vigas debe coincidir, y Y debe crecer con el nivel ---
    if vigas and numero_niveles:
        niveles_en_vigas = sorted({v.get("nivel") for v in vigas if v.get("nivel") is not None})
        if len(niveles_en_vigas) != numero_niveles:
            errores.append(
                f"numero_niveles={numero_niveles} pero se generaron vigas para "
                f"{len(niveles_en_vigas)} nivel(es) distintos: {niveles_en_vigas}."
            )
        y_por_nivel = {}
        for v in vigas:
            nivel, y = v.get("nivel"), v.get("posicion", {}).get("y")
            if nivel is not None and y is not None:
                y_por_nivel.setdefault(nivel, []).append(y)
        niveles_ordenados = sorted(y_por_nivel.keys())
        y_previo = None
        for nivel in niveles_ordenados:
            y_actual = max(y_por_nivel[nivel])
            if y_previo is not None and y_actual <= y_previo + TOL:
                errores.append(
                    f"La altura Y no crece correctamente entre niveles: "
                    f"nivel {nivel} (Y={y_actual}) no es mayor que el nivel anterior (Y={y_previo})."
                )
            y_previo = y_actual

    # --- 5. Ménsulas: deben coincidir en Y con la viga de su mismo nivel, y en X con algún marco ---
    xs_marcos_validos = [
        m.get("posicion", {}).get("x") for m in marcos
        if m.get("posicion") and m.get("posicion", {}).get("x") is not None
    ]
    y_por_nivel_vigas = {
        v.get("nivel"): v.get("posicion", {}).get("y")
        for v in vigas if v.get("nivel") is not None and v.get("posicion")
    }
    for m in mensulas:
        nivel = m.get("nivel")
        pos = m.get("posicion", {}) or {}
        x_mensula, y_mensula = pos.get("x"), pos.get("y")

        if nivel in y_por_nivel_vigas and y_mensula is not None:
            y_viga = y_por_nivel_vigas[nivel]
            if abs(y_mensula - y_viga) > TOL:
                errores.append(
                    f"Ménsula '{m.get('sku')}' en nivel {nivel} tiene Y={y_mensula}, "
                    f"pero la viga de ese nivel está en Y={y_viga}."
                )

        if xs_marcos_validos and x_mensula is not None:
            if not any(abs(x_mensula - x_marco) <= TOL for x_marco in xs_marcos_validos):
                errores.append(
                    f"Ménsula '{m.get('sku')}' en X={x_mensula} no coincide con la posición "
                    f"de ningún marco lateral ({xs_marcos_validos})."
                )

    return errores


@traceable(name="ensamble.procesar_diseno_auto_correctivo", run_type="llm")
def procesar_diseno_auto_correctivo(comentario_usuario: str, session_id: str, vendedor_id: str) -> dict:
    """
    Lógica del Agente de Ensamble:
    Calcula el ensamble de componentes en base a las piezas reales disponibles.
    """
    catalogo_disponible = consultar_catalogo_piezas()
    diseno_previo = obtener_ultimo_diseno(session_id)

    herramienta_guardar_diseno = {
        "name": "guardar_diseno_3d",
        "description": "Registra la matriz y geometría de ensamble 3D del rack.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_rack": {"type": "string"},
                "peso_maximo_por_nivel_kg": {"type": "number"},
                "numero_niveles": {"type": "integer"},
                "marcos": {
                    "type": "array", 
                    "items": {
                        "type": "object", 
                        "properties": {
                            "sku": {"type": "string"}, 
                            "posicion": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}
                        }
                    }
                },
                "vigas": {
                    "type": "array", 
                    "items": {
                        "type": "object", 
                        "properties": {
                            "sku": {"type": "string"}, 
                            "nivel": {"type": "integer"}, 
                            "posicion": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}
                        }
                    }
                },
                "mensulas": {
                    "type": "array", 
                    "items": {
                        "type": "object", 
                        "properties": {
                            "sku": {"type": "string"}, 
                            "nivel": {"type": "integer"}, 
                            "lado": {"type": "string"}, 
                            "posicion": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}
                        }
                    }
                },
                "comentarios_adicionales": {"type": "string"}
            },
            "required": ["tipo_rack", "peso_maximo_por_nivel_kg", "numero_niveles", "marcos", "vigas", "mensulas", "comentarios_adicionales"]
        }
    }

    # --- Reglas técnicas: antes fijas en el string, ahora vienen de Supabase ---
    reglas_activas = consultar_reglas_armado(tipo_rack="todos")
    if reglas_activas:
        reglas_texto = "\n".join(
            f"- [{r.get('tipo_rack', 'todos')}] {r.get('descripcion') or r.get('accion')} "
            f"(condición: {r.get('condicion')})"
            for r in reglas_activas
        )
    else:
        # Respaldo mínimo si la tabla está vacía o falla la consulta,
        # para que el agente no se quede sin reglas base.
        reglas_texto = (
            "- [todos] Nivel 1 en Y=0.8, cada nivel siguiente sube proporcionalmente "
            "(condición: eje_y)\n"
            "- [todos] Marco izquierdo en X=-1.2, marco derecho en X=1.2 "
            "(condición: eje_x)\n"
            "- [todos] Vigas horizontales centradas en X=0, ajustadas al ancho total "
            "(condición: vigas)\n"
            "- [todos] Ménsulas acopladas exactamente sobre los marcos (X=-1.2 / X=1.2), "
            "misma altura Y que su nivel (condición: mensulas)"
        )

    # --- Correcciones históricas relevantes (Fase 1: sin vectores, filtro por tipo) ---
    # Se aplican automáticamente en cuanto el cliente las reporta la primera vez,
    # sin pasar por revisión humana.
    correcciones_previas = consultar_correcciones_relevantes(tipo_rack="todos")
    if correcciones_previas:
        correcciones_texto = "\n".join(
            f"- {c['instruccion_correctiva']}"
            + (f" (pieza: {c['pieza_afectada']})" if c.get("pieza_afectada") else "")
            for c in correcciones_previas
        )
    else:
        correcciones_texto = "- (Sin correcciones registradas todavía.)"

    system_prompt = (
        "Eres un Ingeniero CAD Senior automatizado para sistemas de racks industriales. "
        "Tu única tarea es diseñar estructuras de racks en 3D calculando posiciones físicas "
        "exactas (coordenadas X, Y, Z en metros).\n\n"
        "REGLAS TÉCNICAS DE COORDENADAS (activas, cargadas desde Supabase):\n"
        f"{reglas_texto}\n\n"
        "CORRECCIONES HISTÓRICAS RELEVANTES (aplícalas si el caso coincide; tienen prioridad "
        "sobre el criterio general porque vienen de ajustes reales que pidieron clientes antes):\n"
        f"{correcciones_texto}\n\n"
        "DETERMINACIÓN DE ESCENARIO:\n"
        "1. Si es un diseño nuevo, calcula las coordenadas desde cero basándote en el catálogo "
        "e introduce la Versión 1.\n"
        "2. Si el usuario te da un comentario de ajuste (ej: 'sube el segundo nivel 20cm'), "
        "analiza el JSON del diseño anterior, recalcula estrictamente las coordenadas 'y' "
        "afectadas para las vigas y ménsulas de ese nivel, y genera la siguiente versión "
        "manteniendo todo lo demás idéntico.\n\n"
        f"INVENTARIO TÉCNICO COMPLETO:\n{json.dumps(catalogo_disponible, indent=2)}\n"
    )

    if diseno_previo:
        system_prompt += (
            "\nESTADO: Modo Auto-corrección.\n"
            "El usuario está enviando una solicitud para modificar un diseño anterior.\n"
            "Analiza el JSON del diseño anterior provisto abajo, interpreta la orden del usuario "
            "y recalcula EXCLUSIVAMENTE los parámetros de posición Y o X de los componentes que lo requieran.\n"
            "Mantén intactos todos los demás componentes y SKUs."
        )
        prompt_usuario = f"DISEÑO ANTERIOR:\n{json.dumps(diseno_previo['matriz_ensamble_3d'])}\nCAMBIO: {comentario_usuario}"
        proxima_version = diseno_previo["version_actual"] + 1
        solicitud_inicial = diseno_previo["solicitud_original"]
        historial = diseno_previo.get("historial_comentarios", []) or []
        historial.append(comentario_usuario)
    else:
        system_prompt += (
            "\nESTADO: Modo Diseño Nuevo.\n"
            "Calcula la estructura de ensamble óptima desde cero basándote en los requerimientos del cliente."
        )
        prompt_usuario = f"Requerimiento: {comentario_usuario}"
        proxima_version = 1
        solicitud_inicial = comentario_usuario
        historial = []

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        temperature=0,
        system=system_prompt,
        tools=[herramienta_guardar_diseno],
        tool_choice={"type": "tool", "name": "guardar_diseno_3d"},
        messages=[{"role": "user", "content": prompt_usuario}]
    )

    # Sprint 2, Fase 5: esta era la 2da ruta LLM sin instrumentar del proyecto
    # (el agente rápido de ensamble, separado del proyectista PM) — mapea el
    # uso real a usage_metadata para costo y adjunta el system prompt real.
    _usage_previo = response.usage
    anotar_run(
        usage_metadata={
            "input_tokens": (_usage_previo.input_tokens or 0) if _usage_previo else 0,
            "output_tokens": (_usage_previo.output_tokens or 0) if _usage_previo else 0,
            "total_tokens": (
                ((_usage_previo.input_tokens or 0) + (_usage_previo.output_tokens or 0))
                if _usage_previo else 0
            ),
        },
        system_prompt=system_prompt,
    )

    tool_calls = [c for c in response.content if c.type == "tool_use"]
    if not tool_calls:
        raise ValueError("Claude no pudo mapear de forma estructurada las coordenadas.")
        
    datos_ensamble = tool_calls[0].input

    # --- Validación geométrica/estructural ANTES de guardar nada ---
    errores_validacion = validar_diseno(datos_ensamble, catalogo_disponible)
    if errores_validacion:
        detalle = " | ".join(errores_validacion)
        raise ValueError(f"El diseño calculado no pasó la validación de reglas: {detalle}")

    input_tokens  = response.usage.input_tokens  if response.usage else 0
    output_tokens = response.usage.output_tokens if response.usage else 0

    supabase.table("disenos_racks").insert({
        "vendedor_id": vendedor_id,
        "session_id": session_id,
        "solicitud_original": solicitud_inicial,
        "version_actual": proxima_version,
        "matriz_ensamble_3d": datos_ensamble,
        "historial_comentarios": historial,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }).execute()

    # Si fue una corrección sobre un diseño previo, la registramos en
    # correcciones_armado para que el agente la use automáticamente desde
    # la próxima vez que reciba un caso similar (sin aprobación humana).
    # Si ya existe una corrección idéntica en el mismo tipo_rack, solo
    # incrementamos veces_repetida en vez de duplicar la fila.
    if diseno_previo:
        tipo_rack_actual = datos_ensamble.get("tipo_rack", "todos")
        try:
            existente = (
                supabase.table("correcciones_armado")
                .select("id, veces_repetida")
                .eq("descripcion_error", comentario_usuario)
                .eq("tipo_rack", tipo_rack_actual)
                .limit(1)
                .execute()
            )
            if existente.data:
                fila = existente.data[0]
                supabase.table("correcciones_armado").update({
                    "veces_repetida": fila["veces_repetida"] + 1
                }).eq("id", fila["id"]).execute()
            else:
                supabase.table("correcciones_armado").insert({
                    "session_id": session_id,
                    "tipo_rack": tipo_rack_actual,
                    "pieza_afectada": None,
                    "descripcion_error": comentario_usuario,
                    "instruccion_correctiva": comentario_usuario,
                    "veces_repetida": 1,
                }).execute()
        except Exception as e:
            # No queremos que un fallo al registrar la corrección tumbe
            # la respuesta del diseño ya calculado.
            print(f"⚠️ No se pudo registrar la corrección en correcciones_armado: {e}")

    return {"version": proxima_version, "variables": datos_ensamble,
            "input_tokens": input_tokens, "output_tokens": output_tokens}
