"""Testa 'gate por subcategoria' (a taxonomia manual do SINAPI, coluna
subcategoria_id de class_match/results/regex_subcategories/sinapi-295-regex-
subcategories.csv) como ALTERNATIVA (e como complemento) ao 'gate por
topico' (BERTopic flat) usado em toda a sessao ate aqui.

Motivacao: a correlacao subcategoria x topico e fraca-a-moderada (NMI~0.55,
ARI~0.05 -- ver analise anterior) -- os dois esquemas capturam informacao
so parcialmente sobreposta. Isso sugere duas hipoteses:
  (a) subcategoria sozinha pode servir de gate tao bem quanto (ou melhor
      que) topico, sendo uma taxonomia mais estavel/interpretavel (manual,
      nao depende de retreinar BERTopic);
  (b) combinar os dois (subcategoria E/OU topico) pode capturar mais
      "vizinhanca correta" do que qualquer um sozinho, exatamente porque
      discordam em boa parte dos casos.

Mesma metodologia dos testes anteriores (topico ORACULO -- o topico/
subcategoria do proprio item relevante, nao inferido; ver results/
hierarchical_topic_rerank/ para o cenario com topico INFERIDO, que mostrou
que o gate por topico oraculo superestima o ganho real de producao -- essa
ressalva vale igualmente para subcategoria, que tambem seria um oraculo
aqui).

Nao modifica scripts/retrieval_sinapi.py nem nenhum resultado anterior --
so leitura do CSV de subcategorias (class_match, fora deste projeto) e do
benchmark.

Uso:
    python scripts/analyze_subcategoria_rerank.py

Saida (results/subcategoria_rerank/):
    subcategoria_rerank_per_query.csv   Baseline vs flat-topico vs flat-subcategoria vs combinado, por consulta.
    subcategoria_rerank_resultados.md   Relatorio final.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from retrieval_sinapi import (  # noqa: E402
    DEFAULT_LIMIT,
    INPUT_JSON,
    build_relevance_flags,
    coerce_item_id,
    load_benchmark,
    retrieve_bge_m3_sinapi,
    retrieve_bm25,
)

OUT_DIR = PROJECT_ROOT / "results" / "subcategoria_rerank"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
SUBCATEGORIA_CSV = PROJECT_ROOT.parent / "class_match" / "results" / "regex_subcategories" / "sinapi-295-regex-subcategories.csv"
RRF_K = 60
PREFETCH_LIMIT = 100


def topic_label(t) -> str:
    if t is None or t == "":
        return "-"
    return "outliers" if str(t) == "-1" else f"T{t}"


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


def load_subcategoria_by_item() -> tuple[dict[int, str], dict[str, str]]:
    """item_id -> subcategoria_id (string, ex. '107'); subcategoria_id -> nome legivel."""
    sub_by_item: dict[int, str] = {}
    sub_name: dict[str, str] = {}
    with SUBCATEGORIA_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            item_id = coerce_item_id(row.get("id_itm"))
            sub_id = row.get("subcategoria_id")
            if item_id is not None and sub_id and item_id not in sub_by_item:
                sub_by_item[item_id] = sub_id
                sub_name[sub_id] = row.get("subcategoria", "")
    return sub_by_item, sub_name


def rerank_flat(ranked_items, item_label, query_label):
    def score(item: dict) -> int:
        if query_label is None or query_label == "" or str(query_label) == "-1":
            return 0
        item_id = coerce_item_id(item.get("item_id"))
        return 1 if item_label.get(item_id) == query_label else 0
    return sorted(ranked_items, key=score, reverse=True)


def rerank_combined_topic_subcategoria(ranked_items, codigo_to_topic, sub_by_item, query_topic, query_sub):
    def score(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        same_topic = 1 if (query_topic is not None and query_topic != -1 and codigo_to_topic.get(item_id) == query_topic) else 0
        same_sub = 1 if (query_sub not in (None, "") and str(query_sub) != "-1" and sub_by_item.get(item_id) == query_sub) else 0
        return same_topic + same_sub  # 0, 1 (um dos dois) ou 2 (os dois)
    return sorted(ranked_items, key=score, reverse=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords, map_by_topic = load_topic_meta()
    sub_by_item, sub_name = load_subcategoria_by_item()
    print(f"Consultas no benchmark: {len(benchmark)}")
    print(f"Itens com subcategoria: {len(sub_by_item)}; subcategorias distintas: {len(set(sub_by_item.values()))}")

    rows = []
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        primary_item_id = min(relevant_ids) if relevant_ids else None
        query_topic = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None
        query_sub = sub_by_item.get(primary_item_id) if primary_item_id is not None else None

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)

        flat_topic_ranked = rerank_flat(baseline_ranked, codigo_to_topic, query_topic)
        flat_sub_ranked = rerank_flat(baseline_ranked, sub_by_item, query_sub)
        combined_ranked = rerank_combined_topic_subcategoria(
            baseline_ranked, codigo_to_topic, sub_by_item, query_topic, query_sub
        )

        baseline_ap = average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        flat_topic_ap = average_precision(build_relevance_flags(flat_topic_ranked, relevant_ids), relevant_count)
        flat_sub_ap = average_precision(build_relevance_flags(flat_sub_ranked, relevant_ids), relevant_count)
        combined_ap = average_precision(build_relevance_flags(combined_ranked, relevant_ids), relevant_count)

        rows.append(
            {
                "product_id": product["product_id"],
                "topic": query_topic,
                "subcategoria_id": query_sub,
                "subcategoria_nome": sub_name.get(query_sub, "") if query_sub else "",
                "topic_keywords": topic_keywords.get(query_topic, "") if query_topic is not None else "",
                "topic_e_sub_concordam": (query_topic is not None and query_sub is not None),
                "baseline_ap": baseline_ap,
                "flat_topic_ap": flat_topic_ap,
                "flat_subcategoria_ap": flat_sub_ap,
                "combined_ap": combined_ap,
            }
        )
        if i % 100 == 0 or i == len(benchmark):
            print(f"[{i}/{len(benchmark)}] processado")

    with (OUT_DIR / "subcategoria_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["product_id", "topic", "subcategoria_id", "subcategoria_nome", "baseline_ap",
                          "flat_topic_ap", "flat_subcategoria_ap", "combined_ap"])
        for r in rows:
            writer.writerow(
                [r["product_id"], r["topic"], r["subcategoria_id"], r["subcategoria_nome"],
                 f"{r['baseline_ap']:.6f}", f"{r['flat_topic_ap']:.6f}", f"{r['flat_subcategoria_ap']:.6f}",
                 f"{r['combined_ap']:.6f}"]
            )

    def agg(subset, key):
        if not subset:
            return 0.0
        return sum(r[key] for r in subset) / len(subset)

    all_rows = rows
    print(f"\n=== GERAL ({len(all_rows)} consultas) ===")
    print(f"Baseline:              {agg(all_rows,'baseline_ap'):.4f}")
    print(f"Flat topico (oraculo): {agg(all_rows,'flat_topic_ap'):.4f}  (delta {agg(all_rows,'flat_topic_ap')-agg(all_rows,'baseline_ap'):+.4f})")
    print(f"Flat subcategoria:     {agg(all_rows,'flat_subcategoria_ap'):.4f}  (delta {agg(all_rows,'flat_subcategoria_ap')-agg(all_rows,'baseline_ap'):+.4f})")
    print(f"Combinado (topico+sub):{agg(all_rows,'combined_ap'):.4f}  (delta {agg(all_rows,'combined_ap')-agg(all_rows,'baseline_ap'):+.4f})")

    # segmenta por topicos_e_subcategorias concordarem (mesma "vizinhanca" aproximada) -- proxy:
    # comparamos, por consulta, se o item MAIS PROMOVIDO por subcategoria tambem bate o topico
    # (checagem simples: quantas consultas tem query_topic e query_sub ambos definidos)
    both_defined = [r for r in all_rows if r["topic"] is not None and r["subcategoria_id"] not in (None, "")]
    print(f"\nConsultas com topico E subcategoria definidos: {len(both_defined)}")

    md = []
    md.append("# Gate por subcategoria (SINAPI) vs. gate por topico (BERTopic) -- Resultados\n")
    md.append(
        "Testa a subcategoria manual do SINAPI (`class_match/results/regex_subcategories/"
        "sinapi-295-regex-subcategories.csv`, coluna `subcategoria_id`) como gate de reranking, "
        "em comparacao com o gate por topico BERTopic (flat, ja usado a sessao inteira) e uma "
        "versao combinada dos dois. Mesma convencao anterior: topico/subcategoria da consulta = "
        "os do proprio item relevante (ORACULO -- ver ressalva sobre inferencia em "
        "`results/hierarchical_topic_rerank/`, que vale igualmente aqui).\n"
    )
    md.append("## Resultado geral (852 consultas)\n")
    md.append("| Politica | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline | {agg(all_rows,'baseline_ap'):.4f} | - |")
    md.append(f"| Flat topico (BERTopic, oraculo) | {agg(all_rows,'flat_topic_ap'):.4f} | {agg(all_rows,'flat_topic_ap')-agg(all_rows,'baseline_ap'):+.4f} |")
    md.append(f"| **Flat subcategoria (SINAPI, oraculo)** | **{agg(all_rows,'flat_subcategoria_ap'):.4f}** | **{agg(all_rows,'flat_subcategoria_ap')-agg(all_rows,'baseline_ap'):+.4f}** |")
    md.append(f"| **Combinado (topico + subcategoria)** | **{agg(all_rows,'combined_ap'):.4f}** | **{agg(all_rows,'combined_ap')-agg(all_rows,'baseline_ap'):+.4f}** |")

    md.append("\n## Top 20 subcategorias por N de consultas\n")
    per_sub: dict[str, list[dict]] = {}
    for r in all_rows:
        if r["subcategoria_id"]:
            per_sub.setdefault(r["subcategoria_id"], []).append(r)
    md.append("| Subcategoria | N | MAP baseline | MAP flat-sub | MAP flat-topico | MAP combinado |")
    md.append("|---|---|---|---|---|---|")
    for sid, subset in sorted(per_sub.items(), key=lambda kv: -len(kv[1]))[:20]:
        md.append(
            f"| {subset[0]['subcategoria_nome']} | {len(subset)} | {agg(subset,'baseline_ap'):.4f} | "
            f"{agg(subset,'flat_subcategoria_ap'):.4f} | {agg(subset,'flat_topic_ap'):.4f} | {agg(subset,'combined_ap'):.4f} |"
        )

    md_path = OUT_DIR / "subcategoria_rerank_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
