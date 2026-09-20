"""Estende a validacao PainelConstru (analyze_painelconstru_subcategoria_rerank.py)
de 100 para 300 consultas: reproduz exatamente a mesma amostra original de
100 (mesma seed=42, mesma sequencia de chamadas rng) e adiciona mais 200
consultas novas do mesmo benchmark, sem sobreposicao.

Reusa o corpus de 12000 itens da rodada anterior (reconstruido de forma
deterministica -- mesma trajetoria de rng -- para poder reaproveitar o cache
de embeddings BGE-M3 ja calculado) e so gera embeddings NOVOS para os itens
relevantes das 200 consultas adicionais que ainda nao estavam no corpus
(a maioria dos itens, ~12000, e reaproveitada do cache; poucas centenas de
itens novos sao adicionados e embedados).

Uso:
    python scripts/analyze_painelconstru_subcategoria_rerank_300.py

Saida (results/painelconstru_subcategoria_validation/):
    painelconstru_subcategoria_rerank_300_per_query.csv
    painelconstru_subcategoria_rerank_300_resultados.md
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

import analyze_painelconstru_subcategoria_rerank as base  # noqa: E402

OUT_DIR = PROJECT_ROOT / "results" / "painelconstru_subcategoria_validation"
BGE_M3_CACHE_DIR_300 = PROJECT_ROOT / "cache" / "painelconstru_bge_m3_300"
N_NEW_QUERIES = 200
DENSE_TEXT_MODE = "raw"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(base.RANDOM_SEED)

    print("Carregando benchmark PainelConstru...")
    real_queries = base.load_painelconstru_benchmark()
    print(f"Consultas usaveis: {len(real_queries)}")

    # --- reproduz EXATAMENTE a rodada original de 100 (mesma seed, mesma
    # sequencia de chamadas: sample(100) depois build_corpus com 1 shuffle) ---
    first_100 = rng.sample(real_queries, base.N_QUERIES)
    corpus = base.build_corpus(first_100, real_queries, base.TARGET_CORPUS_SIZE, rng)
    print(f"Corpus original reproduzido: {len(corpus)} itens (deve bater com a rodada de 100)")
    original_item_ids = list(corpus.keys())

    # --- amostra as 200 consultas NOVAS (continuando o mesmo rng, sem sobreposicao) ---
    sampled_ids_100 = {base.coerce_item_id(q["product_id"]) for q in first_100}
    remaining_pool = [q for q in real_queries if base.coerce_item_id(q["product_id"]) not in sampled_ids_100]
    next_200 = rng.sample(remaining_pool, N_NEW_QUERIES)
    sampled_queries = first_100 + next_200
    print(f"Consultas novas amostradas: {len(next_200)} | total combinado: {len(sampled_queries)}")

    # --- adiciona ao corpus os itens relevantes das 200 novas consultas que ainda nao estavam ---
    added = 0
    for q in next_200:
        for item in q.get("relevant_items") or []:
            item_id = base.coerce_item_id(item.get("item_id"))
            if item_id is not None and item_id not in corpus:
                desc = str(item.get("item_description") or "").strip()
                if desc:
                    corpus[item_id] = {"description": desc, "subcategory_id": item.get("subcategory_id")}
                    added += 1
    print(f"Itens novos adicionados ao corpus: {added} (corpus total agora: {len(corpus)})")

    item_ids = list(corpus.keys())
    descriptions = [corpus[iid]["description"] for iid in item_ids]
    sub_by_item = {iid: corpus[iid]["subcategory_id"] for iid in item_ids}
    assert item_ids[: len(original_item_ids)] == original_item_ids, "corpus original nao foi reproduzido identicamente"

    from normalization import TextNormalizer

    normalizer = TextNormalizer()
    print("Tokenizando corpus completo para BM25...")
    tokenized_corpus = [normalizer.normalize(text).split() for text in descriptions]
    bm25_index = base.Bm25Index(tokenized_corpus)

    def retrieve_bm25(search_terms: str, limit: int) -> list[dict[str, Any]]:
        query_tokens = normalizer.normalize(search_terms).split()
        ranked = bm25_index.top_indices(query_tokens, limit)
        return [
            {"item_id": item_ids[idx], "description": descriptions[idx], "retrieval_score": float(score)}
            for idx, score in ranked
        ]

    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-m3")

    # --- reaproveita embeddings ja calculados na rodada de 100; so embeda os itens novos ---
    cached_emb_path = base.BGE_M3_CACHE_DIR / "embeddings.npy"
    cached_idx_path = base.BGE_M3_CACHE_DIR / "index.json"
    cached_item_ids = None
    cached_embeddings = None
    if cached_emb_path.exists() and cached_idx_path.exists():
        saved = json.load(open(cached_idx_path, encoding="utf-8"))
        if saved.get("item_ids") == original_item_ids and saved.get("text_mode") == DENSE_TEXT_MODE:
            cached_item_ids = saved["item_ids"]
            cached_embeddings = np.load(str(cached_emb_path))
            print(f"Reaproveitando {len(cached_item_ids)} embeddings ja calculados do cache original.")

    if cached_item_ids is not None and cached_embeddings is not None:
        new_item_ids = item_ids[len(cached_item_ids):]
        new_descriptions = descriptions[len(cached_item_ids):]
        print(f"Gerando embeddings apenas para os {len(new_item_ids)} itens novos...")
        if new_descriptions:
            new_embeddings = model.encode(
                new_descriptions, batch_size=32, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True
            )
            embeddings = np.vstack([cached_embeddings, new_embeddings])
        else:
            embeddings = cached_embeddings
    else:
        print("Cache original nao encontrado/compativel -- gerando embeddings do zero para todo o corpus.")
        embeddings = model.encode(
            descriptions, batch_size=32, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True
        )

    BGE_M3_CACHE_DIR_300.mkdir(parents=True, exist_ok=True)
    np.save(str(BGE_M3_CACHE_DIR_300 / "embeddings.npy"), embeddings)
    json.dump(
        {"item_ids": item_ids, "text_mode": DENSE_TEXT_MODE},
        open(BGE_M3_CACHE_DIR_300 / "index.json", "w", encoding="utf-8"),
    )

    def retrieve_bge_m3(search_terms: str, limit: int) -> list[dict[str, Any]]:
        query_text = (search_terms or "").strip()
        if not query_text:
            return []
        query_embedding = model.encode(
            [query_text], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )[0]
        scores = embeddings @ query_embedding
        resolved_limit = min(max(int(limit), 0), len(item_ids))
        if resolved_limit <= 0:
            return []
        top_indices = np.argpartition(scores, -resolved_limit)[-resolved_limit:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        return [
            {"item_id": item_ids[int(i)], "description": descriptions[int(i)], "retrieval_score": float(scores[int(i)])}
            for i in top_indices
        ]

    def hybrid_rank(bm25_items, dense_items, limit) -> list[dict]:
        items_by_id: dict[int, dict] = {}
        scores: dict[int, float] = {}
        for ranked_items in (bm25_items, dense_items):
            for rank, item in enumerate(ranked_items, start=1):
                item_id = base.coerce_item_id(item.get("item_id"))
                if item_id is None:
                    continue
                items_by_id.setdefault(item_id, item)
                scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (base.RRF_K + rank)
        ranked_ids = sorted(scores, key=scores.get, reverse=True)[: base.DEFAULT_LIMIT]
        return [items_by_id[item_id] for item_id in ranked_ids]

    print("Rodando retrieval hibrido para as 300 consultas...")
    new_200_ids = {base.coerce_item_id(q["product_id"]) for q in next_200}
    rows = []
    for i, q in enumerate(sampled_queries, start=1):
        search_terms = str(q["product_description"])
        relevant_ids = set(base.coerce_item_id(x) for x in q["relevant_item_ids"] if base.coerce_item_id(x) in corpus)
        relevant_count = len(relevant_ids)
        query_sub = q.get("subcategory_id")
        batch = "new_200" if base.coerce_item_id(q["product_id"]) in new_200_ids else "original_100"

        if relevant_count == 0:
            continue

        bm25_items = retrieve_bm25(search_terms, base.PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3(search_terms, base.PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, base.DEFAULT_LIMIT)
        flat_sub_ranked = base.rerank_flat_subcategoria(baseline_ranked, sub_by_item, query_sub)

        baseline_ap = base.average_precision(base.build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        flat_sub_ap = base.average_precision(base.build_relevance_flags(flat_sub_ranked, relevant_ids), relevant_count)

        rows.append(
            {
                "product_id": q["product_id"],
                "product_description": search_terms,
                "subcategory_id": query_sub,
                "relevant_count": relevant_count,
                "batch": batch,
                "baseline_ap": baseline_ap,
                "flat_subcategoria_ap": flat_sub_ap,
                "delta": flat_sub_ap - baseline_ap,
            }
        )
        if i % 50 == 0 or i == len(sampled_queries):
            print(f"[{i}/{len(sampled_queries)}] processado")

    def summarize(label: str, subset: list[dict]) -> tuple[str, int, float, float]:
        n = len(subset)
        map_b = sum(r["baseline_ap"] for r in subset) / n
        map_s = sum(r["flat_subcategoria_ap"] for r in subset) / n
        print(f"{label:28s} n={n:4d}  baseline={map_b:.4f}  flat_subcategoria={map_s:.4f}  delta={map_s-map_b:+.4f}")
        return label, n, map_b, map_s

    print(f"\n=== PainelConstru -- resultados ===")
    rows_100 = [r for r in rows if r["batch"] == "original_100"]
    rows_200 = [r for r in rows if r["batch"] == "new_200"]
    summary = []
    summary.append(summarize("Original 100 (recalculado)", rows_100))
    summary.append(summarize("Novas 200", rows_200))
    summary.append(summarize("Combinado (300)", rows))

    with (OUT_DIR / "painelconstru_subcategoria_rerank_300_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["product_id", "product_description", "subcategory_id", "relevant_count", "batch", "baseline_ap", "flat_subcategoria_ap", "delta"],
            delimiter=";",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    md = []
    md.append("# Validacao PainelConstru (300 consultas) -- gate por subcategoria\n")
    md.append(
        "Estende `painelconstru_subcategoria_rerank_resultados.md` (100 consultas) com mais 200 "
        "consultas novas do mesmo benchmark (`class_match/ground_truth/benchmark_grouped_v4.json`), "
        "sem sobreposicao (mesma seed=42, sequencia de amostragem continuada). Corpus estendido: "
        f"{len(corpus)} itens ({len(original_item_ids)} do corpus original + {added} itens novos "
        "necessarios para cobrir os itens relevantes das 200 consultas adicionais). Os embeddings "
        "BGE-M3 dos itens originais foram reaproveitados do cache; so os itens novos foram "
        "embedados nesta rodada.\n"
    )
    md.append("## Resultado\n")
    md.append("| Lote | N | MAP baseline | MAP flat-subcategoria | Delta |")
    md.append("|---|---|---|---|---|")
    for label, n, map_b, map_s in summary:
        md.append(f"| {label} | {n} | {map_b:.4f} | {map_s:.4f} | {map_s-map_b:+.4f} |")
    md.append(
        "\nPara referencia: SINAPI (852 consultas, oraculo) = baseline 0.7932, flat subcategoria "
        "0.8016 (+0.0084). PainelConstru 100 consultas (rodada anterior, corpus menor/reprodutivel "
        "de forma independente) = baseline 0.7991, flat subcategoria 0.8080 (+0.0089).\n"
    )
    md_path = OUT_DIR / "painelconstru_subcategoria_rerank_300_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
