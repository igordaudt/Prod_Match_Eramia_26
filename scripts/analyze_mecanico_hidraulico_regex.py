"""Analise de 4 regras mecanicas/hidraulicas de class_match/param_3.json:

  - hidraulico.pressao.r1     (bar, psi, pa, kpa, mpa)
  - mecanico.rpm.r1           (rpm)
  - mecanico.resistencia.r1   (mpa -- ja testado isoladamente em
    results/resistencia_mpa_analysis/; reincluido aqui para comparacao lado
    a lado com pressao.r1, que TAMBEM inclui 'mpa' -- mesma unidade, dois
    parametros/significados diferentes: resistencia estrutural vs pressao
    hidraulica)
  - mecanico.torque.r1        (nm)

Unit-aware (bar != psi != pa != kpa != mpa -- grandezas/escalas diferentes).
Topicos "fracos" calculados dinamicamente (MAP medio do topico < 0.60), como
em analyze_mm_regex.py / analyze_resistencia_regex.py / analyze_eletrico_regex.py.

Se uma regra nao tiver NENHUMA consulta do benchmark com match, isso e
reportado explicitamente (nao da pra rodar reranking sem consultas) --
descobrimos isso ja na checagem previa: rpm e torque tem 0 consultas no
benchmark de 852 (rpm tem 15 itens no catalogo mas nenhum aparece nas
consultas; torque/'nm' nao aparece nem no catalogo).

Nao modifica scripts/retrieval_sinapi.py -- importa read-only; le
class_match/param_3.json read-only.

Uso:
    python scripts/analyze_mecanico_hidraulico_regex.py

Saida (results/mecanico_hidraulico_analysis/):
    <attr>_values_por_item.csv / _rerank_per_query.csv / _rerank_intruders.csv (por atributo com dados)
    mecanico_hidraulico_resultados.md   Relatorio final (as 4 analises, incl. as sem dados).
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

OUT_DIR = PROJECT_ROOT / "results" / "mecanico_hidraulico_analysis"
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


def parse_number(raw: str) -> float | None:
    try:
        return round(float(raw.strip().replace(",", ".")), 2)
    except ValueError:
        return None


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


def make_simple_extractor(compiled: re.Pattern):
    def extract(text: str) -> frozenset[tuple[float, str]]:
        values = set()
        for match in compiled.finditer(text or ""):
            raw_value, raw_unit = match.group(1), match.group(2)
            if not raw_value or not raw_unit:
                continue
            v = parse_number(raw_value)
            if v is not None:
                values.add((v, raw_unit.lower()))
        return frozenset(values)
    return extract


def run_attribute_analysis(
    *, attr_name, label, extract_values, items, benchmark, codigo_to_topic, topic_keywords, map_by_topic,
):
    desc_by_item = {int(it["item_id"]): str(it["description"]) for it in items}
    values_by_item: dict[int, frozenset] = {}
    for item in items:
        values = extract_values(str(item["description"]))
        if values:
            values_by_item[int(item["item_id"])] = values

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
                    "product": product, "query_values": values, "topic": topic_id,
                    "keywords": topic_keywords.get(topic_id, "") if topic_id is not None else "",
                }
            )

    print(f"\n=== {label} ===")
    print(f"Itens do catalogo com valor: {len(values_by_item)} de {len(items)}")
    print(f"Consultas com valor extraido: {len(queries)}")

    if not queries:
        print("SEM CONSULTAS -- nao ha como avaliar reranking (nenhuma consulta do benchmark contem esse atributo).")
        return {
            "attr_name": attr_name, "label": label, "n_items": len(values_by_item),
            "n_items_total": len(items), "n": 0, "no_data": True,
        }

    if not values_by_item:
        print("SEM ITENS DE CATALOGO COM VALOR -- nada para comparar.")

    with (OUT_DIR / f"{attr_name}_values_por_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["item_id", "values", "description"])
        for item in items:
            item_id = int(item["item_id"])
            values = values_by_item.get(item_id)
            if values:
                writer.writerow([item_id, ",".join(f"{v:g}{u}" for v, u in sorted(values)), item["description"]])

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

        baseline_ap = average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        naive_ap = average_precision(build_relevance_flags(naive_ranked, relevant_ids), relevant_count)
        same_topic_ap = average_precision(build_relevance_flags(same_topic_ranked, relevant_ids), relevant_count)

        rows.append(
            {
                "product_id": product["product_id"], "topic": query_topic, "keywords": entry["keywords"],
                "query_values": ",".join(f"{v:g}{u}" for v, u in sorted(entry["query_values"])),
                "relevant_item_ids": ",".join(str(x) for x in sorted(relevant_ids)),
                "baseline_ap": baseline_ap, "naive_ap": naive_ap, "same_topic_ap": same_topic_ap,
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
                intruder_rows.append(
                    {
                        "query_id": product["product_id"], "query_topic": topic_label(query_topic),
                        "intruder_item_id": iid, "intruder_topic": topic_label(i_topic), "mesmo_topico": same,
                        "value_match": ",".join(f"{v:g}{u}" for v, u in sorted(match)),
                        "rank_antes": old_rank, "rank_depois": new_rank,
                        "intruder_description": desc_by_item.get(iid, ""), "query_text": search_terms,
                    }
                )
        print(f"[{attr_name}] [{i}/{len(queries)}] processado")

    with (OUT_DIR / f"{attr_name}_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["product_id", "topic", "keywords", "query_values", "relevant_item_ids",
                          "baseline_ap", "naive_ap", "same_topic_ap", "query_text"])
        for r in rows:
            writer.writerow([r["product_id"], r["topic"], r["keywords"], r["query_values"],
                              r["relevant_item_ids"], f"{r['baseline_ap']:.6f}", f"{r['naive_ap']:.6f}",
                              f"{r['same_topic_ap']:.6f}", r["query_text"]])

    with (OUT_DIR / f"{attr_name}_rerank_intruders.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["query_id", "query_topic", "intruder_item_id", "intruder_topic", "mesmo_topico",
                      "value_match", "rank_antes", "rank_depois", "intruder_description", "query_text"]
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
    weak_rows = [r for r in rows if map_by_topic.get(r["topic"], 1.0) < WEAK_TOPIC_MAP_THRESHOLD]
    strong_rows = [r for r in rows if map_by_topic.get(r["topic"], 1.0) >= WEAK_TOPIC_MAP_THRESHOLD]
    weak_b, weak_naive, n_weak = agg(weak_rows, "naive_ap")
    _, weak_gated, _ = agg(weak_rows, "same_topic_ap")
    strong_b, strong_naive, n_strong = agg(strong_rows, "naive_ap")
    _, strong_gated, _ = agg(strong_rows, "same_topic_ap")
    n_intruders = len(intruder_rows)
    n_diff_topic = sum(1 for r in intruder_rows if not r["mesmo_topico"])

    per_topic: dict[int | None, list[dict]] = {}
    for r in rows:
        per_topic.setdefault(r["topic"], []).append(r)

    print(f"MAP baseline: {overall_b:.4f}  ingenuo: {overall_naive:.4f} ({overall_naive - overall_b:+.4f})  "
          f"gateado: {overall_gated:.4f} ({overall_gated - overall_b:+.4f})")
    print(f"Intrusos: {n_intruders}, de topico diferente: {n_diff_topic}")

    return {
        "attr_name": attr_name, "label": label, "n_items": len(values_by_item), "n_items_total": len(items),
        "n": n, "no_data": False, "overall_b": overall_b, "overall_naive": overall_naive,
        "overall_gated": overall_gated, "weak_b": weak_b, "weak_naive": weak_naive, "weak_gated": weak_gated,
        "n_weak": n_weak, "strong_b": strong_b, "strong_naive": strong_naive, "strong_gated": strong_gated,
        "n_strong": n_strong, "n_intruders": n_intruders, "n_diff_topic": n_diff_topic,
        "per_topic": per_topic, "map_by_topic": map_by_topic,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    attr_specs = [
        ("pressao", "Pressao hidraulica (bar/psi/pa/kpa/mpa)", ("hidraulico", "pressao", "r1")),
        ("rpm", "RPM (rotacoes por minuto)", ("mecanico", "rpm", "r1")),
        ("resistencia", "Resistencia estrutural (mpa)", ("mecanico", "resistencia", "r1")),
        ("torque", "Torque (nm)", ("mecanico", "torque", "r1")),
    ]

    items = read_sinapi_items()
    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords, map_by_topic = load_topic_meta()

    results = []
    for attr_name, label, json_path in attr_specs:
        pattern_str = load_param3_pattern(*json_path)
        compiled = re.compile(pattern_str, re.IGNORECASE)
        print(f"\n{'.'.join(json_path)}: {pattern_str}")
        result = run_attribute_analysis(
            attr_name=attr_name, label=label, extract_values=make_simple_extractor(compiled),
            items=items, benchmark=benchmark, codigo_to_topic=codigo_to_topic,
            topic_keywords=topic_keywords, map_by_topic=map_by_topic,
        )
        result["pattern"] = pattern_str
        result["json_path"] = ".".join(json_path)
        results.append(result)

    md = []
    md.append("# Analise de pressao/rpm/resistencia/torque via param_3.json -- Resultados\n")
    md.append(
        "Testa `hidraulico.pressao.r1`, `mecanico.rpm.r1`, `mecanico.resistencia.r1` (reincluido para "
        "comparacao -- ja testado isoladamente em `results/resistencia_mpa_analysis/`) e "
        "`mecanico.torque.r1`. Todos unit-aware (unidades dentro de cada regra NAO sao "
        "intercambiaveis entre si).\n"
    )
    md.append(
        "**Nota de ambiguidade**: `pressao.r1` e `resistencia.r1` compartilham a unidade `mpa` -- a "
        "mesma grandeza textual pode significar pressao hidraulica (bomba/compressor) OU resistencia "
        "estrutural (concreto/aco) dependendo do produto. Testados aqui como parametros separados "
        "(conforme o schema), sem desambiguacao contextual.\n"
    )

    md.append("## Resumo\n")
    md.append("| Atributo | Regra | Consultas | MAP baseline | MAP ingenuo | MAP gateado | Delta gateado |")
    md.append("|---|---|---|---|---|---|---|")
    for r in results:
        if r.get("no_data"):
            md.append(f"| {r['label']} | `{r['json_path']}` | 0 | - | - | - | **sem dados** |")
        else:
            md.append(
                f"| {r['label']} | `{r['json_path']}` | {r['n']} | {r['overall_b']:.4f} | "
                f"{r['overall_naive']:.4f} | {r['overall_gated']:.4f} | {r['overall_gated'] - r['overall_b']:+.4f} |"
            )

    for r in results:
        md.append(f"\n## {r['label']} (`{r['json_path']}`)\n")
        md.append(f"Regra: `{r['pattern']}`\n")
        md.append(f"- Itens do catalogo com valor: **{r['n_items']}** de {r['n_items_total']}")
        if r.get("no_data"):
            md.append(
                "- Consultas com valor extraido no benchmark: **0** -- nenhuma das 852 consultas contem "
                "esse atributo, entao nao ha como avaliar reranking aqui (mesmo havendo itens no "
                "catalogo com esse valor).\n"
            )
            continue
        md.append(f"- Consultas com valor extraido: **{r['n']}**\n")
        md.append("| Politica | MAP | Delta vs. baseline |")
        md.append("|---|---|---|")
        md.append(f"| Baseline | {r['overall_b']:.4f} | - |")
        md.append(f"| Reranking ingenuo | {r['overall_naive']:.4f} | {r['overall_naive'] - r['overall_b']:+.4f} |")
        md.append(f"| **Gateado por topico (adotado)** | **{r['overall_gated']:.4f}** | **{r['overall_gated'] - r['overall_b']:+.4f}** |")
        md.append("")
        md.append("| Segmento | N | Baseline | Ingenuo | Gateado |")
        md.append("|---|---|---|---|---|")
        md.append(f"| Fracos (MAP<{WEAK_TOPIC_MAP_THRESHOLD}) | {r['n_weak']} | {r['weak_b']:.4f} | {r['weak_naive']:.4f} | {r['weak_gated']:.4f} |")
        md.append(f"| Fortes | {r['n_strong']} | {r['strong_b']:.4f} | {r['strong_naive']:.4f} | {r['strong_gated']:.4f} |")
        md.append(
            f"\nIntrusos: **{r['n_intruders']}**, de topico diferente: **{r['n_diff_topic']}**"
            + (f" ({100*r['n_diff_topic']/r['n_intruders']:.0f}%)" if r['n_intruders'] else "")
            + "\n"
        )
        md.append("### MAP por topico\n")
        md.append("| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |")
        md.append("|---|---|---|---|---|---|---|")
        for topic_id, subset in sorted(r["per_topic"].items(), key=lambda kv: -len(kv[1])):
            b = sum(x["baseline_ap"] for x in subset) / len(subset)
            a = sum(x["same_topic_ap"] for x in subset) / len(subset)
            topic_map = r["map_by_topic"].get(topic_id)
            fraco = "**sim**" if (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD) else "nao"
            md.append(f"| {topic_label(topic_id)} | {subset[0]['keywords']} | {len(subset)} | {fraco} | {b:.4f} | {a:.4f} | {a - b:+.4f} |")

    md_path = OUT_DIR / "mecanico_hidraulico_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
