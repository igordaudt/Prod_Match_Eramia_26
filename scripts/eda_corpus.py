"""EDA (Tarefa 1, adaptada) sobre a base combinada de TODOS os dados usados
neste estudo:
  - Corpus de itens combinado (data/combined_items_all.tsv, 7.252 itens
    unicos = uniao deduplicada do corpus real de 5.813 itens + corpus
    sintetico de 4.851 itens; 3.409 itens aparecem nos dois)
  - Consultas combinadas (data/combined_queries_all.tsv, 996 = 948
    correlacoes reais + 48 consultas sinteticas controladas)

Gerar com scripts/build_combined_dataset.py antes de rodar este script.

Reaproveita a metodologia de '../Topic Modeling/tarefa1_eda_sinapi.py' e
calcula a similaridade de Jaccard entre query_text e target_text para os
dois subconjuntos (real vs. sintetico), permitindo compara-los diretamente
dentro da mesma base.
"""

from __future__ import annotations

import os

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import nltk
import numpy as np
import pandas as pd

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS_TSV = os.path.join(BASE_DIR, "data", "combined_items_all.tsv")
QUERIES_TSV = os.path.join(BASE_DIR, "data", "combined_queries_all.tsv")
OUT_DIR = os.path.join(BASE_DIR, "eda")

os.makedirs(OUT_DIR, exist_ok=True)


def tokenize(t: str) -> list[str]:
    return nltk.word_tokenize(str(t).lower(), language="portuguese")


def jaccard(a: str, b: str) -> float:
    sa, sb = set(tokenize(a)), set(tokenize(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def describe_lengths(series: pd.Series, label: str, report: list[str]) -> tuple[pd.Series, pd.Series]:
    n_docs = len(series)
    n_chars = series.str.len()
    n_tokens = series.apply(lambda t: len(tokenize(t)))
    report.append(f"\n### {label}")
    report.append(f"- Documentos: {n_docs:,}")
    report.append(f"- Total de tokens: {n_tokens.sum():,}")
    report.append(f"- Caracteres — média: {n_chars.mean():.1f} / mediana: {n_chars.median():.0f}")
    report.append(f"- Tokens — média: {n_tokens.mean():.1f} / mediana: {n_tokens.median():.0f}")
    report.append(f"- % docs com <= 30 caracteres: {(n_chars <= 30).mean() * 100:.1f}%")
    return n_chars, n_tokens


def main() -> None:
    print("=" * 65)
    print("EDA — base combinada (corpus de itens + consultas, real + sintético)")
    print("=" * 65)

    items = pd.read_csv(ITEMS_TSV, sep="\t", dtype=str, encoding="utf-8")
    items["description"] = items["description"].fillna("")

    queries = pd.read_csv(QUERIES_TSV, sep="\t", dtype=str, encoding="utf-8")
    queries["query_text"] = queries["query_text"].fillna("")
    queries["target_text"] = queries["target_text"].fillna("")
    queries["jaccard"] = [jaccard(a, b) for a, b in zip(queries["query_text"], queries["target_text"])]

    q_real = queries[queries["source"] == "real_295"]
    q_synth = queries[queries["source"] == "synthetic_4851"]

    report: list[str] = []
    report.append("# EDA — Base Combinada (Todos os Dados: Real + Sintético)\n")
    report.append(
        f"Gerado a partir de `combined_items_all.tsv` ({len(items):,} itens únicos) e "
        f"`combined_queries_all.tsv` ({len(queries):,} consultas: {len(q_real):,} reais + {len(q_synth):,} sintéticas)."
    )
    src_counts = items["source"].value_counts()
    report.append(
        f"\nCorpus de itens por origem: {src_counts.get('real_295', 0):,} só no real, "
        f"{src_counts.get('synthetic_4851', 0):,} só no sintético, "
        f"{src_counts.get('both', 0):,} presentes nos dois (deduplicados por descrição)."
    )

    # --- 1. Estatísticas de comprimento -----------------------------------
    item_chars, item_tokens = describe_lengths(items["description"], f"Corpus de itens combinado ({len(items):,}, deduplicado)", report)
    prod_chars, prod_tokens = describe_lengths(q_real["query_text"], f"Consultas reais (query_text, {len(q_real):,})", report)
    itm_chars, itm_tokens = describe_lengths(q_real["target_text"], f"Itens-alvo das consultas reais (target_text, {len(q_real):,})", report)
    synth_q_chars, synth_q_tokens = describe_lengths(q_synth["query_text"], f"Consultas sintéticas (query_text, {len(q_synth):,})", report)

    vocab_items = set()
    for t in items["description"]:
        vocab_items.update(tokenize(t))
    vocab_prod = set()
    for t in q_real["query_text"]:
        vocab_prod.update(tokenize(t))
    vocab_synth = set()
    for t in q_synth["query_text"]:
        vocab_synth.update(tokenize(t))
    report.append("\n### Vocabulário")
    report.append(f"- Vocabulário único — corpus de itens combinado: {len(vocab_items):,}")
    report.append(f"- Vocabulário único — consultas reais: {len(vocab_prod):,}")
    report.append(f"- Vocabulário único — consultas sintéticas: {len(vocab_synth):,}")
    report.append(
        f"- Sobreposição (itens ∩ consultas reais): {len(vocab_items & vocab_prod):,} "
        f"({len(vocab_items & vocab_prod) / len(vocab_items | vocab_prod) * 100:.1f}% do vocabulário combinado)"
    )

    # --- 2. Similaridade de Jaccard: real vs. sintético, na mesma base ------
    j_real_mean, j_real_median = q_real["jaccard"].mean(), q_real["jaccard"].median()
    j_synth_mean, j_synth_median = q_synth["jaccard"].mean(), q_synth["jaccard"].median()

    report.append("\n### Similaridade lexical (Jaccard) query_text × target_text — comparação direta na base combinada")
    report.append(f"- Real (n={len(q_real)}): Jaccard médio **{j_real_mean:.3f}**, mediano {j_real_median:.3f}")
    report.append(f"- Sintético (n={len(q_synth)}): Jaccard médio **{j_synth_mean:.3f}**, mediano {j_synth_median:.3f}")
    report.append(f"- Diferença (real − sintético): {j_real_mean - j_synth_mean:+.3f}")
    report.append(
        f"- Real: Jaccard = 0 em {(q_real['jaccard'] == 0).sum()} ({(q_real['jaccard'] == 0).mean() * 100:.1f}%); "
        f"Jaccard >= 0,8 em {(q_real['jaccard'] >= 0.8).sum()} ({(q_real['jaccard'] >= 0.8).mean() * 100:.1f}%)"
    )
    report.append(
        f"- Sintético: Jaccard = 0 em {(q_synth['jaccard'] == 0).sum()} ({(q_synth['jaccard'] == 0).mean() * 100:.1f}%); "
        f"Jaccard >= 0,8 em {(q_synth['jaccard'] >= 0.8).sum()} ({(q_synth['jaccard'] >= 0.8).mean() * 100:.1f}%)"
    )

    queries.nsmallest(5, "jaccard")[["source", "query_id", "query_text", "target_text", "jaccard"]].to_csv(
        os.path.join(OUT_DIR, "jaccard_exemplos_baixo.csv"), sep="\t", index=False
    )
    queries.nlargest(5, "jaccard")[["source", "query_id", "query_text", "target_text", "jaccard"]].to_csv(
        os.path.join(OUT_DIR, "jaccard_exemplos_alto.csv"), sep="\t", index=False
    )

    # --- 3. Gráficos ---------------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("EDA — Base Combinada (Todos os Dados: Real + Sintético)", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    ax.hist(item_chars, bins=40, color="#2196F3", edgecolor="white", linewidth=0.5)
    ax.axvline(item_chars.median(), color="tomato", linestyle="--", linewidth=1.5,
               label=f"Mediana: {item_chars.median():.0f}")
    ax.set_title(f"Corpus de itens combinado — N de caracteres (n={len(items):,})")
    ax.set_xlabel("Caracteres por descrição")
    ax.set_ylabel("Frequência")
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    ax = axes[0, 1]
    ax.hist(q_real["jaccard"], bins=30, color="#FF5722", edgecolor="white", linewidth=0.5, alpha=0.7, label=f"Real (n={len(q_real)})", density=True)
    ax.hist(q_synth["jaccard"], bins=30, color="#4CAF50", edgecolor="white", linewidth=0.5, alpha=0.7, label=f"Sintético (n={len(q_synth)})", density=True)
    ax.axvline(j_real_mean, color="#FF5722", linestyle="--", linewidth=1.5)
    ax.axvline(j_synth_mean, color="#4CAF50", linestyle="--", linewidth=1.5)
    ax.set_title("Jaccard query×alvo — real vs. sintético\n(densidade normalizada)")
    ax.set_xlabel("Similaridade de Jaccard")
    ax.set_ylabel("Densidade")
    ax.legend(fontsize=9)

    ax = axes[1, 0]
    data_box = [q_real["query_text"].str.len().values, q_real["target_text"].str.len().values, q_synth["query_text"].str.len().values]
    bp = ax.boxplot(data_box, patch_artist=True, medianprops=dict(color="white", linewidth=2))
    for patch, color in zip(bp["boxes"], ["#FF9800", "#2196F3", "#4CAF50"]):
        patch.set_facecolor(color)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Query real", "Alvo real (SINAPI)", "Query sintética"])
    ax.set_title("Comprimento (chars) por subconjunto")
    ax.set_ylabel("Caracteres")

    ax = axes[1, 1]
    for series, color, label in [(q_real["jaccard"], "#FF5722", f"Real (média={j_real_mean:.3f})"),
                                  (q_synth["jaccard"], "#4CAF50", f"Sintético (média={j_synth_mean:.3f})")]:
        sorted_j = np.sort(series.values)
        cdf = np.arange(1, len(sorted_j) + 1) / len(sorted_j)
        ax.plot(sorted_j, cdf * 100, color=color, linewidth=1.8, label=label)
    ax.set_title("CDF — Jaccard query×alvo, real vs. sintético")
    ax.set_xlabel("Similaridade de Jaccard")
    ax.set_ylabel("% acumulado de consultas")
    ax.set_ylim(0, 103)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out_png = os.path.join(OUT_DIR, "eda_corpus_ground_truth.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"Gráfico salvo em: {out_png}")

    queries[["source", "query_id", "target_id", "jaccard"]].to_csv(
        os.path.join(OUT_DIR, "jaccard_por_correlacao.csv"), sep="\t", index=False
    )

    out_md = os.path.join(OUT_DIR, "eda_corpus_resultados.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"Relatorio salvo em: {out_md}")


if __name__ == "__main__":
    main()
