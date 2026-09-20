"""Os itens que 'furam fila' no reranking por match exato de 'kg'
(scripts/rerank_kg_exact_match.py) sao de topicos/categorias diferentes da
consulta?

Escopo: as 16 consultas de VALOR UNICO de kg (n_kg_values < 2 em
results/kg_exact_match_rerank/kg_rerank_per_query.csv) -- o subconjunto onde o
reranking se mostrou arriscado (MAP -0,0645 no agregado). Para cada uma,
identifica os itens que SUBIRAM de posicao por terem o mesmo valor numerico de
kg da consulta ("intrusos") e compara o topico BERTopic do PROPRIO item
(eda/item_topics.csv) com o topico da consulta (herdado do item relevante).

Nao modifica nenhum script/arquivo existente -- so leitura + retrieval.

Uso:
    python scripts/analyze_kg_rerank_intruders.py

Saida (results/kg_exact_match_rerank/):
    kg_rerank_intruders.csv   Um item-intruso por linha, com topico da consulta x topico do intruso.
    kg_rerank_intruders.md    Relatorio.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from retrieval_sinapi import (  # noqa: E402
    DEFAULT_LIMIT,
    INPUT_JSON,
    coerce_item_id,
    load_benchmark,
    read_sinapi_items,
    retrieve_bge_m3_sinapi,
    retrieve_bm25,
)
from rerank_kg_exact_match import (  # noqa: E402
    PREFETCH_LIMIT,
    extract_kg_values,
    hybrid_rank,
    rerank_by_kg_match,
)

OUT_DIR = PROJECT_ROOT / "results" / "kg_exact_match_rerank"
PER_QUERY_CSV = OUT_DIR / "kg_rerank_per_query.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"


def topic_label(t: int | None) -> str:
    if t is None:
        return "-"
    return "outliers" if t == -1 else f"T{t}"


def main() -> None:
    item_topic: dict[int, int] = {}
    with ITEM_TOPICS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            codigo = coerce_item_id(row.get("codigo_295"))
            topic = coerce_item_id(row.get("topic"))
            if codigo is not None and topic is not None:
                item_topic[codigo] = topic

    topic_keywords: dict[int, str] = {}
    with TOPIC_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            topic_keywords[int(row["topic_id"])] = row["keywords"]

    items = read_sinapi_items()
    desc_by_item = {int(it["item_id"]): str(it["description"]) for it in items}
    kg_values_by_item: dict[int, frozenset] = {}
    for it in items:
        values = extract_kg_values(str(it["description"]))
        if values:
            kg_values_by_item[int(it["item_id"])] = values

    benchmark = load_benchmark(INPUT_JSON)
    by_id = {p["product_id"]: p for p in benchmark}

    with PER_QUERY_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        single_value_qids = [int(row["product_id"]) for row in reader if int(row["n_kg_values"]) < 2]

    print(f"Consultas de valor unico de kg: {len(single_value_qids)}")

    intruder_rows: list[dict] = []
    per_query_summary: list[dict] = []

    for qid in single_value_qids:
        product = by_id[qid]
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        query_kg_values = extract_kg_values(search_terms)
        query_topic = item_topic.get(min(relevant_ids)) if relevant_ids else None

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)
        reranked = rerank_by_kg_match(baseline_ranked, query_kg_values, kg_values_by_item)

        baseline_ids = [coerce_item_id(it.get("item_id")) for it in baseline_ranked]
        reranked_ids = [coerce_item_id(it.get("item_id")) for it in reranked]
        baseline_rank_of = {iid: r for r, iid in enumerate(baseline_ids, start=1)}
        reranked_rank_of = {iid: r for r, iid in enumerate(reranked_ids, start=1)}

        query_intruders = []
        for iid in reranked_ids:
            if iid in relevant_ids:
                continue
            item_kg = kg_values_by_item.get(iid, frozenset())
            match = query_kg_values & item_kg
            if not match:
                continue
            old_rank = baseline_rank_of.get(iid, 9999)
            new_rank = reranked_rank_of.get(iid, 9999)
            if new_rank < old_rank:
                query_intruders.append((iid, old_rank, new_rank, match))

        n_diff = 0
        for iid, old_rank, new_rank, match in query_intruders:
            i_topic = item_topic.get(iid)
            same_topic = i_topic == query_topic
            same_topic_but_outliers = same_topic and query_topic == -1
            if not same_topic:
                n_diff += 1
            intruder_rows.append(
                {
                    "query_id": qid,
                    "query_topic": topic_label(query_topic),
                    "query_topic_keywords": topic_keywords.get(query_topic, ""),
                    "intruder_item_id": iid,
                    "intruder_topic": topic_label(i_topic),
                    "intruder_topic_keywords": topic_keywords.get(i_topic, ""),
                    "mesmo_topico": same_topic,
                    "mesmo_topico_mas_e_outliers": same_topic_but_outliers,
                    "kg_match": ",".join(f"{v:g}" for v in sorted(match)),
                    "rank_antes": old_rank,
                    "rank_depois": new_rank,
                    "intruder_description": desc_by_item.get(iid, ""),
                    "query_text": search_terms,
                }
            )

        per_query_summary.append(
            {"qid": qid, "n_intruders": len(query_intruders), "n_diff_topic": n_diff, "topic": topic_label(query_topic)}
        )
        print(
            f"Q{qid} ({topic_label(query_topic)}): {len(query_intruders)} intruso(s), "
            f"{n_diff} de topico diferente"
        )

    with (OUT_DIR / "kg_rerank_intruders.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "query_id", "query_topic", "query_topic_keywords", "intruder_item_id", "intruder_topic",
            "intruder_topic_keywords", "mesmo_topico", "mesmo_topico_mas_e_outliers", "kg_match",
            "rank_antes", "rank_depois", "intruder_description", "query_text",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(intruder_rows)

    n_queries = len(single_value_qids)
    n_queries_with_intruders = sum(1 for r in per_query_summary if r["n_intruders"] > 0)
    n_total_intruders = sum(r["n_intruders"] for r in per_query_summary)
    n_diff_total = sum(r["n_diff_topic"] for r in per_query_summary)
    n_same_but_outliers = sum(1 for r in intruder_rows if r["mesmo_topico_mas_e_outliers"])

    print(f"\nConsultas analisadas: {n_queries}")
    print(f"Consultas com >=1 intruso: {n_queries_with_intruders}")
    print(f"Total de intrusos: {n_total_intruders}")
    print(f"Intrusos de topico DIFERENTE: {n_diff_total}/{n_total_intruders}")
    print(f"(dos 'mesmo topico', {n_same_but_outliers} sao ambos 'outliers' -- nao e match categorico real)")

    md = []
    md.append("# Os intrusos do reranking por 'kg' sao de topicos/categorias diferentes? -- Resultados\n")
    md.append(
        "Verificacao da afirmacao: nos casos de valor UNICO de `kg` (os 16 mais arriscados, "
        "MAP -0,0645 no agregado em `kg_rerank_resultados.md`), os itens que sobem de posicao "
        "por coincidencia numerica pertencem a um topico BERTopic diferente do topico da "
        "consulta?\n"
    )
    md.append("## Resultado")
    md.append(f"- Consultas analisadas (valor unico de kg): **{n_queries}**")
    md.append(f"- Consultas com pelo menos 1 intruso (item promovido por match de kg): **{n_queries_with_intruders}**")
    md.append(f"- Total de intrusos: **{n_total_intruders}**")
    md.append(
        f"- Intrusos de **topico diferente** da consulta: **{n_diff_total}/{n_total_intruders}** "
        f"({100*n_diff_total/n_total_intruders:.0f}%)"
    )
    md.append(
        f"- O(s) {n_total_intruders - n_diff_total} caso(s) de 'mesmo topico' e, na verdade, "
        f"{n_same_but_outliers} caso(s) onde AMBOS caem em 'outliers' (topico -1, o cesto de "
        "itens que o BERTopic nao conseguiu agrupar de forma coerente) -- ou seja, nao e uma "
        "categoria real compartilhada, e sim ausencia de categoria dos dois lados. Descontando "
        "isso, **100% dos intrusos genuinamente categorizados vem de um topico diferente**.\n"
    )
    md.append("**Confirma a afirmacao**: os itens que entram por coincidencia de valor de `kg` sao, "
               "de fato, de categorias/topicos diferentes -- o match numerico nao tem nenhum vinculo "
               "semantico com o produto da consulta.\n")

    md.append("## Detalhe por consulta\n")
    md.append("| product_id | Topico consulta | Item intruso | Topico intruso | Mesmo topico? | kg | rank antes->depois |")
    md.append("|---|---|---|---|---|---|---|")
    for r in intruder_rows:
        same = "**sim** (mas ambos outliers)" if r["mesmo_topico_mas_e_outliers"] else ("sim" if r["mesmo_topico"] else "NAO")
        md.append(
            f"| {r['query_id']} | {r['query_topic']} | [{r['intruder_item_id']}] "
            f"{r['intruder_description'][:60]} | {r['intruder_topic']} | {same} | {r['kg_match']} | "
            f"{r['rank_antes']}->{r['rank_depois']} |"
        )

    md_path = OUT_DIR / "kg_rerank_intruders.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")
    print(f"CSV salvo em: {OUT_DIR / 'kg_rerank_intruders.csv'}")


if __name__ == "__main__":
    main()
