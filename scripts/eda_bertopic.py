"""EDA via BERTopic sobre o corpus de itens COMBINADO deste estudo
(data/combined_items_all.tsv, 7.252 itens unicos = uniao deduplicada do
corpus real de 5.813 itens + corpus sintetico de 4.851 itens).

Reaproveita a configuracao validada em '../Topic Modeling/tarefa2c_preprocessing.py'
(melhor combinacao identificada no relatorio final: embeddings
paraphrase-multilingual-MiniLM-L12-v2 + UMAP + HDBSCAN min_cluster_size=20 +
pre-processamento customizado com stopwords do dominio + bigramas).

Alem da modelagem de topicos, cruza:
  (a) os topicos dos itens-alvo das 900 consultas combinadas (852 reais +
      48 sinteticas) — distribuicao tematica de cada subconjunto;
  (b) o MAP medio por topico e por metodo de retrieval, combinando
      results/real_295/sinapi_llm_retrieval_results.json (real) e
      results/ppc_weak/sinapi_llm_retrieval_results.json (sintetico), para
      os 4 metodos comuns aos dois conjuntos.

Gerar data/combined_items_all.tsv com scripts/build_combined_dataset.py
antes de rodar este script.
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
from sentence_transformers import SentenceTransformer

nltk.download("stopwords", quiet=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS_TSV = os.path.join(BASE_DIR, "data", "combined_items_all.tsv")
BENCHMARK_JSON = os.path.join(BASE_DIR, "data", "ground_truth", "retrieval-benchmark-295.json")
PPC_WEAK_JSON = os.path.join(BASE_DIR, "data", "ground_truth", "ppc_weak_48.json")
RESULTS_REAL_JSON = os.path.join(BASE_DIR, "results", "real_295", "sinapi_llm_retrieval_results.json")
RESULTS_SYNTH_JSON = os.path.join(BASE_DIR, "results", "ppc_weak", "sinapi_llm_retrieval_results.json")
EMB_CACHE = os.path.join(BASE_DIR, "eda", "combined_items_all_embeddings.npy")
OUT_DIR = os.path.join(BASE_DIR, "eda")

COMMON_METHODS = ["bm25", "e5", "e5_hybrid", "bge_m3_hybrid"]

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
MTS = 20
RANDOM_STATE = 42
UMAP_PARAMS = dict(n_neighbors=15, n_components=5, metric="cosine", min_dist=0.0, random_state=RANDOM_STATE)

SW_PT = set(stopwords.words("portuguese"))
SW_PT.update({"a", "e", "o", "as", "os", "um", "uma", "uns", "umas",
              "ao", "aos", "la", "so", "ha", "ja", "mas", "ou", "se"})

# Reaproveitado de Topic Modeling/tarefa2c_preprocessing.py
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


def load_or_compute_embeddings(texts: list[str]) -> np.ndarray:
    if os.path.exists(EMB_CACHE):
        emb = np.load(EMB_CACHE)
        if emb.shape[0] == len(texts):
            print(f"Embeddings carregados do cache: {EMB_CACHE} {emb.shape}")
            return emb
        print("Cache de embeddings nao bate com o corpus atual — recomputando.")

    print(f"Computando embeddings com {EMBEDDING_MODEL} para {len(texts):,} textos...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    t0 = time.time()
    emb = model.encode(texts, show_progress_bar=True, batch_size=64)
    print(f"Embeddings computados em {time.time() - t0:.1f}s")
    np.save(EMB_CACHE, emb)
    return emb


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 65)
    print("EDA — BERTopic sobre o corpus de itens COMBINADO (real + sintético)")
    print("=" * 65)

    items = pd.read_csv(ITEMS_TSV, sep="\t", dtype=str, encoding="utf-8")
    items["description"] = items["description"].fillna("")
    items["docs_cust"] = items["description"].apply(preprocess_custom)

    mask = items["docs_cust"].str.len() >= 3
    items = items[mask].reset_index(drop=True)
    print(f"Itens validos apos pre-processamento: {len(items):,}")

    embeddings = load_or_compute_embeddings(list(items["description"]))

    umap_model = UMAP(**UMAP_PARAMS)
    hdbscan_model = HDBSCAN(
        min_cluster_size=MTS,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    vectorizer = CountVectorizer(stop_words=list(ALL_SW), ngram_range=(1, 2), min_df=3)

    print("\nTreinando BERTopic (UMAP + HDBSCAN + custom/bigramas)...")
    t0 = time.time()
    topic_model = BERTopic(
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        verbose=False,
        calculate_probabilities=False,
    )
    topics, _ = topic_model.fit_transform(list(items["docs_cust"]), embeddings=embeddings)
    elapsed = time.time() - t0
    items["topic"] = topics

    info = topic_model.get_topic_info()
    n_topicos = len(info) - 1 if -1 in info["Topic"].values else len(info)
    n_outliers = int(info.loc[info["Topic"] == -1, "Count"].values[0]) if -1 in info["Topic"].values else 0
    pct_out = n_outliers / len(items) * 100

    print(f"\nTopicos: {n_topicos} | Outliers: {n_outliers} ({pct_out:.1f}%) | Tempo: {elapsed:.1f}s")

    items[["description", "codigo_295", "codigo_4851", "source", "topic"]].to_csv(
        os.path.join(OUT_DIR, "item_topics.csv"), sep="\t", index=False
    )

    # Mapas de codigo (por espaco de ID) -> topico, para resolver os dois conjuntos de consultas.
    item_to_topic_295: dict[int, int] = {}
    item_to_topic_4851: dict[int, int] = {}
    for _, row in items.iterrows():
        if pd.notna(row["codigo_295"]) and str(row["codigo_295"]).strip():
            item_to_topic_295[int(float(row["codigo_295"]))] = row["topic"]
        if pd.notna(row["codigo_4851"]) and str(row["codigo_4851"]).strip():
            item_to_topic_4851[int(float(row["codigo_4851"]))] = row["topic"]

    # --- Top 20 topicos com rotulo automatico (top-3 palavras) --------------
    top20 = info[info["Topic"] != -1].head(20).copy()
    top20["rotulo_auto"] = top20["Representation"].apply(lambda ws: " / ".join(ws[:3]))

    report: list[str] = []
    report.append(f"# EDA — BERTopic sobre o Corpus de Itens Combinado ({len(items):,} itens, real + sintético)\n")
    report.append(f"Configuracao: embeddings `{EMBEDDING_MODEL}`, UMAP {UMAP_PARAMS}, "
                   f"HDBSCAN(min_cluster_size={MTS}), CountVectorizer(custom+bigramas, min_df=3). "
                   f"Reaproveitada de `Topic Modeling/tarefa2c_preprocessing.py` (melhor config identificada).")
    report.append(f"\n- Topicos encontrados: **{n_topicos}**")
    report.append(f"- Outliers (topico -1): {n_outliers} ({pct_out:.1f}%)")
    report.append(f"- Tempo de treinamento: {elapsed:.1f}s")

    report.append("\n## Top 20 tópicos por tamanho\n")
    report.append("| # | Tópico | Docs | Palavras-chave (top-7) |")
    report.append("|---|---|---|---|")
    for i, (_, row) in enumerate(top20.iterrows(), start=1):
        palavras = ", ".join(row["Representation"][:7])
        report.append(f"| {i} | T{int(row['Topic'])} | {int(row['Count'])} | {palavras} |")

    topic_words = {int(row["Topic"]): ", ".join(row["Representation"][:5]) for _, row in info.iterrows()}

    # --- Distribuicao tematica dos dois conjuntos de consultas ---------------
    with open(BENCHMARK_JSON, encoding="utf-8") as f:
        benchmark = json.load(f)
    gt_topics_real = []
    for entry in benchmark["items"]:
        for mut in entry["mutations"]:
            rel_ids = mut.get("relevant_item_ids") or []
            if rel_ids:
                gt_topics_real.append(item_to_topic_295.get(int(rel_ids[0]), -1))

    with open(PPC_WEAK_JSON, encoding="utf-8") as f:
        ppc = json.load(f)
    gt_topics_synth = []
    for entry in ppc["items"]:
        codigo = entry["codigo"]
        for _mut in entry["mutations"]:
            gt_topics_synth.append(item_to_topic_4851.get(int(codigo), -1))

    gt_real = pd.Series(gt_topics_real)
    gt_synth = pd.Series(gt_topics_synth)

    report.append(f"\n## Distribuição temática das consultas ({len(gt_real)} reais + {len(gt_synth)} sintéticas)\n")
    report.append(f"- Real: consultas cujo item-alvo cai em outlier de tópico: {(gt_real == -1).mean() * 100:.1f}%")
    report.append(f"- Sintético: consultas cujo item-alvo cai em outlier de tópico: {(gt_synth == -1).mean() * 100:.1f}%")

    report.append("\n| Tópico | Palavras-chave | Consultas reais | % real | Consultas sintéticas | % sintético |")
    report.append("|---|---|---|---|---|---|")
    all_topics = sorted(set(gt_real) | set(gt_synth), key=lambda t: -(gt_real == t).sum() - (gt_synth == t).sum())
    for topic_id in all_topics[:15]:
        label = "outliers (-1)" if topic_id == -1 else topic_words.get(int(topic_id), "?")
        n_real = int((gt_real == topic_id).sum())
        n_synth = int((gt_synth == topic_id).sum())
        report.append(
            f"| T{int(topic_id)} | {label} | {n_real} | {n_real / len(gt_real) * 100:.1f}% | "
            f"{n_synth} | {n_synth / len(gt_synth) * 100:.1f}% |"
        )

    # --- Cruzamento com desempenho de retrieval por topico (combinado) -------
    rows = []
    if os.path.exists(RESULTS_REAL_JSON):
        with open(RESULTS_REAL_JSON, encoding="utf-8") as f:
            real_results = json.load(f)["results"]
        for r in real_results:
            if r.get("method") not in COMMON_METHODS:
                continue
            rel_ids = r.get("relevant_item_ids") or []
            if not rel_ids:
                continue
            topic_id = item_to_topic_295.get(int(rel_ids[0]), -1)
            rows.append({"topic": topic_id, "method": r["method"], "map": r["map"], "source": "real"})

    if os.path.exists(RESULTS_SYNTH_JSON):
        with open(RESULTS_SYNTH_JSON, encoding="utf-8") as f:
            synth_results = json.load(f)["results"]
        for r in synth_results:
            if r.get("method") not in COMMON_METHODS:
                continue
            rel_ids = r.get("relevant_item_ids") or []
            if not rel_ids:
                continue
            topic_id = item_to_topic_4851.get(int(rel_ids[0]), -1)
            rows.append({"topic": topic_id, "method": r["method"], "map": r["map"], "source": "synthetic"})

    if rows:
        print("\nCruzando topicos com desempenho de retrieval combinado...")
        perf_df = pd.DataFrame(rows)
        pivot = perf_df.pivot_table(index="topic", columns="method", values="map", aggfunc="mean")
        pivot["n_consultas"] = perf_df[perf_df["method"] == "bm25"].groupby("topic").size()
        pivot = pivot.dropna(subset=["n_consultas"])
        pivot = pivot[pivot["n_consultas"] >= 5].copy()
        if "bm25" in pivot.columns and "bge_m3_hybrid" in pivot.columns:
            pivot["delta_bm25_menos_bge"] = pivot["bm25"] - pivot["bge_m3_hybrid"]
            pivot = pivot.sort_values("delta_bm25_menos_bge", ascending=False)

        pivot.to_csv(os.path.join(OUT_DIR, "map_por_topico_metodo.tsv"), sep="\t")

        report.append("\n## MAP médio por tópico e método — dados combinados (tópicos com >= 5 consultas)\n")
        report.append("Ordenado pela maior vantagem do BM25 sobre o BGE-M3 hybrid (delta = MAP(bm25) − MAP(bge_m3_hybrid)).\n")
        cols = [c for c in ["n_consultas", "bm25", "e5", "e5_hybrid", "bge_m3_hybrid", "delta_bm25_menos_bge"] if c in pivot.columns]
        report.append("| Tópico | Palavras-chave | " + " | ".join(cols) + " |")
        report.append("|---|---|" + "---|" * len(cols))
        for topic_id, row in pivot.iterrows():
            label = "outliers (-1)" if topic_id == -1 else topic_words.get(int(topic_id), "?")
            vals = " | ".join(
                f"{row[c]:.0f}" if c == "n_consultas" else f"{row[c]:.3f}" for c in cols
            )
            report.append(f"| T{int(topic_id)} | {label} | {vals} |")

        # --- Grafico: delta MAP por topico ---
        plot_df = pivot.head(20) if len(pivot) > 20 else pivot
        if "delta_bm25_menos_bge" in plot_df.columns and len(plot_df) > 0:
            fig, ax = plt.subplots(figsize=(11, max(4, 0.4 * len(plot_df))))
            labels = [
                f"T{int(t)} ({int(plot_df.loc[t, 'n_consultas'])})" for t in plot_df.index
            ]
            colors = ["#2196F3" if v >= 0 else "#FF5722" for v in plot_df["delta_bm25_menos_bge"]]
            ax.barh(labels, plot_df["delta_bm25_menos_bge"], color=colors)
            ax.axvline(0, color="black", linewidth=0.8)
            ax.set_xlabel("MAP(BM25) − MAP(BGE-M3 hybrid)")
            ax.set_title("Vantagem do BM25 sobre o BGE-M3 hybrid, por tópico — dados combinados\n(azul = BM25 vence, laranja = BGE-M3 hybrid vence)")
            ax.invert_yaxis()
            plt.tight_layout()
            out_png2 = os.path.join(OUT_DIR, "map_delta_por_topico.png")
            plt.savefig(out_png2, dpi=150, bbox_inches="tight")
            print(f"Grafico salvo em: {out_png2}")

    # --- Grafico de distribuicao de tamanho dos topicos ----------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    info_pos = info[info["Topic"] != -1].head(30)
    labels = [f"T{int(t)}" for t in info_pos["Topic"]]
    ax.bar(labels, info_pos["Count"], color="#2196F3", edgecolor="white")
    ax.set_title(f"BERTopic — 30 maiores tópicos do corpus combinado ({len(items):,} itens, {n_topicos} tópicos, {pct_out:.1f}% outliers)")
    ax.set_ylabel("N de itens")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    plt.tight_layout()
    out_png = os.path.join(OUT_DIR, "bertopic_top30_topicos.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Grafico salvo em: {out_png}")

    out_md = os.path.join(OUT_DIR, "eda_bertopic_resultados.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"\nRelatorio salvo em: {out_md}")


if __name__ == "__main__":
    main()
