"""Cruza similaridade de Jaccard (consulta x descricao do item-alvo) com o MAP
por metodo de retrieval, em duas fontes de dados:

  (a) fornecedor 295 (real, 852 consultas) — Jaccard medio alto (~0,65),
      quebrado por quartil de Jaccard usando os proprios resultados da rodada
      principal (results/real_295/sinapi_llm_retrieval_results.json);
  (b) ppc_weak (sintetico, 48 consultas, LFs de notacao DN/polegada e
      soldavel/roscavel) — Jaccard medio baixo, usando
      results/ppc_weak/sinapi_llm_retrieval_results.json.

Ver tambem scripts/jaccard_median_split.py para a versao com corte simples na
mediana (2 metades), sobre a base combinada dos dois conjuntos.

Os dois benchmarks rodam sobre corpora distintos (ver run_retrieval_ppc_weak.py
para a explicacao) e por isso nao sao unificados em uma unica rodada de
retrieval — a comparacao e feita no nivel de metricas agregadas/por-quartil,
o que e suficiente para testar a hipotese: quanto menor o Jaccard
consulta-documento, maior a vantagem de retrievers densos (E5, BGE-M3) sobre
o BM25.
"""

from __future__ import annotations

import json
import os

import matplotlib.pyplot as plt
import nltk
import numpy as np
import pandas as pd

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JACCARD_295_CSV = os.path.join(BASE_DIR, "eda", "jaccard_por_correlacao.csv")
RESULTS_295_JSON = os.path.join(BASE_DIR, "results", "real_295", "sinapi_llm_retrieval_results.json")
PPC_WEAK_JSON = os.path.join(BASE_DIR, "data", "ground_truth", "ppc_weak_48.json")
RESULTS_PPC_WEAK_JSON = os.path.join(BASE_DIR, "results", "ppc_weak", "sinapi_llm_retrieval_results.json")
OUT_DIR = os.path.join(BASE_DIR, "eda")

METHOD_ORDER = ["bm25", "e5", "e5_hybrid", "bge_m3_hybrid"]
METHOD_COLORS = {"bm25": "#dc2626", "e5": "#2563eb", "e5_hybrid": "#16a34a", "bge_m3_hybrid": "#c026d3", "bge_m3": "#9333ea"}


def tokenize(t: str) -> set[str]:
    return set(nltk.word_tokenize(str(t).lower(), language="portuguese"))


def jaccard(a: str, b: str) -> float:
    sa, sb = tokenize(a), tokenize(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def load_results_per_query(path: str) -> pd.DataFrame:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = [
        {"product_id": r["product_id"], "method": r["method"], "map": r["map"]}
        for r in data["results"]
    ]
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    report: list[str] = []
    report.append("# Jaccard × Desempenho por Método — fornecedor 295 (real) vs. ppc_weak (sintético)\n")

    # --- (a) fornecedor 295: Jaccard por query + MAP por query -------------
    # jaccard_por_correlacao.csv agora mistura real+sintetico (gerado por
    # eda_corpus.py sobre a base combinada) — filtra so o real e usa query_id.
    jacc_295 = pd.read_csv(JACCARD_295_CSV, sep="\t")
    jacc_295 = jacc_295[jacc_295["source"] == "real_295"]
    jacc_by_product = jacc_295.groupby("query_id")["jaccard"].mean().rename("jaccard").reset_index()
    jacc_by_product = jacc_by_product.rename(columns={"query_id": "product_id"})
    jacc_by_product["product_id"] = jacc_by_product["product_id"].astype(int)

    perf_295 = load_results_per_query(RESULTS_295_JSON)
    perf_295 = perf_295.merge(jacc_by_product, on="product_id", how="inner")

    perf_295["jaccard_q"] = pd.qcut(perf_295["jaccard"], 4, labels=["Q1 (menor)", "Q2", "Q3", "Q4 (maior)"], duplicates="drop")
    quartile_bounds = pd.qcut(jacc_by_product["jaccard"], 4, duplicates="drop")

    pivot_295 = perf_295.pivot_table(index="jaccard_q", columns="method", values="map", aggfunc="mean", observed=True)
    n_by_q = perf_295[perf_295["method"] == "bm25"].groupby("jaccard_q", observed=True).size()
    jrange_by_q = perf_295.groupby("jaccard_q", observed=True)["jaccard"].agg(["min", "max", "mean"])

    report.append("## (a) Fornecedor 295 (real, 852 consultas) — MAP por quartil de Jaccard\n")
    report.append("| Quartil | Jaccard (faixa) | Jaccard médio | N consultas | " + " | ".join(METHOD_ORDER) + " |")
    report.append("|---|---|---|---|" + "---|" * len(METHOD_ORDER))
    for q in pivot_295.index:
        jr = jrange_by_q.loc[q]
        vals = " | ".join(f"{pivot_295.loc[q, m]:.3f}" for m in METHOD_ORDER)
        report.append(f"| {q} | {jr['min']:.3f}–{jr['max']:.3f} | {jr['mean']:.3f} | {int(n_by_q.get(q, 0))} | {vals} |")

    # Correlacao Jaccard x vantagem semantica (bge_m3_hybrid - bm25), por query
    wide = perf_295.pivot_table(index="product_id", columns="method", values="map", aggfunc="mean")
    wide = wide.join(jacc_by_product.set_index("product_id")["jaccard"])
    wide["vantagem_semantica"] = wide["bge_m3_hybrid"] - wide["bm25"]
    corr = wide[["jaccard", "vantagem_semantica"]].corr(method="spearman").iloc[0, 1]
    report.append(f"\n- Correlação de Spearman entre Jaccard e (MAP BGE-M3 hybrid − MAP BM25), por consulta: **{corr:.3f}**")
    report.append("  (negativa = quanto menor o Jaccard, maior a vantagem do BGE-M3 hybrid sobre o BM25)")

    # --- (b) ppc_weak: Jaccard por mutacao + MAP agregado -------------------
    with open(PPC_WEAK_JSON, encoding="utf-8") as f:
        ppc = json.load(f)
    ppc_jaccards = []
    for item in ppc["items"]:
        original = item["descricao_original"]
        for mut in item["mutations"]:
            ppc_jaccards.append(jaccard(mut["descricao_mutada"], original))
    ppc_jaccard_mean = float(np.mean(ppc_jaccards))
    ppc_jaccard_median = float(np.median(ppc_jaccards))

    report.append(f"\n## (b) ppc_weak (sintético, 48 consultas, 16 itens)\n")
    report.append(f"- Jaccard médio (consulta × descrição original do item): **{ppc_jaccard_mean:.3f}**")
    report.append(f"- Jaccard mediano: {ppc_jaccard_median:.3f}")

    ppc_map_by_method: dict[str, float] = {}
    if os.path.exists(RESULTS_PPC_WEAK_JSON):
        perf_ppc = load_results_per_query(RESULTS_PPC_WEAK_JSON)
        ppc_map_by_method = perf_ppc.groupby("method")["map"].mean().to_dict()
        report.append("\n| Método | MAP |")
        report.append("|---|---|")
        for m in METHOD_ORDER + (["bge_m3"] if "bge_m3" in ppc_map_by_method else []):
            if m in ppc_map_by_method:
                report.append(f"| {m} | {ppc_map_by_method[m]:.3f} |")
    else:
        report.append("\n*(results/ppc_weak/sinapi_llm_retrieval_results.json ainda não gerado.)*")

    # --- (c) Tabela combinada: Jaccard médio x MAP, por bucket + ppc_weak ---
    report.append("\n## (c) Visão combinada — Jaccard médio × MAP por método\n")
    report.append("| Conjunto | N | Jaccard médio | " + " | ".join(METHOD_ORDER) + " |")
    report.append("|---|---|---|" + "---|" * len(METHOD_ORDER))
    if ppc_map_by_method:
        vals = " | ".join(f"{ppc_map_by_method.get(m, float('nan')):.3f}" for m in METHOD_ORDER)
        report.append(f"| ppc_weak (sintético) | 48 | {ppc_jaccard_mean:.3f} | {vals} |")
    for q in pivot_295.index:
        jr = jrange_by_q.loc[q]
        vals = " | ".join(f"{pivot_295.loc[q, m]:.3f}" for m in METHOD_ORDER)
        report.append(f"| fornecedor 295 — {q} | {int(n_by_q.get(q, 0))} | {jr['mean']:.3f} | {vals} |")
    overall_295 = perf_295.groupby("method")["map"].mean()
    vals = " | ".join(f"{overall_295.get(m, float('nan')):.3f}" for m in METHOD_ORDER)
    report.append(f"| fornecedor 295 — geral | 852 | {jacc_by_product['jaccard'].mean():.3f} | {vals} |")

    # --- Graficos --------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    ax = axes[0]
    x_points = list(jrange_by_q["mean"])
    for m in METHOD_ORDER:
        y = [pivot_295.loc[q, m] for q in pivot_295.index]
        ax.plot(x_points, y, marker="o", color=METHOD_COLORS[m], label=m, linewidth=2)
        if ppc_map_by_method:
            ax.scatter([ppc_jaccard_mean], [ppc_map_by_method.get(m, np.nan)], color=METHOD_COLORS[m], marker="*", s=220, edgecolor="black", zorder=5)
    if ppc_map_by_method:
        ax.annotate("ppc_weak\n(sintético)", xy=(ppc_jaccard_mean, max(ppc_map_by_method.values())), xytext=(ppc_jaccard_mean, 0.95), ha="center", fontsize=9, color="dimgray")
    ax.set_xlabel("Jaccard médio (consulta × descrição do item-alvo)")
    ax.set_ylabel("MAP")
    ax.set_title("MAP por método × Jaccard\n(linhas = quartis do fornecedor 295; estrela = ppc_weak)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    delta = [pivot_295.loc[q, "bge_m3_hybrid"] - pivot_295.loc[q, "bm25"] for q in pivot_295.index]
    ax.plot(x_points, delta, marker="o", color="#c026d3", linewidth=2, label="fornecedor 295 (quartis)")
    if ppc_map_by_method and "bge_m3_hybrid" in ppc_map_by_method:
        ax.scatter([ppc_jaccard_mean], [ppc_map_by_method["bge_m3_hybrid"] - ppc_map_by_method["bm25"]], color="#c026d3", marker="*", s=260, edgecolor="black", zorder=5, label="ppc_weak")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Jaccard médio")
    ax.set_ylabel("MAP(BGE-M3 hybrid) − MAP(BM25)")
    ax.set_title("Vantagem semântica vs. Jaccard\n(positivo = BGE-M3 hybrid vence)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out_png = os.path.join(OUT_DIR, "jaccard_vs_map.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Grafico salvo em: {out_png}")

    out_md = os.path.join(OUT_DIR, "jaccard_vs_map_resultados.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"Relatorio salvo em: {out_md}")


if __name__ == "__main__":
    main()
