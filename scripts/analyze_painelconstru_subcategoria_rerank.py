"""Valida a descoberta de "gate por subcategoria melhora o reranking" em uma
base INDEPENDENTE da SINAPI: o benchmark PainelConstru
(class_match/ground_truth/benchmark_grouped_v4.json).

Por que esse arquivo e nao o t-correlations-full4.tsv: os dois tem a MESMA
origem (t-correlations-full4.tsv e a forma "longa"/desnormalizada,
1 linha por par consulta-item; benchmark_grouped_v4.json e a forma
"agrupada", 1 objeto por consulta com relevant_item_ids/relevant_items ja
prontos, no MESMO formato usado a sessao inteira para o benchmark SINAPI
-- product_id/product_description/relevant_item_ids). O JSON agrupado ja
inclui subcategory_id tanto no nivel da consulta quanto de cada item
relevante (nao precisa fazer join extra como fizemos para a SINAPI), entao
e a escolha natural: menos codigo, menos chance de erro de join, e reusa
diretamente a mesma convencao de dado das analises anteriores.

Amostragem: o benchmark completo tem 43305 entradas de "consulta", mas a
maioria (30747) tem 0 itens relevantes (sobras da desnormalizacao original
-- nao sao consultas reais utilizaveis). So sao usaveis as 12558 entradas
com >=1 item relevante E subcategory_id definido. Amostramos 100 dessas
(seed fixa=42) para uma validacao rapida, conforme pedido.

Corpus de recuperacao: o catalogo completo do PainelConstru tem ~110 mil
itens distintos -- BGE-M3 rodando em CPU (sem GPU disponivel neste
ambiente, medido em ~12.8 docs/seg) levaria ~2h so pra indexar. Para manter
o teste rapido mas ainda realista (nao um teste "de brinde" com poucos
itens), o corpus usado e: todos os itens relevantes das 100 consultas
amostradas + distratores aleatorios ate completar um catalogo de ~12000
itens (~15-20 min de indexacao).

Metodologia identica a results/subcategoria_rerank/ (SINAPI): hibrido
BM25+BGE-M3 via RRF (k=60) como baseline, depois reranking "flat" por
subcategoria (mesma subcategoria da consulta sobe, resto mantem ordem
original do hibrido).

Uso:
    python scripts/analyze_painelconstru_subcategoria_rerank.py

Saida (results/painelconstru_subcategoria_validation/):
    painelconstru_subcategoria_rerank_per_query.csv
    painelconstru_subcategoria_rerank_resultados.md
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BENCHMARK_JSON = PROJECT_ROOT.parent / "class_match" / "ground_truth" / "benchmark_grouped_v4.json"
OUT_DIR = PROJECT_ROOT / "results" / "painelconstru_subcategoria_validation"
BGE_M3_CACHE_DIR = PROJECT_ROOT / "cache" / "painelconstru_bge_m3"

RANDOM_SEED = 42
N_QUERIES = 100
TARGET_CORPUS_SIZE = 12000
RRF_K = 60
DEFAULT_LIMIT = 100
PREFETCH_LIMIT = 100
DENSE_TEXT_MODE = "raw"


def coerce_item_id(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def load_painelconstru_benchmark() -> list[dict[str, Any]]:
    with BENCHMARK_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    real = [
        d
        for d in data
        if coerce_item_id(d.get("product_id")) not in (None, 0)
        and d.get("product_description") != "no_prod"
        and len(d.get("relevant_item_ids") or []) > 0
        and d.get("subcategory_id") not in (None, 0, "0")
    ]
    return real


def build_corpus(
    sampled_queries: list[dict[str, Any]],
    full_benchmark: list[dict[str, Any]],
    target_size: int,
    rng: random.Random,
) -> dict[int, dict[str, Any]]:
    """item_id -> {description, subcategory_id}. Inclui todos os itens
    relevantes das consultas amostradas + distratores aleatorios."""
    corpus: dict[int, dict[str, Any]] = {}
    for q in sampled_queries:
        for item in q.get("relevant_items") or []:
            item_id = coerce_item_id(item.get("item_id"))
            if item_id is not None and item_id not in corpus:
                corpus[item_id] = {
                    "description": str(item.get("item_description") or "").strip(),
                    "subcategory_id": item.get("subcategory_id"),
                }

    # pool de distratores: itens de TODAS as entradas do benchmark completo
    # (inclui os buckets "no_prod", que cobrem o catalogo inteiro)
    all_pool: dict[int, dict[str, Any]] = {}
    with BENCHMARK_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for entry in data:
        for item in entry.get("relevant_items") or []:
            item_id = coerce_item_id(item.get("item_id"))
            if item_id is not None and item_id not in all_pool:
                all_pool[item_id] = {
                    "description": str(item.get("item_description") or "").strip(),
                    "subcategory_id": item.get("subcategory_id"),
                }

    candidate_ids = [iid for iid in all_pool if iid not in corpus]
    rng.shuffle(candidate_ids)
    needed = max(target_size - len(corpus), 0)
    for item_id in candidate_ids[:needed]:
        corpus[item_id] = all_pool[item_id]

    corpus = {iid: v for iid, v in corpus.items() if v["description"]}
    return corpus


class Bm25Index:
    def __init__(self, tokenized_corpus: list[list[str]], *, k1: float = 1.5, b: float = 0.75):
        import math

        self.k1 = k1
        self.b = b
        self.document_lengths = [len(tokens) for tokens in tokenized_corpus]
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths) if self.document_lengths else 0.0
        )
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for document_index, tokens in enumerate(tokenized_corpus):
            frequencies: dict[str, int] = defaultdict(int)
            for token in tokens:
                frequencies[token] += 1
            for token, frequency in frequencies.items():
                self.postings[token].append((document_index, frequency))

        document_count = len(tokenized_corpus)
        self.idf = {
            token: math.log(1.0 + (document_count - len(entries) + 0.5) / (len(entries) + 0.5))
            for token, entries in self.postings.items()
        }

    def top_indices(self, query_tokens: list[str], limit: int) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for token in set(query_tokens):
            token_idf = self.idf.get(token)
            if token_idf is None:
                continue
            for document_index, frequency in self.postings[token]:
                length = self.document_lengths[document_index]
                normalization = 1.0 - self.b
                if self.average_document_length:
                    normalization += self.b * length / self.average_document_length
                denominator = frequency + self.k1 * normalization
                scores[document_index] += token_idf * (frequency * (self.k1 + 1.0) / denominator)
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]


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


def build_relevance_flags(items: list[dict[str, Any]], relevant_ids: set[int]) -> list[int]:
    flags: list[int] = []
    seen: set[int] = set()
    for item in items:
        item_id = coerce_item_id(item.get("item_id"))
        if item_id is None or item_id in seen:
            flags.append(0)
            continue
        seen.add(item_id)
        flags.append(1 if item_id in relevant_ids else 0)
    return flags


def rerank_flat_subcategoria(ranked_items, sub_by_item, query_sub):
    def score(item: dict) -> int:
        if query_sub is None or str(query_sub) in ("", "0", "-1"):
            return 0
        item_id = coerce_item_id(item.get("item_id"))
        return 1 if str(sub_by_item.get(item_id)) == str(query_sub) else 0
    return sorted(ranked_items, key=score, reverse=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(RANDOM_SEED)

    print("Carregando benchmark PainelConstru...")
    real_queries = load_painelconstru_benchmark()
    print(f"Consultas usaveis (>=1 item relevante e subcategoria definida): {len(real_queries)}")

    sampled_queries = rng.sample(real_queries, N_QUERIES)
    print(f"Amostradas {len(sampled_queries)} consultas (seed={RANDOM_SEED})")

    corpus = build_corpus(sampled_queries, real_queries, TARGET_CORPUS_SIZE, rng)
    print(f"Corpus de recuperacao: {len(corpus)} itens")

    item_ids = list(corpus.keys())
    descriptions = [corpus[iid]["description"] for iid in item_ids]
    sub_by_item = {iid: corpus[iid]["subcategory_id"] for iid in item_ids}

    from normalization import TextNormalizer

    normalizer = TextNormalizer()
    print("Tokenizando corpus para BM25...")
    tokenized_corpus = [normalizer.normalize(text).split() for text in descriptions]
    bm25_index = Bm25Index(tokenized_corpus)

    def retrieve_bm25(search_terms: str, limit: int) -> list[dict[str, Any]]:
        query_tokens = normalizer.normalize(search_terms).split()
        ranked = bm25_index.top_indices(query_tokens, limit)
        return [
            {"item_id": item_ids[idx], "description": descriptions[idx], "retrieval_score": float(score)}
            for idx, score in ranked
        ]

    print("Carregando/gerando embeddings BGE-M3 do corpus (pode demorar)...")
    import numpy as np
    from sentence_transformers import SentenceTransformer

    emb_path = BGE_M3_CACHE_DIR / "embeddings.npy"
    idx_path = BGE_M3_CACHE_DIR / "index.json"
    model = SentenceTransformer("BAAI/bge-m3")

    if emb_path.exists() and idx_path.exists():
        saved = json.load(open(idx_path, encoding="utf-8"))
        if saved.get("item_ids") == item_ids and saved.get("text_mode") == DENSE_TEXT_MODE:
            embeddings = np.load(str(emb_path))
        else:
            embeddings = None
    else:
        embeddings = None

    if embeddings is None:
        embeddings = model.encode(
            descriptions, batch_size=32, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True
        )
        BGE_M3_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(str(emb_path), embeddings)
        json.dump({"item_ids": item_ids, "text_mode": DENSE_TEXT_MODE}, open(idx_path, "w", encoding="utf-8"))

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
                item_id = coerce_item_id(item.get("item_id"))
                if item_id is None:
                    continue
                items_by_id.setdefault(item_id, item)
                scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (RRF_K + rank)
        ranked_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
        return [items_by_id[item_id] for item_id in ranked_ids]

    print("Rodando retrieval hibrido para as 100 consultas amostradas...")
    rows = []
    baseline_aps, flat_sub_aps = [], []
    for i, q in enumerate(sampled_queries, start=1):
        search_terms = str(q["product_description"])
        relevant_ids = set(coerce_item_id(x) for x in q["relevant_item_ids"] if coerce_item_id(x) in corpus)
        relevant_count = len(relevant_ids)
        query_sub = q.get("subcategory_id")

        if relevant_count == 0:
            continue

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)
        flat_sub_ranked = rerank_flat_subcategoria(baseline_ranked, sub_by_item, query_sub)

        baseline_flags = build_relevance_flags(baseline_ranked, relevant_ids)
        flat_sub_flags = build_relevance_flags(flat_sub_ranked, relevant_ids)

        baseline_ap = average_precision(baseline_flags, relevant_count)
        flat_sub_ap = average_precision(flat_sub_flags, relevant_count)
        baseline_aps.append(baseline_ap)
        flat_sub_aps.append(flat_sub_ap)

        rows.append(
            {
                "product_id": q["product_id"],
                "product_description": search_terms,
                "subcategory_id": query_sub,
                "relevant_count": relevant_count,
                "baseline_ap": baseline_ap,
                "flat_subcategoria_ap": flat_sub_ap,
                "delta": flat_sub_ap - baseline_ap,
            }
        )
        if i % 20 == 0 or i == len(sampled_queries):
            print(f"[{i}/{len(sampled_queries)}] processado")

    n = len(rows)
    map_baseline = sum(baseline_aps) / n
    map_flat_sub = sum(flat_sub_aps) / n

    print(f"\n=== PainelConstru -- {n} consultas ===")
    print(f"Baseline (hibrido BM25+BGE-M3):     {map_baseline:.4f}")
    print(f"Flat subcategoria:                  {map_flat_sub:.4f}  (delta {map_flat_sub-map_baseline:+.4f})")

    with (OUT_DIR / "painelconstru_subcategoria_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["product_id", "product_description", "subcategory_id", "relevant_count", "baseline_ap", "flat_subcategoria_ap", "delta"],
            delimiter=";",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    md = []
    md.append("# Validacao PainelConstru -- gate por subcategoria\n")
    md.append(
        f"Replica a descoberta de `results/subcategoria_rerank/` (SINAPI) em uma base "
        f"INDEPENDENTE: {N_QUERIES} consultas amostradas (seed={RANDOM_SEED}) do benchmark "
        f"PainelConstru (`class_match/ground_truth/benchmark_grouped_v4.json`, escolhido em vez "
        f"de `t-correlations-full4.tsv` por ja vir agrupado por consulta com "
        f"`relevant_item_ids`/`subcategory_id` prontos, mesmo formato usado a sessao inteira). "
        f"Corpus de recuperacao: {len(corpus)} itens (itens relevantes das consultas amostradas + "
        f"distratores aleatorios do catalogo completo de ~110 mil itens, reduzido por custo de "
        f"indexacao BGE-M3 em CPU).\n"
    )
    md.append("## Resultado\n")
    md.append("| Politica | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline (hibrido BM25+BGE-M3) | {map_baseline:.4f} | - |")
    md.append(f"| **Flat subcategoria** | **{map_flat_sub:.4f}** | **{map_flat_sub-map_baseline:+.4f}** |")
    md.append(
        f"\nPara referencia, no SINAPI (852 consultas, oraculo): flat subcategoria = 0.8016 "
        f"(+0.0084 sobre baseline 0.7932).\n"
    )
    md_path = OUT_DIR / "painelconstru_subcategoria_rerank_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
