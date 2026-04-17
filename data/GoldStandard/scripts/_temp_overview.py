import json, os, re
base = r'c:\Users\WG918GS\OneDrive - EY\Desktop\TFG\TFG-RAG\data\eu\es\json'
for f in sorted(os.listdir(base)):
    if f.endswith('.json'):
        d = json.load(open(os.path.join(base,f), encoding='utf-8'))
        text = d['contenido'][:3000]
        # Find document type (REGLAMENTO, DECISIÓN, DIRECTIVA, etc.)
        m = re.search(r'(REGLAMENTO|DECISIÓN|DIRECTIVA|CORRECCIÓN|RECTIFICACIÓN|ACUERDO)[\s\S]{0,200}', text)
        tipo = m.group(0)[:200].replace('\n', ' ') if m else 'N/A'
        pags = d["num_paginas"]
        chars = len(d["contenido"])
        print(f"\n{f}: {pags} págs | {chars} chars")
        print(f"  TIPO: {tipo[:150]}")
