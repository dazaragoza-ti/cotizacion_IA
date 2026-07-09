"""Cuestionario interactivo para recolectar datos OBLIGATORIOS antes de cotizar.

Datos obligatorios (definidos por Xocotzin):
  1. Producto a almacenar (qué se va a guardar)
  2. Dimensiones del espacio (frente, fondo, altura libre)
  3. Tarima / unidad de carga (medidas, peso, cuántas por nivel)
  4. Montacargas y pasillo (tipo y ancho)

Modo híbrido:
  - Si todos OK → procede directo a generar el proyecto.
  - Si faltan 1-3 → mensaje agrupado con todas las preguntas.
  - Si faltan 4 → cuestionario guiado paso a paso.

Estado por usuario en memoria. Archivos se pueden mandar en cualquier momento.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

log = logging.getLogger("cuestionario")


# ── Definición de los 4 datos críticos ─────────────────────────────────────
@dataclass
class CampoCritico:
    key: str                 # identificador interno
    nombre: str              # nombre humano (para preguntar)
    pregunta_corta: str      # para modo agrupado
    pregunta_larga: str      # para modo guiado
    palabras_clave: list[str]  # patrones para detectar si ya está mencionado
    regex_numerico: str | None = None  # regex para detectar valores numéricos


CAMPOS = [
    CampoCritico(
        key="producto",
        nombre="Producto a almacenar",
        pregunta_corta="¿Qué vas a almacenar? (producto, material, mercancía)",
        pregunta_larga=(
            "📦 **¿Qué vas a almacenar?**\n\n"
            "Necesito saber qué producto guardarás: harina, refacciones, archivo, "
            "muebles, granel, etc. Esto define si aplica alguna norma sanitaria "
            "(NOM-251) o de seguridad."
        ),
        palabras_clave=[
            r"alimento", r"h?arina", r"granel", r"grano", r"refacci",
            r"mueble", r"archivo", r"caja", r"producto", r"mercanc",
            r"material", r"insumo", r"empaque", r"electr[oó]nic",
            r"bebida", r"botella", r"\bsal\b", r"az[uú]car", r"cereal",
            r"polvo", r"qu[ií]mico", r"farmac", r"medicament", r"textil",
            r"ropa", r"calzado", r"tornill", r"pieza", r"refrigera",
            r"l[aá]cteo", r"carne", r"verdura", r"fruta", r"l[ií]quido",
            r"papel", r"libro", r"document", r"computa", r"servidor",
            r"agroqu[ií]m", r"fertilizante", r"plaguicida", r"pintura",
            r"herramienta", r"juguete", r"bobina", r"rollo",
            r"automotr[ií]z", r"refacciones",
            # Tolerancia a errores: "tarima de X" donde X es el producto
            r"tarimas?\s+de\s+\w{3,}",   # "tarima de arina/harina/cualquiercosa"
            r"sacos?\s+de\s+\w{3,}",
            r"costales?\s+de\s+\w{3,}",
            r"cajas?\s+de\s+\w{3,}",
            r"bultos?\s+de\s+\w{3,}",
        ],
    ),
    CampoCritico(
        key="dimensiones_espacio",
        nombre="Dimensiones del espacio",
        pregunta_corta=(
            "¿Cuáles son las dimensiones del espacio? "
            "(frente, fondo y altura libre)"
        ),
        pregunta_larga=(
            "📐 **Dimensiones del espacio**\n\n"
            "Necesito 3 datos del lugar:\n"
            "• **Frente** (ancho disponible para los racks)\n"
            "• **Fondo** (profundidad)\n"
            "• **Altura libre** (la MÁS BAJA: lámparas, A/C, sistema anti-incendio)\n\n"
            "Ejemplo: *\"10 m de frente, 8 m de fondo, 6 m de altura libre\"*."
        ),
        palabras_clave=[
            r"\d+\s*(m|metros|cm)\s*(de|x|por|×)",  # "10m x 8m" o "10 metros de"
            r"frente.{0,20}\d", r"fondo.{0,20}\d", r"largo.{0,20}\d",
            r"ancho.{0,20}\d", r"altura.{0,20}\d", r"alto.{0,20}\d",
            r"\d+\s*(x|×)\s*\d+",
            r"bodega.{0,30}\d", r"espacio.{0,30}\d", r"\d+\s*m[²2]",
        ],
        regex_numerico=r"\d+(\.\d+)?\s*(m|metros)\b",
    ),
    CampoCritico(
        key="tarima",
        nombre="Tarima / unidad de carga",
        pregunta_corta=(
            "¿Cómo es la unidad de carga? "
            "(tarima/caja: medidas, peso, cuántas por nivel)"
        ),
        pregunta_larga=(
            "🪵 **Unidad de carga**\n\n"
            "Necesito:\n"
            "• **Medidas** de la tarima/caja (largo × ancho)\n"
            "• **Peso** por unidad\n"
            "• **Cuántas** por nivel/módulo\n\n"
            "Ejemplo: *\"tarima 1.2 × 1.0 m, 1 tonelada, 2 por nivel\"*."
        ),
        palabras_clave=[
            r"tarima", r"pallet", r"paleta", r"caja", r"bulto", r"saco",
            r"costal", r"tambo", r"contenedor", r"unidad", r"bolsa",
            r"a granel", r"al granel",
            r"\d+\s*(kg|kilos|kilogramo|ton|tonelada)",
            r"\d+\s*(x|por|×)\s*\d+",
            r"peso", r"carga",
        ],
        regex_numerico=r"\d+(\.\d+)?\s*(kg|kilos|ton|tonelada)",
    ),
    CampoCritico(
        key="montacargas",
        nombre="Montacargas y pasillo",
        pregunta_corta=(
            "¿Qué tipo de montacargas usarás y qué ancho de pasillo necesita?"
        ),
        pregunta_larga=(
            "🚛 **Montacargas y pasillo**\n\n"
            "Necesito:\n"
            "• **Tipo de montacargas**: contrabalanceado / reach truck / "
            "pasillo angosto (VNA) / apilador / patín / manual.\n"
            "• **Ancho de pasillo** requerido.\n\n"
            "Si no hay montacargas (acceso manual o patín), dímelo también — "
            "cambia las defensas que se cotizan (NOM-006)."
        ),
        palabras_clave=[
            r"montacarga", r"reach", r"contrabalan", r"VNA",
            r"pasillo.{0,30}\d", r"apilador", r"pat[ií]n",
            r"manual", r"diablo", r"traspaleta",
            r"angosto", r"acceso", r"circulaci[oó]n",
        ],
        regex_numerico=None,
    ),
]


# ── Estado por usuario ─────────────────────────────────────────────────────
@dataclass
class EstadoUsuario:
    """Estado del cuestionario para un usuario.

    Acumula texto y archivos hasta tener los 4 datos críticos.
    """
    texto_acumulado: str = ""
    campos_recolectados: set[str] = field(default_factory=set)
    modo_guiado: bool = False
    siguiente_pregunta_idx: int = 0  # índice en CAMPOS, solo en modo guiado

    def agregar_texto(self, txt: str) -> None:
        if not txt:
            return
        self.texto_acumulado += "\n" + txt
        # Re-evaluar qué campos ya tenemos
        self.campos_recolectados = detectar_campos_presentes(self.texto_acumulado)

    @property
    def faltantes(self) -> list[CampoCritico]:
        return [c for c in CAMPOS if c.key not in self.campos_recolectados]

    @property
    def completo(self) -> bool:
        return len(self.faltantes) == 0


# Estado global (por user_id). En producción podría persistir, por ahora memoria.
_ESTADOS: dict[int, EstadoUsuario] = {}


def estado_de(uid: int) -> EstadoUsuario:
    if uid not in _ESTADOS:
        _ESTADOS[uid] = EstadoUsuario()
    return _ESTADOS[uid]


def limpiar(uid: int) -> None:
    _ESTADOS.pop(uid, None)


# ── Detección de campos presentes en texto ─────────────────────────────────
def detectar_campos_presentes(texto: str) -> set[str]:
    """Devuelve el set de campos que el texto YA cubre razonablemente."""
    if not texto:
        return set()
    txt = texto.lower()
    presentes: set[str] = set()
    for campo in CAMPOS:
        # Cuenta cuántas keywords matchean
        matches = sum(1 for kw in campo.palabras_clave if re.search(kw, txt))
        # Para dimensiones/tarima, además debe haber un número (medida/peso)
        if campo.regex_numerico:
            tiene_numero = bool(re.search(campo.regex_numerico, txt))
            if matches >= 1 and tiene_numero:
                presentes.add(campo.key)
        else:
            if matches >= 1:
                presentes.add(campo.key)
    return presentes


# ── Construcción de mensajes ───────────────────────────────────────────────
def mensaje_faltantes_agrupado(faltantes: list[CampoCritico]) -> str:
    """Mensaje cuando faltan pocos datos (1-3)."""
    if not faltantes:
        return ""
    if len(faltantes) == 1:
        intro = "⚠️ Antes de generar el proyecto, me falta este dato:"
    else:
        intro = f"⚠️ Antes de generar el proyecto, me faltan estos {len(faltantes)} datos:"
    bullets = "\n".join(
        f"• **{c.nombre}** — {c.pregunta_corta}" for c in faltantes
    )
    return (
        f"{intro}\n\n{bullets}\n\n"
        "Mándame los datos en un mensaje (también puedes adjuntar plano/fotos)."
    )


def mensaje_pregunta_guiada(campo: CampoCritico, idx: int, total: int) -> str:
    """Mensaje cuando vamos paso a paso (modo guiado)."""
    return (
        f"📋 **Paso {idx + 1} de {total}**\n\n"
        f"{campo.pregunta_larga}\n\n"
        "_Comandos disponibles:_ `/cancelar` para abandonar."
    )


# ── Entry point: evaluar mensaje del usuario y decidir qué hacer ───────────
@dataclass
class DecisionCuestionario:
    accion: str            # "generar" | "preguntar" | "esperar"
    mensaje: str = ""      # mensaje al usuario (vacío si accion="generar")
    texto_completo: str = ""  # cuando accion="generar": el texto acumulado


def procesar(uid: int, nuevo_texto: str,
              hay_archivos_pendientes: bool = False,
              hay_proyecto_anterior: bool = False) -> DecisionCuestionario:
    """Procesa un mensaje del usuario y decide qué hacer.

    accion = "generar" → ya tenemos todo, llamar a Claude con texto_completo.
    accion = "preguntar" → enviar `mensaje` al usuario y esperar más.
    accion = "esperar" → no hay nada que generar todavía (sin texto + sin archivos).

    `hay_proyecto_anterior`: True si ya existe un proyecto generado antes en
    esta misma sesión de Telegram. Sin esto, un mensaje como "está mal el
    diseño del 3D" (que no menciona producto/medidas) se trataba como una
    petición NUEVA incompleta y reiniciaba el cuestionario desde el Paso 1,
    en vez de reconocerse como una corrección sobre el proyecto ya generado.
    Solo aplica si el usuario NO estaba a medio cuestionario (sin texto
    acumulado todavía) — si ya venía respondiendo preguntas, se sigue
    pidiendo lo que falte con normalidad.
    """
    est = estado_de(uid)

    # Antes de acumular el texto nuevo: ¿el usuario ya traía algo en curso?
    ya_habia_conversacion_en_curso = bool(est.texto_acumulado.strip())

    if hay_proyecto_anterior and not ya_habia_conversacion_en_curso and nuevo_texto.strip():
        limpiar(uid)  # por si acaso quedó basura de un intento previo
        return DecisionCuestionario(accion="generar", texto_completo=nuevo_texto.strip())

    est.agregar_texto(nuevo_texto)

    # Caso: no hay texto significativo y no hay archivos
    if not est.texto_acumulado.strip() and not hay_archivos_pendientes:
        return DecisionCuestionario(accion="esperar")

    faltantes = est.faltantes

    # Caso: todo completo → generar
    if not faltantes:
        texto = est.texto_acumulado.strip()
        limpiar(uid)  # reset para el siguiente proyecto
        return DecisionCuestionario(accion="generar", texto_completo=texto)

    # Caso: faltan pocos (1-3) → mensaje agrupado
    if len(faltantes) <= 3:
        est.modo_guiado = False
        return DecisionCuestionario(
            accion="preguntar",
            mensaje=mensaje_faltantes_agrupado(faltantes),
        )

    # Caso: faltan 4 → modo guiado (1 pregunta)
    est.modo_guiado = True
    # Primera pregunta = el primer faltante
    campo = faltantes[0]
    return DecisionCuestionario(
        accion="preguntar",
        mensaje=mensaje_pregunta_guiada(campo, 0, len(faltantes)),
    )


def es_comando_cancelar(texto: str) -> bool:
    if not texto:
        return False
    t = texto.strip().lower()
    return t in ("/cancelar", "/cancel", "/reset", "/abandonar")


# ── Stub para pruebas manuales ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Probar con un mensaje específico
        msg = " ".join(sys.argv[1:])
        d = procesar(1, msg)
        print(f"Acción: {d.accion}")
        if d.mensaje:
            print(f"\n--- mensaje al usuario ---\n{d.mensaje}")
        if d.texto_completo:
            print(f"\n--- texto a Claude ---\n{d.texto_completo}")
        print(f"\nCampos presentes: {estado_de(1).campos_recolectados}")
        print(f"Faltantes: {[c.key for c in estado_de(1).faltantes]}")
    else:
        # Demo
        mensajes_prueba = [
            "Hola",
            "Para almacenar harina",
            "10 m de frente, 8 m de fondo, 6 m de altura libre",
            "Tarima de 1.2 × 1.0 m, 1 tonelada, 2 por nivel",
            "Montacargas contrabalanceado, pasillo 3 m",
        ]
        uid = 42
        for m in mensajes_prueba:
            print(f"\n>>> USUARIO: {m}")
            d = procesar(uid, m)
            print(f"    Acción: {d.accion}")
            if d.mensaje:
                print(f"    Mensaje:\n{d.mensaje[:200]}...")
            if d.accion == "generar":
                print(f"\n    TEXTO COMPLETO A CLAUDE:\n{d.texto_completo}")
                break
