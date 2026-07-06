# -*- coding: utf-8 -*-
"""
Proyectista de racks — PM La Piedad / Grupo PEME.

Este módulo implementa el agente completo descrito en las instrucciones del
proyectista: prompt de sistema, catálogo, validador de reglas estructurales,
y generadores de PDF de planos, XLSX de despiece/cotización, y render 3D
determinista en HTML/Three.js.

Se mantiene separado de main.py para no inflar más ese archivo; main.py solo
importa y orquesta (llamar al modelo, guardar en Supabase, subir a Storage).

⚠️ IMPORTANTE: `CATALOGO_PM` de este archivo es un PLACEHOLDER con los códigos
que menciona el documento de instrucciones, pero SIN precios reales (no los
tengo). Reemplázalo por tu `catalogo_pm.json` real, o carga el catálogo real
en la tabla `catalogo_pm` de Supabase (ver `consultar_catalogo_pm`, que
prioriza Supabase sobre este placeholder).
"""

import io
import json
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas


# ============================================================================
# 1. SYSTEM PROMPT (verbatim de las instrucciones del proyectista)
# ============================================================================

SYSTEM_PROMPT_PM_BASE = r"""# Proyectista de racks — PM La Piedad / Grupo PEME

Eres el proyectista de **PM La Piedad / Grupo PEME**, especialista en sistemas de
racks industriales (selectivo carga pesada gota, carga ligera gota, cantilever,
entrepiso/mezanine). A partir de lo que mande el cliente —boceto, plano (PDF/DWG),
fotos del sitio, o medidas escritas— diseñas la solución y entregas: descripción
del diseño, despiece, cotización, el JSON del proyecto y un render 3D interactivo.

## Checklist OBLIGATORIO antes de responder

Antes de generar el JSON y la respuesta, **recorre esta lista paso a paso**. Si
omites un punto, el proyecto queda mal hecho. Marca explícitamente en la sección
"Memoria" u "Observaciones" cómo aplicas cada punto:

1. **¿Qué se va a almacenar?** (extraer del mensaje del cliente):
   - Si es **alimento, bebida, suplemento o agroquímico** → aplicar
     **NOM-251-SSA1-2009**: pintura horneable, superficie sin poros, sin cantos
     vivos en zonas de contacto, separación de productos de limpieza. Declararlo
     en `observaciones` con el código de la norma.
   - Si es **harina, granos, polvos**: añadir nota *"Producto sensible a humedad
     y contaminación cruzada — superficie limpiable, pintura horneable, racks
     anclados a piso para evitar movimiento durante limpieza"*.

2. **¿Hay montacargas?** (cualquier mención de montacargas, patín hidráulico,
   pasillo > 1.5 m) → aplicar **NOM-006-STPS-2023**:
   - **Defensas amarillas obligatorias** (≥ 30 cm de alto, código `DR-7452` para
     defensa grande, `DR-7451` o similar para chica). 1 defensa por cada **esquina
     expuesta a tráfico**: cabeceras al inicio de cada corrida × 2 caras = mínimo
     `2 × n_corridas` defensas, MÁS las del pasillo central si lo hay.
   - **Anclaje obligatorio** (taquetes según altura, calzas 6 por cabecera).
   - **Capacidad máxima visible** en placa metálica (1 por corrida).

3. **¿El cliente pidió pasillo central o transversal?** → Si sí:
   - Refleja el pasillo central en el `layout` (NO uses `zones`, sigue siendo
     rejilla simple, pero CUENTA los módulos a cada lado).
   - Agrega defensas adicionales en las esquinas del pasillo central.
   - Decláralo en `observaciones`.

4. **¿La altura libre del cliente cabe el rack?** → Si la altura del cliente es
   ≤ altura_total_mm, el rack NO ENTRA. Bájalo a la altura estándar inmediatamente
   inferior que sí entre.

5. **¿Validador pasaría?** → Recorre mentalmente:
   - Frente del larguero ∈ {1294, 1594, 1894, 2294, 2504, 2804, 3104} mm
   - Fondo de cabecera ∈ {612, 917, 1232} mm
   - Peralte ∈ pesada {100,125,150} / ligera {75}
   - Cargadores: 2 si frente ≥ 2804, 1 si ≤ 2504
   - Calzas: 6 por cabecera
   - Tornillos seguridad: 2 por larguero
   - Tensores (solo ligera): 1 por par de largueros

## Cómo trabajas

1. **Extrae** del material todo lo que puedas (dimensiones del almacén, ejes,
   columnas, niveles, alturas, tarima, cargas, accesos, montacargas).
2. Para lo que falte, usa el **cuestionario** (`cuestionario_selectivo.md` /
   `cuestionario_cantilever_entrepiso.md`) como guía mental.
3. Como esto responde por un bot (un solo turno), **no te quedes esperando**:
   toma supuestos razonables de ingeniería, **decláralos claramente** en una
   sección "Supuestos" y deja una lista corta de "Datos a confirmar". Solo pide
   datos antes de cotizar si falta algo realmente crítico (p. ej. no hay ninguna
   dimensión del espacio).
4. Elige piezas **del catálogo** (`catalogo_pm.json`): cabeceras, largueros,
   accesorios — con sus códigos, dimensiones y precios reales. Respeta sus reglas
   (fondos en stock 61/91.5/123 cm; largueros 272/302 requieren 2 cargadores;
   capacidades por sección; etc.).
5. Calcula cantidades del despiece según el layout (marcos = módulos+1 por corrida,
   largueros = pares por nivel por bay, entrepaños, cargadores, taquetes, grapas…).

## Fichas técnicas (USAR SIEMPRE — tienen prioridad sobre tu memoria)

En `knowledge/tecnico/` están las **fichas técnicas oficiales** de PM La Piedad,
construidas desde el catálogo PEME + análisis FEA reales + listas de precios.
**Son la verdad técnica del proyecto.** Cuando elijas o justifiques una pieza:

1. **Consulta primero la ficha técnica** correspondiente (`postes_y_cabeceras.md`,
   y las que se vayan agregando).
2. **Aplica sus reglas de decisión** (sección "Reglas de decisión" de cada ficha)
   — son obligatorias, no orientativas. Si tu cálculo sugiere algo distinto,
   ganan las fichas.
3. **Cita la ficha cuando justifiques una elección crítica** en la memoria u
   observaciones. Ej.: *"Cabecera carga PESADA elegida porque carga_modulo
   = 6,000 kg > 2,500 kg (límite de LIGERA según `postes_y_cabeceras.md` §1)."*
4. **Si detectas una contradicción** entre lo que pide el cliente y la ficha
   (p. ej. piden carga ligera con módulo de 8 t), **alerta en `observaciones`**
   con el problema y la opción correcta (no hagas ingeniería incorrecta solo
   por agradar al cliente).
5. **Si una ficha técnica no cubre algo** que necesitas decidir, decláralo en
   "Supuestos" con tu mejor criterio razonado.

Las fichas existen para evitar **errores de ingeniería**. Es preferible alertar
y proponer alternativas antes que entregar un rack mal calculado.

## Reglas estructurales OBLIGATORIAS (validador rechaza el proyecto si no cumple)

Estas reglas las verifica un validador automático tras tu respuesta. Si no las
respetas, el bot le muestra los errores al usuario y queda mal. Cúmplelas SIEMPRE:

### Medidas y stock
- **Frentes de larguero válidos**: 1294, 1594, 1894, 2294, 2504, 2804, 3104 mm
  (= 121, 151, 181, 221, 242, 272, 302 cm). NINGÚN OTRO VALOR.
- **Fondos de cabecera en stock**: 612, 917, 1232 mm (= 61, 91.5, 123 cm). Solo estos.
- **Alturas de cabecera de catálogo**: 1226, 1530, 1834, 2240, 2443, 2748, 3001,
  3357, 3665, 4025 mm. Elige la INMEDIATAMENTE SUPERIOR a la altura útil. Si
  necesitas más de 4025 mm, apila dos cabeceras con GRAPA UNIDORA POSTE (GR-7492
  para pesada, RA0063 para ligera) e inclúyela en el despiece.

### Cargadores
- **Frente ≥ 2804 mm (272 cm)**: 2 cargadores por par de largueros (NO 1).
- **Frente ≤ 2504 mm (242 cm)**: 1 cargador por par.
- **Cantidad total**: `n_bays × n_niveles × cargadores_por_par`.

### Anclaje (según altura de cabecera)
- **Cabecera ≥ 4025 mm**: usar TAQUETE 5/8" × 6" (`MPR0833`) + CALZA 4+ (`RA0047`).
  NO mezclar con taquete pequeño. 8 taquetes por cabecera (4 por placa × 2 placas).
- **Cabecera < 4025 mm**: usar TAQUETE 1/2" × 4½" (`TEM-0019` o `MPR0313`) +
  CALZA estándar (`CNP-7931`). 8 por cabecera.

### Carga vs capacidad del marco
- **Carga pesada gota**: cap. máx. **4,500 kg** por sección individual.
- **Carga ligera gota**: cap. máx. **2,500 kg** por sección individual.
- **Factor de seguridad mínimo: 1.5** sobre `carga_modulo_kg`. Es decir:
  `carga_modulo_kg ≤ cap_marco / 1.5` (pesada: ≤ 3,000 kg, ligera: ≤ 1,667 kg).
- Si `carga_modulo > cap_marco`, ALERTA en rojo y propón (a) reducir niveles,
  (b) reducir peso por nivel, o (c) poste doble especial.

### Familias — NO mezclar
- Carga PESADA: códigos `CRG-*` (cabeceras), `LRS-*`/`LRC-*` (largueros).
- Carga LIGERA: códigos `CRL-*` (cabeceras), `LRL-*` (largueros). Sin escalón NO existe en ligera.
- Mezclar pesada con ligera = error crítico (postes 73 mm vs 38 mm — geometrías distintas).

### Despiece — siempre incluir
1. **Tornillos de seguridad** `MPR0272` (5/16" × 3/4" alta resistencia):
   1 por ménsula × 2 ménsulas por larguero = 2 tornillos por larguero.
2. **Taquetes**: 8 por cabecera (según altura, ver arriba).
3. **Calzas**: **6 por cabecera** (Presentacion_producto_Racks.pdf §CHECKLIST).
4. **Cargadores** (solo carga pesada): según frente.
5. **Tensores unidores** (solo carga ligera, **OBLIGATORIO en todo ensamble**
   — Presentacion_producto_Racks.pdf §ACCESORIOS): 1 por par de largueros.

### Peraltes válidos por familia
- **Carga PESADA**: 100, 125 o 150 mm (10 / 12.5 / 15 cm). NINGÚN OTRO valor.
- **Carga LIGERA**: SOLO 75 mm (7.5 cm). Si necesitas otro peralte, usa pesada.

### Largueros — escalón
- **Carga LIGERA**: largueros SIEMPRE llevan escalón (todos vienen con escalón).
- **Carga PESADA**: con o sin escalón (sin escalón para tarima directa, con escalón si hay entrepaño).

### Entrepaños — calibres válidos
- **Carga PESADA** (alto 40 mm): calibre 22, 18 o 14.
- **Carga LIGERA** (alto 25 mm): calibre 22 o 18 (NO 14).

### NOM-006-STPS-2023 (cuando hay montacargas)
- **Defensas obligatorias** (≥ 30 cm de alto, color amarillo).
- **Capacidad máxima visible** en el rack (placa con la carga máxima).
- **Anclaje a piso obligatorio** (losa mínimo 20 cm de espesor).
- **Espejos convexos** en cruce de pasillos.

### Levantamiento — 3 datos sin los que NO hay cotización correcta
1. **Altura libre del espacio** (lámparas / A/C / anti-incendio define máximo).
2. **Frente disponible** (espacio total para racks).
3. **Fondo disponible** (con holgura para maniobra de montacargas).

Si falta uno de estos 3, declárelo en "Datos a confirmar" y propón un valor
razonable como supuesto.

## Reglas de cotización

- Precios del catálogo: **MXN, mayoreo, sin IVA**.
- Indica subtotal; menciona que **IVA, flete e instalación** se agregan aparte
  (no los incluyas salvo que el cliente lo pida).
- Usa el formato/criterios de PM (FO-DD-4.03).

## Qué entregas (FORMATO DE SALIDA — respétalo)

Responde **en este orden**:

1. **Diseño propuesto** — descripción del layout: tipo de rack, nº de filas/corridas,
   módulos por corrida, frente/fondo, niveles y alturas, pasillos, montacargas.
2. **Supuestos** y **Datos a confirmar** (si aplica).
3. **Despiece** — tabla Markdown: `Pzas | Código | Descripción | Color`.
4. **Cotización** — tabla Markdown: `Código | Descripción | Cant | P.Unit | Importe`,
   con subtotal y nota de IVA/flete/instalación.
5. **JSON del proyecto** — un único bloque ```json. **CONTRATO ESTRICTO**: usa
   EXACTAMENTE estas claves; NO las renombres ni agregues otras dentro de `layout`.
   Cualquier dato del almacén o info extra va en `memoria`/`observaciones`, NUNCA
   dentro de `layout`. (Esto es obligatorio: los generadores fallan si cambias las
   claves de `layout`.)

   ```json
   {
     "proyecto": "...", "clave": "X999", "cliente": "...",
     "elaboro": "Xocotzin", "reviso": "...", "aprobo": "...",
     "fecha": "DD/MM/AAAA", "revision": "R0",
     "material": "Acero rolado en frío",
     "especificacion": "Rack selectivo carga pesada gota",
     "calibre": "Cal 14", "dim_corte": "—",
     "layout": {
       "tipo": "Selectivo",
       "modulos_x": 8,
       "modulos_y": 3,
       "frente_mm": 2724,
       "fondo_mm": 1100,
       "pasillo_mm": 3000,
       "niveles": [0, 1800, 3600, 5400],
       "altura_total_mm": 7000,
       "peralte_larguero_mm": 150
     },
     "materiales": [
       {"pzas": 33, "codigo": "...", "descripcion": "...", "color": "...",
        "obs": "", "precio": 1640.65}
     ],
     "memoria": {"tipo_carga": "...", "tarima_lxa": "1200 x 1000", "peso_tarima_kg": 1000,
                 "tarimas_nivel": 3, "carga_nivel_kg": 3000, "carga_modulo_kg": 9000,
                 "cap_marco_kg": 4500, "factor_seguridad": 1.5,
                 "anclaje": "...", "montacargas": "..."},
     "observaciones": ["..."],
     "render_path": null
   }
   ```
   - `materiales` = despiece. Cada renglón incluye **`precio`** (unitario MXN, del
     catálogo). De aquí se generan el **XLSX de despiece** y el **XLSX de cotización**
     (importe = pzas × precio); debe coincidir con la tabla de cotización del punto 4.
   - `niveles` = lista de alturas en mm, **siempre empezando en 0**.
   - **`layout` = rejilla simple**: usa `modulos_x` (bays por corrida) y `modulos_y`
     (nº de corridas). **NO uses `zones` ni `background_image`**.
   - **El `layout` debe describir EXACTAMENTE lo que muestra el render 3D**.
   - Sigue el **nivel de detalle** de los ejemplos `ejemplo_proyecto_*.json`.

El bot toma el bloque ```json (→ planos PDF + render 3D HTML determinista +
renders PNG + XLSX de despiece y cotización). **El render 3D ya NO lo escribes
tú** — un generador determinista en Python lo construye desde la misma geometría
que dibuja el modelo 3D (postes 73mm carga pesada / 38mm ligera, x-bracing
zigzag con el número correcto de paneles, cargadores según frente, taquetes y
calzas según altura). Lo que ve el cliente es exactamente lo que se fabrica.

Esto significa que **no necesitas incluir ningún bloque ```html** — el sistema
lo arma solo. Concentra todo tu esfuerzo en (1) un layout fabricable y (2) un
despiece completo y exacto.

## Estilo

Técnico, claro y conciso, en español de México. Eres el proyectista de PM —
hablas con propiedad de ingeniería pero sin relleno.
"""


# ============================================================================
# 2. CATÁLOGO (PLACEHOLDER — reemplazar por datos reales)
# ============================================================================

# ⚠️ Precios en None = PENDIENTE. Dimensiones puestas a modo de ejemplo
# respetando los valores válidos del validador, pero NO son el catálogo real
# de PM. Súbelo a la tabla `catalogo_pm` de Supabase o reemplaza esta lista.
CATALOGO_PM_PLACEHOLDER: list[dict] = [
    # --- Cabeceras / postes — PESADA ---
    {"codigo": "CRG-1226", "descripcion": "Cabecera carga pesada 1226mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 1226, "precio": None},
    {"codigo": "CRG-1530", "descripcion": "Cabecera carga pesada 1530mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 1530, "precio": None},
    {"codigo": "CRG-1834", "descripcion": "Cabecera carga pesada 1834mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 1834, "precio": None},
    {"codigo": "CRG-2240", "descripcion": "Cabecera carga pesada 2240mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 2240, "precio": None},
    {"codigo": "CRG-2443", "descripcion": "Cabecera carga pesada 2443mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 2443, "precio": None},
    {"codigo": "CRG-2748", "descripcion": "Cabecera carga pesada 2748mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 2748, "precio": None},
    {"codigo": "CRG-3001", "descripcion": "Cabecera carga pesada 3001mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 3001, "precio": None},
    {"codigo": "CRG-3357", "descripcion": "Cabecera carga pesada 3357mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 3357, "precio": None},
    {"codigo": "CRG-3665", "descripcion": "Cabecera carga pesada 3665mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 3665, "precio": None},
    {"codigo": "CRG-4025", "descripcion": "Cabecera carga pesada 4025mm", "familia": "pesada", "categoria": "cabecera", "altura_mm": 4025, "precio": None},
    # --- Cabeceras — LIGERA ---
    {"codigo": "CRL-1226", "descripcion": "Cabecera carga ligera 1226mm", "familia": "ligera", "categoria": "cabecera", "altura_mm": 1226, "precio": None},
    {"codigo": "CRL-1834", "descripcion": "Cabecera carga ligera 1834mm", "familia": "ligera", "categoria": "cabecera", "altura_mm": 1834, "precio": None},
    {"codigo": "CRL-2240", "descripcion": "Cabecera carga ligera 2240mm", "familia": "ligera", "categoria": "cabecera", "altura_mm": 2240, "precio": None},
    # --- Largueros — PESADA (con / sin escalón) ---
    {"codigo": "LRS-1294", "descripcion": "Larguero pesado sin escalón 1294mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 1294, "precio": None},
    {"codigo": "LRC-1294", "descripcion": "Larguero pesado con escalón 1294mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 1294, "precio": None},
    {"codigo": "LRS-1594", "descripcion": "Larguero pesado sin escalón 1594mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 1594, "precio": None},
    {"codigo": "LRC-1594", "descripcion": "Larguero pesado con escalón 1594mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 1594, "precio": None},
    {"codigo": "LRS-1894", "descripcion": "Larguero pesado sin escalón 1894mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 1894, "precio": None},
    {"codigo": "LRC-1894", "descripcion": "Larguero pesado con escalón 1894mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 1894, "precio": None},
    {"codigo": "LRS-2294", "descripcion": "Larguero pesado sin escalón 2294mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 2294, "precio": None},
    {"codigo": "LRC-2294", "descripcion": "Larguero pesado con escalón 2294mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 2294, "precio": None},
    {"codigo": "LRS-2504", "descripcion": "Larguero pesado sin escalón 2504mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 2504, "precio": None},
    {"codigo": "LRC-2504", "descripcion": "Larguero pesado con escalón 2504mm", "familia": "pesada", "categoria": "larguero", "frente_mm": 2504, "precio": None},
    {"codigo": "LRS-2804", "descripcion": "Larguero pesado sin escalón 2804mm (requiere 2 cargadores)", "familia": "pesada", "categoria": "larguero", "frente_mm": 2804, "precio": None},
    {"codigo": "LRC-2804", "descripcion": "Larguero pesado con escalón 2804mm (requiere 2 cargadores)", "familia": "pesada", "categoria": "larguero", "frente_mm": 2804, "precio": None},
    {"codigo": "LRS-3104", "descripcion": "Larguero pesado sin escalón 3104mm (requiere 2 cargadores)", "familia": "pesada", "categoria": "larguero", "frente_mm": 3104, "precio": None},
    {"codigo": "LRC-3104", "descripcion": "Larguero pesado con escalón 3104mm (requiere 2 cargadores)", "familia": "pesada", "categoria": "larguero", "frente_mm": 3104, "precio": None},
    # --- Largueros — LIGERA (siempre con escalón) ---
    {"codigo": "LRL-1294", "descripcion": "Larguero ligero con escalón 1294mm", "familia": "ligera", "categoria": "larguero", "frente_mm": 1294, "precio": None},
    {"codigo": "LRL-1594", "descripcion": "Larguero ligero con escalón 1594mm", "familia": "ligera", "categoria": "larguero", "frente_mm": 1594, "precio": None},
    {"codigo": "LRL-1894", "descripcion": "Larguero ligero con escalón 1894mm", "familia": "ligera", "categoria": "larguero", "frente_mm": 1894, "precio": None},
    # --- Anclaje ---
    {"codigo": "MPR0833", "descripcion": "Taquete 5/8\" x 6\" (cabecera >= 4025mm)", "familia": "comun", "categoria": "taquete", "precio": None},
    {"codigo": "RA0047", "descripcion": "Calza 4+ (cabecera >= 4025mm)", "familia": "comun", "categoria": "calza", "precio": None},
    {"codigo": "TEM-0019", "descripcion": "Taquete 1/2\" x 4 1/2\" (cabecera < 4025mm)", "familia": "comun", "categoria": "taquete", "precio": None},
    {"codigo": "MPR0313", "descripcion": "Taquete 1/2\" x 4 1/2\" (alterno)", "familia": "comun", "categoria": "taquete", "precio": None},
    {"codigo": "CNP-7931", "descripcion": "Calza estándar (cabecera < 4025mm)", "familia": "comun", "categoria": "calza", "precio": None},
    # --- Tornillería / uniones ---
    {"codigo": "MPR0272", "descripcion": "Tornillo de seguridad 5/16\" x 3/4\" alta resistencia", "familia": "comun", "categoria": "tornillo", "precio": None},
    {"codigo": "GR-7492", "descripcion": "Grapa unidora poste (pesada, cabecera > 4025mm)", "familia": "pesada", "categoria": "grapa", "precio": None},
    {"codigo": "RA0063", "descripcion": "Grapa unidora poste (ligera, cabecera > 4025mm)", "familia": "ligera", "categoria": "grapa", "precio": None},
    # --- Cargadores ---
    {"codigo": "CRD-PESADA", "descripcion": "Cargador para larguero pesado", "familia": "pesada", "categoria": "cargador", "precio": None},
    # --- Tensores (solo ligera) ---
    {"codigo": "TEN-LIGERA", "descripcion": "Tensor unidor (obligatorio en ligera)", "familia": "ligera", "categoria": "tensor", "precio": None},
    # --- Defensas NOM-006 ---
    {"codigo": "DR-7452", "descripcion": "Defensa amarilla grande (>=30cm)", "familia": "comun", "categoria": "defensa", "precio": None},
    {"codigo": "DR-7451", "descripcion": "Defensa amarilla chica", "familia": "comun", "categoria": "defensa", "precio": None},
    # --- Entrepaños ---
    {"codigo": "ENT-PESADA-C22", "descripcion": "Entrepaño pesado (alto 40mm) calibre 22", "familia": "pesada", "categoria": "entrepano", "calibre": 22, "precio": None},
    {"codigo": "ENT-PESADA-C18", "descripcion": "Entrepaño pesado (alto 40mm) calibre 18", "familia": "pesada", "categoria": "entrepano", "calibre": 18, "precio": None},
    {"codigo": "ENT-PESADA-C14", "descripcion": "Entrepaño pesado (alto 40mm) calibre 14", "familia": "pesada", "categoria": "entrepano", "calibre": 14, "precio": None},
    {"codigo": "ENT-LIGERA-C22", "descripcion": "Entrepaño ligero (alto 25mm) calibre 22", "familia": "ligera", "categoria": "entrepano", "calibre": 22, "precio": None},
    {"codigo": "ENT-LIGERA-C18", "descripcion": "Entrepaño ligero (alto 25mm) calibre 18", "familia": "ligera", "categoria": "entrepano", "calibre": 18, "precio": None},
]

FRENTES_VALIDOS = {1294, 1594, 1894, 2294, 2504, 2804, 3104}
FONDOS_VALIDOS = {612, 917, 1232}
ALTURAS_CABECERA_CATALOGO = [1226, 1530, 1834, 2240, 2443, 2748, 3001, 3357, 3665, 4025]
PERALTES_PESADA = {100, 125, 150}
PERALTE_LIGERA = 75
CAP_MARCO_PESADA_KG = 4500
CAP_MARCO_LIGERA_KG = 2500
FACTOR_SEGURIDAD_MIN = 1.5


def consultar_catalogo_pm(supabase_client) -> list[dict]:
    """
    Trae el catálogo real de PM desde Supabase (tabla `catalogo_pm`) si existe
    y tiene datos; si no, usa el placeholder de este archivo (sin precios).
    """
    try:
        resultado = supabase_client.table("catalogo_pm").select("*").execute()
        if resultado.data and len(resultado.data) > 0:
            return resultado.data
    except Exception:
        pass
    return CATALOGO_PM_PLACEHOLDER


def construir_system_prompt_pm(catalogo: list[dict], fichas_tecnicas: str = "") -> str:
    """
    Arma el system_prompt completo: instrucciones base + catálogo disponible +
    fichas técnicas (si se proporcionan; Fase 1 pueden ir vacías/embebidas).
    """
    prompt = SYSTEM_PROMPT_PM_BASE
    prompt += f"\n\n## CATÁLOGO DISPONIBLE (`catalogo_pm.json`)\n```json\n{json.dumps(catalogo, indent=2, ensure_ascii=False)}\n```\n"
    if fichas_tecnicas:
        prompt += f"\n## FICHAS TÉCNICAS (knowledge/tecnico/)\n{fichas_tecnicas}\n"
    else:
        prompt += (
            "\n## FICHAS TÉCNICAS (knowledge/tecnico/)\n"
            "(No hay fichas técnicas cargadas todavía. Usa las reglas estructurales "
            "de este prompt como única fuente de verdad mientras tanto.)\n"
        )
    return prompt


# ============================================================================
# 3. EXTRACCIÓN DEL JSON DESDE LA RESPUESTA DE CLAUDE
# ============================================================================

def extraer_json_proyecto(texto_respuesta: str) -> tuple[dict | None, str]:
    """
    Separa la respuesta de Claude en (json_del_proyecto, texto_narrativo).
    El texto narrativo es todo lo anterior al bloque ```json (secciones 1-4:
    Diseño propuesto, Supuestos, Despiece, Cotización) — eso es lo que se le
    manda al cliente por Telegram/dashboard tal cual.
    """
    match = re.search(r"```json\s*(\{.*?\})\s*```", texto_respuesta, re.DOTALL)
    if not match:
        return None, texto_respuesta.strip()

    texto_narrativo = texto_respuesta[: match.start()].strip()
    try:
        datos = json.loads(match.group(1))
    except json.JSONDecodeError:
        datos = None
    return datos, texto_narrativo


# ============================================================================
# 4. VALIDADOR DE REGLAS ESTRUCTURALES
# ============================================================================

def _es_pesada(especificacion: str) -> bool:
    return "pesada" in (especificacion or "").lower()


def _es_ligera(especificacion: str) -> bool:
    return "ligera" in (especificacion or "").lower()


def validar_proyecto_pm(datos: dict) -> list[str]:
    """
    Recorre las reglas estructurales OBLIGATORIAS del proyectista PM.
    Devuelve una lista de errores; vacía = el proyecto puede fabricarse.
    """
    errores: list[str] = []
    layout = datos.get("layout", {}) or {}
    materiales = datos.get("materiales", []) or []
    memoria = datos.get("memoria", {}) or {}
    especificacion = datos.get("especificacion", "") or ""
    pesada = _es_pesada(especificacion)
    ligera = _es_ligera(especificacion)

    if not pesada and not ligera:
        errores.append(
            f"especificacion='{especificacion}' no deja claro si es carga PESADA o LIGERA "
            "(debe contener una de esas dos palabras)."
        )

    # --- Frente ---
    frente = layout.get("frente_mm")
    if frente not in FRENTES_VALIDOS:
        errores.append(f"frente_mm={frente} no es un valor de stock válido {sorted(FRENTES_VALIDOS)}.")

    # --- Fondo ---
    fondo = layout.get("fondo_mm")
    if fondo not in FONDOS_VALIDOS:
        errores.append(f"fondo_mm={fondo} no está en stock {sorted(FONDOS_VALIDOS)}.")

    # --- Peralte ---
    peralte = layout.get("peralte_larguero_mm")
    if pesada and peralte not in PERALTES_PESADA:
        errores.append(f"peralte_larguero_mm={peralte} inválido para carga PESADA {sorted(PERALTES_PESADA)}.")
    if ligera and peralte != PERALTE_LIGERA:
        errores.append(f"peralte_larguero_mm={peralte} inválido para carga LIGERA (debe ser {PERALTE_LIGERA}mm).")

    # --- Niveles / altura total ---
    niveles = layout.get("niveles") or []
    altura_total = layout.get("altura_total_mm")
    if not niveles:
        errores.append("layout.niveles está vacío.")
    else:
        if niveles[0] != 0:
            errores.append("niveles debe empezar en 0 (piso).")
        if any(niveles[i] >= niveles[i + 1] for i in range(len(niveles) - 1)):
            errores.append("niveles debe ser estrictamente creciente.")
        if altura_total is not None and max(niveles) > altura_total:
            errores.append(f"El nivel más alto ({max(niveles)}mm) excede altura_total_mm ({altura_total}mm).")

        # Altura de cabecera de catálogo: inmediatamente superior a la altura útil.
        altura_util = max(niveles)
        if altura_util <= ALTURAS_CABECERA_CATALOGO[-1]:
            candidatas = [a for a in ALTURAS_CABECERA_CATALOGO if a >= altura_util]
            if candidatas and altura_total is not None and altura_total not in ALTURAS_CABECERA_CATALOGO:
                errores.append(
                    f"altura_total_mm={altura_total} no es una altura de cabecera de catálogo "
                    f"{ALTURAS_CABECERA_CATALOGO}. Debería ser {min(candidatas)}mm "
                    f"(inmediatamente superior a la altura útil {altura_util}mm)."
                )
        else:
            # Requiere apilar 2 cabeceras con grapa unidora poste.
            grapa_esperada = "GR-7492" if pesada else "RA0063"
            if not any(m.get("codigo") == grapa_esperada for m in materiales):
                errores.append(
                    f"altura_util={altura_util}mm > {ALTURAS_CABECERA_CATALOGO[-1]}mm: se requiere apilar "
                    f"dos cabeceras con grapa unidora poste ('{grapa_esperada}') en el despiece."
                )

    n_bays = layout.get("modulos_x") or 0
    n_corridas = layout.get("modulos_y") or 0
    n_niveles_usables = max(len(niveles) - 1, 0)
    n_cabeceras = n_corridas * (n_bays + 1)

    # --- Cargadores (solo carga pesada) ---
    if pesada and frente is not None:
        cargadores_por_par = 2 if frente >= 2804 else 1
        cargadores_esperados = n_bays * n_niveles_usables * cargadores_por_par
        cargadores_en_despiece = sum(
            m.get("pzas", 0) for m in materiales
            if (m.get("codigo") or "").upper().startswith("CRD") or "cargador" in (m.get("descripcion") or "").lower()
        )
        if cargadores_esperados > 0 and cargadores_en_despiece != cargadores_esperados:
            errores.append(
                f"Cargadores en despiece ({cargadores_en_despiece}) no coincide con lo esperado "
                f"({cargadores_esperados} = {n_bays} bays × {n_niveles_usables} niveles × "
                f"{cargadores_por_par} cargador(es)/par, por frente={frente}mm)."
            )

    # --- Anclaje: taquetes y calzas ---
    altura_max_cabecera = max(niveles) if niveles else 0
    usa_taquete_grande = altura_max_cabecera >= 4025 or (altura_total or 0) >= 4025
    codigo_taquete_esperado = "MPR0833" if usa_taquete_grande else ("TEM-0019", "MPR0313")
    tiene_taquete = any(
        (m.get("codigo") == codigo_taquete_esperado) if isinstance(codigo_taquete_esperado, str)
        else (m.get("codigo") in codigo_taquete_esperado)
        for m in materiales
    )
    if n_cabeceras > 0 and not tiene_taquete:
        errores.append(
            f"Falta el taquete correcto en el despiece para altura de cabecera "
            f"{'>= 4025mm (MPR0833)' if usa_taquete_grande else '< 4025mm (TEM-0019 o MPR0313)'}."
        )
    taquetes_totales = sum(
        m.get("pzas", 0) for m in materiales if "taquete" in (m.get("descripcion") or "").lower()
    )
    if n_cabeceras > 0 and taquetes_totales != n_cabeceras * 8:
        errores.append(f"Taquetes totales ({taquetes_totales}) debería ser 8 × n_cabeceras ({n_cabeceras * 8}).")

    calzas_totales = sum(
        m.get("pzas", 0) for m in materiales if "calza" in (m.get("descripcion") or "").lower()
    )
    if n_cabeceras > 0 and calzas_totales != n_cabeceras * 6:
        errores.append(f"Calzas totales ({calzas_totales}) debería ser 6 × n_cabeceras ({n_cabeceras * 6}).")

    # --- Tornillos de seguridad: 2 por larguero ---
    n_largueros = n_bays * n_corridas * n_niveles_usables * 2  # 2 largueros por par, por bay, por nivel, por corrida
    tornillos_totales = sum(
        m.get("pzas", 0) for m in materiales if m.get("codigo") == "MPR0272"
    )
    tornillos_esperados = n_largueros * 2
    if n_largueros > 0 and tornillos_totales != tornillos_esperados:
        errores.append(
            f"Tornillos de seguridad MPR0272 ({tornillos_totales}) debería ser "
            f"2 × n_largueros = {tornillos_esperados}."
        )

    # --- Tensores obligatorios en carga ligera ---
    if ligera:
        tensores_totales = sum(
            m.get("pzas", 0) for m in materiales if "tensor" in (m.get("descripcion") or "").lower()
        )
        pares_largueros_esperados = n_bays * n_corridas * n_niveles_usables
        if pares_largueros_esperados > 0 and tensores_totales < pares_largueros_esperados:
            errores.append(
                f"Faltan tensores unidores (obligatorios en carga ligera): hay {tensores_totales}, "
                f"se esperaban al menos {pares_largueros_esperados} (1 por par de largueros)."
            )

    # --- Familias no mezcladas ---
    prefijos_pesada = ("CRG-", "LRS-", "LRC-")
    prefijos_ligera = ("CRL-", "LRL-")
    tiene_pesada = any((m.get("codigo") or "").startswith(prefijos_pesada) for m in materiales)
    tiene_ligera = any((m.get("codigo") or "").startswith(prefijos_ligera) for m in materiales)
    if tiene_pesada and tiene_ligera:
        errores.append("El despiece mezcla piezas de familia PESADA y LIGERA (postes 73mm vs 38mm no son compatibles).")
    if pesada and tiene_ligera:
        errores.append("especificacion es PESADA pero el despiece incluye piezas de familia LIGERA.")
    if ligera and tiene_pesada:
        errores.append("especificacion es LIGERA pero el despiece incluye piezas de familia PESADA.")

    # --- Capacidad vs carga (memoria) ---
    carga_modulo = memoria.get("carga_modulo_kg")
    cap_marco = memoria.get("cap_marco_kg")
    if carga_modulo is not None:
        cap_max_familia = CAP_MARCO_PESADA_KG if pesada else (CAP_MARCO_LIGERA_KG if ligera else None)
        if cap_marco is not None and cap_max_familia is not None and cap_marco > cap_max_familia:
            errores.append(f"cap_marco_kg={cap_marco} excede el máximo de la familia ({cap_max_familia}kg).")
        cap_referencia = cap_marco or cap_max_familia
        if cap_referencia is not None and carga_modulo > cap_referencia / FACTOR_SEGURIDAD_MIN:
            errores.append(
                f"carga_modulo_kg={carga_modulo} excede el límite con factor de seguridad "
                f"{FACTOR_SEGURIDAD_MIN} (máximo permitido: {cap_referencia / FACTOR_SEGURIDAD_MIN:.0f}kg "
                f"sobre cap_marco_kg={cap_referencia})."
            )

    # --- Entrepaños: calibre válido ---
    for m in materiales:
        desc = (m.get("descripcion") or "").lower()
        if "entrepañ" in desc or "entrepan" in desc:
            cal_match = re.search(r"calibre\s*(\d+)", desc)
            if cal_match:
                calibre = int(cal_match.group(1))
                if pesada and calibre not in (14, 18, 22):
                    errores.append(f"Entrepaño '{m.get('codigo')}' calibre {calibre} inválido para PESADA (14/18/22).")
                if ligera and calibre not in (18, 22):
                    errores.append(f"Entrepaño '{m.get('codigo')}' calibre {calibre} inválido para LIGERA (18/22, no 14).")

    # --- Materiales sin precio (aviso, no bloqueante si viene del placeholder) ---
    sin_precio = [m.get("codigo") for m in materiales if m.get("precio") in (None, 0)]
    if sin_precio:
        errores.append(
            f"AVISO (no crítico): {len(sin_precio)} renglón(es) sin precio real: {sin_precio}. "
            "Verifica el catálogo antes de enviar la cotización al cliente."
        )

    return errores


# ============================================================================
# 5. GENERADOR DE XLSX — DESPIECE Y COTIZACIÓN
# ============================================================================

_FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
_FILL_HEADER = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
_FONT_BODY = Font(name="Calibri", size=10)
_BORDER_THIN = Border(*(Side(style="thin", color="D1D5DB"),) * 4)


def _autosize(ws):
    for col_cells in ws.columns:
        length = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max(length + 3, 10), 60)


def generar_xlsx_despiece(datos: dict) -> bytes:
    """Genera el XLSX de despiece: Pzas | Código | Descripción | Color."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Despiece"

    ws.append([f"Proyecto: {datos.get('proyecto', '')}", "", f"Clave: {datos.get('clave', '')}", ""])
    ws.append([f"Cliente: {datos.get('cliente', '')}", "", f"Fecha: {datos.get('fecha', '')}", ""])
    ws.append([])

    headers = ["Pzas", "Código", "Descripción", "Color", "Obs"]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = _FONT_HEADER
        cell.fill = _FILL_HEADER
        cell.alignment = Alignment(horizontal="center")

    for m in datos.get("materiales", []) or []:
        ws.append([
            m.get("pzas", 0), m.get("codigo", ""), m.get("descripcion", ""),
            m.get("color", ""), m.get("obs", ""),
        ])
        for cell in ws[ws.max_row]:
            cell.font = _FONT_BODY
            cell.border = _BORDER_THIN

    _autosize(ws)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generar_xlsx_cotizacion(datos: dict) -> bytes:
    """Genera el XLSX de cotización: Código | Descripción | Cant | P.Unit | Importe + subtotal."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Cotización"

    ws.append([f"Proyecto: {datos.get('proyecto', '')}", "", f"Clave: {datos.get('clave', '')}"])
    ws.append([f"Cliente: {datos.get('cliente', '')}", "", f"Fecha: {datos.get('fecha', '')}"])
    ws.append([])

    headers = ["Código", "Descripción", "Cant", "P.Unit (MXN)", "Importe (MXN)"]
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = _FONT_HEADER
        cell.fill = _FILL_HEADER
        cell.alignment = Alignment(horizontal="center")

    subtotal = 0.0
    for m in datos.get("materiales", []) or []:
        pzas = m.get("pzas", 0) or 0
        precio = m.get("precio") or 0
        importe = pzas * precio
        subtotal += importe
        ws.append([m.get("codigo", ""), m.get("descripcion", ""), pzas, precio, importe])
        row = ws[ws.max_row]
        row[3].number_format = '"$"#,##0.00'
        row[4].number_format = '"$"#,##0.00'
        for cell in row:
            cell.font = _FONT_BODY
            cell.border = _BORDER_THIN

    ws.append([])
    ws.append(["", "", "", "Subtotal (MXN, s/IVA):", subtotal])
    subtotal_row = ws[ws.max_row]
    subtotal_row[3].font = Font(bold=True)
    subtotal_row[4].font = Font(bold=True)
    subtotal_row[4].number_format = '"$"#,##0.00'
    ws.append(["", "", "", "IVA, flete e instalación se cotizan aparte.", ""])
    ws[ws.max_row][3].font = Font(italic=True, size=9, color="64748B")

    _autosize(ws)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ============================================================================
# 6. GENERADOR DE PDF DE PLANOS (vista superior determinista)
# ============================================================================

def generar_pdf_planos(datos: dict) -> bytes:
    """
    Dibuja un plano en vista superior (top-down) desde `layout`: corridas,
    bays, pasillo central, con acotación y cuadro de datos del proyecto.
    """
    layout = datos.get("layout", {}) or {}
    n_bays = layout.get("modulos_x", 1) or 1
    n_corridas = layout.get("modulos_y", 1) or 1
    frente_mm = layout.get("frente_mm", 2000) or 2000
    fondo_mm = layout.get("fondo_mm", 1000) or 1000
    pasillo_mm = layout.get("pasillo_mm", 3000) or 3000

    buf = io.BytesIO()
    page_w, page_h = landscape(A4)
    c = pdf_canvas.Canvas(buf, pagesize=landscape(A4))

    margin = 15 * mm
    dibujo_w = page_w - 2 * margin
    dibujo_h = page_h - 2 * margin - 30 * mm  # deja espacio al cuadro de datos

    ancho_total_mm = n_bays * frente_mm
    fondo_total_mm = n_corridas * fondo_mm + max(n_corridas - 1, 0) * pasillo_mm
    escala = min(dibujo_w / ancho_total_mm, dibujo_h / fondo_total_mm) * 0.92

    origen_x = margin + (dibujo_w - ancho_total_mm * escala) / 2
    origen_y = margin + 30 * mm

    # --- Título ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, page_h - margin, f"{datos.get('proyecto', 'Proyecto')} — Plano en planta")
    c.setFont("Helvetica", 9)
    c.drawString(margin, page_h - margin - 14, f"Clave: {datos.get('clave', '—')}   Cliente: {datos.get('cliente', '—')}   Fecha: {datos.get('fecha', '—')}   Rev: {datos.get('revision', '—')}")

    # --- Corridas y bays ---
    c.setLineWidth(1)
    y_cursor = origen_y
    for corrida in range(n_corridas):
        x_cursor = origen_x
        for bay in range(n_bays):
            c.setFillColorRGB(0.93, 0.93, 0.97)
            c.rect(x_cursor, y_cursor, frente_mm * escala, fondo_mm * escala, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            x_cursor += frente_mm * escala
        # Etiqueta de corrida
        c.setFont("Helvetica-Bold", 8)
        c.drawString(origen_x - 12 * mm, y_cursor + (fondo_mm * escala) / 2 - 3, f"C{corrida + 1}")
        y_cursor += fondo_mm * escala
        if corrida < n_corridas - 1:
            # Pasillo entre corridas
            c.setDash(3, 3)
            c.setStrokeColorRGB(0.6, 0.6, 0.6)
            c.rect(origen_x, y_cursor, ancho_total_mm * escala, pasillo_mm * escala, fill=0, stroke=1)
            c.setStrokeColorRGB(0, 0, 0)
            c.setDash()
            c.setFont("Helvetica-Oblique", 7)
            c.drawCentredString(origen_x + (ancho_total_mm * escala) / 2, y_cursor + (pasillo_mm * escala) / 2 - 3,
                                 f"Pasillo {pasillo_mm}mm")
            y_cursor += pasillo_mm * escala

    # --- Acotación general ---
    c.setFont("Helvetica", 7)
    c.drawCentredString(origen_x + (ancho_total_mm * escala) / 2, origen_y - 10,
                         f"Frente total: {ancho_total_mm}mm ({n_bays} módulos x {frente_mm}mm)")
    c.saveState()
    c.translate(origen_x - 22, origen_y + (fondo_total_mm * escala) / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, f"Fondo total: {fondo_total_mm}mm")
    c.restoreState()

    # --- Cuadro de datos ---
    cuadro_y = margin
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, cuadro_y + 12, "Elaboró:")
    c.drawString(margin + 110, cuadro_y + 12, "Revisó:")
    c.drawString(margin + 220, cuadro_y + 12, "Aprobó:")
    c.setFont("Helvetica", 8)
    c.drawString(margin, cuadro_y, str(datos.get("elaboro", "—")))
    c.drawString(margin + 110, cuadro_y, str(datos.get("reviso", "—")))
    c.drawString(margin + 220, cuadro_y, str(datos.get("aprobo", "—")))
    c.drawString(margin + 340, cuadro_y + 12, f"Especificación: {datos.get('especificacion', '—')}")
    c.drawString(margin + 340, cuadro_y, f"Material: {datos.get('material', '—')}  {datos.get('calibre', '')}")

    c.showPage()
    c.save()
    return buf.getvalue()


# ============================================================================
# 7. RENDER 3D DETERMINISTA (HTML + Three.js)
# ============================================================================

def generar_render_3d_html(datos: dict) -> str:
    """
    Construye un render 3D determinista en HTML/Three.js a partir de `layout`.
    No es CAD de fabricación pixel-perfect, pero refleja fielmente: número de
    marcos/corridas/bays, alturas de niveles, postes 73mm (pesada) / 38mm
    (ligera), largueros por nivel, cargadores extra si frente >= 2804mm, y
    cruces (x-bracing) en zigzag entre postes frontal/trasero de cada marco.
    """
    layout = datos.get("layout", {}) or {}
    especificacion = datos.get("especificacion", "") or ""
    pesada = _es_pesada(especificacion)

    n_bays = layout.get("modulos_x", 1) or 1
    n_corridas = layout.get("modulos_y", 1) or 1
    frente_mm = layout.get("frente_mm", 2000) or 2000
    fondo_mm = layout.get("fondo_mm", 1000) or 1000
    pasillo_mm = layout.get("pasillo_mm", 3000) or 3000
    niveles = layout.get("niveles") or [0]
    altura_total = layout.get("altura_total_mm") or max(niveles)

    radio_poste = 0.073 if pesada else 0.038
    color_poste = "0xd97706" if pesada else "0x2563eb"
    dos_cargadores = frente_mm >= 2804

    # Convertimos a metros para Three.js
    m_frente = frente_mm / 1000
    m_fondo = fondo_mm / 1000
    m_pasillo = pasillo_mm / 1000
    m_niveles = [n / 1000 for n in niveles]
    m_altura = altura_total / 1000

    geometria_json = json.dumps({
        "n_bays": n_bays, "n_corridas": n_corridas,
        "frente": m_frente, "fondo": m_fondo, "pasillo": m_pasillo,
        "niveles": m_niveles, "altura": m_altura,
        "radio_poste": radio_poste, "color_poste": color_poste,
        "dos_cargadores": dos_cargadores, "pesada": pesada,
    })

    proyecto_nombre = (datos.get("proyecto") or "Proyecto").replace("<", "").replace(">", "")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Render 3D — {proyecto_nombre}</title>
<style>
  html, body {{ margin:0; height:100%; background:#0f172a; overflow:hidden; font-family: sans-serif; }}
  #info {{ position:absolute; top:10px; left:10px; color:#e2e8f0; font-size:12px; z-index:10; background:rgba(15,23,42,.7); padding:8px 12px; border-radius:8px; }}
</style>
</head>
<body>
<div id="info">{proyecto_nombre} — render determinista desde layout</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const G = {geometria_json};

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f172a);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 0.1, 1000);
const anchoTotal = G.n_bays * G.frente;
const fondoTotal = G.n_corridas * G.fondo + Math.max(G.n_corridas-1,0) * G.pasillo;
camera.position.set(anchoTotal*0.9, G.altura*1.6, fondoTotal*1.6 + anchoTotal*0.4);

const renderer = new THREE.WebGLRenderer({{antialias:true}});
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(anchoTotal/2, G.altura/2, fondoTotal/2);
controls.update();

scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const dir = new THREE.DirectionalLight(0xffffff, 0.8);
dir.position.set(5, 10, 5);
scene.add(dir);

const matPoste = new THREE.MeshStandardMaterial({{color: parseInt(G.color_poste)}});
const matViga = new THREE.MeshStandardMaterial({{color: 0x94a3b8}});
const matCruz = new THREE.MeshStandardMaterial({{color: 0x475569}});
const matPiso = new THREE.MeshStandardMaterial({{color: 0x1e293b}});

scene.add(new THREE.Mesh(new THREE.PlaneGeometry(anchoTotal*1.4, fondoTotal*1.4), matPiso).rotateX(-Math.PI/2).translateZ(0));

function poste(x, y, z, alto) {{
  const geo = new THREE.CylinderGeometry(G.radio_poste, G.radio_poste, alto, 12);
  const mesh = new THREE.Mesh(geo, matPoste);
  mesh.position.set(x, y + alto/2, z);
  scene.add(mesh);
}}

function viga(x1, x2, y, z) {{
  const largo = Math.abs(x2 - x1);
  const geo = new THREE.BoxGeometry(largo, 0.08, 0.05);
  const mesh = new THREE.Mesh(geo, matViga);
  mesh.position.set((x1+x2)/2, y, z);
  scene.add(mesh);
}}

function cruzZigzag(x, z1, z2, yBase, yTope) {{
  const puntos1 = [new THREE.Vector3(x, yBase, z1), new THREE.Vector3(x, yTope, z2)];
  const puntos2 = [new THREE.Vector3(x, yBase, z2), new THREE.Vector3(x, yTope, z1)];
  [puntos1, puntos2].forEach(p => {{
    const geo = new THREE.BufferGeometry().setFromPoints(p);
    scene.add(new THREE.Line(geo, new THREE.LineBasicMaterial({{color: 0x475569}})));
  }});
}}

for (let corrida = 0; corrida < G.n_corridas; corrida++) {{
  const zBase = corrida * (G.fondo + G.pasillo);
  const zFrente = zBase;
  const zFondo = zBase + G.fondo;

  // Marcos (postes en pares frente/fondo) en cada división de bay
  for (let m = 0; m <= G.n_bays; m++) {{
    const x = m * G.frente;
    poste(x, 0, zFrente, G.altura);
    poste(x, 0, zFondo, G.altura);

    // Cruces (x-bracing) en zigzag entre niveles, en el plano frente-fondo
    for (let n = 0; n < G.niveles.length - 1; n++) {{
      cruzZigzag(x, zFrente, zFondo, G.niveles[n], G.niveles[n+1]);
    }}

    // Cargador extra si frente >= 2804mm: poste intermedio a media altura de cada nivel
    if (G.dos_cargadores && m < G.n_bays) {{
      const xMedio = x + G.frente/2;
      G.niveles.slice(1).forEach(ny => {{
        const geo = new THREE.BoxGeometry(0.05, 0.05, G.fondo);
        const mesh = new THREE.Mesh(geo, matCruz);
        mesh.position.set(xMedio, ny, (zFrente+zFondo)/2);
        scene.add(mesh);
      }});
    }}
  }}

  // Largueros (vigas horizontales) por nivel, uniendo cada par de marcos consecutivos
  G.niveles.slice(1).forEach(ny => {{
    for (let m = 0; m < G.n_bays; m++) {{
      const x1 = m * G.frente, x2 = (m+1) * G.frente;
      viga(x1, x2, ny, zFrente);
      viga(x1, x2, ny, zFondo);
    }}
  }});
}}

function animate() {{
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}}
animate();

window.addEventListener('resize', () => {{
  camera.aspect = window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}});
</script>
</body>
</html>"""
