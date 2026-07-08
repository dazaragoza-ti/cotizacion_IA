# Ejemplos dorados (carga automática)

Todo archivo **`.json`** que pongas en esta carpeta se carga solo en el "cerebro"
del bot **al reiniciarlo**. El bot imita estos ejemplos, así que entre más buenos
ejemplos haya, mejores salen los proyectos.

## Formato requerido (rejilla simple)

Cada ejemplo debe ser un JSON de proyecto como `ejemplo_proyecto_scop.json`:

- `layout` con **`modulos_x`** (bays por corrida) y **`modulos_y`** (nº de corridas),
  `frente_mm`, `fondo_mm`, `pasillo_mm`, `niveles` (lista empezando en 0),
  `altura_total_mm`, `peralte_larguero_mm`.
- **NO** uses `zones` ni `background_image` (no son compatibles con los planos del bot).
- `materiales`: cada renglón con `pzas`, `codigo`, `descripcion`, `color`, `obs` y
  **`precio`** (unitario MXN).
- `memoria` y `observaciones` con buen detalle de ingeniería.

## La forma más fácil de crear uno

1. Mándale un proyecto al bot en Telegram.
2. En su respuesta, copia el bloque ```json (es justo este formato).
3. Revísalo/corrígelo y guárdalo aquí como `ejemplo_<algo>.json`.
4. Reinicia el bot.

> Los DWG/PDF/xlsx NO sirven como ejemplo (el bot no los lee). Son material fuente;
> hay que convertirlos a este JSON.

## Reiniciar el bot tras agregar ejemplos

```bash
cd ~/Documents/rack-bot
pkill -9 -f "[b]ot\.py"; sleep 2
nohup .venv/bin/python bot.py >/tmp/rackbot.log 2>&1 &
```
