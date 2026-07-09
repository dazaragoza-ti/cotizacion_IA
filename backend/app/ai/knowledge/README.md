# Carpeta de conocimiento (knowledge/)

Coloca aquí los archivos de referencia de tu Proyecto. Se concatenan
automáticamente al system prompt, en orden alfabético, cada vez que arranca el
bot.

Formatos que se leen: `.md`, `.txt`, `.csv`, `.tsv`.

Ejemplos de lo que va aquí:
- `precios.csv` — lista de precios de componentes.
- `medidas.md` — medidas estándar, tolerancias, alcances.
- `ejemplos.md` — ejemplos de cotizaciones/despieces bien hechos.

Sugerencias:
- Nombres con prefijo numérico para controlar el orden si importa
  (`01_precios.csv`, `02_medidas.md`, ...).
- Si una lista de precios es muy grande, conviértela a CSV/Markdown compacto.
- Tras editar o agregar archivos aquí, **reinicia el bot** para que los recargue.

> Este README no se incluye en el prompt (solo se leen .md/.txt/.csv/.tsv con
> contenido de referencia; puedes borrarlo cuando agregues tus archivos).
