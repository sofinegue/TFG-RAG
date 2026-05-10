"""Resume costes y errores de los ficheros de resultados de tests.

Uso:
    python -m test.scripts.summarize_result_costs
"""

import glob
import json
import os

from test.scripts.pricing import token_cost_usd


def main() -> None:
    total_coste = 0.0
    total_q = 0
    total_errors = 0
    summary_rows = []

    for file_path in sorted(glob.glob("test/results/results_*.json")):
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
        questions = data.get("preguntas", [])
        count = len(questions)
        errors = sum(1 for question in questions if question.get("error"))
        cost = sum((question.get("coste_rag_usd") or 0) for question in questions)
        summary_rows.append((os.path.basename(file_path), count, errors, cost))
        total_coste += cost
        total_q += count
        total_errors += errors

    print("Fichero                                           n  err   coste_rag     avg/q")
    print("-" * 80)
    for file_name, count, errors, cost in summary_rows:
        avg = cost / count if count else 0
        print(
            file_name.ljust(50)
            + str(count).rjust(3)
            + "  "
            + str(errors).rjust(3)
            + "  "
            + f"{cost:9.4f}"
            + "  "
            + f"{avg:8.5f}"
        )
    print("-" * 80)

    avg_total = total_coste / total_q if total_q else 0
    print(
        "TOTAL".ljust(50)
        + str(total_q).rjust(3)
        + "  "
        + str(total_errors).rjust(3)
        + "  "
        + f"{total_coste:9.4f}"
        + "  "
        + f"{avg_total:8.5f}"
    )

    evaluable_questions = total_q - total_errors
    coste_llm = evaluable_questions * token_cost_usd("gpt-5-mini", 90, 60)
    coste_emb = evaluable_questions * token_cost_usd("ada-002", 200, 0)
    coste_eval = coste_llm + coste_emb

    print()
    print(f"Preguntas evaluables (sin error):    {evaluable_questions}")
    print(f"Fase 2 LLM coincidencia (est.):      {coste_llm:.4f} USD")
    print(f"Fase 2 embeddings relevancia (est.): {coste_emb:.4f} USD")
    print(f"Fase 2 total (est.):                 {coste_eval:.4f} USD")
    print()
    print(f"COSTE TOTAL Fase1+Fase2: {total_coste + coste_eval:.4f} USD")


if __name__ == "__main__":
    main()