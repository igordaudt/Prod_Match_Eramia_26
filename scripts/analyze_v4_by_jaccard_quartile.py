"""Cruza o AP por consulta do experimento V4 (peso denso x esparso no RRF,
scripts/retrieval_weighted_rrf_v4.py) com os quartis de Jaccard do conjunto
real -- mesma metodologia de scripts/jaccard_vs_performance.py (groupby
query_id, media do Jaccard por consulta, pd.qcut em 4 quartis) -- para ver
se o efeito do peso e uniforme ou concentrado em algum quartil.

Nao mexe em nenhum arquivo/resultado existente, so le
results/real_295_v4_rrf_weights/per_query_ap.csv (gerado antes) e
eda/jaccard_por_correlacao.csv.

Uso:
    python scripts/analyze_v4_by_jaccard_quartile.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
PER_QUERY_AP_CSV = BASE_DIR / "results" / "real_295_v4_rrf_weights" / "per_query_ap.csv"
JACCARD_CSV = BASE_DIR / "eda" / "jaccard_por_correlacao.csv"
OUT_DIR = BASE_DIR / "results" / "real_295_v4_rrf_weights"


def main() -> None:
    ap_df = pd.read_csv(PER_QUERY_AP_CSV, sep=";")
    config_cols = [c for c in ap_df.columns if c != "product_id"]

    jacc = pd.read_csv(JACCARD_CSV, sep="\t")
    jacc_295 = jacc[jacc["source"] == "real_295"]
    jacc_by_product = jacc_295.groupby("query_id")["jaccard"].mean().rename("jaccard").reset_index()

    merged = ap_df.merge(jacc_by_product, left_on="product_id", right_on="query_id", how="inner")
    print(f"Consultas com AP e Jaccard: {len(merged)} de {len(ap_df)}")

    merged["jaccard_q"] = pd.qcut(merged["jaccard"], 4, labels=["Q1 (menor)", "Q2", "Q3", "Q4 (maior)"], duplicates="drop")

    n_by_q = merged.groupby("jaccard_q", observed=True).size()
    jrange_by_q = merged.groupby("jaccard_q", observed=True)["jaccard"].agg(["min", "max", "mean"])

    pivot = merged.groupby("jaccard_q", observed=True)[config_cols].mean()

    baseline_col = config_cols[0]
    print(f"\nBaseline (coluna de referencia para delta): {baseline_col}\n")

    report = ["# V4 por quartil de Jaccard -- peso denso x esparso na fusao RRF\n"]
    report.append(
        "Mesma metodologia de quartis de `scripts/jaccard_vs_performance.py` "
        "(media de Jaccard por consulta, `pd.qcut` em 4 grupos de tamanho igual).\n"
    )
    report.append("| Quartil | N | Jaccard (min-max, media) | " + " | ".join(config_cols) + " |")
    report.append("|---|---|---|" + "---|" * len(config_cols))
    for q in pivot.index:
        n = n_by_q[q]
        jr = jrange_by_q.loc[q]
        vals = " | ".join(f"{pivot.loc[q, c]:.4f}" for c in config_cols)
        report.append(f"| {q} | {n} | {jr['min']:.3f}-{jr['max']:.3f} ({jr['mean']:.3f}) | {vals} |")

    report.append("\n## Delta de MAP vs. baseline (1:1), por quartil\n")
    report.append("| Quartil | " + " | ".join(c for c in config_cols if c != baseline_col) + " |")
    report.append("|---|" + "---|" * (len(config_cols) - 1))
    for q in pivot.index:
        deltas = " | ".join(
            f"{pivot.loc[q, c] - pivot.loc[q, baseline_col]:+.4f}" for c in config_cols if c != baseline_col
        )
        report.append(f"| {q} | {deltas} |")

    out_md = OUT_DIR / "rrf_weights_by_jaccard_quartile.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"Relatorio salvo em: {out_md}")

    out_csv = OUT_DIR / "rrf_weights_by_jaccard_quartile.csv"
    pivot_out = pivot.copy()
    pivot_out.insert(0, "n", n_by_q)
    pivot_out.insert(1, "jaccard_mean", jrange_by_q["mean"])
    pivot_out.to_csv(out_csv, sep=";")
    print(f"CSV salvo em: {out_csv}")

    print("\n" + "\n".join(report))


if __name__ == "__main__":
    main()
