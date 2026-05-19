"""
execute_tests.py
================
Fase 1 del testing del TFG: **ejecución** del sistema RAG sobre cada gold
standard y registro de los resultados crudos en JSON para su posterior
evaluación con :mod:`evaluation.py`.
Funcionamiento
--------------
1. Recorre todos los archivos ``src/test/gold_standard_data/gold_standard_*.json``.
2. Para cada uno deduce ``use_case`` e ``idioma`` a partir del nombre del
   fichero (``gold_standard_<caso>_<idioma>.json``) y los mapea a los
   identificadores que usa el RAG (``cvs`` | ``eu`` | ``wiki``).
3. Lanza secuencialmente cada pregunta contra :func:`rag_graph.run` y captura
   métricas de tiempo, chunks, modelo(s) y tokens.
4. Escribe un JSON paralelo por cada gold standard de entrada en
   ``test/results/results_<gold_standard>.json``.
Uso
---
.. code-block:: powershell
    # Ejecutar todos los gold standards
    python -m test.scripts.execute_tests
    # Solo un caso de uso / idioma concreto
    python -m test.scripts.execute_tests --use-case cvs --language en
    # Limitar nº de preguntas (smoke test)
    python -m test.scripts.execute_tests --limit 3
Salida (estructura del JSON)
----------------------------
::
    {
      "caso_uso": "cvs",
      "idioma": "en",
      "total_preguntas": 86,
      "fecha_ejecucion": "2026-05-06T18:32:11",
      "rag_version": "cvs_parallel",          # estrategia detectada
      "descripcion": "...",
      "errores": 0,
      "tiempo_total_ejecucion_s": 412.7,
      "preguntas": [
        {
          "id": 1,
          "categoria": "search_by_skill",
          "pregunta": "...",
          "respuesta_esperada": [ ... ],
          "respuesta": "...",
          "chunks_consultados": 50,
          "chunks_usados": 32,
          "tiempo_total_s": 4.81,
          "modelos": ["gpt-4.1"],
          "num_llamadas_llm": 1,
          "tokens_in": 1234,
          "tokens_out": 256,
          "llm_calls": [
             {"model": "gpt-4.1", "tokens_in": 1234,
              "tokens_out": 256, "tiempo_s": 4.81}
          ],
          "rag_version": "cvs_parallel",
          "error": null
        }
      ]
    }
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional
# Asegurar import desde la raíz del repo (src/test/scripts/ → repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# Importar config primero para que cargue el .env vía load_dotenv().
from src.config import config  # noqa: E402
from test.scripts.pricing import token_cost_usd  # noqa: E402
# rag_graph es pesado (carga LangGraph, Azure clients...) y sólo se necesita
# para la ejecución real. Para `--dry-run` lo importamos perezosamente.
rag_graph = None  # type: ignore[assignment]
def _load_rag_graph():
    global rag_graph
    if rag_graph is None:
        from src.rag.app_langgraph import rag_graph as _rg  # noqa: WPS433
        rag_graph = _rg
    return rag_graph
# ---------------------------------------------------------------------------
# Configuración leída desde .env (todos los valores son externalizables)
# ---------------------------------------------------------------------------
def _resolve_path(env_var: str, default: str) -> Path:
    raw = os.getenv(env_var, default)
    p = Path(raw)
    return p if p.is_absolute() else (REPO_ROOT / p)
def _parse_json_env(env_var: str, default: dict[str, str]) -> dict[str, str]:
    raw = os.getenv(env_var)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{env_var} no es un JSON válido: {exc}") from exc
DATA_DIR = _resolve_path("TEST_DATA_DIR", "src/test/gold_standard_data")
RESULTS_DIR = _resolve_path("TEST_RESULTS_DIR", "src/test/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
GOLD_STANDARD_PREFIX = os.getenv("TEST_GOLD_STANDARD_PREFIX", "gold_standard_")
GOLD_STANDARD_GLOB   = os.getenv("TEST_GOLD_STANDARD_GLOB",   "gold_standard_*.json")
RESULTS_PREFIX       = os.getenv("TEST_RESULTS_PREFIX",       "results_")
USE_CASE_FILE_PREFIX_MAP: dict[str, str] = _parse_json_env(
    "TEST_USE_CASE_MAP",
    {"cvs": "cvs", "eu": "eu", "wikipedia": "wiki"},
)
SUPPORTED_LANGUAGES = {
    s.strip()
    for s in os.getenv("TEST_SUPPORTED_LANGUAGES", "es,en,fr,it,pt").split(",")
    if s.strip()
}
DEFAULT_USER_ID  = os.getenv("TEST_DEFAULT_USER_ID", "tester")
DEFAULT_RAG_MODE = os.getenv("TEST_RAG_MODE", "gpt")
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_gold_standard_filename(path: Path) -> Optional[tuple[str, str]]:
    """Devuelve ``(use_case, language)`` o ``None`` si el nombre no encaja.
    Espera ``gold_standard_<prefijo>_<idioma>.json``.
    """
    stem = path.stem  # gold_standard_cvs_en
    if not stem.startswith(GOLD_STANDARD_PREFIX):
        return None
    rest = stem[len(GOLD_STANDARD_PREFIX):]
    parts = rest.rsplit("_", 1)
    if len(parts) != 2:
        return None
    file_prefix, lang = parts
    if file_prefix not in USE_CASE_FILE_PREFIX_MAP or lang not in SUPPORTED_LANGUAGES:
        return None
    return USE_CASE_FILE_PREFIX_MAP[file_prefix], lang
def _extract_llm_calls(metadata: dict, elapsed_s: float) -> list[dict]:
    """Construye la lista de llamadas a LLM a partir del ``metadata`` del RAG.
    El RAG actual sólo expone agregados (``metadata.usage``) para la última
    llamada de generación. Se reporta lo disponible: una entrada por modelo
    detectado, con tokens_in/out totales y el tiempo total como aproximación.
    Si en el futuro el RAG expone más detalle (lista de llamadas), basta con
    extenderlo aquí.
    """
    usage = metadata.get("usage", {}) or {}
    model = usage.get("model") or metadata.get("model") or "unknown"
    if not usage:
        return []
    return [
        {
            "model":      model,
            "tokens_in":  int(usage.get("prompt_tokens", 0) or 0),
            "tokens_out": int(usage.get("completion_tokens", 0) or 0),
            "tiempo_s":   round(elapsed_s, 3),
        }
    ]
def run_single_query(
    question: dict,
    use_case: str,
    language: str,
    user_id: str,
    rag_mode: str = DEFAULT_RAG_MODE,
) -> dict:
    """Ejecuta una pregunta contra el RAG y devuelve un dict con métricas."""
    pregunta_txt = question.get("pregunta", "")
    base_record: dict = {
        "id":                 question.get("id"),
        "categoria":          question.get("categoria"),
        "pregunta":           pregunta_txt,
        "respuesta_esperada": question.get("respuesta"),
        "respuesta":          "",
        "chunks_consultados": 0,
        "chunks_usados":      0,
        "tiempo_total_s":     0.0,
        "modelos":            [],
        "num_llamadas_llm":   0,
        "tokens_in":          0,
        "tokens_out":         0,
        "coste_rag_usd":      0.0,
        "llm_calls":          [],
        "rag_version":        None,
        "error":              None,
    }
    start = time.perf_counter()
    try:
        result = _load_rag_graph().run(
            query=pregunta_txt,
            user_id=user_id,
            conversation_history=[],
            rag_mode=rag_mode,
            use_case=use_case,
            language=language,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start
        base_record["tiempo_total_s"] = round(elapsed, 3)
        base_record["error"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        return base_record
    elapsed = time.perf_counter() - start
    metadata = result.get("metadata", {}) or {}
    llm_calls = _extract_llm_calls(metadata, elapsed)
    base_record.update({
        "respuesta":          result.get("answer", ""),
        "chunks_consultados": len(result.get("chunks_retrieved", []) or []),
        "chunks_usados":      len(result.get("chunks_used", []) or []),
        "tiempo_total_s":     round(elapsed, 3),
        "modelos":            sorted({c["model"] for c in llm_calls}) or ["unknown"],
        "num_llamadas_llm":   len(llm_calls),
        "tokens_in":          sum(c["tokens_in"] for c in llm_calls),
        "tokens_out":         sum(c["tokens_out"] for c in llm_calls),
        "coste_rag_usd":      round(sum(
            token_cost_usd(c["model"], c["tokens_in"], c["tokens_out"])
            for c in llm_calls
        ), 8),
        "llm_calls":          llm_calls,
        "rag_version":        result.get("strategy_name") or metadata.get("strategy"),
    })
    if result.get("error"):
        base_record["error"] = str(result.get("error"))
    return base_record
# ---------------------------------------------------------------------------
# Núcleo
# ---------------------------------------------------------------------------
def process_gold_standard(
    gs_path: Path,
    limit: Optional[int] = None,
    user_id: str = DEFAULT_USER_ID,
    rag_mode: str = DEFAULT_RAG_MODE,
) -> Path:
    """Ejecuta todas las preguntas de un gold standard y guarda el JSON.
    Devuelve la ruta del fichero de resultados generado.
    """
    parsed = parse_gold_standard_filename(gs_path)
    if not parsed:
        raise ValueError(f"Nombre no reconocido: {gs_path.name}")
    use_case, language = parsed
    with gs_path.open(encoding="utf-8") as fh:
        gs_data = json.load(fh)
    gs_root = gs_data.get("gold_standard", gs_data)
    preguntas = gs_root.get("preguntas", [])
    if limit:
        preguntas = preguntas[:limit]
    print(f"\n{'#' * 70}")
    print(f"# {gs_path.name}  →  use_case={use_case}, lang={language}, "
          f"preguntas={len(preguntas)}")
    print(f"{'#' * 70}")
    resultados: list[dict] = []
    errores = 0
    rag_version_detectada: Optional[str] = None
    inicio_total = time.perf_counter()
    for idx, pregunta in enumerate(preguntas, 1):
        print(f"\n[{idx}/{len(preguntas)}] {pregunta.get('categoria','?')} → "
              f"{(pregunta.get('pregunta') or '')[:80]}")
        record = run_single_query(pregunta, use_case, language, user_id, rag_mode)
        if record["error"]:
            errores += 1
            print(f"   ⚠️  ERROR: {record['error']}")
        else:
            print(f"   ⏱️  {record['tiempo_total_s']}s | "
                  f"chunks {record['chunks_usados']}/{record['chunks_consultados']} | "
                  f"tokens in/out {record['tokens_in']}/{record['tokens_out']} | "
                  f"coste ${record['coste_rag_usd']:.6f}")
        if not rag_version_detectada and record.get("rag_version"):
            rag_version_detectada = record["rag_version"]
        resultados.append(record)
    duracion_total = round(time.perf_counter() - inicio_total, 2)
    out_payload = {
        "caso_uso":                gs_root.get("caso_uso"),
        "use_case_rag":            use_case,
        "idioma":                  gs_root.get("idioma", language),
        "total_preguntas":         len(resultados),
        "errores":                 errores,
        "tiempo_total_ejecucion_s": duracion_total,
        "fecha_ejecucion":         datetime.now().isoformat(timespec="seconds"),
        "rag_version":             rag_version_detectada,
        "descripcion":             gs_root.get("descripcion", ""),
        "preguntas":               resultados,
    }
    out_path = RESULTS_DIR / f"{RESULTS_PREFIX}{gs_path.stem}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(out_payload, fh, ensure_ascii=False, indent=2)
    print(f"\n✅ Resultados guardados en {out_path.relative_to(REPO_ROOT)}  "
          f"(errores: {errores}/{len(resultados)})")
    return out_path
# ---------------------------------------------------------------------------
# Estimación de coste / llamadas a Azure AI Search
# ---------------------------------------------------------------------------
def estimate_search_calls(use_case: str, language: str, n_questions: int) -> dict:
    """Devuelve la estimación de llamadas a Azure AI Search por cada pregunta.
    Reglas (basadas en ``src/rag/strategies``):
    * ``language == "es"``           → ``basic_fusion`` →
      ``RAG_FUSION_QUERIES`` (=``config.rag_fusion_queries``) llamadas a search
      por pregunta + 1 llamada al chat LLM para generar las queries sintéticas
      + N llamadas a embeddings (una por search). No usa semantic ranker.
    * ``use_case == "cvs"`` y no ``es`` → ``cvs_parallel`` →
      1 llamada a search (``CVS_TOP_K`` chunks) + 1 embedding por pregunta.
    * ``use_case in ("eu","wiki")`` y no ``es`` → ``graph_rag`` →
      0 llamadas a Azure AI Search (usa Neo4j Graphiti).
    """
    if language == "es":
        strategy = "basic_fusion"
        per_q_search = int(getattr(config, "rag_fusion_queries", 6) or 6)
    elif use_case == "cvs":
        strategy = "cvs_parallel"
        per_q_search = 1
    else:
        strategy = "graph_rag"
        per_q_search = 0
    return {
        "strategy":               strategy,
        "search_calls_per_q":     per_q_search,
        "search_calls_total":     per_q_search * n_questions,
        "embedding_calls_total":  per_q_search * n_questions,
    }
def print_dry_run_summary(filtered: list[Path], limit: Optional[int]) -> None:
    """Imprime un resumen de llamadas estimadas a Azure AI Search."""
    print("\n" + "=" * 78)
    print(" 🔎  DRY RUN  ·  Estimación de llamadas a Azure AI Search")
    print("=" * 78)
    header = f"{'fichero':40s} {'strategy':14s} {'q':>4s} {'x/q':>5s} {'total':>7s}"
    print(header)
    print("-" * len(header))
    grand_search   = 0
    grand_emb      = 0
    by_strategy: dict[str, int] = {}
    for f in filtered:
        parsed = parse_gold_standard_filename(f)
        if not parsed:
            continue
        use_case, language = parsed
        with f.open(encoding="utf-8") as fh:
            data = json.load(fh)
        gs_root = data.get("gold_standard", data)
        n = len(gs_root.get("preguntas", []))
        if limit:
            n = min(n, limit)
        est = estimate_search_calls(use_case, language, n)
        grand_search += est["search_calls_total"]
        grand_emb    += est["embedding_calls_total"]
        by_strategy[est["strategy"]] = by_strategy.get(est["strategy"], 0) + est["search_calls_total"]
        print(f"{f.name:40s} {est['strategy']:14s} {n:4d} "
              f"{est['search_calls_per_q']:5d} {est['search_calls_total']:7d}")
    print("-" * len(header))
    print(f"{'TOTAL Azure Search query operations':>54s}: {grand_search:7d}")
    print(f"{'TOTAL Azure OpenAI embedding calls':>54s}: {grand_emb:7d}")
    for strat, total in by_strategy.items():
        print(f"{'  · por estrategia ' + strat:>54s}: {total:7d}")
    print("\n💰 Coste en Azure AI Search")
    print("-" * 78)
    print(
        "Azure AI Search NO factura por consulta en los planes Basic/Standard:\n"
        "se paga por **search unit · hora** del servicio aprovisionado, no por\n"
        "cada query. El coste incremental de ejecutar estos tests es 0 € sobre\n"
        "el plan ya contratado, siempre que NO uses Semantic Ranker (este código\n"
        "NO lo usa: emplea búsqueda híbrida texto + vector sin `query_type=semantic`).\n"
        "Si activaras Semantic Ranker, costaría ≈ 1 $ por cada 1000 queries\n"
        "(plan Standard) — para esta tanda serían "
        f"≈ {grand_search/1000:.2f} $.\n"
        "\n"
        "Lo que SÍ incurre coste por llamada es Azure OpenAI:\n"
        "  · Embeddings (ada-002): 1 llamada por cada search → "
        f"{grand_emb} llamadas.\n"
        "  · Chat LLM: 1 llamada extra por pregunta para queries sintéticas en\n"
        "    `basic_fusion` + 1 llamada de generación final por pregunta\n"
        "    (en cvs_parallel, además, mini-LLM por cada lote de chunks).\n"
        "\n"
        "Para obtener un coste $$ exacto, ejecuta primero `--limit 1` y mira el\n"
        "campo `tokens_in`/`tokens_out` por estrategia en `test/results/`."
    )
    print("=" * 78 + "\n")
# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta los gold standards contra el RAG y registra los resultados.",
    )
    parser.add_argument(
        "--use-case", choices=list(USE_CASE_FILE_PREFIX_MAP.values()),
        help="Filtra por caso de uso del RAG (cvs|eu|wiki).",
    )
    parser.add_argument(
        "--language", choices=sorted(SUPPORTED_LANGUAGES),
        help="Filtra por idioma (es|en|fr|it|pt).",
    )
    parser.add_argument(
        "--file", help="Ejecuta sólo un gold standard concreto (nombre o ruta).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Máximo nº de preguntas a ejecutar por gold standard (debug).",
    )
    parser.add_argument(
        "--user-id", default=DEFAULT_USER_ID,
        help=f"user_id para las trazas del RAG (env TEST_DEFAULT_USER_ID, default: {DEFAULT_USER_ID}).",
    )
    parser.add_argument(
        "--rag-mode", default=DEFAULT_RAG_MODE,
        help=f"rag_mode pasado a rag_graph.run (env TEST_RAG_MODE, default: {DEFAULT_RAG_MODE}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="No ejecuta el RAG: sólo estima nº de llamadas a Azure AI Search "
             "y embeddings que se harían, agrupadas por estrategia.",
    )
    args = parser.parse_args()
    # Selección de archivos
    if args.file:
        candidate = Path(args.file)
        if not candidate.is_absolute():
            candidate = DATA_DIR / candidate.name
        if not candidate.exists():
            sys.exit(f"❌ No se encontró {candidate}")
        files = [candidate]
    else:
        files = sorted(DATA_DIR.glob(GOLD_STANDARD_GLOB))
    # Filtros opcionales
    filtered: list[Path] = []
    for f in files:
        parsed = parse_gold_standard_filename(f)
        if not parsed:
            print(f"⏭  Ignorado (nombre no reconocido): {f.name}")
            continue
        uc, lang = parsed
        if args.use_case and uc != args.use_case:
            continue
        if args.language and lang != args.language:
            continue
        filtered.append(f)
    if not filtered:
        sys.exit("❌ Ningún gold standard cumple los filtros.")
    print(f"📋 Se ejecutarán {len(filtered)} gold standard(s):")
    for f in filtered:
        print(f"   · {f.name}")
    if args.dry_run:
        print_dry_run_summary(filtered, args.limit)
        return
    for f in filtered:
        try:
            process_gold_standard(
                f, limit=args.limit, user_id=args.user_id, rag_mode=args.rag_mode,
            )
        except Exception as exc:
            print(f"❌ Falló {f.name}: {exc}")
            traceback.print_exc()
if __name__ == "__main__":
    main()
