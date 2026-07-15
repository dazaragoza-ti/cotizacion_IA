"""
Adaptador visor 3D — traduce el JSON del proyectista PM (layout/materiales)
al mismo formato (marcos/vigas/mensulas) que lee tu visor de GitHub Pages
(frontend/index.html, tabla disenos_racks).

Siempre arma el rack pieza por pieza (marco + viga + ménsula posicionados
por separado), sin importar cuántos niveles tenga — el módulo pre-armado
"(-)_RACK_180X61X151" es solo una referencia de proporciones reales para el
catálogo, no algo que se inserte como bloque completo en el ensamble.

Prioriza los SKUs REALES de la tabla catalogo_piezas (los que tienen
url_modelo_glb en Supabase Storage) para que el visor cargue el modelo .glb
de verdad en vez de caer a geometría de fallback (cajas/cilindros).

Si no hay pieza real que matchee una categoría (p. ej. todavía no hay .glb
de larguero), cae al código del despiece real del proyectista PM — el visor
sigue mostrando el rack a escala correcta, solo que esa pieza en particular
se ve con geometría de fallback en vez del modelo real.

El cargador es un caso aparte: no existe (todavía) ningún .glb real para
esta pieza en ningún proveedor -- ni el catalogo de Supabase ni el kit de
referencia del bucket de ejemplos la incluyen. Por eso, ademas del SKU,
mandamos "dimensiones" ya calculadas (en metros, a partir del fondo_mm real
de este rack) para que el visor arme un fallback geometrico con las
proporciones correctas en vez de caer al tamano generico por defecto.

El entrepano SI tiene modelo(s) real(es) en catalogo_piezas, pero en tallas
fijas de fondo (91.5cm, 123cm) que no siempre calzan con el fondo exacto de
cada diseño -- se elige la más parecida y, como con el cargador, también se
manda "dimensiones" (con el ancho real del bay) para el fallback geométrico.
No todos los racks llevan entrepano: si no hay ninguna pieza real cargada
en catalogo_piezas, simplemente no se generan (a diferencia de marco/viga/
mensula, que siempre existen como fallback del despiece del proyectista PM).

La placa soporte (base bajo cada poste) es una de las 4 piezas centrales
del kit de referencia "(-)_RACK_180X61X151" -- antes no se generaba en
absoluto. Todavía no existe un .glb real independiente para ella (solo
viene empaquetada dentro de ese kit de referencia), así que siempre cae
al fallback geométrico con dimensiones estimadas (15x15cm, 1cm de grueso
-- una placa de acero típica bajo poste, no un dato de catálogo real).
"""
from __future__ import annotations


def _sku_de(pieza: dict) -> str | None:
    """catalogo_piezas usa 'codigo_sku'; el fallback interno usa 'sku'. Soporta ambos."""
    sku = pieza.get("codigo_sku") or pieza.get("sku")
    return sku.strip() if sku else None


def _buscar_pieza_real(catalogo_piezas: list[dict], categorias: list[str], lado: str | None = None) -> str | None:
    """
    Busca en catalogo_piezas (Supabase) el SKU real más apropiado para una
    categoría (marco/mensula/larguero...), priorizando piezas que sí tengan
    url_modelo_glb (para que el visor cargue el modelo real). Devuelve el
    código SKU, o None si no hay ningún match.
    """
    candidatos = []
    for p in catalogo_piezas or []:
        sku = _sku_de(p)
        if not sku:
            continue
        texto = f"{p.get('tipo', '')} {p.get('nombre', '')} {sku}".lower()
        if any(cat in texto for cat in categorias):
            candidatos.append(p)
    if not candidatos:
        return None

    con_glb = [p for p in candidatos if (p.get("url_modelo_glb") or "").strip()]
    pool = con_glb or candidatos

    if lado:
        emparejado = [p for p in pool if lado in f"{p.get('nombre', '')} {_sku_de(p)}".lower()]
        if emparejado:
            return _sku_de(emparejado[0])

    return _sku_de(pool[0])


def _sku_representativo(materiales: list[dict], palabras_clave: list[str], default: str) -> str:
    """Fallback: busca en el despiece real del proyectista PM un código que matchee la categoría."""
    for m in materiales:
        desc = (m.get("descripcion") or "").lower()
        if any(k in desc for k in palabras_clave):
            return m.get("codigo") or default
    return default


def _buscar_entrepano(catalogo_piezas: list[dict], fondo_m: float) -> str | None:
    """Los entrepanos (tipo 'entrepano' en catalogo_piezas) vienen en tallas
    fijas de fondo (91.5cm, 123cm...) que no siempre calzan exacto con el
    fondo real de cada rack -- se elige, entre las piezas reales (con .glb),
    la que tenga longitud_metros (fondo de fabrica) mas parecido a este
    diseño. A diferencia de marco/viga/mensula, no todos los racks llevan
    entrepano, asi que si no hay ninguna pieza real cargada, se devuelve
    None y sencillamente no se generan (no hay SKU generico de respaldo)."""
    candidatos = [
        p for p in catalogo_piezas or []
        if "entrepano" in f"{p.get('tipo', '')} {p.get('nombre', '')}".lower()
        and (p.get("url_modelo_glb") or "").strip()
    ]
    if not candidatos:
        return None
    mas_cercano = min(candidatos, key=lambda p: abs((p.get("longitud_metros") or 0) - fondo_m))
    return _sku_de(mas_cercano)


def _es_carga_pesada(proyecto: dict) -> bool:
    """Misma heuristica que validator_engine._es_carga_pesada -- carga ligera
    usa tensor en vez de cargador, asi que solo se generan cargadores para
    carga pesada (default: pesada, es la mas comun)."""
    layout = proyecto.get("layout", {}) or {}
    memoria = proyecto.get("memoria", {}) or {}
    textos = " ".join([
        (proyecto.get("especificacion") or ""),
        (layout.get("tipo") or ""),
        (memoria.get("tipo_carga") or ""),
    ]).lower()
    return "ligera" not in textos


# Frentes de larguero que requieren 2 cargadores por par en vez de 1
# (misma tabla que validator_engine.FRENTES_CON_2_CARGADORES).
_FRENTES_CON_2_CARGADORES = (2804, 3104)


def layout_a_matriz_ensamble_3d(proyecto: dict, catalogo_piezas: list[dict] | None = None) -> dict:
    """
    Convierte {layout, materiales, memoria, ...} (contrato del proyectista PM)
    a {tipo_rack, peso_maximo_por_nivel_kg, numero_niveles, marcos, vigas,
    mensulas, ...} (contrato que espera disenos_racks / el visor de GitHub Pages).

    Siempre compone el rack desde cero: marcos en cada división de bay,
    largueros por nivel, ménsulas en cada extremo — sin importar si el
    diseño tiene 1 nivel o varios.

    `catalogo_piezas` es el resultado de consultar_catalogo_piezas() — la
    tabla real de Supabase con los SKUs que tienen modelo .glb. Si no se
    pasa, todo cae al código de despiece del proyectista PM (geometría de
    fallback en el visor, pero sigue siendo fiel a las medidas).
    """
    layout = proyecto.get("layout", {}) or {}
    materiales = proyecto.get("materiales", []) or []
    memoria = proyecto.get("memoria", {}) or {}
    catalogo_piezas = catalogo_piezas or []

    n_bays = layout.get("modulos_x", 1) or 1
    n_corridas = layout.get("modulos_y", 1) or 1
    frente_mm = layout.get("frente_mm", 2000) or 2000
    fondo_mm = layout.get("fondo_mm", 1000) or 1000
    pasillo_mm = layout.get("pasillo_mm", 3000) or 3000
    niveles_mm = layout.get("niveles") or [0]

    m_frente = frente_mm / 1000
    m_fondo = fondo_mm / 1000
    m_pasillo = pasillo_mm / 1000
    niveles_m = [n / 1000 for n in niveles_mm]

    # --- Elegir SKU por categoría: primero el real (con .glb), si no, el del despiece PM ---
    sku_cabecera = (
        _buscar_pieza_real(catalogo_piezas, ["marco", "cabecera"])
        or _sku_representativo(materiales, ["cabecera"], "CABECERA-PM")
    )
    sku_larguero = (
        _buscar_pieza_real(catalogo_piezas, ["larguero", "viga"])
        or _sku_representativo(materiales, ["larguero"], "LARGUERO-PM")
    )
    sku_mensula_izq = (
        _buscar_pieza_real(catalogo_piezas, ["mensula", "ménsula"], lado="izquierda")
        or _buscar_pieza_real(catalogo_piezas, ["mensula", "ménsula"])
        or _sku_representativo(materiales, ["mensula", "ménsula"], sku_larguero)
    )
    sku_mensula_der = (
        _buscar_pieza_real(catalogo_piezas, ["mensula", "ménsula"], lado="derecha")
        or _buscar_pieza_real(catalogo_piezas, ["mensula", "ménsula"])
        or _sku_representativo(materiales, ["mensula", "ménsula"], sku_larguero)
    )
    sku_cargador = (
        _buscar_pieza_real(catalogo_piezas, ["cargador"])
        or _sku_representativo(materiales, ["cargador"], "CARGADOR-PM")
    )
    sku_entrepano = _buscar_entrepano(catalogo_piezas, m_fondo)
    sku_placa = (
        _buscar_pieza_real(catalogo_piezas, ["placa"])
        or _sku_representativo(materiales, ["placa"], "PLACA-PM")
    )

    peralte_larguero_m = (layout.get("peralte_larguero_mm", 100) or 100) / 1000
    tiene_cargadores = _es_carga_pesada(proyecto)
    cargadores_por_bay = 2 if frente_mm in _FRENTES_CON_2_CARGADORES else 1
    # Dimensiones reales del cargador (ver modelo_3d.py: ancho 60mm, espesor
    # 30mm) -- el "largo" que varia por rack es el fondo, no un valor fijo de
    # catalogo, por eso se calcula aqui en vez de venir de catalogo_piezas.
    dim_cargador = {"largo": 0.06, "alto": 0.03, "profundidad": round(m_fondo, 3)}
    # El entrepano si tiene modelo real, pero su "largo" (ancho del bay) varia
    # por diseño mientras que la pieza de catalogo es de talla fija -- se manda
    # tambien "dimensiones" para que el visor escale el fallback si hiciera falta.
    dim_entrepano = {"alto": 0.02, "profundidad": round(m_fondo, 3)}
    # Placa soporte: sin .glb ni medida real de catalogo todavia -- estimado
    # razonable de una placa de acero bajo poste (15x15cm, 1cm de grueso).
    dim_placa = {"largo": 0.15, "alto": 0.01, "profundidad": 0.15}

    marcos: list[dict] = []
    vigas: list[dict] = []
    mensulas: list[dict] = []
    cargadores: list[dict] = []
    entrepanos: list[dict] = []
    placas: list[dict] = []

    for corrida in range(n_corridas):
        z_base = corrida * (m_fondo + m_pasillo)
        z_frente, z_fondo = z_base, z_base + m_fondo
        z_centro = (z_frente + z_fondo) / 2

        xs_marco = [b * m_frente for b in range(n_bays + 1)]
        for x in xs_marco:
            marcos.append({"sku": sku_cabecera, "posicion": {"x": round(x, 3), "y": 0, "z": round(z_frente, 3)}})
            marcos.append({"sku": sku_cabecera, "posicion": {"x": round(x, 3), "y": 0, "z": round(z_fondo, 3)}})
            # Placa soporte bajo cada poste (misma posicion x/z que el marco, y=0).
            placas.append({"sku": sku_placa, "posicion": {"x": round(x, 3), "y": 0, "z": round(z_frente, 3)}, "dimensiones": dim_placa})
            placas.append({"sku": sku_placa, "posicion": {"x": round(x, 3), "y": 0, "z": round(z_fondo, 3)}, "dimensiones": dim_placa})

        for nivel_idx, ny in enumerate(niveles_m[1:], start=1):
            for bay in range(n_bays):
                x1, x2 = xs_marco[bay], xs_marco[bay + 1]
                xc = (x1 + x2) / 2
                for z in (z_frente, z_fondo):
                    vigas.append({
                        "sku": sku_larguero, "nivel": nivel_idx,
                        "posicion": {"x": round(xc, 3), "y": round(ny, 3), "z": round(z, 3)},
                    })
                    mensulas.append({
                        "sku": sku_mensula_izq, "nivel": nivel_idx, "lado": "izq",
                        "posicion": {"x": round(x1, 3), "y": round(ny, 3), "z": round(z, 3)},
                    })
                    mensulas.append({
                        "sku": sku_mensula_der, "nivel": nivel_idx, "lado": "der",
                        "posicion": {"x": round(x2, 3), "y": round(ny, 3), "z": round(z, 3)},
                    })

                if tiene_cargadores:
                    # Un cargador centrado (o dos a 30%/70% del bay si el frente
                    # es ancho) -- va ENCIMA de las vigas, en medio del rack,
                    # atravesando de la fila frontal a la trasera.
                    fracciones = [0.5] if cargadores_por_bay == 1 else [0.3, 0.7]
                    for frac in fracciones:
                        cargadores.append({
                            "sku": sku_cargador, "nivel": nivel_idx,
                            "posicion": {
                                "x": round(x1 + (x2 - x1) * frac, 3),
                                "y": round(ny + peralte_larguero_m, 3),
                                "z": round(z_centro, 3),
                            },
                            "dimensiones": dim_cargador,
                        })

                if sku_entrepano:
                    # Un panel por bay por nivel, apoyado encima de las vigas
                    # (mismo "y" que el cargador), cubriendo todo el fondo.
                    entrepanos.append({
                        "sku": sku_entrepano, "nivel": nivel_idx,
                        "posicion": {
                            "x": round(xc, 3),
                            "y": round(ny + peralte_larguero_m, 3),
                            "z": round(z_centro, 3),
                        },
                        "dimensiones": {"largo": round(x2 - x1, 3), **dim_entrepano},
                    })

    return {
        "tipo_rack": proyecto.get("especificacion") or layout.get("tipo") or "Rack",
        "peso_maximo_por_nivel_kg": memoria.get("carga_nivel_kg"),
        "numero_niveles": max(len(niveles_m) - 1, 0),
        "ancho_pasillo_maniobra_metros": round(m_pasillo, 2),
        "comentarios_adicionales": (
            f"Proyecto {proyecto.get('clave', '')} — {proyecto.get('cliente', '')}. "
            f"Generado por el proyectista PM (despiece y cotización completos en Telegram)."
        ),
        "marcos": marcos,
        "vigas": vigas,
        "mensulas": mensulas,
        "cargadores": cargadores,
        "entrepanos": entrepanos,
        "placas": placas,
    }
