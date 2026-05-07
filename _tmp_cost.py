import json, glob, os, sys
sys.path.insert(0, '.')
from test.scripts.pricing import token_cost_usd

total_coste = 0.0
total_q = 0
total_errors = 0
rows = []

for f in sorted(glob.glob('test/results/results_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    qs = d.get('preguntas', [])
    n = len(qs)
    errors = sum(1 for q in qs if q.get('error'))
    coste = sum((q.get('coste_rag_usd') or 0) for q in qs)
    rows.append((os.path.basename(f), n, errors, coste))
    total_coste += coste
    total_q += n
    total_errors += errors

print('Fichero                                           n  err   coste_rag     avg/q')
print('-' * 80)
for fname, n, errors, coste in rows:
    avg = coste / n if n else 0
    print(fname.ljust(50) + str(n).rjust(3) + '  ' + str(errors).rjust(3) + '  ' + f'{coste:9.4f}' + '  ' + f'{avg:8.5f}')
print('-' * 80)
avg_total = total_coste / total_q if total_q else 0
print('TOTAL'.ljust(50) + str(total_q).rjust(3) + '  ' + str(total_errors).rjust(3) + '  ' + f'{total_coste:9.4f}' + '  ' + f'{avg_total:8.5f}')

n_ok = total_q - total_errors
coste_llm = n_ok * token_cost_usd('gpt-5-mini', 90, 60)
coste_emb = n_ok * token_cost_usd('ada-002', 200, 0)
coste_eval = coste_llm + coste_emb

print()
print('Preguntas evaluables (sin error):    ' + str(n_ok))
print('Fase 2 LLM coincidencia (est.):     ' + f'{coste_llm:.4f} USD')
print('Fase 2 embeddings relevancia (est.): ' + f'{coste_emb:.4f} USD')
print('Fase 2 total (est.):                 ' + f'{coste_eval:.4f} USD')
print()
print('COSTE TOTAL Fase1+Fase2: ' + f'{total_coste + coste_eval:.4f} USD')

# dummy line to satisfy old script structure
rows_old = []
for f in sorted(glob.glob('test/results/results_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    qs = d.get('preguntas', [])
    if not qs:
        continue
    q = qs[0]
    rows_old.append({
        'file': os.path.basename(f),
        'use_case': d.get('use_case_rag'),
        'lang': d.get('idioma'),
        'rag_version': d.get('rag_version') or q.get('rag_version'),
        'tokens_in': q.get('tokens_in'),
        'tokens_out': q.get('tokens_out'),
        'tiempo_s': q.get('tiempo_total_s'),
        'chunks_consultados': q.get('chunks_consultados'),
        'chunks_usados': q.get('chunks_usados'),
        'modelos': q.get('modelos'),
        'num_llamadas_llm': q.get('num_llamadas_llm'),
    })
print(f'{"file":42s} {"strat":14s} {"in":>8s} {"out":>7s} {"t(s)":>7s} {"chunks":>7s}  modelos')
for r in rows:
    print(f'{r["file"][:42]:42s} {(r["rag_version"] or "")[:14]:14s} '
          f'{(r["tokens_in"] or 0):>8d} {(r["tokens_out"] or 0):>7d} '
          f'{(r["tiempo_s"] or 0):>7.2f} {(r["chunks_usados"] or 0):>7d}  {r["modelos"]}')
