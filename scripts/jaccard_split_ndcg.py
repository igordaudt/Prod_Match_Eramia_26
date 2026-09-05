"""Calcula NDCG@10 e NDCG@100 por consulta (relevancia binaria, DCG log2(i+1))
para as duas metades de Jaccard definidas em jaccard_median_split.py, como
alternativa macro-agregada (por consulta, depois media) a curva Precisao x
Recall pooled usada em jaccard_split_precision_recall.py.

Diferente da curva pooled, o NDCG nao mistura scores de consultas diferentes
em um unico ranking global -- e calculado inteiramente dentro de cada
consulta (como o MAP), entao nao deveria sofrer o mesmo vies contra o BM25
(score bruto, nao calibravel entre consultas).

Saida: results/jaccard_split/ndcg_by_half.csv + .md
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
PER_QUERY_CSV = BASE_DIR / "results" / "jaccard_split" / "jaccard_split_per_query.csv"
REAL_CANDIDATES = BASE_DIR / "results" / "real_295" / "sinapi_llm_candidates.jsonl"
SYNTH_CANDIDATES = BASE_DIR / "results" / "ppc_weak" / "sinapi_llm_candidates.jsonl"
OUT_DIR = BASE_DIR / "results" / "jaccard_split"

COMMON_METHODS = ["bm25", "e5", "e5_hybrid", "bge_m3_hybrid"]
METHOD_LABELS = {"bm25": "BM25", "e5": "E5 puro", "e5_hybrid": "E5 hybrid", "bge_m3_hybrid": "BGE-M3 hybrid"}
CUTOFFS = [10, 100]


def load_half_map(path: Path) -> dict[tuple[str, int], str]:
    df = pd.read_csv(path, sep="\t")
    return {(row["source"], int(row["query_id"])): row["half"] for _, row in df.iterrows()}


def dcg(rels: list[int], k: int) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(rels[:k]))


def ndcg_at_k(relevance_flags: list[int], total_relevant: int, k: int) -> float:
    actual = dcg(relevance_flags, k)
    ideal_flags = [1] * min(total_relevant, k)
    ideal = dcg(ideal_flags, k)
    return actual / ideal if ideal > 0 else 0.0


def compute_ndcg_rows(path: Path, source_tag: str, half_map: dict[tuple[str, int], str]) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            method = row.get("method")
            if method not in COMMON_METHODS:
                continue
            query_id = int(row["product_id"])
            half = half_map.get((source_tag, query_id))
            if half is None:
                continue
            relevant_ids = {int(x) for x in (row.get("relevant_item_ids") or [])}
            total_relevant = len(relevant_ids)
            if total_relevant == 0:
                continue
            candidates = row.get("candidates") or []
            seen: set[int] = set()
            flags: list[int] = []
            for cand in candidates:
                item_id = cand.get("item_id")
                if item_id is None or item_id in seen:
                    continue
                seen.add(item_id)
                flags.append(1 if item_id in relevant_ids else 0)
            entry = {"source": source_tag, "query_id": query_id, "method": method, "half": half}
            for k in CUTOFFS:
                entry[f"ndcg@{k}"] = ndcg_at_k(flags, total_relevant, k)
            rows.append(entry)
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    half_map = load_half_map(PER_QUERY_CSV)

    print("Calculando NDCG por consulta (conjunto real)...")
    rows_real = compute_ndcg_rows(REAL_CANDIDATES, "real_295", half_map)
    print("Calculando NDCG por consulta (conjunto sintético)...")
    rows_synth = compute_ndcg_rows(SYNTH_CANDIDATES, "synthetic_4851", half_map)

    df = pd.DataFrame(rows_real + rows_synth)
    df.to_csv(OUT_DIR / "ndcg_per_query.csv", sep="\t", index=False)

    report: list[str] = []
    report.append("# NDCG por Metade de Jaccard — Comparação com MAP e com a Curva Pooled\n")
    report.append("NDCG calculado por consulta (relevância binária, desconto log2(rank+1)), "
                   "depois macro-agregado por método e metade — mesma lógica do MAP, "
                   "sem misturar scores de consultas diferentes.\n")

    for k in CUTOFFS:
        col = f"ndcg@{k}"
        pivot = df.pivot_table(index="half", columns="method", values=col, aggfunc="mean")
        report.append(f"\n## NDCG@{k}\n")
        report.append("| Metade | " + " | ".join(METHOD_LABELS[m] for m in COMMON_METHODS) + " | Vant. sem. (BGE-M3 h. − BM25) |")
        report.append("|---|" + "---|" * (len(COMMON_METHODS) + 1))
        for half in ["inferior", "superior"]:
            vals = " | ".join(f"{pivot.loc[half, m]:.4f}" for m in COMMON_METHODS)
            adv = pivot.loc[half, "bge_m3_hybrid"] - pivot.loc[half, "bm25"]
            report.append(f"| {half.capitalize()} | {vals} | {adv:+.4f} |")

    out_md = OUT_DIR / "ndcg_by_half.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"Relatorio salvo em: {out_md}")
    print(f"Dados por consulta salvos em: {OUT_DIR / 'ndcg_per_query.csv'}")

    # --- Grafico: NDCG@10 por metodo, por metade ---
    pivot10 = df.pivot_table(index="half", columns="method", values="ndcg@10", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(COMMON_METHODS))
    width = 0.35
    inf_vals = [pivot10.loc["inferior", m] for m in COMMON_METHODS]
    sup_vals = [pivot10.loc["superior", m] for m in COMMON_METHODS]
    ax.bar([i - width / 2 for i in x], inf_vals, width, label="Jaccard inferior (n=450)", color="#16a34a")
    ax.bar([i + width / 2 for i in x], sup_vals, width, label="Jaccard superior (n=450)", color="#dc2626")
    for i, (iv, sv) in enumerate(zip(inf_vals, sup_vals)):
        ax.text(i - width / 2, iv + 0.01, f"{iv:.3f}", ha="center", fontsize=9)
        ax.text(i + width / 2, sv + 0.01, f"{sv:.3f}", ha="center", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels([METHOD_LABELS[m] for m in COMMON_METHODS])
    ax.set_ylabel("NDCG@10")
    ax.set_ylim(0, 1.0)
    ax.set_title("NDCG@10 por método — metade inferior vs. superior de Jaccard\n(900 consultas combinadas, mediana de Jaccard = 0,754)")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    out_png = OUT_DIR / "ndcg_by_half.png"
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Grafico salvo em: {out_png}")


if __name__ == "__main__":
    main()
