import pandas as pd
import glob
import os
import sys

def run_analysis():
    files = glob.glob('test/evaluation/*.xlsx')
    if not files:
        print("No files found")
        return

    mapping = {
        'cvs_en': 'cvs_parallel', 'cvs_es': 'basic_fusion',
        'eu_en': 'graph_rag', 'eu_fr': 'graph_rag', 'eu_it': 'graph_rag', 'eu_pt': 'graph_rag', 'eu_es': 'basic_fusion',
        'wiki_en': 'graph_rag', 'wiki_es': 'basic_fusion'
    }

    all_data = []
    for f in files:
        try:
            xls = pd.ExcelFile(f)
            for sheet in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet)
                filename_stem = os.path.basename(f).split('.')[0]
                lang = sheet.lower().split('_')[-1]
                key = f'{filename_stem}_{lang}'
                df['caso_uso'] = filename_stem
                df['idioma'] = lang
                df['estrategia'] = mapping.get(key, 'unknown')
                all_data.append(df)
        except Exception as e:
            print(f"Error {f}: {e}")

    if not all_data:
        print("No data collected")
        return

    full_df = pd.concat(all_data, ignore_index=True)
    col_map = {'coincidencia_porcentaje': 'coincidencia_%', 'relevancia_porcentaje': 'relevancia_%', 'total_time_s': 'tiempo_total_s', 'total_cost': 'coste_total_usd'}
    full_df.rename(columns=lambda x: col_map.get(x, x), inplace=True)
    
    full_df['veredicto_umbral'] = ((full_df['coincidencia_%'] >= 65) & (full_df['relevancia_%'] >= 65)).astype(int)

    def stats(df, col):
        s = df.groupby(col)['veredicto_umbral'].agg(['count', 'sum', 'mean'])
        s.columns = ['n', 'OK', '%OK']
        s['%OK'] = (s['%OK'] * 100).round(1)
        return s

    print("--- TABLA POR IDIOMA ---")
    print(stats(full_df, 'idioma'))
    print("\n--- TABLA POR ESTRATEGIA ---")
    print(stats(full_df, 'estrategia'))
    print("\n--- TOP 8 PEORES POR CASO ---")
    for case in sorted(full_df['caso_uso'].unique()):
        sub = full_df[full_df['caso_uso'] == case]
        if 'categoria' in sub.columns:
            cs = stats(sub, 'categoria').sort_values('%OK').head(8)
            print(f"\n{case}:\n{cs}")
    
    print("\n--- PROMEDIOS ---")
    ops = [o for o in ['tiempo_total_s', 'coste_total_usd'] if o in full_df.columns]
    if ops:
        res = full_df.groupby('caso_uso')[ops].mean()
        if 'tiempo_total_s' in res.columns: res['tiempo_total_s'] = res['tiempo_total_s'].round(1)
        if 'coste_total_usd' in res.columns: res['coste_total_usd'] = res['coste_total_usd'].round(4)
        print(res)

run_analysis()
