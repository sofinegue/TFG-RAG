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

`test/scripts/evaluation.py` lee los `results_*.json` y evalúa cada pregunta
mediante **dos métricas automáticas**:

| Métrica | Método | Coste |
|---------|--------|-------|
| `coincidencia_%` | LLM (`gpt-5-mini`) en lotes de 10 preguntas/llamada | ~$0.00009/q |
| `relevancia_%`   | Cosine similarity con embeddings `ada-002` (sin LLM) | ~$0.0001/q |

`veredicto_umbral` = `OK` si **ambas métricas ≥ umbral** (por defecto 80 %).

Columnas del Excel:

| Campo | Descripción |
|-------|-------------|
| `coincidencia_%` | Similitud semántica respuesta real vs. esperada (LLM, 0-100) |
| `relevancia_%`   | Similitud por embeddings coseno (ada-002, 0-100) |
| `veredicto_umbral` | `OK` / `KO` según ambas métricas ≥ umbral |
| `justificacion`  | Explicación breve del LLM evaluador |
| `coste_rag_usd`  | Coste Fase 1 (tokens generación RAG) |
| `coste_eval_usd` | Coste Fase 2 (LLM evaluación + embeddings) |
| `coste_total_usd`| Suma de ambas fases |

Después construye **un Excel por caso de uso** con **una hoja por idioma** en
`test/evaluation/<use_case>.xlsx`. El umbral se ajusta con `--threshold`.

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

## Estimación de costes (gpt-5-mini: $0.25 in / $2.00 out por 1M · ada-002: $0.10 por 1M)

### Fase 1 — por gold standard

| Gold standard | n | Estrategia RAG | Coste/q estimado | **Total est.** |
|---|---:|---|---:|---:|
| `cvs_en`   |  86 | `cvs_parallel` | $0.00625 | **~$0.54** |
| `cvs_es`   |  86 | `basic_fusion` | $0.00233 | **~$0.20** |
| `eu_en`    |  98 | `graph_rag`    | $0.00123 | **~$0.12** |
| `eu_es`    |  91 | `basic_fusion` | $0.00233 | **~$0.21** |
| `eu_fr`    |  98 | `graph_rag`    | $0.00123 | **~$0.12** |
| `eu_it`    |  99 | `graph_rag`    | $0.00123 | **~$0.12** |
| `eu_pt`    |  91 | `graph_rag`    | $0.00123 | **~$0.11** |
| `wiki_en`  | 100 | `graph_rag`    | $0.00123 | **~$0.12** |
| `wiki_es`  | 100 | `basic_fusion` | $0.00233 | **~$0.23** |

> `cvs_parallel` es la estrategia más cara porque procesa todos los CVs en paralelo;
> el coste real depende del tamaño del corpus. Ejecutar `--limit 3` para calibrar.

### Fase 1 — por caso de uso / idioma

| `--use-case` | Gold standards incluidos | **Fase 1 est.** |
|---|---|---:|
| `cvs`  | cvs_en + cvs_es          | **~$0.74** |
| `eu`   | eu_en/es/fr/it/pt        | **~$0.68** |
| `wiki` | wiki_en + wiki_es        | **~$0.36** |
| *(todo)* | los 9 gold standards  | **~$1.78** |

| `--language` | Estrategia(s) involucradas | n total | **Fase 1 est.** |
|---|---|---:|---:|
| `en` | cvs_parallel + graph_rag×2 | 284 | **~$0.78** |
| `es` | basic_fusion×3             | 277 | **~$0.64** |
| `fr` | graph_rag                  |  98 | **~$0.12** |
| `it` | graph_rag                  |  99 | **~$0.12** |
| `pt` | graph_rag                  |  91 | **~$0.11** |

### Coste total (Fase 1 + Fase 2)

| Escenario | Fase 1 | Fase 2 (eval) | **Total est.** |
|---|---:|---:|---:|
| Solo `cvs`    | $0.74 | $0.03 | **~$0.77** |
| Solo `eu`     | $0.68 | $0.08 | **~$0.76** |
| Solo `wiki`   | $0.36 | $0.03 | **~$0.39** |
| **Run completo** | **$1.78** | **$0.16** | **~$1.94** |

Fase 2 = ~849 preguntas × ($0.00009 LLM coincidencia + $0.0001 embeddings relevancia).

---

## Convenciones de nombres

* Gold standards: `gold_standard_<prefijo>_<idioma>.json`, donde
  `<prefijo>` ∈ `{cvs, eu, wikipedia}` y `<idioma>` ∈ `{es, en, fr, it, pt}`.
* Mapeo a `use_case` del RAG: `cvs→cvs`, `eu→eu`, `wikipedia→wiki`.
* Resultados: `results_<gold_standard>.json` en `test/results/`.
* Excel evaluación: `<use_case>.xlsx` en `test/evaluation/` con una hoja por idioma.
