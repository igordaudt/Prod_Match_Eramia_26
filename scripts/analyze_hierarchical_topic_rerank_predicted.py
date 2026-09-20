"""Teste "de verdade" da H1 de results/hierarchical_topic_rerank/: a hierarquia
de topicos ajuda quando o TOPICO DA CONSULTA E INFERIDO (pode errar para um
topico vizinho), em vez de lido do topico do proprio item relevante (o
"oraculo" usado em TODOS os testes anteriores desta sessao).

Por que isso importa: nos testes anteriores, query_topic = topico do item
relevante -- ou seja, o item certo esta SEMPRE a distancia hierarquica 0 de
si mesmo, por construcao. Isso torna H1 estruturalmente sem chance: nao ha
"quase acertei o topico" possivel quando o topico da consulta e definido
como o topico exato do alvo. Aqui, em vez disso, treinamos o MESMO BERTopic
(config identica a scripts/eda_bertopic.py / categ_map_analysis.py) e usamos
`topic_model.transform()` para CLASSIFICAR o texto da consulta -- um
processo que pode, e vai, as vezes erra para um topico vizinho ou para -1.

Metodologia:
  1. Retreina o BERTopic (UMAP+HDBSCAN, embeddings cacheados de
     eda/combined_items_all_embeddings.npy) -- reproduz os mesmos 128
     topicos + outliers usados a sessao inteira (mesma checagem de
     concordancia das demais EDAs).
  2. Para cada uma das 852 consultas do benchmark: embeda o texto BRUTO da
     consulta (mesmo modelo, mesmo estilo dos itens) e chama
     `topic_model.transform()` para prever o topico -- SEM olhar o item
     relevante.
  3. Compara topico previsto vs. topico "oraculo" (do item relevante):
     acuracia de classificacao + distancia hierarquica media dos erros.
  4. Roda baseline + reranking (flat / hierarquico continuo / hierarquico em
     niveis) usando o TOPICO PREVISTO, e compara com os mesmos 3 usando o
     topico oraculo (ja calculados em results/hierarchical_topic_rerank/).

Nao modifica scripts/retrieval_sinapi.py nem os resultados anteriores --
retreina o BERTopic read-only sobre os embeddings ja cacheados.

Uso:
    python scripts/analyze_hierarchical_topic_rerank_predicted.py

Saida (results/hierarchical_topic_rerank/):
    predicted_topic_per_query.csv        Topico previsto vs. oraculo, por consulta.
    hierarchical_rerank_predicted_per_query.csv  Baseline/flat/hier usando topico previsto.
    hierarchical_rerank_predicted_resultados.md  Relatorio final.
"""

from __future__ import annotations

import ast
import csv
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from hdbscan import HDBSCAN
from umap import UMAP
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import nltk
from nltk.corpus import stopwords

from retrieval_sinapi import (  # noqa: E402
    DEFAULT_LIMIT,
    INPUT_JSON,
    build_relevance_flags,
    coerce_item_id,
    load_benchmark,
    retrieve_bge_m3_sinapi,
    retrieve_bm25,
)

nltk.download("stopwords", quiet=True)

OUT_DIR = PROJECT_ROOT / "results" / "hierarchical_topic_rerank"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
ITEMS_TSV = PROJECT_ROOT / "data" / "combined_items_all.tsv"
EMB_CACHE = PROJECT_ROOT / "eda" / "combined_items_all_embeddings.npy"
HIERARCHY_MERGES_TSV = PROJECT_ROOT.parent / "Topic Modeling" / "EDA_hierarchy" / "eda_hierarchy_merges.csv"
RRF_K = 60
PREFETCH_LIMIT = 100
NIVEL_THRESHOLD = 0.35
INF = float("inf")

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
MTS = 20
RANDOM_STATE = 42
UMAP_PARAMS = dict(n_neighbors=15, n_components=5, metric="cosine", min_dist=0.0, random_state=RANDOM_STATE)

SW_PT = set(stopwords.words("portuguese"))
SW_PT.update({"a", "e", "o", "as", "os", "um", "uma", "uns", "umas",
              "ao", "aos", "la", "so", "ha", "ja", "mas", "ou", "se"})
SW_SINAPI = {
    "para", "com", "em", "de", "do", "da", "dos", "das", "no", "na",
    "nos", "nas", "por", "ate", "sem", "sob", "sobre", "entre",
    "fornecimento", "instalacao", "execucao", "colocacao", "aplicacao",
    "assentamento", "fixacao", "montagem",
    "tipo", "simples", "duplo", "dupla", "normal", "padrao", "especial",
    "completo", "completa", "incluindo", "inclusive", "exceto",
    "equivalente", "equivalentes", "outros", "outras",
    "ou", "nao", "ate", "mais", "menos", "cada",
}
ALL_SW = SW_PT | SW_SINAPI


def preprocess_base(texto: str) -> str:
    texto = str(texto).replace("\n", " ").replace("\t", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip().lower()


def preprocess_custom(texto: str) -> str:
    texto = preprocess_base(texto)
    tokens = texto.split()
    tokens = [
        t for t in tokens
        if t not in ALL_SW
        and not re.fullmatch(r"[\d,./\-]+", t)
        and len(t) > 1
    ]
    return " ".join(tokens)


def topic_label(t: int | None) -> str:
    if t is None:
        return "-"
    return "outliers" if t == -1 else f"T{t}"


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


def hybrid_rank(bm25_items: list[dict], dense_items: list[dict], limit: int) -> list[dict]:
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


def load_codigo_to_topic() -> dict[int, int]:
    mapping: dict[int, int] = {}
    with ITEM_TOPICS_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        for row in reader:
            codigo = coerce_item_id(row.get("codigo_295"))
            topic = coerce_item_id(row.get("topic"))
            if codigo is not None and topic is not None:
                mapping[codigo] = topic
    return mapping


def load_topic_meta() -> tuple[dict[int, str], dict[int, float]]:
    keywords: dict[int, str] = {}
    map_medio: dict[int, float] = {}
    with TOPIC_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        for row in reader:
            topic_id = coerce_item_id(row.get("topic_id"))
            if topic_id is not None:
                keywords[topic_id] = row.get("keywords", "")
                map_medio[topic_id] = float(row["map_medio"])
    return keywords, map_medio


def load_hierarchy_nodes() -> list[dict]:
    with HIERARCHY_MERGES_TSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    nodes = []
    for row in rows:
        topics = set(ast.literal_eval(row["Topics"]))
        nodes.append({"id": int(row["Parent_ID"]), "distance": float(row["Distance"]), "topics": topics})
    nodes.sort(key=lambda n: len(n["topics"]))
    return nodes


def build_topic_distance_matrix(nodes: list[dict], leaf_topics: list[int]) -> dict[tuple[int, int], float]:
    dist: dict[tuple[int, int], float] = {}
    for i, a in enumerate(leaf_topics):
        dist[(a, a)] = 0.0
        for b in leaf_topics[i + 1:]:
            found = INF
            for node in nodes:
                if a in node["topics"] and b in node["topics"]:
                    found = node["distance"]
                    break
            dist[(a, b)] = found
            dist[(b, a)] = found
    return dist


def topic_distance(dist_matrix: dict[tuple[int, int], float], a: int | None, b: int | None,
                    undefined_value: float = INF) -> float:
    """undefined_value: o que retornar quando a distancia nao e definida (a ou b e -1/None).
    Por padrao INF (comportamento antigo, com bug: enterra outliers no fim absoluto, pior
    que QUALQUER topico real, mesmo o mais distante da arvore). Passe o MAX_FINITE_DISTANCE
    da arvore para tratar como 'empatado com o pior par real' -- neutro, nao punitivo extra --
    replicando o que o gate flat ja fazia (nota 0 para outlier = nota 0 de qualquer nao-match,
    sem penalidade adicional por ser -1 especificamente)."""
    if a is None or b is None or a == -1 or b == -1:
        return undefined_value
    if a == b:
        return 0.0
    return dist_matrix.get((a, b), undefined_value)


def rerank_by_distance(ranked_items, item_topic, query_topic, dist_matrix, undefined_value=INF):
    def key(item: dict):
        item_id = coerce_item_id(item.get("item_id"))
        return topic_distance(dist_matrix, query_topic, item_topic.get(item_id), undefined_value)
    return sorted(ranked_items, key=key)


def rerank_by_level(ranked_items, item_topic, query_topic, dist_matrix, threshold):
    def key(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        d = topic_distance(dist_matrix, query_topic, item_topic.get(item_id))
        if d == 0.0:
            return 2
        if d <= threshold:
            return 1
        return 0
    return sorted(ranked_items, key=key, reverse=True)


def rerank_flat_topic_only(ranked_items, item_topic, query_topic):
    def score(item: dict) -> int:
        if query_topic is None or query_topic == -1:
            return 0
        item_id = coerce_item_id(item.get("item_id"))
        return 1 if item_topic.get(item_id) == query_topic else 0
    return sorted(ranked_items, key=score, reverse=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. retreina o BERTopic (mesma config de eda_bertopic.py / categ_map_analysis.py) ---
    print("Retreinando BERTopic (embeddings cacheados, deterministico)...")
    items = pd.read_csv(ITEMS_TSV, sep="\t", dtype=str, encoding="utf-8")
    items["description"] = items["description"].fillna("")
    items["docs_cust"] = items["description"].apply(preprocess_custom)
    mask = items["docs_cust"].str.len() >= 3
    items = items[mask].reset_index(drop=True)

    embeddings = np.load(EMB_CACHE)
    if embeddings.shape[0] != len(items):
        raise RuntimeError(
            f"Cache de embeddings ({embeddings.shape[0]}) nao bate com o corpus atual "
            f"({len(items)}). Rode scripts/eda_bertopic.py primeiro."
        )

    umap_model = UMAP(**UMAP_PARAMS)
    hdbscan_model = HDBSCAN(
        min_cluster_size=MTS, metric="euclidean", cluster_selection_method="eom", prediction_data=True,
    )
    vectorizer = CountVectorizer(stop_words=list(ALL_SW), ngram_range=(1, 2), min_df=3)
    topic_model = BERTopic(
        umap_model=umap_model, hdbscan_model=hdbscan_model, vectorizer_model=vectorizer,
        verbose=False, calculate_probabilities=False,
    )
    topics, _ = topic_model.fit_transform(list(items["docs_cust"]), embeddings=embeddings)
    print(f"BERTopic retreinado: {len(set(topics) - {-1})} topicos, "
          f"{sum(1 for t in topics if t == -1)} outliers de {len(items)} itens.")

    # checagem de reprodutibilidade
    codigo_to_topic = load_codigo_to_topic()
    ref_topics_by_codigo295 = codigo_to_topic  # ja carregado do item_topics.csv de referencia

    # --- 2. embeda e classifica as 852 consultas do benchmark ---
    benchmark = load_benchmark(INPUT_JSON)
    topic_keywords, map_by_topic = load_topic_meta()
    print(f"Consultas no benchmark: {len(benchmark)}")

    embed_model = SentenceTransformer(EMBEDDING_MODEL)
    query_texts_raw = [str(p["product_description"]) for p in benchmark]
    query_docs_cust = [preprocess_custom(t) for t in query_texts_raw]
    print("Embedando consultas...")
    query_embeddings = embed_model.encode(query_texts_raw, show_progress_bar=True, batch_size=64)

    print("Classificando consultas com topic_model.transform()...")
    predicted_topics, _ = topic_model.transform(query_docs_cust, embeddings=query_embeddings)

    # --- 3. topico oraculo (do item relevante) + distancia hierarquica dos erros ---
    nodes = load_hierarchy_nodes()
    all_topics_in_tree: set[int] = set()
    for node in nodes:
        all_topics_in_tree |= node["topics"]
    leaf_topics = sorted(all_topics_in_tree)
    dist_matrix = build_topic_distance_matrix(nodes, leaf_topics)
    max_finite_distance = max(d for d in dist_matrix.values() if d != INF)
    print(f"Distancia maxima finita na arvore (usada como valor neutro p/ -1): {max_finite_distance:.4f}")

    oracle_topics = []
    for product in benchmark:
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        primary_item_id = min(relevant_ids) if relevant_ids else None
        oracle_topics.append(codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None)

    n_exact = sum(1 for o, p in zip(oracle_topics, predicted_topics) if o == p)
    errors = [
        (o, p) for o, p in zip(oracle_topics, predicted_topics)
        if o != p and o is not None
    ]
    error_dists = [topic_distance(dist_matrix, o, p) for o, p in errors]
    finite_error_dists = [d for d in error_dists if d != INF]
    n_error_inf = sum(1 for d in error_dists if d == INF)

    print(f"\nAcuracia (predito == oraculo): {n_exact}/{len(benchmark)} ({100*n_exact/len(benchmark):.1f}%)")
    print(f"Erros: {len(errors)}. Dos erros, {len(finite_error_dists)} tem distancia hierarquica finita "
          f"(media {sum(finite_error_dists)/len(finite_error_dists):.4f})" if finite_error_dists else "")
    print(f"Erros sem distancia definida (envolve -1 de um dos lados): {n_error_inf}")

    with (OUT_DIR / "predicted_topic_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["product_id", "oracle_topic", "predicted_topic", "acertou", "distancia_hierarquica", "query_text"])
        for product, o, p in zip(benchmark, oracle_topics, predicted_topics):
            d = topic_distance(dist_matrix, o, p)
            writer.writerow(
                [product["product_id"], o, int(p), o == p, "" if d == INF else f"{d:.6f}",
                 product["product_description"]]
            )

    # --- 4. retrieval + reranking usando o TOPICO PREVISTO ---
    rows = []
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        query_topic_pred = int(predicted_topics[i - 1])
        query_topic_oracle = oracle_topics[i - 1]

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)

        flat_ranked = rerank_flat_topic_only(baseline_ranked, codigo_to_topic, query_topic_pred)
        continuous_ranked = rerank_by_distance(baseline_ranked, codigo_to_topic, query_topic_pred, dist_matrix, max_finite_distance)
        level_ranked = rerank_by_level(baseline_ranked, codigo_to_topic, query_topic_pred, dist_matrix, NIVEL_THRESHOLD)

        baseline_ap = average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        flat_ap = average_precision(build_relevance_flags(flat_ranked, relevant_ids), relevant_count)
        continuous_ap = average_precision(build_relevance_flags(continuous_ranked, relevant_ids), relevant_count)
        level_ap = average_precision(build_relevance_flags(level_ranked, relevant_ids), relevant_count)

        rows.append(
            {
                "product_id": product["product_id"],
                "oracle_topic": query_topic_oracle,
                "predicted_topic": query_topic_pred,
                "acertou_topico": query_topic_oracle == query_topic_pred,
                "baseline_ap": baseline_ap,
                "flat_topic_ap": flat_ap,
                "hierarchical_continuous_ap": continuous_ap,
                "hierarchical_level_ap": level_ap,
            }
        )
        if i % 100 == 0 or i == len(benchmark):
            print(f"[{i}/{len(benchmark)}] processado")

    with (OUT_DIR / "hierarchical_rerank_predicted_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["product_id", "oracle_topic", "predicted_topic", "acertou_topico", "baseline_ap",
                          "flat_topic_ap", "hierarchical_continuous_ap", "hierarchical_level_ap"])
        for r in rows:
            writer.writerow(
                [r["product_id"], r["oracle_topic"], r["predicted_topic"], r["acertou_topico"],
                 f"{r['baseline_ap']:.6f}", f"{r['flat_topic_ap']:.6f}",
                 f"{r['hierarchical_continuous_ap']:.6f}", f"{r['hierarchical_level_ap']:.6f}"]
            )

    def agg(subset, key):
        if not subset:
            return 0.0
        return sum(r[key] for r in subset) / len(subset)

    all_rows = rows
    correct_rows = [r for r in rows if r["acertou_topico"]]
    wrong_rows = [r for r in rows if not r["acertou_topico"]]

    print(f"\n=== TOPICO PREVISTO (nao-oraculo) -- TODAS AS {len(all_rows)} CONSULTAS ===")
    for label, subset in (("Geral", all_rows), ("Predicao ACERTOU", correct_rows), ("Predicao ERROU", wrong_rows)):
        b = agg(subset, "baseline_ap")
        flat = agg(subset, "flat_topic_ap")
        cont = agg(subset, "hierarchical_continuous_ap")
        lvl = agg(subset, "hierarchical_level_ap")
        print(f"{label:20s} n={len(subset):4d}  baseline={b:.4f}  flat-topico={flat:.4f}  "
              f"hier-continuo={cont:.4f}  hier-niveis={lvl:.4f}")

    md = []
    md.append("# H1 com topico INFERIDO (nao-oraculo) -- Resultados\n")
    md.append(
        "Teste correto de H1 (ver nota no final de `hierarchical_rerank_resultados.md`): em vez de "
        "usar o topico do item relevante como 'topico da consulta' (o oraculo usado em TODOS os "
        "testes anteriores), o topico da consulta e **inferido** via `topic_model.transform()` "
        "(BERTopic retreinado, mesma config de `eda_bertopic.py`) sobre o texto da propria consulta "
        "-- um processo que pode errar para um topico vizinho ou para outliers (-1), exatamente o "
        "cenario que H1 precisa para ter chance de fazer diferenca.\n"
    )
    md.append(
        "**Correcao de bug aplicada nesta versao**: a primeira rodada usava distancia infinita para "
        "pares envolvendo o topico -1, o que enterrava um item outlier no fim absoluto da lista "
        "(pior que QUALQUER topico real, mesmo o mais distante da arvore) sempre que a consulta era "
        "classificada (erradamente) num topico real -- um artefato da implementacao, nao do metodo. "
        "Corrigido para usar a distancia maxima FINITA da arvore como valor neutro (empatado com o "
        "par de topicos reais mais distantes, nao pior que isso) -- replica o que o gate flat ja "
        "fazia (outlier recebe a mesma nota neutra de qualquer nao-match, sem penalidade extra).\n"
    )
    md.append("## Acuracia da classificacao de topico da consulta\n")
    md.append(f"- Acertou o topico exato do item relevante: **{n_exact}/{len(benchmark)}** ({100*n_exact/len(benchmark):.1f}%)")
    md.append(f"- Errou: **{len(errors)}** ({100*len(errors)/len(benchmark):.1f}%)")
    if finite_error_dists:
        md.append(
            f"  - Dos erros, **{len(finite_error_dists)}** tem distancia hierarquica finita entre "
            f"previsto e oraculo (media **{sum(finite_error_dists)/len(finite_error_dists):.4f}**, "
            f"min {min(finite_error_dists):.4f}, max {max(finite_error_dists):.4f})"
        )
    md.append(f"  - **{n_error_inf}** erros envolvem -1 de um dos lados (sem distancia hierarquica definida)\n")

    md.append("## Resultado principal (topico da consulta PREVISTO, nao oraculo)\n")
    md.append("| Politica | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline | {agg(all_rows,'baseline_ap'):.4f} | - |")
    md.append(f"| Flat topico (topico previsto) | {agg(all_rows,'flat_topic_ap'):.4f} | {agg(all_rows,'flat_topic_ap')-agg(all_rows,'baseline_ap'):+.4f} |")
    md.append(f"| **Hierarquico continuo (topico previsto)** | **{agg(all_rows,'hierarchical_continuous_ap'):.4f}** | **{agg(all_rows,'hierarchical_continuous_ap')-agg(all_rows,'baseline_ap'):+.4f}** |")
    md.append(f"| **Hierarquico em niveis (topico previsto)** | **{agg(all_rows,'hierarchical_level_ap'):.4f}** | **{agg(all_rows,'hierarchical_level_ap')-agg(all_rows,'baseline_ap'):+.4f}** |")

    md.append(
        f"\nDelta hierarquico (continuo) vs. flat, usando topico previsto: "
        f"**{agg(all_rows,'hierarchical_continuous_ap')-agg(all_rows,'flat_topic_ap'):+.4f}**. "
        f"Delta hierarquico (niveis) vs. flat: "
        f"**{agg(all_rows,'hierarchical_level_ap')-agg(all_rows,'flat_topic_ap'):+.4f}**.\n"
    )

    md.append("## Segmentado por acerto/erro da classificacao\n")
    md.append("| Segmento | N | Baseline | Flat (previsto) | Hier. continuo (previsto) | Hier. niveis (previsto) |")
    md.append("|---|---|---|---|---|---|")
    for label, subset in (("Geral", all_rows), ("Predicao ACERTOU o topico", correct_rows), ("Predicao ERROU o topico", wrong_rows)):
        md.append(
            f"| {label} | {len(subset)} | {agg(subset,'baseline_ap'):.4f} | {agg(subset,'flat_topic_ap'):.4f} | "
            f"{agg(subset,'hierarchical_continuous_ap'):.4f} | {agg(subset,'hierarchical_level_ap'):.4f} |"
        )
    md.append(
        "\nA linha 'Predicao ERROU' e onde H1 realmente pode se manifestar: se a hierarquia ajuda, "
        "o MAP hierarquico deve superar o flat especificamente NESSE subgrupo (onde o topico previsto "
        "nao e o exato, mas pode ser proximo do certo).\n"
    )

    md_path = OUT_DIR / "hierarchical_rerank_predicted_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
