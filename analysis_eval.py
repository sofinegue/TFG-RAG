
import pandas as pd
import glob
import os

files = glob.glob("test/evaluation/*.xlsx")
all_df = []

for f in files:
    df = pd.read_excel(f)
    filename = os.path.basename(f).lower()
    if "cvs" in filename:
        df["case"] = "cvs"
    elif "eu" in filename:
        df["case"] = "eu"
    elif "wiki" in filename:
        df["case"] = "wiki"
    else:
        df["case"] = "other"
    all_df.append(df)

df = pd.concat(all_df, ignore_index=True)

metrics_perc = ["coincidencia_%", "relevancia_%"]
# Available columns: num_llamadas_llm, tokens_in, tokens_out, coste_total_usd, tiempo_total_s
# Missing in Excel: chunks_consultados, chunks_usados (I will omit or use 0 if required but they arent in the file)
metrics_ops = ["num_llamadas_llm", "tokens_in", "tokens_out", "coste_total_usd", "tiempo_total_s"]

def print_table(data, title, cost_dec=4):
    print(f"\n--- {title} ---")
    cols = data.columns.tolist()
    format_dict = {col: "{:.1f}" for col in cols if col != "coste_total_usd" and col != "case"}
    if "coste_total_usd" in cols:
        format_dict["coste_total_usd"] = "{:." + str(cost_dec) + "f}"
    
    header_list = ["case"] + [c for c in cols if c != "case"]
    header = " | ".join([f"{col:<20}" for col in header_list])
    print(header)
    print("-" * len(header))
    
    for index, row in data.iterrows():
        current_case = str(index)
        line = f"{current_case:<20}"
        for col in cols:
            if col == "case": continue
            val = row[col]
            fmt = format_dict.get(col, "{}")
            line += " | " + f"{fmt.format(val):<20}"
        print(line)

# Block 1: Percentages
res_perc_case = df.groupby("case")[metrics_perc].mean()
res_perc_global = pd.DataFrame(df[metrics_perc].mean()).T
res_perc_global.index = ["Global"]
print_table(res_perc_case, "MEDIAS DE PORCENTAJES POR CASO")
print_table(res_perc_global, "MEDIA DE PORCENTAJES GLOBAL")

# Block 2: Operations
res_ops_case = df.groupby("case")[metrics_ops].mean()
res_ops_global = pd.DataFrame(df[metrics_ops].mean()).T
res_ops_global.index = ["Global"]
print_table(res_ops_case, "MEDIAS OPERATIVAS POR CASO")
print_table(res_ops_global, "MEDIAS OPERATIVAS GLOBAL")
