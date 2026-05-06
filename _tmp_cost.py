import json, glob, os
rows = []
for f in sorted(glob.glob('test/results/results_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    qs = d.get('preguntas', [])
    if not qs:
        continue
    q = qs[0]
    rows.append({
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
