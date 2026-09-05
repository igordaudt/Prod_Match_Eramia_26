"""Analise exploratoria: mescla os dois conjuntos (852 consultas reais do
fornecedor 295 + 48 consultas sinteticas do ppc_weak) em uma unica base de
900 consultas, e recalcula:

  (a) MAP combinado por metodo (media ponderada das APs por consulta, ja
      calculadas em cada rodada — sem re-executar retrieval);
  (b) a curva Precisao x Recall micro-agregada por threshold, IGUAL ao
      algoritmo de aggregate_precision_recall_by_threshold() em
      retrieval_sinapi.py, mas agora com o pool de candidatos das duas
      rodadas juntas;
  (c) a envoltoria interpolada dessa curva combinada (mesmo algoritmo de
      plot_interpolated_pr.py).

Uso apenas exploratorio (nao altera results/real_295/ nem results/ppc_weak/,
nem o texto do artigo) — grava tudo em results/combined_900/.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_JSON = BASE_DIR / "results" / "real_295" / "sinapi_llm_retrieval_results.json"
RESULTS_CANDIDATES = BASE_DIR / "results" / "real_295" / "sinapi_llm_candidates.jsonl"
PPC_RESULTS_JSON = BASE_DIR / "results" / "ppc_weak" / "sinapi_llm_retrieval_results.json"
PPC_CANDIDATES = BASE_DIR / "results" / "ppc_weak" / "sinapi_llm_candidates.jsonl"
OUT_DIR = BASE_DIR / "results" / "combined_900"

COMMON_METHODS = ["bm25", "e5", "e5_hybrid", "bge_m3_hybrid"]
METHOD_LABELS = {"bm25": "BM25", "e5": "E5 puro", "e5_hybrid": "E5 hybrid", "bge_m3_hybrid": "BGE-M3 hybrid"}
METHOD_COLORS = {"bm25": "#dc2626", "e5": "#2563eb", "e5_hybrid": "#16a34a", "bge_m3_hybrid": "#c026d3"}


def load_per_query_map(path: Path) -> dict[str, list[float]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by_method: dict[str, list[float]] = {m: [] for m in COMMON_METHODS}
    for row in data["results"]:
        method = row.get("method")
        if method in by_method and row.get("success"):
            by_method[method].append(float(row["map"]))
    return by_method


def load_candidate_pool(path: Path) -> dict[str, list[tuple[float, int]]]:
    """Retorna, por metodo, lista de (score, is_relevant) de todos os candidatos de todas as consultas."""
    pool: dict[str, list[tuple[float, int]]] = {m: [] for m in COMMON_METHODS}
    relevant_count_by_method: dict[str, int] = {m: 0 for m in COMMON_METHODS}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            method = row.get("method")
            if method not in pool:
                continue
            relevant_ids = {int(x) for x in (row.get("relevant_item_ids") or [])}
            relevant_count_by_method[method] += len(relevant_ids)
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
                pool[method].append((score, 1 if item_id in relevant_ids else 0))
    return pool, relevant_count_by_method


def merge_pools(pool_a, rel_a, pool_b, rel_b):
    merged_pool = {m: list(pool_a[m]) + list(pool_b[m]) for m in COMMON_METHODS}
    merged_rel = {m: rel_a[m] + rel_b[m] for m in COMMON_METHODS}
    return merged_pool, merged_rel


def build_curve(scored: list[tuple[float, int]], total_relevant: int) -> list[dict]:
    """Reproduz aggregate_precision_recall_by_threshold() para um pool ja combinado."""
    if total_relevant <= 0 or not scored:
        return []
    scored = sorted(scored, key=lambda c: c[0], reverse=True)
    points = [{"threshold": None, "precision": 1.0, "recall": 0.0}]
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
        points.append(
            {
                "threshold": threshold,
                "precision": total_hits / total_returned,
                "recall": total_hits / total_relevant,
            }
        )
    return points


def micro_ap_from_curve(points: list[dict]) -> float:
    ap = 0.0
    prev_recall = 0.0
    for p in points:
        r, prec = p["recall"], p["precision"]
        if r > prev_recall:
            ap += (r - prev_recall) * prec
            prev_recall = r
    return ap


def interpolate(points: list[dict]) -> tuple[list[float], list[float]]:
    """Envoltoria interpolada: p_interp(r) = max precisao para recall >= r, nos niveis de recall observados."""
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

    # --- (a) MAP combinado (ponderado por consulta, sem re-rodar retrieval) ---
    map_real = load_per_query_map(RESULTS_JSON)
    map_synth = load_per_query_map(PPC_RESULTS_JSON)

    print("=" * 70)
    print("MAP combinado (900 consultas = 852 reais + 48 sinteticas)")
    print("=" * 70)
    print(f"{'Metodo':<16}{'MAP real (852)':>16}{'MAP sint (48)':>16}{'MAP combinado (900)':>22}")
    combined_map = {}
    for m in COMMON_METHODS:
        n_real, n_synth = len(map_real[m]), len(map_synth[m])
        all_maps = map_real[m] + map_synth[m]
        combined = sum(all_maps) / len(all_maps)
        combined_map[m] = combined
        avg_real = sum(map_real[m]) / n_real
        avg_synth = sum(map_synth[m]) / n_synth
        print(f"{METHOD_LABELS[m]:<16}{avg_real:>16.4f}{avg_synth:>16.4f}{combined:>22.4f}")

    # --- (b) Pool de candidatos combinado + curva por threshold ---
    print("\nCarregando candidatos (pode levar um tempo, arquivo de 852 consultas e grande)...")
    pool_real, rel_real = load_candidate_pool(RESULTS_CANDIDATES)
    pool_synth, rel_synth = load_candidate_pool(PPC_CANDIDATES)
    pool, rel = merge_pools(pool_real, rel_real, pool_synth, rel_synth)

    curves = {}
    micro_ap = {}
    for m in COMMON_METHODS:
        curves[m] = build_curve(pool[m], rel[m])
        micro_ap[m] = micro_ap_from_curve(curves[m])

    print("\n" + "=" * 70)
    print("AUC micro-agregada (pool bruto, threshold global) — 900 consultas combinadas")
    print("=" * 70)
    for m in COMMON_METHODS:
        print(f"{METHOD_LABELS[m]:<16} AUC-micro={micro_ap[m]:.4f}  (candidatos no pool={len(pool[m]):,}, relevantes={rel[m]:,})")

    # --- salvar CSV bruto ---
    with open(OUT_DIR / "combined_metrics.csv", "w", encoding="utf-8") as f:
        f.write("method;n_real;n_synth;map_real;map_synth;map_combined_900;auc_micro_pooled\n")
        for m in COMMON_METHODS:
            f.write(
                f"{m};{len(map_real[m])};{len(map_synth[m])};"
                f"{sum(map_real[m])/len(map_real[m]):.6f};{sum(map_synth[m])/len(map_synth[m]):.6f};"
                f"{combined_map[m]:.6f};{micro_ap[m]:.6f}\n"
            )

    # --- (c) Graficos ---
    fig, ax = plt.subplots(figsize=(11, 8))
    for m in COMMON_METHODS:
        recalls = [p["recall"] for p in curves[m]]
        precisions = [p["precision"] for p in curves[m]]
        ax.plot(recalls, precisions, color=METHOD_COLORS[m], linewidth=1.4,
                label=f"{METHOD_LABELS[m]} (AUC-micro={micro_ap[m]:.3f})")
    ax.set_title("Precisão x Recall por threshold — 900 consultas combinadas (852 reais + 48 sintéticas)")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precisão")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "sinapi_llm_precision_recall_combined.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 8))
    for m in COMMON_METHODS:
        levels, precs = interpolate(curves[m])
        auc_int = sum((levels[i] - levels[i - 1]) * precs[i] for i in range(1, len(levels)))
        ax.step(levels, precs, where="pre", linewidth=2.2, color=METHOD_COLORS[m],
                label=f"{METHOD_LABELS[m]} (AUC-int={auc_int:.3f})")
    ax.set_title("Precisão interpolada × Recall — 900 consultas combinadas (852 reais + 48 sintéticas)")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precisão interpolada")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "sinapi_llm_precision_recall_interpolated_combined.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"\nGraficos salvos em: {OUT_DIR}")


if __name__ == "__main__":
    main()
