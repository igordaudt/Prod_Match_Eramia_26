"""Divide as 900 consultas combinadas (852 reais + 48 sinteticas) em 2 metades
pela MEDIANA do Jaccard consulta x item-alvo — metade inferior (baixa
sobreposicao lexical) e metade superior (alta sobreposicao lexical) — e
recalcula o MAP por metodo em cada metade.

Objetivo: confirmar (ou nao) a hipotese de que a busca semantica (E5/BGE-M3)
se destaca na metade de Jaccard inferior, enquanto a busca lexical (BM25)
melhora relativamente na metade superior.

Diferente de jaccard_vs_performance.py (que usa quartis e trata os dois
conjuntos separadamente), este script faz um UNICO corte na mediana sobre a
base combinada (real + sintetico juntos), no nivel de consulta agrupada
(852 reais + 48 sinteticas = 900), consistente com a granularidade usada
para MAP em scripts/merge_datasets_analysis.py.

Fontes:
  - Jaccard por consulta: eda/jaccard_por_correlacao.csv (gerado por
    eda_corpus.py sobre data/combined_queries_all.tsv), agregado por
    query_id para o conjunto real (948 correlacoes -> 852 consultas
    agrupadas) e usado 1:1 para o conjunto sintetico (48 consultas).
  - MAP por consulta: results/real_295/sinapi_llm_retrieval_results.json e
    results/ppc_weak/sinapi_llm_retrieval_results.json.

Saidas em results/jaccard_split/.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
JACCARD_CSV = BASE_DIR / "eda" / "jaccard_por_correlacao.csv"
RESULTS_REAL_JSON = BASE_DIR / "results" / "real_295" / "sinapi_llm_retrieval_results.json"
RESULTS_SYNTH_JSON = BASE_DIR / "results" / "ppc_weak" / "sinapi_llm_retrieval_results.json"
OUT_DIR = BASE_DIR / "results" / "jaccard_split"

COMMON_METHODS = ["bm25", "e5", "e5_hybrid", "bge_m3_hybrid"]
METHOD_LABELS = {"bm25": "BM25", "e5": "E5 puro", "e5_hybrid": "E5 hybrid", "bge_m3_hybrid": "BGE-M3 hybrid"}
METHOD_COLORS = {"bm25": "#dc2626", "e5": "#2563eb", "e5_hybrid": "#16a34a", "bge_m3_hybrid": "#c026d3"}


def load_per_query_map(path: Path, methods: list[str]) -> pd.DataFrame:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = [
        {"query_id": r["product_id"], "method": r["method"], "map": r["map"]}
        for r in data["results"]
        if r.get("method") in methods and r.get("success")
    ]
    df = pd.DataFrame(rows)
    return df.pivot_table(index="query_id", columns="method", values="map", aggfunc="mean").reset_index()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jacc = pd.read_csv(JACCARD_CSV, sep="\t")
    jacc["query_id"] = jacc["query_id"].astype(int)

    jacc_real = jacc[jacc["source"] == "real_295"].groupby("query_id")["jaccard"].mean().reset_index()
    jacc_synth = jacc[jacc["source"] == "synthetic_4851"][["query_id", "jaccard"]].copy()
    # ppc_weak tem mut_ID (query_id) repetido apenas quando ha mais de uma linha por consulta,
    # o que nao ocorre aqui — cada mutacao ja e uma consulta.

    map_real = load_per_query_map(RESULTS_REAL_JSON, COMMON_METHODS)
    map_synth = load_per_query_map(RESULTS_SYNTH_JSON, COMMON_METHODS)

    real = jacc_real.merge(map_real, on="query_id", how="inner")
    real["source"] = "real_295"
    synth = jacc_synth.merge(map_synth, on="query_id", how="inner")
    synth["source"] = "synthetic_4851"

    combined = pd.concat([real, synth], ignore_index=True)
    print(f"Consultas combinadas com Jaccard + MAP: {len(combined)} "
          f"({len(real)} reais + {len(synth)} sinteticas)")

    median_jaccard = combined["jaccard"].median()
    combined["half"] = combined["jaccard"].apply(lambda j: "inferior" if j < median_jaccard else "superior")

    report: list[str] = []
    report.append("# Divisão por Mediana de Jaccard — Metade Inferior vs. Superior (900 consultas combinadas)\n")
    report.append(f"Mediana de Jaccard (base combinada, 900 consultas): **{median_jaccard:.4f}**")

    summary_rows = []
    for half in ["inferior", "superior"]:
        sub = combined[combined["half"] == half]
        n_real = int((sub["source"] == "real_295").sum())
        n_synth = int((sub["source"] == "synthetic_4851").sum())
        row = {
            "half": half,
            "n": len(sub),
            "n_real": n_real,
            "n_synth": n_synth,
            "jaccard_min": sub["jaccard"].min(),
            "jaccard_max": sub["jaccard"].max(),
            "jaccard_mean": sub["jaccard"].mean(),
        }
        for m in COMMON_METHODS:
            row[m] = sub[m].mean()
        row["vantagem_semantica_bge_bm25"] = row["bge_m3_hybrid"] - row["bm25"]
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).set_index("half")
    summary.to_csv(OUT_DIR / "jaccard_split_metrics.csv", sep=";")
    combined.to_csv(OUT_DIR / "jaccard_split_per_query.csv", sep="\t", index=False)

    report.append("\n## MAP por método, por metade\n")
    report.append("| Metade | N (real+sint) | Jaccard (faixa) | Jaccard médio | " +
                   " | ".join(METHOD_LABELS[m] for m in COMMON_METHODS) +
                   " | Vantagem semântica (BGE-M3 hyb. − BM25) |")
    report.append("|---|---|---|---|" + "---|" * len(COMMON_METHODS) + "---|")
    for half in ["inferior", "superior"]:
        r = summary.loc[half]
        vals = " | ".join(f"{r[m]:.4f}" for m in COMMON_METHODS)
        report.append(
            f"| {half.capitalize()} (Jaccard {'<' if half == 'inferior' else '>='} {median_jaccard:.3f}) | "
            f"{int(r['n'])} ({int(r['n_real'])}+{int(r['n_synth'])}) | "
            f"{r['jaccard_min']:.3f}–{r['jaccard_max']:.3f} | {r['jaccard_mean']:.3f} | "
            f"{vals} | {r['vantagem_semantica_bge_bm25']:+.4f} |"
        )

    # --- Veredito da hipotese ---
    v_inf = summary.loc["inferior", "vantagem_semantica_bge_bm25"]
    v_sup = summary.loc["superior", "vantagem_semantica_bge_bm25"]
    hyp_confirmed = v_inf > v_sup
    report.append(f"\n## Teste da hipótese\n")
    report.append(
        f"Vantagem semântica (MAP BGE-M3 hybrid − MAP BM25): **{v_inf:+.4f}** na metade inferior "
        f"vs. **{v_sup:+.4f}** na metade superior."
    )
    report.append(
        f"\n**Hipótese {'CONFIRMADA' if hyp_confirmed else 'NÃO confirmada'}**: "
        + (
            "a vantagem semântica é maior na metade de Jaccard inferior do que na superior, "
            "consistente com 'busca semântica se destaca em baixo Jaccard, lexical melhora em alto Jaccard'."
            if hyp_confirmed else
            "a vantagem semântica NÃO é maior na metade de Jaccard inferior — o padrão não se confirma "
            "de forma simples num corte único de mediana sobre a base combinada."
        )
    )
    for m in COMMON_METHODS:
        d = summary.loc["superior", m] - summary.loc["inferior", m]
        report.append(f"- {METHOD_LABELS[m]}: MAP inferior={summary.loc['inferior', m]:.4f}, "
                       f"MAP superior={summary.loc['superior', m]:.4f} (Δ={d:+.4f})")

    # --- Grafico: MAP por metodo, por metade ---
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(COMMON_METHODS))
    width = 0.35
    inf_vals = [summary.loc["inferior", m] for m in COMMON_METHODS]
    sup_vals = [summary.loc["superior", m] for m in COMMON_METHODS]
    ax.bar([i - width / 2 for i in x], inf_vals, width, label=f"Inferior (Jaccard < {median_jaccard:.3f}, n={int(summary.loc['inferior','n'])})", color="#16a34a")
    ax.bar([i + width / 2 for i in x], sup_vals, width, label=f"Superior (Jaccard ≥ {median_jaccard:.3f}, n={int(summary.loc['superior','n'])})", color="#dc2626")
    for i, (iv, sv) in enumerate(zip(inf_vals, sup_vals)):
        ax.text(i - width / 2, iv + 0.01, f"{iv:.3f}", ha="center", fontsize=9)
        ax.text(i + width / 2, sv + 0.01, f"{sv:.3f}", ha="center", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels([METHOD_LABELS[m] for m in COMMON_METHODS])
    ax.set_ylabel("MAP")
    ax.set_ylim(0, 1.0)
    ax.set_title(f"MAP por método — metade inferior vs. superior de Jaccard\n(mediana = {median_jaccard:.3f}, 900 consultas combinadas)")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    out_png = OUT_DIR / "jaccard_split_map.png"
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Grafico salvo em: {out_png}")

    out_md = OUT_DIR / "jaccard_split_resultados.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"Relatorio salvo em: {out_md}")


if __name__ == "__main__":
    main()
