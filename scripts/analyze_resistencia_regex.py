"""Analise de 'mpa' (resistencia estrutural, ex. resistencia do concreto/aco) --
mesma metodologia de scripts/validate_param3_regex.py / analyze_mm_regex.py,
usando a regra OFICIAL de class_match/param_3.json:

  - parametros.mecanico.resistencia.r1  ->  "NN MPA" (megapascal)

Motivacao: 'mpa' e uma das keywords do topico T2 ("bloco, furos, cm, vedacao,
mpa, estrutural") na analise original de piores topicos (eda/categ_map/
topic_map_resultados.md) -- nunca testamos esse atributo isoladamente antes.

Nota de ambiguidade: 'mpa' tambem aparece em hidraulico.pressao.r1 (pressao de
bombas/compressores) -- a MESMA unidade pode descrever resistencia estrutural
(concreto, aco) OU pressao hidraulica dependendo do produto. Este script usa
so mecanico.resistencia.r1; nao testa hidraulico.pressao.r1 ainda.

Unidade unica (mpa) -- sem necessidade de canonicalizacao unit-aware como em
peso (kg/g/mg/t) ou dimensional (mm/cm/m/pol).

Topicos "fracos" calculados dinamicamente (MAP medio do topico < 0.60), igual
a analyze_mm_regex.py -- nao hardcoda T101/T73 (que sao especificos de
peso/potencia mecanica).

Nao modifica scripts/retrieval_sinapi.py -- importa read-only; le
class_match/param_3.json read-only.

Uso:
    python scripts/analyze_resistencia_regex.py

Saida (results/resistencia_mpa_analysis/):
    mpa_values_por_item.csv
    mpa_rerank_per_query.csv
    mpa_rerank_intruders.csv
    mpa_por_topico.csv
    mpa_resultados.md
"""

from __future__ import annotations

import csv
import json
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

OUT_DIR = PROJECT_ROOT / "results" / "resistencia_mpa_analysis"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
PARAM3_JSON = PROJECT_ROOT.parent / "class_match" / "param_3.json"
RRF_K = 60
PREFETCH_LIMIT = 100
WEAK_TOPIC_MAP_THRESHOLD = 0.60


def load_param3_pattern(*path: str) -> str:
    with PARAM3_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    node = data["parametros"]
    for key in path:
        node = node[key]
    return node


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


def rerank_by_match(ranked_items, query_values, values_by_item):
    def match_count(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        return len(query_values & values_by_item.get(item_id, frozenset()))

    return sorted(ranked_items, key=match_count, reverse=True)


def rerank_by_match_same_topic(ranked_items, query_values, values_by_item, item_topic, query_topic):
    def match_count(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        if query_topic is None or query_topic == -1:
            return 0
        if item_topic.get(item_id) != query_topic:
            return 0
        return len(query_values & values_by_item.get(item_id, frozenset()))

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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pattern_str = load_param3_pattern("mecanico", "resistencia", "r1")
    compiled = re.compile(pattern_str, re.IGNORECASE)
    print(f"Regra: mecanico.resistencia.r1 = {pattern_str}")

    def extract_values(text: str) -> frozenset[float]:
        values = set()
        for match in compiled.finditer(text or ""):
            raw_value = match.group(1)
            if not raw_value:
                continue
            try:
                values.add(round(float(raw_value.replace(",", ".")), 2))
            except ValueError:
                continue
        return frozenset(values)

    items = read_sinapi_items()
    desc_by_item = {int(it["item_id"]): str(it["description"]) for it in items}
    values_by_item: dict[int, frozenset] = {}
    for item in items:
        values = extract_values(str(item["description"]))
        if values:
            values_by_item[int(item["item_id"])] = values
    print(f"Itens do catalogo com valor mpa: {len(values_by_item)} de {len(items)}")

    with (OUT_DIR / "mpa_values_por_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["item_id", "mpa_values", "description"])
        for item in items:
            item_id = int(item["item_id"])
            values = values_by_item.get(item_id)
            if values:
                writer.writerow([item_id, ",".join(f"{v:g}" for v in sorted(values)), item["description"]])

    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords, map_by_topic = load_topic_meta()

    queries = []
    for product in benchmark:
        text = str(product["product_description"])
        values = extract_values(text)
        if values:
            relevant_ids = set(int(x) for x in product["relevant_item_ids"])
            primary_item_id = min(relevant_ids) if relevant_ids else None
            topic_id = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None
            queries.append(
                {
                    "product": product,
                    "query_values": values,
                    "topic": topic_id,
                    "keywords": topic_keywords.get(topic_id, "") if topic_id is not None else "",
                }
            )
    print(f"Consultas com valor mpa extraido: {len(queries)} de {len(benchmark)}")

    rows = []
    intruder_rows = []
    for i, entry in enumerate(queries, start=1):
        product = entry["product"]
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        query_topic = entry["topic"]

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)
        naive_ranked = rerank_by_match(baseline_ranked, entry["query_values"], values_by_item)
        same_topic_ranked = rerank_by_match_same_topic(
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
                        "intruder_item_id": iid,
                        "intruder_topic": topic_label(i_topic),
                        "mesmo_topico": same,
                        "mesmo_topico_mas_outliers": same_but_outliers,
                        "value_match": ",".join(f"{v:g}" for v in sorted(match)),
                        "rank_antes": old_rank,
                        "rank_depois": new_rank,
                        "intruder_description": desc_by_item.get(iid, ""),
                        "query_text": search_terms,
                    }
                )

        print(f"[{i}/{len(queries)}] processado")

    with (OUT_DIR / "mpa_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
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

    with (OUT_DIR / "mpa_rerank_intruders.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["query_id", "query_topic", "intruder_item_id", "intruder_topic", "mesmo_topico",
                      "mesmo_topico_mas_outliers", "value_match", "rank_antes", "rank_depois",
                      "intruder_description", "query_text"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(intruder_rows)

    def agg(subset, key):
        if not subset:
            return 0.0, 0.0, 0
        b = sum(r["baseline_ap"] for r in subset) / len(subset)
        a = sum(r[key] for r in subset) / len(subset)
        return b, a, len(subset)

    overall_b, overall_naive, n = agg(rows, "naive_ap")
    _, overall_gated, _ = agg(rows, "same_topic_ap")

    per_topic: dict[int | None, list[dict]] = {}
    for r in rows:
        per_topic.setdefault(r["topic"], []).append(r)

    weak_rows = [r for r in rows if map_by_topic.get(r["topic"], 1.0) < WEAK_TOPIC_MAP_THRESHOLD]
    strong_rows = [r for r in rows if map_by_topic.get(r["topic"], 1.0) >= WEAK_TOPIC_MAP_THRESHOLD]
    weak_b, weak_naive, n_weak = agg(weak_rows, "naive_ap")
    _, weak_gated, _ = agg(weak_rows, "same_topic_ap")
    strong_b, strong_naive, n_strong = agg(strong_rows, "naive_ap")
    _, strong_gated, _ = agg(strong_rows, "same_topic_ap")

    n_unrecoverable = sum(1 for r in rows if not r["recuperavel_no_top100"])
    n_intruders = len(intruder_rows)
    n_diff_topic = sum(1 for r in intruder_rows if not r["mesmo_topico"])
    n_same_but_outliers = sum(1 for r in intruder_rows if r["mesmo_topico_mas_outliers"])

    print(f"\nMAP baseline (n={n}): {overall_b:.4f}")
    print(f"MAP ingenuo: {overall_naive:.4f} (delta {overall_naive - overall_b:+.4f})")
    print(f"MAP gateado por topico: {overall_gated:.4f} (delta {overall_gated - overall_b:+.4f})")
    print(f"  fracos (n={n_weak}): baseline={weak_b:.4f} ingenuo={weak_naive:.4f} gateado={weak_gated:.4f}")
    print(f"  fortes (n={n_strong}): baseline={strong_b:.4f} ingenuo={strong_naive:.4f} gateado={strong_gated:.4f}")
    print(f"Intrusos: {n_intruders}, de topico diferente: {n_diff_topic}")
    print(f"Consultas com item relevante fora do top-{DEFAULT_LIMIT}: {n_unrecoverable}")

    with (OUT_DIR / "mpa_por_topico.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["topic_id", "keywords", "map_medio_topico", "n", "fraco", "map_baseline", "map_gateado", "delta"])
        for topic_id in sorted(per_topic, key=lambda t: (t is None, t if t is not None else 0)):
            subset = per_topic[topic_id]
            b, a, cnt = agg(subset, "same_topic_ap")
            topic_map = map_by_topic.get(topic_id)
            fraco = topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD
            writer.writerow(
                [topic_id, subset[0]["keywords"], f"{topic_map:.4f}" if topic_map is not None else "",
                 cnt, "sim" if fraco else "nao", f"{b:.4f}", f"{a:.4f}", f"{a - b:+.4f}"]
            )

    md = []
    md.append("# Analise de 'mpa' (mecanico.resistencia.r1) via param_3.json -- Resultados\n")
    md.append(
        "Mesma metodologia de `results/param3_regex_validation/` e `results/mm_regex_analysis/`, "
        "aplicada a `mecanico.resistencia.r1` de `class_match/param_3.json` -- resistencia "
        "estrutural (concreto, aco), ex. \"BLOCO... 6 MPA\". Motivacao: `mpa` e keyword do "
        "topico T2 na analise original de piores topicos, nunca testado isoladamente.\n"
    )
    md.append(f"## Regra usada\n\n`mecanico.resistencia.r1`: `{pattern_str}`\n")
    md.append(
        "Nota: `mpa` tambem existe em `hidraulico.pressao.r1` (pressao de bombas/compressores) -- "
        "a mesma unidade pode significar resistencia estrutural OU pressao hidraulica dependendo do "
        "produto. Este teste usa so `mecanico.resistencia.r1`; a ambiguidade semantica entre as duas "
        "leituras de \"mpa\" fica para um teste futuro.\n"
    )
    md.append("## Resultado principal\n")
    md.append(f"- Itens do catalogo com valor: **{len(values_by_item)}** de {len(items)}")
    md.append(f"- Consultas com valor extraido: **{n}** de {len(benchmark)} ({100*n/len(benchmark):.1f}%)\n")
    md.append("| Politica | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline (hibrido publicado) | {overall_b:.4f} | - |")
    md.append(f"| Reranking ingenuo (ignora topico) | {overall_naive:.4f} | {overall_naive - overall_b:+.4f} |")
    md.append(f"| **Reranking gateado por topico (adotado)** | **{overall_gated:.4f}** | **{overall_gated - overall_b:+.4f}** |")
    md.append(
        f"\n{n_unrecoverable} de {n} consultas tem o item relevante fora do top-{DEFAULT_LIMIT} candidato "
        "-- reranking nao pode corrigir esses casos.\n"
    )
    md.append(f"Topicos \"fracos\" definidos dinamicamente como MAP medio do topico < {WEAK_TOPIC_MAP_THRESHOLD}.\n")
    md.append("| Segmento | N | Baseline | Ingenuo | Gateado por topico |")
    md.append("|---|---|---|---|---|")
    md.append(f"| Topicos fracos (MAP<{WEAK_TOPIC_MAP_THRESHOLD}) | {n_weak} | {weak_b:.4f} | {weak_naive:.4f} | {weak_gated:.4f} |")
    md.append(f"| Topicos fortes | {n_strong} | {strong_b:.4f} | {strong_naive:.4f} | {strong_gated:.4f} |")

    md.append("\n## Intrusos do reranking ingenuo\n")
    md.append(
        f"- Total de intrusos: **{n_intruders}**\n"
        f"- De topico DIFERENTE da consulta: **{n_diff_topic}/{n_intruders}**"
        + (f" ({100*n_diff_topic/n_intruders:.0f}%)" if n_intruders else "")
        + f"\n- 'Mesmo topico' mas ambos outliers: **{n_same_but_outliers}**\n"
    )

    md.append("\n## MAP por topico\n")
    md.append("| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |")
    md.append("|---|---|---|---|---|---|---|")
    for topic_id, subset in sorted(per_topic.items(), key=lambda kv: -len(kv[1])):
        b, a, cnt = agg(subset, "same_topic_ap")
        topic_map = map_by_topic.get(topic_id)
        fraco = "**sim**" if (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD) else "nao"
        md.append(f"| {topic_label(topic_id)} | {subset[0]['keywords']} | {cnt} | {fraco} | {b:.4f} | {a:.4f} | {a - b:+.4f} |")

    if intruder_rows:
        md.append("\n## Todos os intrusos\n")
        md.append("| product_id | Topico consulta | Item intruso | Topico intruso | Mesmo topico? | Valor | rank antes->depois |")
        md.append("|---|---|---|---|---|---|---|")
        for r in intruder_rows:
            same = "**sim (outliers)**" if r["mesmo_topico_mas_outliers"] else ("sim" if r["mesmo_topico"] else "NAO")
            md.append(
                f"| {r['query_id']} | {r['query_topic']} | [{r['intruder_item_id']}] "
                f"{r['intruder_description'][:60]} | {r['intruder_topic']} | {same} | {r['value_match']} | "
                f"{r['rank_antes']}->{r['rank_depois']} |"
            )

    md_path = OUT_DIR / "mpa_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
