# Testing del TFG-RAG

Pipeline de pruebas en **dos fases** sobre el sistema RAG (CVs, EU, Wikipedia)
con cobertura multi-idioma.

```
test/
├── data/            ← gold standards de entrada (gold_standard_*.json)
├── gold_standard/   ← scripts que generan esos gold standards
├── scripts/
│   ├── execute_tests.py   ← Fase 1: ejecución del RAG
│   └── evaluation.py      ← Fase 2: evaluación con LLM y export Excel
├── results/         ← salidas crudas de la fase 1 (results_*.json)
└── evaluation/      ← Excel finales por caso de uso (cvs.xlsx, eu.xlsx, wiki.xlsx)
```

## Fase 1 — Ejecución

`test/scripts/execute_tests.py` recorre cada `test/data/gold_standard_*.json`,
deduce el caso de uso e idioma del nombre del fichero, y lanza **secuencialmente**
cada pregunta contra `rag_graph.run(...)`. Para cada pregunta registra:

| Campo | Descripción |
|-------|-------------|
| `respuesta_esperada` | Lo que figura como `respuesta` en el gold standard |
| `respuesta`          | Respuesta real generada por el RAG |
| `chunks_consultados` | `len(chunks_retrieved)` — chunks recuperados por el retriever |
| `chunks_usados`      | `len(chunks_used)` — chunks que el generador utilizó |
| `tiempo_total_s`     | Tiempo de pared para la consulta entera |
| `modelos`            | Lista única de modelos LLM usados |
| `num_llamadas_llm`   | Número de llamadas detectadas |
| `tokens_in/out`      | Suma de prompt/completion tokens |
| `llm_calls`          | Detalle por llamada (`model`, `tokens_in`, `tokens_out`, `tiempo_s`) |
| `rag_version`        | Estrategia seleccionada (p.ej. `cvs_parallel`, `basic_fusion`) |
| `error`              | Mensaje si la consulta lanzó excepción |

> El RAG actual sólo expone uso agregado del último LLM. El campo `llm_calls`
> queda preparado para crecer cuando se instrumente cada llamada interna.

### Ejemplos

```powershell
# Todos los gold standards
python -m test.scripts.execute_tests

# Solo CVs en inglés
python -m test.scripts.execute_tests --use-case cvs --language en

# Smoke test con 3 preguntas por gold standard
python -m test.scripts.execute_tests --limit 3
```

Genera `test/results/results_<gold_standard>.json` por cada entrada.

## Fase 2 — Evaluación

`test/scripts/evaluation.py` lee los `results_*.json` y, por cada pregunta,
pide a un LLM barato (por defecto `gpt-5-mini`, configurable con `--model`)
que devuelva un JSON con:

* `coincidencia_pct` (0-100)
* `calidad_pct`      (0-100)
* `veredicto`        (`OK` | `KO`)
* `justificacion`    (texto breve)

Después construye **un Excel por caso de uso** con **una hoja por idioma** en
`test/evaluation/<use_case>.xlsx`. Cada fila contiene la pregunta, ambas
respuestas, métricas de coste/tiempo y dos veredictos:

* `veredicto_llm`     — el que decide directamente el LLM evaluador.
* `veredicto_umbral`  — `OK` si **`coincidencia_% ≥ 80` y `calidad_% ≥ 80`**,
  `KO` si alguna baja del umbral. El umbral se ajusta con `--threshold`.

### Ejemplos

```powershell
# Evaluar todo lo que haya en test/results/
python -m test.scripts.evaluation

# Cambiar modelo y umbral
python -m test.scripts.evaluation --model gpt-5-mini --threshold 80

# Solo un caso de uso o un fichero
python -m test.scripts.evaluation --use-case cvs
python -m test.scripts.evaluation --file results_gold_standard_cvs_en.json
```

Requiere `openpyxl` (`pip install openpyxl`).

## Convenciones de nombres

* Gold standards: `gold_standard_<prefijo>_<idioma>.json`, donde
  `<prefijo>` ∈ `{cvs, eu, wikipedia}` y `<idioma>` ∈ `{es, en, fr, it, pt}`.
* Mapeo a `use_case` del RAG: `cvs→cvs`, `eu→eu`, `wikipedia→wiki`.
* Resultados: `results_<gold_standard>.json` en `test/results/`.
* Excel evaluación: `<use_case>.xlsx` en `test/evaluation/` con una hoja por idioma.
