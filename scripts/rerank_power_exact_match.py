"""Reranking por match exato de valor de potencia ('cv'/'hp') entre consulta e item.

Mesma metodologia aplicada a 'kg' em scripts/rerank_kg_exact_match.py, adaptada
para as unidades de potencia 'cv' (cavalo-vapor) e 'hp' (horsepower) -- tratadas
como a MESMA grandeza (o catalogo usa as duas indistintamente para motores/
maquinas de potencia equivalente; nao ha conversao cv<->hp aplicada, apenas
igualdade numerica do valor, replicando a decisao ja tomada para 'kg').

Politica final adotada (mesma decisao tomada para 'kg', "condicional por N de
valores" descartada por nao generalizar): reranking gateado por topico -- um
item so e promovido se (a) tiver valor de potencia identico ao da consulta E
(b) pertencer ao MESMO topico BERTopic da consulta (topico -1 "outliers" nunca
conta como match). Comparado contra baseline e contra a versao ingenua (match
sem olhar topico) para evidenciar por que o gate e necessario.

Nao modifica scripts/retrieval_sinapi.py nem scripts/rerank_kg_exact_match.py
-- importa read-only.

Uso:
    python scripts/rerank_power_exact_match.py

Saida (results/power_cv_hp_analysis/):
    power_values_por_item.csv       Valor(es) de potencia extraidos de cada item do catalogo (295).
    power_rerank_per_query.csv      AP baseline vs ingenuo vs gateado por topico, por consulta.
    power_rerank_intruders.csv      Itens que sobem de posicao por match ingenuo, com topico da consulta x do item.
    power_rerank_resultados.md      Relatorio final.
"""

from __future__ import annotations

import csv
import re
import sys
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
    read_sinapi_items,
    retrieve_bge_m3_sinapi,
    retrieve_bm25,
)

OUT_DIR = PROJECT_ROOT / "results" / "power_cv_hp_analysis"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
RRF_K = 60
PREFETCH_LIMIT = 100

# Nenhuma contaminacao tipo "kg/m" foi encontrada para cv/hp no catalogo (nao ha
# "CV/..." nem "HP/..." nas 295 descricoes) -- diferente de kg, nao precisa de
# lookahead negativo para excluir razoes/densidades.
POWER_VALUE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:cv|hp)\b", re.IGNORECASE)


def extract_power_values(text: str) -> frozenset[float]:
    values = set()
    for raw in POWER_VALUE_RE.findall(text or ""):
        try:
            values.add(round(float(raw.replace(",", ".")), 2))
        except ValueError:
            continue
    return frozenset(values)


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


def rerank_by_value_match(
    ranked_items: list[dict],
    query_values: frozenset[float],
    values_by_item: dict[int, frozenset[float]],
) -> list[dict]:
    def match_count(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        item_values = values_by_item.get(item_id, frozenset())
        return len(query_values & item_values)

    return sorted(ranked_items, key=match_count, reverse=True)


def rerank_by_value_match_same_topic(
    ranked_items: list[dict],
    query_values: frozenset[float],
    values_by_item: dict[int, frozenset[float]],
    item_topic: dict[int, int],
    query_topic: int | None,
) -> list[dict]:
    def match_count(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        if query_topic is None or query_topic == -1:
            return 0
        if item_topic.get(item_id) != query_topic:
            return 0
        item_values = values_by_item.get(item_id, frozenset())
        return len(query_values & item_values)

    return sorted(ranked_items, key=match_count, reverse=True)


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


def load_topic_keywords() -> dict[int, str]:
    keywords: dict[int, str] = {}
    with TOPIC_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        for row in reader:
            topic_id = coerce_item_id(row.get("topic_id"))
            if topic_id is not None:
                keywords[topic_id] = row.get("keywords", "")
    return keywords


def topic_label(t: int | None) -> str:
    if t is None:
        return "-"
    return "outliers" if t == -1 else f"T{t}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. valores de potencia por item do catalogo ---
    items = read_sinapi_items()
    desc_by_item = {int(it["item_id"]): str(it["description"]) for it in items}
    values_by_item: dict[int, frozenset[float]] = {}
    for item in items:
        values = extract_power_values(str(item["description"]))
        if values:
            values_by_item[int(item["item_id"])] = values

    with (OUT_DIR / "power_values_por_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["item_id", "power_values", "description"])
        for item in items:
            item_id = int(item["item_id"])
            values = values_by_item.get(item_id)
            if values:
                writer.writerow([item_id, ",".join(f"{v:g}" for v in sorted(values)), item["description"]])
    print(f"Itens do catalogo com valor(es) de potencia: {len(values_by_item)} de {len(items)}")

    # --- 2. consultas com token cv/hp precedido de numero ---
    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords = load_topic_keywords()

    power_queries = []
    for product in benchmark:
        text = str(product["product_description"])
        values = extract_power_values(text)
        if values:
            relevant_ids = set(int(x) for x in product["relevant_item_ids"])
            primary_item_id = min(relevant_ids) if relevant_ids else None
            topic_id = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None
            power_queries.append(
                {
                    "product": product,
                    "query_values": values,
                    "topic": topic_id,
                    "keywords": topic_keywords.get(topic_id, "") if topic_id is not None else "",
                }
            )

    print(f"Consultas com valor(es) de potencia extraidos: {len(power_queries)}")

    # --- 3. baseline + rerank ingenuo + rerank gateado por topico ---
    rows = []
    intruder_rows = []
    for entry in power_queries:
        product = entry["product"]
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        query_topic = entry["topic"]

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)
        naive_ranked = rerank_by_value_match(baseline_ranked, entry["query_values"], values_by_item)
        same_topic_ranked = rerank_by_value_match_same_topic(
            baseline_ranked, entry["query_values"], values_by_item, codigo_to_topic, query_topic
        )

        baseline_flags = build_relevance_flags(baseline_ranked, relevant_ids)
        naive_flags = build_relevance_flags(naive_ranked, relevant_ids)
        same_topic_flags = build_relevance_flags(same_topic_ranked, relevant_ids)

        baseline_ap = average_precision(baseline_flags, relevant_count)
        naive_ap = average_precision(naive_flags, relevant_count)
        same_topic_ap = average_precision(same_topic_flags, relevant_count)

        candidate_ids = {coerce_item_id(it.get("item_id")) for it in baseline_ranked}
        recoverable = bool(relevant_ids & candidate_ids)

        rows.append(
            {
                "product_id": product["product_id"],
                "topic": query_topic,
                "keywords": entry["keywords"],
                "query_values": ",".join(f"{v:g}" for v in sorted(entry["query_values"])),
                "n_values": len(entry["query_values"]),
                "relevant_item_ids": ",".join(str(x) for x in sorted(relevant_ids)),
                "recuperavel_no_top100": recoverable,
                "baseline_ap": baseline_ap,
                "naive_ap": naive_ap,
                "same_topic_ap": same_topic_ap,
                "delta_naive": naive_ap - baseline_ap,
                "delta_same_topic": same_topic_ap - baseline_ap,
                "query_text": search_terms,
            }
        )

        # intrusos: itens que sobem de posicao no rerank ingenuo e NAO sao relevantes
        baseline_ids = [coerce_item_id(it.get("item_id")) for it in baseline_ranked]
        naive_ids = [coerce_item_id(it.get("item_id")) for it in naive_ranked]
        baseline_rank_of = {iid: r for r, iid in enumerate(baseline_ids, start=1)}
        naive_rank_of = {iid: r for r, iid in enumerate(naive_ids, start=1)}
        for iid in naive_ids:
            if iid in relevant_ids:
                continue
            item_values = values_by_item.get(iid, frozenset())
            match = entry["query_values"] & item_values
            if not match:
                continue
            old_rank = baseline_rank_of.get(iid, 9999)
            new_rank = naive_rank_of.get(iid, 9999)
            if new_rank < old_rank:
                i_topic = codigo_to_topic.get(iid)
                same = i_topic == query_topic
                same_but_outliers = same and query_topic == -1
                intruder_rows.append(
                    {
                        "query_id": product["product_id"],
                        "query_topic": topic_label(query_topic),
                        "query_topic_keywords": entry["keywords"],
                        "intruder_item_id": iid,
                        "intruder_topic": topic_label(i_topic),
                        "intruder_topic_keywords": topic_keywords.get(i_topic, ""),
                        "mesmo_topico": same,
                        "mesmo_topico_mas_outliers": same_but_outliers,
                        "power_match": ",".join(f"{v:g}" for v in sorted(match)),
                        "rank_antes": old_rank,
                        "rank_depois": new_rank,
                        "intruder_description": desc_by_item.get(iid, ""),
                        "query_text": search_terms,
                    }
                )

    # --- 4. salvar per-query ---
    with (OUT_DIR / "power_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            ["product_id", "topic", "keywords", "query_values", "n_values", "relevant_item_ids",
             "recuperavel_no_top100", "baseline_ap", "naive_ap", "same_topic_ap", "delta_naive",
             "delta_same_topic", "query_text"]
        )
        for r in rows:
            writer.writerow(
                [r["product_id"], r["topic"], r["keywords"], r["query_values"], r["n_values"],
                 r["relevant_item_ids"], r["recuperavel_no_top100"], f"{r['baseline_ap']:.6f}",
                 f"{r['naive_ap']:.6f}", f"{r['same_topic_ap']:.6f}", f"{r['delta_naive']:+.6f}",
                 f"{r['delta_same_topic']:+.6f}", r["query_text"]]
            )
    print(f"AP por consulta salvo em: {OUT_DIR / 'power_rerank_per_query.csv'}")

    # --- 5. salvar intrusos ---
    with (OUT_DIR / "power_rerank_intruders.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "query_id", "query_topic", "query_topic_keywords", "intruder_item_id", "intruder_topic",
            "intruder_topic_keywords", "mesmo_topico", "mesmo_topico_mas_outliers", "power_match",
            "rank_antes", "rank_depois", "intruder_description", "query_text",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(intruder_rows)
    print(f"Intrusos salvos em: {OUT_DIR / 'power_rerank_intruders.csv'}")

    # --- 6. agregacoes ---
    def agg(subset, key="naive_ap"):
        if not subset:
            return 0.0, 0.0, 0
        b = sum(r["baseline_ap"] for r in subset) / len(subset)
        a = sum(r[key] for r in subset) / len(subset)
        return b, a, len(subset)

    overall_b, overall_naive, n_overall = agg(rows)
    _, overall_same_topic, _ = agg(rows, key="same_topic_ap")
    weak_topics = {101, 73}
    weak_rows = [r for r in rows if r["topic"] in weak_topics]
    strong_rows = [r for r in rows if r["topic"] not in weak_topics]
    weak_b, weak_naive, n_weak = agg(weak_rows)
    strong_b, strong_naive, n_strong = agg(strong_rows)
    _, weak_same_topic, _ = agg(weak_rows, key="same_topic_ap")
    _, strong_same_topic, _ = agg(strong_rows, key="same_topic_ap")
    n_unrecoverable = sum(1 for r in rows if not r["recuperavel_no_top100"])

    per_topic: dict[int | None, list[dict]] = {}
    for r in rows:
        per_topic.setdefault(r["topic"], []).append(r)

    n_intruders = len(intruder_rows)
    n_intruders_diff_topic = sum(1 for r in intruder_rows if not r["mesmo_topico"])
    n_intruders_same_but_outliers = sum(1 for r in intruder_rows if r["mesmo_topico_mas_outliers"])

    print(f"\nMAP baseline (n={n_overall}): {overall_b:.4f}")
    print(f"MAP reranked -- ingenuo (n={n_overall}): {overall_naive:.4f}  (delta {overall_naive - overall_b:+.4f})")
    print(f"MAP reranked -- gateado por topico (n={n_overall}): {overall_same_topic:.4f}  (delta {overall_same_topic - overall_b:+.4f})")
    print(f"  T101+T73 (n={n_weak}): baseline={weak_b:.4f} -> ingenuo={weak_naive:.4f} -> gateado={weak_same_topic:.4f}")
    print(f"  outros topicos (n={n_strong}): baseline={strong_b:.4f} -> ingenuo={strong_naive:.4f} -> gateado={strong_same_topic:.4f}")
    print(f"Consultas com item relevante FORA do top-{DEFAULT_LIMIT} candidato: {n_unrecoverable}")
    print(f"Intrusos (rerank ingenuo): {n_intruders}, de topico diferente: {n_intruders_diff_topic}, mesmo-mas-outliers: {n_intruders_same_but_outliers}")

    # --- 7. relatorio final ---
    md = []
    md.append("# Reranking por match exato de valor de potencia ('cv'/'hp') -- Resultados\n")
    md.append(
        "Mesma metodologia de `results/kg_exact_match_rerank/`, aplicada as unidades de potencia "
        "`cv` (cavalo-vapor) e `hp` (horsepower) -- tratadas como a mesma grandeza (sem conversao "
        f"cv<->hp, so igualdade numerica do valor). Das 852 consultas reais, **{n_overall}** tem "
        "valor(es) de potencia extraiveis via regex (`(\\d+(?:[.,]\\d+)?)\\s*(?:cv|hp)\\b`).\n"
    )
    md.append("## Metodo")
    md.append(
        "1. Baseline: fusao hibrida padrao publicada (BM25 + BGE-M3, RRF `k=60`, `limit=100`).\n"
        "2. Reranking ingenuo: promove itens com valor de potencia identico, ignorando topico "
        "(so para evidenciar o problema).\n"
        "3. **Reranking gateado por topico (adotado)**: so promove se, alem do valor bater, o item "
        "pertencer ao MESMO topico BERTopic da consulta (topico -1 'outliers' nunca conta como "
        "match).\n"
    )
    md.append("## Resultado principal\n")
    md.append("| Politica | N consultas | MAP | Delta vs. baseline |")
    md.append("|---|---|---|---|")
    md.append(f"| Baseline (hibrido publicado) | {n_overall} | {overall_b:.4f} | - |")
    md.append(f"| Reranking ingenuo (ignora topico) | {n_overall} | {overall_naive:.4f} | {overall_naive - overall_b:+.4f} |")
    md.append(f"| **Reranking gateado por topico (adotado)** | {n_overall} | **{overall_same_topic:.4f}** | **{overall_same_topic - overall_b:+.4f}** |")
    md.append(
        f"\n{n_unrecoverable} de {n_overall} consultas tem o item relevante fora do top-{DEFAULT_LIMIT} "
        "candidato -- reranking nao pode corrigir esses casos.\n"
    )
    md.append("| Segmento | N | Baseline | Ingenuo | Gateado por topico |")
    md.append("|---|---|---|---|---|")
    md.append(f"| T101+T73 (topicos fracos) | {n_weak} | {weak_b:.4f} | {weak_naive:.4f} | {weak_same_topic:.4f} |")
    md.append(f"| Outros topicos | {n_strong} | {strong_b:.4f} | {strong_naive:.4f} | {strong_same_topic:.4f} |")

    md.append("\n## Intrusos do reranking ingenuo (mesma verificacao feita para 'kg')\n")
    md.append(
        f"- Total de intrusos (itens promovidos por match de potencia, nao relevantes): **{n_intruders}**\n"
        f"- De topico DIFERENTE da consulta: **{n_intruders_diff_topic}/{n_intruders}**"
        + (f" ({100*n_intruders_diff_topic/n_intruders:.0f}%)" if n_intruders else "")
        + f"\n- 'Mesmo topico' mas na verdade ambos outliers (nao e match categorico real): **{n_intruders_same_but_outliers}**\n"
    )
    if intruder_rows:
        md.append("| product_id | Topico consulta | Item intruso | Topico intruso | Mesmo topico? | Valor | rank antes->depois |")
        md.append("|---|---|---|---|---|---|---|")
        for r in intruder_rows:
            same = "**sim (outliers)**" if r["mesmo_topico_mas_outliers"] else ("sim" if r["mesmo_topico"] else "NAO")
            md.append(
                f"| {r['query_id']} | {r['query_topic']} | [{r['intruder_item_id']}] "
                f"{r['intruder_description'][:60]} | {r['intruder_topic']} | {same} | {r['power_match']} | "
                f"{r['rank_antes']}->{r['rank_depois']} |"
            )

    md.append("\n## Detalhamento por topico (politica adotada: gateada por topico)\n")
    md.append("| Topico | Palavras-chave | N | MAP baseline | MAP gateado por topico | Delta |")
    md.append("|---|---|---|---|---|---|")
    for topic_id in sorted(per_topic, key=lambda t: (t is None, t if t is not None else 0)):
        subset = per_topic[topic_id]
        b, a, n = agg(subset, key="same_topic_ap")
        label = topic_label(topic_id)
        kw = subset[0]["keywords"]
        md.append(f"| {label} | {kw} | {n} | {b:.4f} | {a:.4f} | {a - b:+.4f} |")

    md.append("\n## Todas as consultas (baseline vs. politica adotada)\n")
    md.append("| product_id | Topico | Valores potencia | AP baseline | AP gateado por topico | Delta |")
    md.append("|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: abs(r["delta_same_topic"]), reverse=True):
        md.append(
            f"| {r['product_id']} | {topic_label(r['topic'])} | {r['query_values']} | {r['baseline_ap']:.4f} | "
            f"{r['same_topic_ap']:.4f} | {r['delta_same_topic']:+.4f} |"
        )

    md_path = OUT_DIR / "power_rerank_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
