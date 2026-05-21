# Cambios pendientes de commit

Resumen de todos los cambios actualmente en *working tree* (sin commitear todavía),
agrupados por bloque funcional.

---

## 1. Evaluación (`test/scripts/evaluation.py`)

Tres correcciones / mejoras independientes que han cambiado la **foto real**
de los resultados sin tocar el RAG en sí.

### 1.1 Umbral por defecto bajado a 65
- `DEFAULT_THRESHOLD = _env_int("EVAL_THRESHOLD", 65)` (antes `80`).
- Nuevo `DEFAULT_THRESHOLD_HIGH = 75` para distinguir OK "claro" en los Excel.
- Motivo: estábamos midiendo con `EVAL_THRESHOLD=80` heredado del `.env`,
  no con 65 como se daba por hecho. Esto inflaba los KO falsos.

### 1.2 Embeddings en sub-lotes (corrección crítica)
- `compute_relevancia_batch` antes mandaba **todos los textos** en una única
  llamada a `client.embeddings.create`. Azure OpenAI rechaza arrays >128
  inputs (~65 preguntas con 2 textos c/u → 130 → 400 *invalid `$.input`*).
- Ahora se procesa en sub-lotes (`EVAL_EMBEDDING_BATCH`, default 64).
- Se sustituyen entradas vacías por `" "` (Azure rechaza inputs vacíos).
- Si un sub-lote falla, se rellena con `None` y la pregunta sale `relevancia=0`
  en lugar de tirar todo el run.
- Esto era el causante de los **KO en cascada** que veíamos antes (relevancia=0
  para ficheros enteros).

### 1.3 Coincidencia LLM en paralelo
- Nuevo env `EVAL_WORKERS` (default 4) → `ThreadPoolExecutor` para procesar
  varios batches de coincidencia en paralelo.
- Logs por batch indican el índice original (`idx=`) para depurar order.

### 1.4 Coloreado del Excel por intensidad
- Antes: solo verde/rojo según OK/KO.
- Ahora 4 colores:
  - Verde intenso (`63BE7B`): OK con ambas métricas ≥ 75.
  - Verde claro (`C6EFCE`): OK con ambas métricas ≥ umbral (65).
  - Amarillo (`FFEB9C`): KO con al menos una métrica ≥ umbral.
  - Rojo (`FFC7CE`): KO con ninguna métrica ≥ umbral.

### 1.5 Filtrado temprano por fichero + detalle de `--use-case`
- Se añadió filtrado por nombre de fichero antes de evaluar para ahorrar coste
  cuando se pide un subconjunto (`--use-case`, `--language`).
- El patrón de resultados wiki es `results_gold_standard_wikipedia_<lang>.json`,
  por eso el filtro correcto es:
  - `--use-case wikipedia` (no `--use-case wiki`).
- Se añadió `import re` para soportar el filtrado por regex.

---

## 2. Catálogos del corpus (nuevos scripts)

Idea común: precomputar **metadatos exhaustivos** del corpus en un JSON e
inyectarlos en el prompt del RAG, para que las preguntas de catálogo /
conteo / listado / metadatos no dependan de que la búsqueda vectorial
recupere "el chunk mágico".

### 2.1 `test/scripts/build_eu_catalog.py` *(nuevo)*
- Recorre `data/eu/<lang>/json/*.json`.
- Por cada documento extrae: filename, type (REGULATION/DECISION/...),
  subtype (Implementing/Delegated/CFSP), title, long_title, num_pages,
  num_articles, act_number, act_year, adoption_year, issuer.
- Salida: `data/eu/catalog.json` con `{lang: [...]}`.

### 2.2 `test/scripts/build_wiki_catalog.py` *(nuevo)*
- Recorre `data/wikipedia/<lang>/json/*.json`.
- Por cada artículo extrae: titulo, url, pageid, idioma, fecha_descarga,
  num_palabras, num_secciones, secciones, num_categorias, categorias.
- Calcula stats globales (total artículos, categorías únicas, artículo
  más largo / más corto / con más secciones / con más categorías,
  promedios, top5 categorías).
- Construye también un **índice inverso** `categoría → artículos`.
- Importante: usa la **misma blacklist de prefijos** de categorías
  administrativas que el gold standard (`Wikipedia:`, `CS1 `, `Articles `,
  etc.) para que `total_categorias_unicas` coincida con la respuesta
  esperada (425 EN / 353 ES).
- Salida: `data/wikipedia/catalog.json`.

---

## 3. Prompts del RAG

### 3.1 `src/rag/prompts/eu_prompts.py`
- Carga perezosa de `data/eu/catalog.json` (cacheado por proceso).
- `_format_catalog(language)` genera un bloque de texto con:
  - resumen agregado (totales por tipo y por año),
  - lista exhaustiva (filename | tipo | subtipo | páginas | artículos |
    nº acto | año adopción | emisor) + título descriptivo.
- El prompt `generation()`:
  - Inyecta el bloque "**CATÁLOGO COMPLETO DEL CORPUS UE (autoritativo y
    exhaustivo)**" antes de los fragmentos.
  - Añade instrucción explícita: usar catálogo para conteo/listado/
    identificación/estructura, fragmentos para contenido literal.
  - Permite al LLM contestar aunque el documento concreto no haya sido
    recuperado.
- Resultado medido: EU pasó de ~6% OK a ~29% OK incluso con umbral 80
  estricto, y a **58.9% (281/477)** con umbral 65.

### 3.2 `src/rag/prompts/wiki_prompts.py` *(esta sesión)*
- Mismo patrón que EU pero con catálogo Wikipedia.
- Incluye:
  - Estadísticas globales (totales, promedios, artículo más largo/corto,
    top5 categorías).
  - Catálogo exhaustivo: por cada artículo título, URL, pageid, fecha
    descarga, nº palabras, nº secciones, lista completa de secciones,
    lista completa de categorías.
  - Índice inverso categoría → artículos (filtrado a categorías con ≥2
    artículos para no inflar contexto).
- Instrucciones nuevas en `generation()`:
  - **Catálogo** para: catálogo / conteo / listado / metadatos /
    categorías / secciones / existencia.
  - **Fragmentos** para: contenido del cuerpo, definiciones, citas
    literales.
  - Énfasis en exhaustividad de listados y en no inventar.
- Tamaño añadido al prompt: ~75 KB EN (~19k tokens), ~84 KB ES (~21k
  tokens). Aceptable para `gpt-5-mini` (window 128k).

---

## 4. Recompute de veredictos (`test/scripts/recompute_verdicts.py`) *(nuevo)*

- Permite re-aplicar un umbral distinto sobre los Excel ya generados,
  **sin re-llamar al LLM ni a embeddings**.
- Recalcula `veredicto_umbral` y los 4 colores de fondo.
- Usado para pasar de la foto con umbral 80 a la foto con umbral 65 sin
  pagar otra evaluación: 75/859 → 151/859 → 464/849 (54.7% global).

---

## 5. Resultados regenerados

Ficheros JSON re-ejecutados con el RAG actualizado (catálogo en prompt):

- `test/results/results_gold_standard_eu_{en,es,fr,it,pt}.json`
- `test/results/results_gold_standard_wikipedia_{en,es}.json`

Ficheros Excel re-generados con la nueva evaluación + coloreado:

- `test/evaluation/cvs.xlsx`
- `test/evaluation/eu.xlsx`
- `test/evaluation/wiki.xlsx`

---

## 6. Logs de ejecución (no entran en commit normalmente)

`*.log` y `*.err` en raíz: salida de las ejecuciones por idioma. Conviene
añadirlos a `.gitignore` antes de commitear (o borrarlos):

```
eu_en.{log,err}  eu_es.{log,err}  eu_fr.{log,err}
eu_it.{log,err}  eu_pt.{log,err}  eu_full.log  eu_smoke.log  eu_eval.log
wiki_en.log      wiki_es.log      wiki_eval_en.log
eval_run.log
_test_indexes.py   ← script de depuración, no entra en producción
```

---

## 7. Documentación

- `doc/SofíaNegueruelaAvellaneda_TFG_IMAT.docx` modificado.
- `doc/memoria_borrador.md` y `doc/memoria_supongo.md` añadidos (untracked).

---

## Foto actual de resultados (umbral 65)

Resultados consolidados de la ejecución completa más reciente
(`python -m test.scripts.evaluation --threshold 65`):

| Caso | Idioma | OK / Total | % OK |
|------|--------|------------|------|
| CVS  | en     | 65 / 86    | 75.6 % |
| CVS  | es     | 36 / 86    | 41.9 % |
| EU   | en     | 61 / 98    | 62.2 % |
| EU   | es     | 47 / 91    | 51.6 % |
| EU   | fr     | 54 / 98    | 55.1 % |
| EU   | it     | 59 / 99    | 59.6 % |
| EU   | pt     | 56 / 91    | 61.5 % |
| Wiki | en     | 84 / 100   | 84.0 % |
| Wiki | es     | 82 / 100   | 82.0 % |

Conclusiones de objetivo:
- **Wiki**: todos los idiomas > 50 %.
- **EU**: todos los idiomas > 50 %.
- **CVS**: `es` sigue por debajo (41.9 %), fuera del alcance principal pedido
  en esta fase (Wiki + EU).

Resumen agregado:
- EU: 277 / 477 = 58.1 % en valor absoluto de OK, con **todos los idiomas >50%**.
- Wiki: 166 / 200 = 83.0 %.
- CVS: 101 / 172 = 58.7 % (desbalanceado por `es`).
