"""Mesma analise de diagnostico feita para "Cimentos" (169), agora para as
outras subcategorias que ficaram entre as piores com o gate no teste
PainelConstru (300 consultas): Madeiras para Construcao (152), Disjuntores
e Fusiveis (190), EPI (255), Acos para Construcao (159), Tubos e
Eletrodutos (203), Ferramentas para Pintura (127).

Para cada consulta dessas subcategorias, verifica se os itens corretos
(ground truth) tem subcategory_id preenchido e igual ao da consulta. Quando
NAO bate (None/vazio ou valor diferente), imprime o ranking baseline vs.
pos-gate para confirmar o mesmo mecanismo encontrado em Cimentos: item
correto despenca porque falta/diverge o metadado de subcategoria, nao por
"excesso de variantes concorrentes".

Uso:
    python scripts/inspect_painelconstru_worst_subcategories.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

import analyze_painelconstru_subcategoria_rerank as base  # noqa: E402

BGE_M3_CACHE_DIR_300 = PROJECT_ROOT / "cache" / "painelconstru_bge_m3_300"
TARGET_SUBCATEGORY_IDS = ["152", "190", "255", "159", "203", "127"]
TOP_N_DISPLAY = 10


def main() -> None:
    rng = random.Random(base.RANDOM_SEED)
    real_queries = base.load_painelconstru_benchmark()

    first_100 = rng.sample(real_queries, base.N_QUERIES)
    corpus = base.build_corpus(first_100, real_queries, base.TARGET_CORPUS_SIZE, rng)
    original_item_ids = list(corpus.keys())

    sampled_ids_100 = {base.coerce_item_id(q["product_id"]) for q in first_100}
    remaining_pool = [q for q in real_queries if base.coerce_item_id(q["product_id"]) not in sampled_ids_100]
    next_200 = rng.sample(remaining_pool, 200)
    sampled_queries = first_100 + next_200

    for q in next_200:
        for item in q.get("relevant_items") or []:
            item_id = base.coerce_item_id(item.get("item_id"))
            if item_id is not None and item_id not in corpus:
                desc = str(item.get("item_description") or "").strip()
                if desc:
                    corpus[item_id] = {"description": desc, "subcategory_id": item.get("subcategory_id")}

    item_ids = list(corpus.keys())
    descriptions = [corpus[iid]["description"] for iid in item_ids]
    sub_by_item = {iid: corpus[iid]["subcategory_id"] for iid in item_ids}
    assert item_ids[: len(original_item_ids)] == original_item_ids

    from normalization import TextNormalizer

    normalizer = TextNormalizer()
    tokenized_corpus = [normalizer.normalize(text).split() for text in descriptions]
    bm25_index = base.Bm25Index(tokenized_corpus)

    def retrieve_bm25(search_terms: str, limit: int):
        query_tokens = normalizer.normalize(search_terms).split()
        ranked = bm25_index.top_indices(query_tokens, limit)
        return [
            {"item_id": item_ids[idx], "description": descriptions[idx], "retrieval_score": float(score)}
            for idx, score in ranked
        ]

    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-m3")
    saved = json.load(open(BGE_M3_CACHE_DIR_300 / "index.json", encoding="utf-8"))
    assert saved["item_ids"] == item_ids
    embeddings = np.load(str(BGE_M3_CACHE_DIR_300 / "embeddings.npy"))

    def retrieve_bge_m3(search_terms: str, limit: int):
        query_text = (search_terms or "").strip()
        query_embedding = model.encode([query_text], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)[0]
        scores = embeddings @ query_embedding
        resolved_limit = min(max(int(limit), 0), len(item_ids))
        top_indices = np.argpartition(scores, -resolved_limit)[-resolved_limit:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        return [
            {"item_id": item_ids[int(i)], "description": descriptions[int(i)], "retrieval_score": float(scores[int(i)])}
            for i in top_indices
        ]

    def hybrid_rank(bm25_items, dense_items, limit):
        items_by_id = {}
        scores = {}
        for ranked_items in (bm25_items, dense_items):
            for rank, item in enumerate(ranked_items, start=1):
                item_id = base.coerce_item_id(item.get("item_id"))
                if item_id is None:
                    continue
                items_by_id.setdefault(item_id, item)
                scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (base.RRF_K + rank)
        ranked_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
        return [items_by_id[item_id] for item_id in ranked_ids]

    mismatches_found = []

    for target_sub in TARGET_SUBCATEGORY_IDS:
        target_queries = [q for q in sampled_queries if str(q.get("subcategory_id")) == target_sub]
        print("#" * 100)
        print(f"SUBCATEGORIA {target_sub} -- {len(target_queries)} consultas")
        print("#" * 100)

        for q in target_queries:
            search_terms = str(q["product_description"])
            relevant_ids = set(base.coerce_item_id(x) for x in q["relevant_item_ids"] if base.coerce_item_id(x) in corpus)
            query_sub = q.get("subcategory_id")

            # deteccao rapida de mismatch (sem precisar rodar retrieval se nao houver)
            item_mismatches = [
                rid for rid in relevant_ids if str(sub_by_item.get(rid)) != str(query_sub)
            ]

            bm25_items = retrieve_bm25(search_terms, base.PREFETCH_LIMIT)
            dense_items = retrieve_bge_m3(search_terms, base.PREFETCH_LIMIT)
            baseline_ranked = hybrid_rank(bm25_items, dense_items, base.DEFAULT_LIMIT)
            flat_sub_ranked = base.rerank_flat_subcategoria(baseline_ranked, sub_by_item, query_sub)

            baseline_ap = base.average_precision(base.build_relevance_flags(baseline_ranked, relevant_ids), len(relevant_ids))
            flat_sub_ap = base.average_precision(base.build_relevance_flags(flat_sub_ranked, relevant_ids), len(relevant_ids))
            delta = flat_sub_ap - baseline_ap

            print(f"\nCONSULTA: {search_terms!r}  (product_id={q['product_id']})  AP baseline={baseline_ap:.4f} -> gate={flat_sub_ap:.4f}  delta={delta:+.4f}")
            for rid in sorted(relevant_ids):
                item_sub = sub_by_item.get(rid)
                ok = str(item_sub) == str(query_sub)
                tag = "OK" if ok else f"*** MISMATCH (item_sub={item_sub}, query_sub={query_sub}) ***"
                print(f"    item {rid}: {tag}  desc={corpus.get(rid, {}).get('description', '?')[:80]}")

            if item_mismatches and abs(delta) > 0.001:
                mismatches_found.append(
                    {
                        "subcategory": target_sub,
                        "product_id": q["product_id"],
                        "query": search_terms,
                        "mismatched_items": item_mismatches,
                        "delta": delta,
                    }
                )
                for rid in item_mismatches:
                    baseline_rank = next((r for r, it in enumerate(baseline_ranked, start=1) if base.coerce_item_id(it.get("item_id")) == rid), None)
                    gated_rank = next((r for r, it in enumerate(flat_sub_ranked, start=1) if base.coerce_item_id(it.get("item_id")) == rid), None)
                    print(f"    >>> item {rid} rank baseline={baseline_rank} -> rank pos-gate={gated_rank} (subcategoria do item = {sub_by_item.get(rid)!r})")

    print("\n\n" + "=" * 100)
    print("RESUMO: consultas com mismatch de subcategoria E impacto real no AP")
    print("=" * 100)
    for m in mismatches_found:
        print(f"sub={m['subcategory']:>4} product_id={m['product_id']:>8} delta={m['delta']:+.4f}  query={m['query']!r}  itens_mismatch={m['mismatched_items']}")


if __name__ == "__main__":
    main()
