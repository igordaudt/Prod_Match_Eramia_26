"""Gera a curva Precisao x Recall (envoltoria interpolada, micro-agregada por
threshold) para as duas metades de Jaccard definidas em
scripts/jaccard_median_split.py (inferior/superior, corte na mediana sobre as
900 consultas combinadas), em um UNICO grafico: mesma cor por metodo, linha
continua para a metade inferior e tracejada para a metade superior.

Le os candidatos brutos (score por item recuperado) de
results/real_295/sinapi_llm_candidates.jsonl e
results/ppc_weak/sinapi_llm_candidates.jsonl, filtra por (source, query_id)
conforme a metade atribuida em results/jaccard_split/jaccard_split_per_query.csv,
e agrega os pools separadamente por metade — mesmo algoritmo de
aggregate_precision_recall_by_threshold() em retrieval_sinapi.py.

Saida: results/jaccard_split/precision_recall_by_half.png (+ .csv)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import PercentFormatter

BASE_DIR = Path(__file__).resolve().parent.parent
PER_QUERY_CSV = BASE_DIR / "results" / "jaccard_split" / "jaccard_split_per_query.csv"
REAL_CANDIDATES = BASE_DIR / "results" / "real_295" / "sinapi_llm_candidates.jsonl"
SYNTH_CANDIDATES = BASE_DIR / "results" / "ppc_weak" / "sinapi_llm_candidates.jsonl"
OUT_DIR = BASE_DIR / "results" / "jaccard_split"

COMMON_METHODS = ["bm25", "e5", "e5_hybrid", "bge_m3_hybrid"]
METHOD_LABELS = {"bm25": "BM25", "e5": "E5 puro", "e5_hybrid": "E5 hybrid", "bge_m3_hybrid": "BGE-M3 hybrid"}
METHOD_COLORS = {"bm25": "#dc2626", "e5": "#2563eb", "e5_hybrid": "#16a34a", "bge_m3_hybrid": "#c026d3"}
HALVES = ["inferior", "superior"]
LINESTYLE = {"inferior": "-", "superior": "--"}


def load_half_map(path: Path) -> dict[tuple[str, int], str]:
    df = pd.read_csv(path, sep="\t")
    return {(row["source"], int(row["query_id"])): row["half"] for _, row in df.iterrows()}


def load_candidate_pool_by_half(
    path: Path, source_tag: str, half_map: dict[tuple[str, int], str]
) -> tuple[dict[str, dict[str, list[tuple[float, int]]]], dict[str, dict[str, int]]]:
    """Retorna, por metodo e por metade, lista de (score, is_relevant) e total_relevant."""
    pool = {m: {h: [] for h in HALVES} for m in COMMON_METHODS}
    total_relevant = {m: {h: 0 for h in HALVES} for m in COMMON_METHODS}
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
            total_relevant[method][half] += len(relevant_ids)
            seen: set[int] = set()
            for cand in row.get("candidates") or []:
                item_id = cand.get("item_id")
                if item_id is None or item_id in seen:
                    continue
                seen.add(item_id)
                try:
                    score = float(cand.get("retrieval_score"))
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(score):
                    continue
                pool[method][half].append((score, 1 if item_id in relevant_ids else 0))
    return pool, total_relevant


def merge_pool_dicts(a, b):
    merged = {m: {h: list(a[m][h]) + list(b[m][h]) for h in HALVES} for m in COMMON_METHODS}
    return merged


def merge_rel_dicts(a, b):
    return {m: {h: a[m][h] + b[m][h] for h in HALVES} for m in COMMON_METHODS}


def build_curve(scored: list[tuple[float, int]], total_relevant: int) -> list[dict]:
    if total_relevant <= 0 or not scored:
        return []
    scored = sorted(scored, key=lambda c: c[0], reverse=True)
    points = [{"recall": 0.0, "precision": 1.0}]
    total_hits = 0
    total_returned = 0
    index = 0
    while index < len(scored):
        threshold = scored[index][0]
        group_returned = 0
        group_hits = 0
        while index < len(scored) and scored[index][0] == threshold:
            group_returned += 1
            group_hits += scored[index][1]
            index += 1
        total_returned += group_returned
        total_hits += group_hits
        points.append({"recall": total_hits / total_relevant, "precision": total_hits / total_returned})
    return points


def interpolate(points: list[dict]) -> tuple[list[float], list[float]]:
    precision_by_recall: dict[float, float] = {}
    for p in points:
        r = min(max(p["recall"], 0.0), 1.0)
        precision_by_recall[r] = max(precision_by_recall.get(r, 0.0), p["precision"])
    levels = sorted(set(precision_by_recall) | {0.0, 1.0})
    suffix_max = [0.0] * len(levels)
    m = 0.0
    for i in range(len(levels) - 1, -1, -1):
        m = max(m, precision_by_recall.get(levels[i], 0.0))
        suffix_max[i] = m
    return levels, suffix_max


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    half_map = load_half_map(PER_QUERY_CSV)

    print("Carregando candidatos do conjunto real...")
    pool_real, rel_real = load_candidate_pool_by_half(REAL_CANDIDATES, "real_295", half_map)
    print("Carregando candidatos do conjunto sintético...")
    pool_synth, rel_synth = load_candidate_pool_by_half(SYNTH_CANDIDATES, "synthetic_4851", half_map)

    pool = merge_pool_dicts(pool_real, pool_synth)
    rel = merge_rel_dicts(rel_real, rel_synth)

    fig, ax = plt.subplots(figsize=(12, 8))
    csv_rows = []
    for method in COMMON_METHODS:
        for half in HALVES:
            points = build_curve(pool[method][half], rel[method][half])
            levels, precs = interpolate(points)
            auc_int = sum((levels[i] - levels[i - 1]) * precs[i] for i in range(1, len(levels)))
            n_relevant = rel[method][half]
            ax.step(
                levels, precs, where="pre", linewidth=2.2,
                color=METHOD_COLORS[method], linestyle=LINESTYLE[half],
                label=f"{METHOD_LABELS[method]} — {half} (AUC-int={auc_int:.3f})",
            )
            for lvl, prec in zip(levels, precs):
                csv_rows.append({"method": method, "half": half, "recall": lvl, "precision_interpolated": prec})

    ax.set_title(
        "Precisão interpolada × Recall — metade inferior vs. superior de Jaccard\n"
        "(linha contínua = Jaccard inferior, tracejada = Jaccard superior; 900 consultas combinadas)"
    )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precisão interpolada")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.02)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    plt.tight_layout()

    out_png = OUT_DIR / "precision_recall_by_half.png"
    plt.savefig(out_png, dpi=160, bbox_inches="tight")
    print(f"Grafico salvo em: {out_png}")

    out_csv = OUT_DIR / "precision_recall_by_half.csv"
    pd.DataFrame(csv_rows).to_csv(out_csv, sep=";", index=False)
    print(f"Pontos salvos em: {out_csv}")


if __name__ == "__main__":
    main()
