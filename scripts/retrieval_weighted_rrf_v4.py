"""V4: testa se o peso relativo entre BGE-M3 (denso) e BM25 (esparso) na
fusao RRF do BGE-M3 hybrid impacta o MAP sobre o conjunto real (852
consultas).

Nao modifica scripts/retrieval_sinapi.py nem nenhum resultado existente --
so importa (read-only) retrieve_bm25/retrieve_bge_m3_sinapi/load_benchmark
de la e implementa, aqui, uma variante de RRF com peso por modalidade:

    score(d) = w_denso / (k + rank_denso(d)) + w_esparso / (k + rank_bm25(d))

O RRF atual (retrieve_bge_m3_hybrid_sinapi, usado em todos os resultados
publicados) equivale a w_denso = w_esparso = 1.0 -- e testado aqui como
"baseline" para conferencia (deve reproduzir o MAP=0,7932 ja reportado).

Uso:
    python scripts/retrieval_weighted_rrf_v4.py

Saida: results/real_295_v4_rrf_weights/rrf_weights_map.csv + .md
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from retrieval_sinapi import (  # noqa: E402
    DEFAULT_LIMIT,
    INPUT_JSON,
    build_relevance_flags,
    coerce_item_id,
    load_benchmark,
    retrieve_bge_m3_sinapi,
    retrieve_bm25,
)

OUT_DIR = PROJECT_ROOT / "results" / "real_295_v4_rrf_weights"
RRF_K = 60
PREFETCH_LIMIT = 100

# (nome, peso_denso, peso_esparso). (1.0, 1.0) == RRF atual (baseline).
WEIGHT_CONFIGS: list[tuple[str, float, float]] = [
    ("baseline_1.0_1.0 (atual)", 1.0, 1.0),
    ("denso_1.5x", 1.5, 1.0),
    ("denso_2x", 2.0, 1.0),
    ("denso_3x", 3.0, 1.0),
    ("esparso_1.5x", 1.0, 1.5),
    ("esparso_2x", 1.0, 2.0),
    ("esparso_3x", 1.0, 3.0),
]


def average_precision(flags: list[int], relevant_count: int) -> float:
    if relevant_count <= 0:
        return 0.0
    precision_sum = 0.0
    hits_so_far = 0
    for rank, flag in enumerate(flags, start=1):
        if not flag:
            continue
        hits_so_far += 1
        precision_sum += hits_so_far / rank
    return precision_sum / relevant_count


def recall_at_k(flags: list[int], relevant_count: int, k: int) -> float:
    if relevant_count <= 0 or k <= 0:
        return 0.0
    return sum(flags[:k]) / relevant_count


def weighted_rrf_rank(
    bm25_items: list[dict],
    dense_items: list[dict],
    w_dense: float,
    w_sparse: float,
    limit: int,
) -> list[dict]:
    items_by_id: dict[int, dict] = {}
    scores: dict[int, float] = {}

    for ranked_items, weight in ((bm25_items, w_sparse), (dense_items, w_dense)):
        for rank, item in enumerate(ranked_items, start=1):
            item_id = coerce_item_id(item.get("item_id"))
            if item_id is None:
                continue
            items_by_id.setdefault(item_id, item)
            scores[item_id] = scores.get(item_id, 0.0) + weight / (RRF_K + rank)

    ranked_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
    return [items_by_id[item_id] for item_id in ranked_ids]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    benchmark = load_benchmark(INPUT_JSON)
    print(f"Consultas carregadas de {INPUT_JSON}: {len(benchmark)}")

    per_config_aps: dict[str, list[float]] = {name: [] for name, _, _ in WEIGHT_CONFIGS}
    per_config_recall10: dict[str, list[float]] = {name: [] for name, _, _ in WEIGHT_CONFIGS}
    per_query_rows: list[dict] = []

    started = time.perf_counter()
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)

        query_row = {"product_id": product["product_id"]}
        for name, w_dense, w_sparse in WEIGHT_CONFIGS:
            ranked = weighted_rrf_rank(bm25_items, dense_items, w_dense, w_sparse, DEFAULT_LIMIT)
            flags = build_relevance_flags(ranked, relevant_ids)
            ap = average_precision(flags, relevant_count)
            per_config_aps[name].append(ap)
            per_config_recall10[name].append(recall_at_k(flags, relevant_count, 10))
            query_row[name] = ap
        per_query_rows.append(query_row)

        if i % 100 == 0 or i == len(benchmark):
            elapsed = time.perf_counter() - started
            print(f"[{i}/{len(benchmark)}] {elapsed:.1f}s decorridos")

    per_query_csv = OUT_DIR / "per_query_ap.csv"
    config_names = [name for name, _, _ in WEIGHT_CONFIGS]
    with open(per_query_csv, "w", encoding="utf-8") as f:
        f.write("product_id;" + ";".join(config_names) + "\n")
        for row in per_query_rows:
            f.write(str(row["product_id"]) + ";" + ";".join(f"{row[name]:.6f}" for name in config_names) + "\n")
    print(f"AP por consulta salvo em: {per_query_csv}")

    rows = []
    for name, w_dense, w_sparse in WEIGHT_CONFIGS:
        aps = per_config_aps[name]
        recalls = per_config_recall10[name]
        map_score = sum(aps) / len(aps)
        recall10 = sum(recalls) / len(recalls)
        rows.append(
            {
                "config": name,
                "w_denso": w_dense,
                "w_esparso": w_sparse,
                "MAP": map_score,
                "Recall@10": recall10,
                "n_consultas": len(aps),
            }
        )
        print(f"{name:28s} w_denso={w_dense:.1f} w_esparso={w_sparse:.1f}  MAP={map_score:.4f}  Recall@10={recall10:.4f}")

    csv_path = OUT_DIR / "rrf_weights_map.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("config;w_denso;w_esparso;MAP;Recall@10;n_consultas\n")
        for row in rows:
            f.write(
                f"{row['config']};{row['w_denso']};{row['w_esparso']};"
                f"{row['MAP']:.6f};{row['Recall@10']:.6f};{row['n_consultas']}\n"
            )
    print(f"\nCSV salvo em: {csv_path}")

    baseline_map = rows[0]["MAP"]
    md_lines = [
        "# V4 -- Peso denso x esparso na fusao RRF do BGE-M3 hybrid\n",
        f"Conjunto real, {len(benchmark)} consultas, `limit={DEFAULT_LIMIT}`, `k={RRF_K}` (mesmo k do RRF atual).",
        "Score ponderado: `w_denso / (k + rank_BGE-M3) + w_esparso / (k + rank_BM25)`.",
        f"Baseline (`w_denso=w_esparso=1.0`) e matematicamente identico ao RRF hybrid usado em todos os resultados publicados (MAP esperado ~0,7932).\n",
        "| Config | w_denso | w_esparso | MAP | Delta MAP vs. baseline | Recall@10 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        delta = row["MAP"] - baseline_map
        md_lines.append(
            f"| {row['config']} | {row['w_denso']:.1f} | {row['w_esparso']:.1f} | "
            f"{row['MAP']:.4f} | {delta:+.4f} | {row['Recall@10']:.4f} |"
        )
    md_path = OUT_DIR / "rrf_weights_resultados.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Relatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
