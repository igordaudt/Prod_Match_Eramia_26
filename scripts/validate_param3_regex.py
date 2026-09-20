"""Reproduz as analises de 'kg' (results/kg_exact_match_rerank/) e 'cv'/'hp'
(results/power_cv_hp_analysis/), mas usando as regras OFICIAIS de
class_match/param_3.json em vez das regexes ad-hoc construidas antes
(KG_VALUE_RE / POWER_VALUE_RE) -- serve para validar se param_3.json produz
resultado equivalente (ou melhor) que as regexes caseiras.

Regras usadas (class_match/param_3.json, v1.1.0):
  - parametros.massa.peso.r1        -> "kg" (agora inclui g/mg/t tambem;
    ganhou (?!\\s*\\/) nesta versao para nao casar kg/m -- mesma correcao que
    ja tinhamos aplicado manualmente). Unidades NAO sao intercambiaveis (1kg
    != 1g != 1mg != 1t) -- match exige mesmo VALOR e mesma UNIDADE.
  - parametros.mecanico.potencia_mecanica.r1 -> "cv"/"hp" (nesta versao,
    separado de potencia eletrica w/kw/kva). Mantemos a equivalencia cv~=hp
    por VALOR (sem exigir mesma unidade) -- mesma decisao da analise anterior,
    pois cv e hp sao usados de forma intercambiavel no catalogo para a mesma
    grandeza (diferente de kg/g/mg/t, que sao escalas ordens de grandeza
    diferentes).

Politica de reranking: gateada por topico (a mesma adotada nas analises
anteriores -- a politica 'condicional por N de valores' foi descartada por
nao generalizar).

Nao modifica scripts/retrieval_sinapi.py nem os scripts kg/power anteriores
-- importa read-only e usa param_3.json read-only.

Uso:
    python scripts/validate_param3_regex.py

Saida (results/param3_regex_validation/):
    kg_param3_values_por_item.csv
    kg_param3_rerank_per_query.csv
    kg_param3_rerank_intruders.csv
    power_param3_values_por_item.csv
    power_param3_rerank_per_query.csv
    power_param3_rerank_intruders.csv
    param3_validation_resultados.md   Relatorio final, com comparacao vs as regexes ad-hoc.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

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

OUT_DIR = PROJECT_ROOT / "results" / "param3_regex_validation"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
PARAM3_JSON = PROJECT_ROOT.parent / "class_match" / "param_3.json"
RRF_K = 60
PREFETCH_LIMIT = 100
WEAK_TOPICS = {101, 73}


def load_param3_pattern(*path: str) -> str:
    with PARAM3_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    node: Any = data["parametros"]
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
        item_values = values_by_item.get(item_id, frozenset())
        return len(query_values & item_values)

    return sorted(ranked_items, key=match_count, reverse=True)


def rerank_by_match_same_topic(ranked_items, query_values, values_by_item, item_topic, query_topic):
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


def run_attribute_analysis(
    *,
    attr_name: str,
    label: str,
    regex_pattern: str,
    unit_aware: bool,
    items: list[dict],
    benchmark: list[dict],
    codigo_to_topic: dict[int, int],
    topic_keywords: dict[int, str],
) -> dict:
    compiled = re.compile(regex_pattern, re.IGNORECASE)

    def extract_values(text: str) -> frozenset:
        values = set()
        for match in compiled.finditer(text or ""):
            raw_value, raw_unit = match.group(1), match.group(2)
            if not raw_value or not raw_unit:
                continue
            try:
                value = round(float(raw_value.replace(",", ".")), 2)
            except ValueError:
                continue
            if unit_aware:
                values.add((value, raw_unit.lower()))
            else:
                values.add(value)
        return frozenset(values)

    desc_by_item = {int(it["item_id"]): str(it["description"]) for it in items}
    values_by_item: dict[int, frozenset] = {}
    for item in items:
        values = extract_values(str(item["description"]))
        if values:
            values_by_item[int(item["item_id"])] = values

    with (OUT_DIR / f"{attr_name}_param3_values_por_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["item_id", "values", "description"])
        for item in items:
            item_id = int(item["item_id"])
            values = values_by_item.get(item_id)
            if values:
                if unit_aware:
                    vs = ",".join(f"{v:g}{u}" for v, u in sorted(values))
                else:
                    vs = ",".join(f"{v:g}" for v in sorted(values))
                writer.writerow([item_id, vs, item["description"]])

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

    rows = []
    intruder_rows = []
    for entry in queries:
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

        if unit_aware:
            qv_str = ",".join(f"{v:g}{u}" for v, u in sorted(entry["query_values"]))
        else:
            qv_str = ",".join(f"{v:g}" for v in sorted(entry["query_values"]))

        rows.append(
            {
                "product_id": product["product_id"],
                "topic": query_topic,
                "keywords": entry["keywords"],
                "query_values": qv_str,
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
                if unit_aware:
                    match_str = ",".join(f"{v:g}{u}" for v, u in sorted(match))
                else:
                    match_str = ",".join(f"{v:g}" for v in sorted(match))
                intruder_rows.append(
                    {
                        "query_id": product["product_id"],
                        "query_topic": topic_label(query_topic),
                        "intruder_item_id": iid,
                        "intruder_topic": topic_label(i_topic),
                        "mesmo_topico": same,
                        "mesmo_topico_mas_outliers": same_but_outliers,
                        "value_match": match_str,
                        "rank_antes": old_rank,
                        "rank_depois": new_rank,
                        "intruder_description": desc_by_item.get(iid, ""),
                        "query_text": search_terms,
                    }
                )

    with (OUT_DIR / f"{attr_name}_param3_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            ["product_id", "topic", "keywords", "query_values", "relevant_item_ids", "recuperavel_no_top100",
             "baseline_ap", "naive_ap", "same_topic_ap", "delta_naive", "delta_same_topic", "query_text"]
        )
        for r in rows:
            writer.writerow(
                [r["product_id"], r["topic"], r["keywords"], r["query_values"], r["relevant_item_ids"],
                 r["recuperavel_no_top100"], f"{r['baseline_ap']:.6f}", f"{r['naive_ap']:.6f}",
                 f"{r['same_topic_ap']:.6f}", f"{r['delta_naive']:+.6f}", f"{r['delta_same_topic']:+.6f}",
                 r["query_text"]]
            )

    with (OUT_DIR / f"{attr_name}_param3_rerank_intruders.csv").open("w", encoding="utf-8", newline="") as f:
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
    weak_rows = [r for r in rows if r["topic"] in WEAK_TOPICS]
    strong_rows = [r for r in rows if r["topic"] not in WEAK_TOPICS]
    weak_b, weak_naive, n_weak = agg(weak_rows, "naive_ap")
    _, weak_gated, _ = agg(weak_rows, "same_topic_ap")
    strong_b, strong_naive, n_strong = agg(strong_rows, "naive_ap")
    _, strong_gated, _ = agg(strong_rows, "same_topic_ap")

    n_intruders = len(intruder_rows)
    n_diff_topic = sum(1 for r in intruder_rows if not r["mesmo_topico"])

    print(f"\n=== {label} (param_3.json) ===")
    print(f"Itens do catalogo com valor: {len(values_by_item)} de {len(items)}")
    print(f"Consultas com valor extraido: {n}")
    print(f"MAP baseline: {overall_b:.4f}")
    print(f"MAP ingenuo: {overall_naive:.4f} (delta {overall_naive - overall_b:+.4f})")
    print(f"MAP gateado por topico: {overall_gated:.4f} (delta {overall_gated - overall_b:+.4f})")
    print(f"  T101+T73 (n={n_weak}): baseline={weak_b:.4f} ingenuo={weak_naive:.4f} gateado={weak_gated:.4f}")
    print(f"  outros (n={n_strong}): baseline={strong_b:.4f} ingenuo={strong_naive:.4f} gateado={strong_gated:.4f}")
    print(f"Intrusos: {n_intruders}, de topico diferente: {n_diff_topic}")

    return {
        "attr_name": attr_name,
        "label": label,
        "n_items_com_valor": len(values_by_item),
        "n_items_total": len(items),
        "n_queries": n,
        "overall_b": overall_b,
        "overall_naive": overall_naive,
        "overall_gated": overall_gated,
        "weak_b": weak_b,
        "weak_naive": weak_naive,
        "weak_gated": weak_gated,
        "n_weak": n_weak,
        "strong_b": strong_b,
        "strong_naive": strong_naive,
        "strong_gated": strong_gated,
        "n_strong": n_strong,
        "n_intruders": n_intruders,
        "n_diff_topic": n_diff_topic,
        "rows": rows,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    items = read_sinapi_items()
    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords = load_topic_keywords()

    peso_pattern = load_param3_pattern("massa", "peso", "r1")
    potencia_mecanica_pattern = load_param3_pattern("mecanico", "potencia_mecanica", "r1")

    kg_result = run_attribute_analysis(
        attr_name="kg",
        label="Peso (massa.peso.r1: kg/g/mg/t, unit-aware)",
        regex_pattern=peso_pattern,
        unit_aware=True,
        items=items,
        benchmark=benchmark,
        codigo_to_topic=codigo_to_topic,
        topic_keywords=topic_keywords,
    )

    power_result = run_attribute_analysis(
        attr_name="power",
        label="Potencia mecanica (mecanico.potencia_mecanica.r1: cv/hp, valor apenas)",
        regex_pattern=potencia_mecanica_pattern,
        unit_aware=False,
        items=items,
        benchmark=benchmark,
        codigo_to_topic=codigo_to_topic,
        topic_keywords=topic_keywords,
    )

    # --- relatorio final, com comparacao vs as regexes ad-hoc anteriores ---
    md = []
    md.append("# Validacao de class_match/param_3.json -- kg e cv/hp refeitos com as regras oficiais\n")
    md.append(
        "Reproduz `results/kg_exact_match_rerank/` e `results/power_cv_hp_analysis/`, mas usando "
        "`massa.peso.r1` e `mecanico.potencia_mecanica.r1` de `class_match/param_3.json` (v1.1.0) "
        "em vez das regexes ad-hoc (`KG_VALUE_RE`/`POWER_VALUE_RE`) construidas antes nesta sessao.\n"
    )
    md.append("## Regras usadas\n")
    md.append(f"- `massa.peso.r1`: `{peso_pattern}`")
    md.append(
        "  - Agora cobre `kg`, `g`, `mg`, `t` (a regex ad-hoc so cobria `kg`). Match exige **mesmo "
        "valor E mesma unidade** (1kg != 1g != 1mg != 1t -- unidades NAO sao intercambiaveis).\n"
    )
    md.append(f"- `mecanico.potencia_mecanica.r1`: `{potencia_mecanica_pattern}`")
    md.append(
        "  - Cobre `cv` e `hp`. Mantida a equivalencia por VALOR (sem exigir mesma unidade), como na "
        "analise anterior -- cv e hp sao usados de forma intercambiavel no catalogo para a mesma "
        "grandeza fisica aproximada.\n"
    )

    for result, prev_baseline, prev_gated, prev_n in (
        (kg_result, 0.6599, 0.6967, 27),
        (power_result, 0.6162, 0.6389, 22),
    ):
        md.append(f"\n## {result['label']}\n")
        md.append(
            f"- Itens do catalogo com valor: **{result['n_items_com_valor']}** de {result['n_items_total']}\n"
            f"- Consultas com valor extraido: **{result['n_queries']}** (regex ad-hoc anterior: {prev_n})\n"
        )
        md.append("| Politica | MAP | Delta vs. baseline |")
        md.append("|---|---|---|")
        md.append(f"| Baseline | {result['overall_b']:.4f} | - |")
        md.append(f"| Reranking ingenuo (ignora topico) | {result['overall_naive']:.4f} | {result['overall_naive'] - result['overall_b']:+.4f} |")
        md.append(f"| **Gateado por topico (adotado)** | **{result['overall_gated']:.4f}** | **{result['overall_gated'] - result['overall_b']:+.4f}** |")
        md.append("")
        md.append("| Segmento | N | Baseline | Ingenuo | Gateado por topico |")
        md.append("|---|---|---|---|---|")
        md.append(f"| T101+T73 | {result['n_weak']} | {result['weak_b']:.4f} | {result['weak_naive']:.4f} | {result['weak_gated']:.4f} |")
        md.append(f"| Outros topicos | {result['n_strong']} | {result['strong_b']:.4f} | {result['strong_naive']:.4f} | {result['strong_gated']:.4f} |")
        md.append(
            f"\nIntrusos do reranking ingenuo: **{result['n_intruders']}**, de topico diferente da consulta: "
            f"**{result['n_diff_topic']}**"
            + (f" ({100*result['n_diff_topic']/result['n_intruders']:.0f}%)" if result['n_intruders'] else "")
            + "\n"
        )
        md.append(
            f"**Comparacao com a regex ad-hoc anterior**: baseline {prev_baseline:.4f} -> gateado "
            f"{prev_gated:.4f} (delta {prev_gated - prev_baseline:+.4f}) usando `KG_VALUE_RE`/`POWER_VALUE_RE`; "
            f"aqui, baseline {result['overall_b']:.4f} -> gateado {result['overall_gated']:.4f} "
            f"(delta {result['overall_gated'] - result['overall_b']:+.4f}) usando `param_3.json`.\n"
        )

    md_path = OUT_DIR / "param3_validation_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
