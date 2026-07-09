# Ficha técnica — Postes y Cabeceras (sistema GOTA)

> **Fuente:** catálogo RACKS-PEME + lista de precios D2 ENERO 2024 + análisis
> estático FEA (SolidWorks, INGENIERÍA, dic-2025) de PM La Piedad.
>
> Esta ficha es OBLIGATORIA para que el bot elija postes/cabeceras con criterio
> técnico real. Si una recomendación contradice algo de aquí, está mal.

---

## 1) Concepto y morfología

Una **cabecera** es el marco vertical lateral del rack, formada por:
- **2 postes verticales** (perfil de acero rolado en frío, tipo "gota").
- **Cross-bracing** (diagonales + horizontales que dan rigidez al marco).
- **2 placas base** (una por poste) ancladas al piso con taquetes.

La cabecera se ensambla con **soldadura** en fábrica; al sitio llega lista.

### Dos familias (NO mezclar)

| Familia | Poste (fondo del perfil) | Cap. máx. por sección individual | Cap. compartida | Aplicación típica |
|---|---|---|---|---|
| **Carga PESADA gota** | 73 mm | **4,500 kg** | 2,250 kg | Tarimas, bobinas, almacenaje industrial pesado |
| **Carga LIGERA gota** | 38 mm | **2,500 kg** | 1,250 kg | Archivo, mueble, refacción, almacén ligero/medio |

> **"Sección individual"** = capacidad de UN marco que no comparte carga (extremo de corrida o aislado).
> **"Sección compartida"** = capacidad de un marco intermedio que recibe carga de DOS bays (los dos lados pesan sobre él, por eso se divide a la mitad).

**Regla rápida para distinguir en obra:** mira el frente del poste — 73 mm = PESADA, 38 mm = LIGERA. Si dudas, fíjate también en los REMACHES de la ménsula del larguero: pesada lleva 3 remaches, ligera lleva 2.

---

## 2) Fondos disponibles (STOCK PM)

**SOLO existen estos fondos en almacén estándar PM.** Cualquier otro fondo es especial (no se cotiza directo).

| Fondo nominal | Fondo real (mm) | Cuándo se usa |
|---|---|---|
| 61 cm  | 612 mm  | Tarima Euro 800 mm, cajas de archivo (Leford 40 cm), refacción |
| 91.5 cm| 917 mm  | Tarima americana 1000 mm de fondo (la más común en MX) |
| 123 cm | 1232 mm | Tarima americana con sobresalida, productos voluminosos |

### Cómo elegir el fondo según tarima
- Tarima **800×1200 mm** colocada con 800 al fondo → cabecera **61 cm**.
- Tarima **1000×1200 mm** colocada con 1000 al fondo → cabecera **91.5 cm**.
- Tarima con sobresalida o producto > 1 m de fondo → cabecera **123 cm**.
- **Holgura mínima recomendada:** 5-10 cm entre tarima y borde del entrepaño (para manipulación con uñas de montacargas).

---

## 3) Alturas estándar (catálogo PM)

Todas las cabeceras se fabrican en estas alturas estándar (mm de altura total del marco):

```
1226   1530   1834   2240   2443   2748   3001   3357   3665   4025
(120)  (150)  (180)  (221)  (242)  (272)  (300)  (336)  (367)  (397) cm
```

Para **alturas mayores** (rack alto), se usan **grapas unidoras** (GUS/GUD) para apilar dos cabeceras y crecer.

### Códigos por familia (referencia)

#### Cabeceras CARGA PESADA gota
- Fondo 61 cm: `CRG-7111` (120 alto) … `CRG-7120` (397 alto)
- Fondo 91.5 cm: `CRG-7131` (120) … `CRG-7140` (397)
- Fondo 123 cm: `CRG-7141` (120) … `CRG-7150` (397)

#### Cabeceras CARGA LIGERA gota
- Mismos fondos. Códigos diferentes (verificar en `catalogo_pm.json`).

> **Regla de selección de altura:** elige la altura estándar **inmediatamente superior** a la altura útil requerida (no inventes medidas). Si la altura útil son 3.50 m, usa cabecera de 367 cm (= 3.665 m).

---

## 4) Material y propiedades estructurales

Validado por análisis estático FEA (INGENIERÍA PM, diciembre 2025):

- **Material:** ASTM A36 acero rolado en frío decapado.
- **Calibre:** Cal 14 (estructura principal). Cal 22/18 solo aplica a entrepaños.
- **Densidad:** 7,850 kg/m³.
- **Módulo elástico:** 200 GPa.
- **Límite elástico:** 250 MPa (2.5 × 10⁸ N/m²).
- **Límite de tracción (ruptura):** 400 MPa.
- **Coeficiente de Poisson:** 0.26.

### Carga FEA validada (cabecera 91.5×401 carga LIGERA + larguero 242×10 sin escalón)

| Parámetro | Valor |
|---|---|
| **Carga aplicada en simulación** | **4,200 kgf** (≈ 41.2 kN) |
| Desplazamiento máx | 2.32 mm (en larguero, despreciable) |
| Tensión von Mises máx | 1,662 MPa* |

> *La tensión máxima de 1,662 MPa aparece en concentraciones puntuales de la malla
> (esquinas internas de la ménsula gota), no en el volumen del material. Esto es
> típico en FEA por singularidad geométrica y NO refleja falla. La capacidad
> operativa probada y aceptada por ingeniería es 4,200 kgf en esta configuración.

**Interpretación práctica:** la cabecera carga LIGERA admite 4,200 kgf en pruebas
controladas. El catálogo limita su uso operativo a **2,500 kg/sección individual**
para mantener un factor de seguridad ≈ 1.7 sobre la carga probada.

---

## 5) Anclaje al piso

| Altura del rack | Taquete obligatorio | Calza nivelar |
|---|---|---|
| < 4 m | Arpón **1/2" × 4½"** (`TEM-0019` / `MPR0313`) | `CNP-7931` estándar |
| ≥ 4 m | Arpón **5/8" × 6"** (`MPR0833`) — OBLIGATORIO | `RA0047` calza 4+ |

**Cantidad:** 4 taquetes por placa × 2 placas por cabecera = **8 taquetes por cabecera**.
**Calza:** 2 por cabecera (una bajo cada placa, para nivelar piso).

**Resistencia del piso:** verificar ≥ 5,000 kg/m² (firme nivelado de concreto estructural).
Si el piso no resiste, el cliente debe firmar bajo su responsabilidad o reforzar.

---

## 6) Cross-bracing (rigidez del marco)

El patrón típico PM tiene **diagonales en X (zigzag)** alternadas + horizontales
cada ~700 mm. Esto da la estabilidad longitudinal de la cabecera.

- Diagonales: solera de 1/8" × 1" (calibre 14).
- Espaciamiento: aproximadamente cada 60-80 cm (`max(3, altura_mm/700)` paneles).

Para alturas mayores a 4 m, ingeniería puede requerir **separador de cabecera**
(`SC-7415` a `SC-7411`) entre marcos contiguos, para rigidizar el conjunto a lo
largo de la corrida.

---

## 7) Reglas de decisión (USAR ESTAS al elegir cabecera)

1. **Calcula carga_modulo:** `carga_modulo = tarimas_nivel × peso_tarima × niveles`.
2. **Compara con capacidad:**
   - `carga_modulo ≤ 2,500 kg/sección` → **CARGA LIGERA gota** es suficiente.
   - `2,500 < carga_modulo ≤ 4,500` → **CARGA PESADA gota**, sección individual.
   - `carga_modulo > 4,500` → ⚠️ ALERTA: **poste sencillo no alcanza**.
     Opciones: (a) reducir niveles, (b) reducir peso por nivel, (c) cotizar
     poste DOBLE especial con ingeniería.
3. **Aplica factor de seguridad ≥ 1.5** sobre la carga requerida (estándar PM).
4. **Si el cliente especifica "carga pesada" aunque el cálculo no lo requiera,
   se entrega carga pesada** (sobre-dimensionado para uso intensivo / archivo
   institucional). Documentar en la memoria que es decisión del cliente.

### Ejemplos rápidos

| Caso | Cálculo | Recomendación |
|---|---|---|
| Tarima 800 kg, 3 tarimas/nivel, 4 niveles | 800×3×4 = 9,600 kg/módulo | ⚠️ Excede 4,500 — **reducir niveles** o usar poste doble |
| Tarima 1,000 kg, 3 tarimas/nivel, 3 niveles | 1,000×3×3 = 9,000 kg/módulo | ⚠️ Igual — reducir o doble |
| Tarima 1,000 kg, 2 tarimas/nivel, 3 niveles | 1,000×2×3 = 6,000 kg/módulo | ⚠️ Aún excede 4,500 — alertar |
| Tarima 1,000 kg, 2 tarimas/nivel, 2 niveles | 1,000×2×2 = 4,000 kg/módulo | ✅ PESADA gota OK (FS = 4,500/4,000 = 1.13 ⚠️ ajustado) |
| Caja Leford 12 kg, 5 cajas/nivel, 5 niveles | 12×5×5 = 300 kg/módulo | ✅ LIGERA gota basta y sobra (uso típico archivo) |

---

## 8) Errores típicos a EVITAR

- ❌ Especificar fondo distinto a 61 / 91.5 / 123 cm (no es stock; encarece y retrasa).
- ❌ Elegir altura no estándar (siempre escoge una de la lista oficial).
- ❌ Mezclar familias pesada/ligera en la misma corrida (no se pueden compartir postes ni accesorios — son geometrías distintas, 73 vs 38 mm).
- ❌ Olvidar el taquete 5/8" cuando rack ≥ 4 m (es el error de anclaje más común).
- ❌ No considerar que en racks ≥ 4 m la **calza** también cambia (`RA0047`, no `CNP-7931`).
- ❌ Asumir que poste sencillo aguanta > 4,500 kg/módulo. **No aguanta**; usa doble o reduce.
- ❌ Cotizar sin defensa frontal en corridas expuestas a tráfico de montacargas.

---

## 9) Para reportar en la memoria del proyecto

Cuando el bot elabore un proyecto, en `memoria` debe incluir:
- `tipo_carga`: "Carga pesada gota" o "Carga ligera gota" + razón (cálculo o spec del cliente).
- `cap_marco_kg`: capacidad publicada del marco (4500 o 2500).
- `carga_modulo_kg`: cálculo real (`tarimas_nivel × peso_tarima × niveles`).
- `factor_seguridad`: `cap_marco / carga_modulo` (debe ser ≥ 1.5).
- `anclaje`: tipo de taquete según altura.

Y en `observaciones` debe alertar explícitamente si:
- `factor_seguridad < 1.5`
- `carga_modulo > cap_marco_kg` (no debe pasar; si pasa, ALERTA EN ROJO)
- Piso del cliente no verificado (`PENDIENTE: visita al sitio para piso`)
