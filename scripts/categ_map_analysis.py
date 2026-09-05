"""Quais subcategorias (topicos do BERTopic, nao categorias de sistema) tem o
maior e o menor MAP?

Reaproveita o modelo BERTopic ja treinado sobre o corpus combinado (mesma
config de scripts/eda_bertopic.py, embeddings cacheados em
eda/combined_items_all_embeddings.npy -> retreino aqui e deterministico e
rapido, ~40s) para obter as palavras-chave de TODOS os topicos (o relatorio
anterior so guardou o top 20). Cruza cada topico com o MAP medio das 900
consultas combinadas (852 reais + 48 sinteticas), nos 4 metodos comuns.

Saidas em eda/categ_map/:
  - topic_map_results.csv   (todas as topicas, todas as colunas)
  - topic_map_top_bottom.png (grafico dos N topicos com maior/menor MAP)
  - topic_map_resultados.md (resumo)
"""

from __future__ import annotations

import json
import os
import re
import time

import matplotlib.pyplot as plt
import nltk
import numpy as np
import pandas as pd
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer
from hdbscan import HDBSCAN
from umap import UMAP
from bertopic import BERTopic

nltk.download("stopwords", quiet=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS_TSV = os.path.join(BASE_DIR, "data", "combined_items_all.tsv")
EMB_CACHE = os.path.join(BASE_DIR, "eda", "combined_items_all_embeddings.npy")
BENCHMARK_REAL_JSON = os.path.join(BASE_DIR, "data", "ground_truth", "retrieval-benchmark-295.json")
PPC_WEAK_JSON = os.path.join(BASE_DIR, "data", "ground_truth", "ppc_weak_48.json")
RESULTS_REAL_JSON = os.path.join(BASE_DIR, "results", "real_295", "sinapi_llm_retrieval_results.json")
RESULTS_SYNTH_JSON = os.path.join(BASE_DIR, "results", "ppc_weak", "sinapi_llm_retrieval_results.json")
OUT_DIR = os.path.join(BASE_DIR, "eda", "categ_map")

COMMON_METHODS = ["bm25", "e5", "e5_hybrid", "bge_m3_hybrid"]
METHOD_LABELS = {"bm25": "BM25", "e5": "E5 puro", "e5_hybrid": "E5 hybrid", "bge_m3_hybrid": "BGE-M3 hybrid"}

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
MTS = 20
RANDOM_STATE = 42
UMAP_PARAMS = dict(n_neighbors=15, n_components=5, metric="cosine", min_dist=0.0, random_state=RANDOM_STATE)
MIN_QUERIES_FOR_RANKING = 5
TOP_N = 12

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


def retrain_bertopic() -> tuple[pd.DataFrame, "BERTopic"]:
    """Retreina o BERTopic (embeddings cacheados) para obter keywords de todos os topicos."""
    items = pd.read_csv(ITEMS_TSV, sep="\t", dtype=str, encoding="utf-8")
    items["description"] = items["description"].fillna("")
    items["docs_cust"] = items["description"].apply(preprocess_custom)
    mask = items["docs_cust"].str.len() >= 3
    items = items[mask].reset_index(drop=True)

    embeddings = np.load(EMB_CACHE)
    if embeddings.shape[0] != len(items):
        raise RuntimeError(
            f"Cache de embeddings ({embeddings.shape[0]}) nao bate com o corpus atual "
            f"({len(items)}). Rode scripts/eda_bertopic.py primeiro para recomputar o cache."
        )

    umap_model = UMAP(**UMAP_PARAMS)
    hdbscan_model = HDBSCAN(
        min_cluster_size=MTS, metric="euclidean", cluster_selection_method="eom", prediction_data=True,
    )
    vectorizer = CountVectorizer(stop_words=list(ALL_SW), ngram_range=(1, 2), min_df=3)

    print("Retreinando BERTopic (embeddings cacheados, deterministico)...")
    t0 = time.time()
    topic_model = BERTopic(
        umap_model=umap_model, hdbscan_model=hdbscan_model, vectorizer_model=vectorizer,
        verbose=False, calculate_probabilities=False,
    )
    topics, _ = topic_model.fit_transform(list(items["docs_cust"]), embeddings=embeddings)
    print(f"Concluido em {time.time() - t0:.1f}s")
    items["topic"] = topics
    return items, topic_model


def build_item_topic_maps(items: pd.DataFrame) -> tuple[dict[int, int], dict[int, int]]:
    item_to_topic_295: dict[int, int] = {}
    item_to_topic_4851: dict[int, int] = {}
    for _, row in items.iterrows():
        if pd.notna(row["codigo_295"]) and str(row["codigo_295"]).strip():
            item_to_topic_295[int(float(row["codigo_295"]))] = row["topic"]
        if pd.notna(row["codigo_4851"]) and str(row["codigo_4851"]).strip():
            item_to_topic_4851[int(float(row["codigo_4851"]))] = row["topic"]
    return item_to_topic_295, item_to_topic_4851


def load_query_topics(item_to_topic_295, item_to_topic_4851) -> pd.DataFrame:
    rows = []
    with open(BENCHMARK_REAL_JSON, encoding="utf-8") as f:
        benchmark = json.load(f)
    for entry in benchmark["items"]:
        for mut in entry["mutations"]:
            rel_ids = mut.get("relevant_item_ids") or []
            if not rel_ids:
                continue
            topic = item_to_topic_295.get(int(rel_ids[0]), -1)
            rows.append({"source": "real_295", "query_id": int(entry["codigo"]), "topic": topic})

    with open(PPC_WEAK_JSON, encoding="utf-8") as f:
        ppc = json.load(f)
    for entry in ppc["items"]:
        codigo = int(entry["codigo"])
        topic = item_to_topic_4851.get(codigo, -1)
        for mut in entry["mutations"]:
            rows.append({"source": "synthetic_4851", "query_id": int(mut["mut_ID"]), "topic": topic})

    return pd.DataFrame(rows)


def load_per_query_map() -> pd.DataFrame:
    rows = []
    with open(RESULTS_REAL_JSON, encoding="utf-8") as f:
        for r in json.load(f)["results"]:
            if r.get("method") in COMMON_METHODS and r.get("success"):
                rows.append({"source": "real_295", "query_id": int(r["product_id"]), "method": r["method"], "map": r["map"]})
    with open(RESULTS_SYNTH_JSON, encoding="utf-8") as f:
        for r in json.load(f)["results"]:
            if r.get("method") in COMMON_METHODS and r.get("success"):
                rows.append({"source": "synthetic_4851", "query_id": int(r["product_id"]), "method": r["method"], "map": r["map"]})
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    items, topic_model = retrain_bertopic()
    info = topic_model.get_topic_info()
    topic_words = {int(row["Topic"]): ", ".join(row["Representation"][:6]) for _, row in info.iterrows()}
    topic_size = {int(row["Topic"]): int(row["Count"]) for _, row in info.iterrows()}

    item_to_topic_295, item_to_topic_4851 = build_item_topic_maps(items)

    query_topics = load_query_topics(item_to_topic_295, item_to_topic_4851)
    query_maps = load_per_query_map()

    merged = query_maps.merge(query_topics, on=["source", "query_id"], how="inner")
    print(f"Consultas com topico + MAP resolvidos: {merged[['source','query_id']].drop_duplicates().shape[0]} "
          f"(esperado 900); linhas metodo x consulta: {len(merged)}")

    # --- Pivot: MAP medio por topico e metodo ---------------------------------
    pivot = merged.pivot_table(index="topic", columns="method", values="map", aggfunc="mean")
    n_queries = merged[merged["method"] == "bm25"].groupby("topic").size().rename("n_queries")
    n_real = merged[(merged["method"] == "bm25") & (merged["source"] == "real_295")].groupby("topic").size().rename("n_real")
    n_synth = merged[(merged["method"] == "bm25") & (merged["source"] == "synthetic_4851")].groupby("topic").size().rename("n_synth")

    result = pivot.join(n_queries).join(n_real, how="left").join(n_synth, how="left")
    result["n_real"] = result["n_real"].fillna(0).astype(int)
    result["n_synth"] = result["n_synth"].fillna(0).astype(int)
    result["map_medio"] = result[COMMON_METHODS].mean(axis=1)
    result["keywords"] = [("outliers (sem tópico coerente)" if t == -1 else topic_words.get(int(t), "?")) for t in result.index]
    result["item_count_no_topico"] = [topic_size.get(int(t), 0) for t in result.index]
    result = result.reset_index().rename(columns={"topic": "topic_id"})
    result = result.sort_values("map_medio", ascending=False)

    cols_order = ["topic_id", "keywords", "n_queries", "n_real", "n_synth", "item_count_no_topico",
                  "map_medio"] + COMMON_METHODS
    result = result[cols_order]

    out_csv = os.path.join(OUT_DIR, "topic_map_results.csv")
    result.to_csv(out_csv, sep=";", index=False, float_format="%.4f")
    print(f"CSV salvo em: {out_csv}  ({len(result)} tópicos)")

    # --- Ranking (min N consultas para confiabilidade) ------------------------
    ranked = result[result["n_queries"] >= MIN_QUERIES_FOR_RANKING].copy()
    ranked = ranked.sort_values("map_medio", ascending=False)
    best = ranked.head(TOP_N)
    worst = ranked.tail(TOP_N).sort_values("map_medio")

    report: list[str] = []
    report.append("# MAP por Subcategoria (Tópicos BERTopic) — Melhores e Piores\n")
    report.append(f"Tópicos definidos por BERTopic sobre o corpus combinado (7.252 itens, mesma config de "
                   f"`scripts/eda_bertopic.py`). MAP médio das 900 consultas combinadas (852 reais + 48 sintéticas), "
                   f"média dos 4 métodos comuns ({', '.join(METHOD_LABELS[m] for m in COMMON_METHODS)}). "
                   f"Ranking considera apenas tópicos com >= {MIN_QUERIES_FOR_RANKING} consultas "
                   f"({len(ranked)} de {len(result)} tópicos qualificam).\n")

    report.append(f"\n## Top {TOP_N} tópicos com MAIOR MAP\n")
    report.append("| Tópico | Palavras-chave | N consultas | MAP médio |")
    report.append("|---|---|---|---|")
    for _, row in best.iterrows():
        label = "outliers" if row["topic_id"] == -1 else f"T{int(row['topic_id'])}"
        report.append(f"| {label} | {row['keywords']} | {int(row['n_queries'])} | {row['map_medio']:.4f} |")

    report.append(f"\n## Top {TOP_N} tópicos com MENOR MAP\n")
    report.append("| Tópico | Palavras-chave | N consultas | MAP médio |")
    report.append("|---|---|---|---|")
    for _, row in worst.iterrows():
        label = "outliers" if row["topic_id"] == -1 else f"T{int(row['topic_id'])}"
        report.append(f"| {label} | {row['keywords']} | {int(row['n_queries'])} | {row['map_medio']:.4f} |")

    outlier_row = result[result["topic_id"] == -1]
    if not outlier_row.empty:
        report.append(f"\n*Nota: tópico -1 ('outliers') agrupa itens que o BERTopic não conseguiu associar a "
                       f"nenhum cluster coerente — {int(outlier_row.iloc[0]['n_queries'])} consultas, "
                       f"MAP médio {outlier_row.iloc[0]['map_medio']:.4f}.*")

    out_md = os.path.join(OUT_DIR, "topic_map_resultados.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"Relatorio salvo em: {out_md}")

    # --- Grafico: top/bottom N ------------------------------------------------
    plot_df = pd.concat([best, worst]).drop_duplicates(subset="topic_id")
    plot_df = plot_df.sort_values("map_medio")
    labels = [
        (f"outliers ({int(r['n_queries'])})" if r["topic_id"] == -1 else f"T{int(r['topic_id'])} ({int(r['n_queries'])})")
        + " — " + ", ".join(r["keywords"].split(", ")[:3])
        for _, r in plot_df.iterrows()
    ]
    colors = ["#16a34a" if v >= plot_df["map_medio"].median() else "#dc2626" for v in plot_df["map_medio"]]

    fig, ax = plt.subplots(figsize=(12, max(6, 0.35 * len(plot_df))))
    ax.barh(labels, plot_df["map_medio"], color=colors)
    ax.set_xlabel("MAP médio (4 métodos, 900 consultas combinadas)")
    ax.set_xlim(0, 1.0)
    ax.set_title(f"Subcategorias (tópicos BERTopic) com maior e menor MAP\n"
                 f"(tópicos com >= {MIN_QUERIES_FOR_RANKING} consultas; verde = acima da mediana, vermelho = abaixo)")
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    out_png = os.path.join(OUT_DIR, "topic_map_top_bottom.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Grafico salvo em: {out_png}")


if __name__ == "__main__":
    main()
