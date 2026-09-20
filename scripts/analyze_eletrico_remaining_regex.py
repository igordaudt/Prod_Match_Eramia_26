"""Analise das regras eletricas restantes de class_match/param_3.json (fecha
a categoria 'eletrico' -- tensao.r1 e potencia_eletrica.r1 ja testados em
results/eletrico_analysis/):

  - eletrico.corrente.r1                 (a, ma) -- numerico
  - eletrico.frequencia.r1               (hz) -- numerico (so 1 consulta no
    benchmark -- resultado pouco confiavel, reportado com ressalva)
  - eletrico.vias_condutoras.r1_quantidade  (N condutor(es)/par(es)/fio(s)) --
    numerico, unidade = substantivo contado (nao grandeza fisica)
  - eletrico.categoria_rede.r1           (CAT5, CAT6A...) -- CATEGORICO (1
    grupo de captura so: codigo alfanumerico, nao um par valor+unidade)
  - eletrico.tensao.r2_bivolt            (a palavra 'bivolt') -- BOOLEANO (0
    grupos de captura: so presenca/ausencia)
  - eletrico.tensao.r3_fases_polos       (monofasico/bifasico/trifasico/
    monopolar/bipolar/tripolar) -- CATEGORICO (1 grupo: a palavra em si)

As 3 ultimas nao sao pares (valor numerico, unidade) como todos os testes
anteriores -- sao categoricas ou booleanas. Adaptamos o extrator: valor =
string (o codigo/categoria/marcador), 'unidade' = uma tag fixa por regra, so
para manter a mesma estrutura de frozenset (valor, tag) e reusar o mesmo
motor de reranking/match_count por interseccao de conjunto.

Topicos "fracos" calculados dinamicamente (MAP medio do topico < 0.60), como
nos lotes anteriores.

Nao modifica scripts/retrieval_sinapi.py -- importa read-only; le
class_match/param_3.json read-only.

Uso:
    python scripts/analyze_eletrico_remaining_regex.py

Saida (results/eletrico_analysis/):
    <attr>_values_por_item.csv / _rerank_per_query.csv / _rerank_intruders.csv
    eletrico_remaining_resultados.md
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

OUT_DIR = PROJECT_ROOT / "results" / "eletrico_analysis"
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


def make_numeric_extractor(compiled: re.Pattern):
    def extract(text: str) -> frozenset:
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


def make_categorical_extractor(compiled: re.Pattern, tag: str):
    def extract(text: str) -> frozenset:
        values = set()
        for match in compiled.finditer(text or ""):
            raw = match.group(1)
            if raw:
                values.add((raw.strip().lower(), tag))
        return frozenset(values)
    return extract


def make_presence_extractor(compiled: re.Pattern, tag: str):
    def extract(text: str) -> frozenset:
        if compiled.search(text or ""):
            return frozenset({(tag, "presence")})
        return frozenset()
    return extract


def fmt_value(v, u) -> str:
    if isinstance(v, float):
        return f"{v:g}{u}"
    return f"{v}:{u}"


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
        print("SEM CONSULTAS -- nao ha como avaliar reranking.")
        return {"attr_name": attr_name, "label": label, "n_items": len(values_by_item),
                "n_items_total": len(items), "n": 0, "no_data": True}

    with (OUT_DIR / f"{attr_name}_values_por_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["item_id", "values", "description"])
        for item in items:
            item_id = int(item["item_id"])
            values = values_by_item.get(item_id)
            if values:
                writer.writerow([item_id, ",".join(fmt_value(v, u) for v, u in sorted(values, key=str)), item["description"]])

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
                "query_values": ",".join(fmt_value(v, u) for v, u in sorted(entry["query_values"], key=str)),
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
                        "value_match": ",".join(fmt_value(v, u) for v, u in sorted(match, key=str)),
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

    items = read_sinapi_items()
    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords, map_by_topic = load_topic_meta()

    corrente_re = re.compile(load_param3_pattern("eletrico", "corrente", "r1"), re.IGNORECASE)
    freq_re = re.compile(load_param3_pattern("eletrico", "frequencia", "r1"), re.IGNORECASE)
    vias_re = re.compile(load_param3_pattern("eletrico", "vias_condutoras", "r1_quantidade"), re.IGNORECASE)
    catrede_re = re.compile(load_param3_pattern("eletrico", "categoria_rede", "r1"), re.IGNORECASE)
    bivolt_re = re.compile(load_param3_pattern("eletrico", "tensao", "r2_bivolt"), re.IGNORECASE)
    fases_re = re.compile(load_param3_pattern("eletrico", "tensao", "r3_fases_polos"), re.IGNORECASE)

    attr_specs = [
        ("corrente", "Corrente eletrica (a/ma)", corrente_re.pattern, "eletrico.corrente.r1",
         make_numeric_extractor(corrente_re)),
        ("frequencia", "Frequencia (hz)", freq_re.pattern, "eletrico.frequencia.r1",
         make_numeric_extractor(freq_re)),
        ("vias_condutoras", "Vias condutoras (N condutor/par/fio)", vias_re.pattern, "eletrico.vias_condutoras.r1_quantidade",
         make_numeric_extractor(vias_re)),
        ("categoria_rede", "Categoria de rede (CAT5, CAT6A...)", catrede_re.pattern, "eletrico.categoria_rede.r1",
         make_categorical_extractor(catrede_re, "categoria_rede")),
        ("bivolt", "Bivolt (presenca da palavra)", bivolt_re.pattern, "eletrico.tensao.r2_bivolt",
         make_presence_extractor(bivolt_re, "bivolt")),
        ("fases_polos", "Fases/polos (monofasico...tripolar)", fases_re.pattern, "eletrico.tensao.r3_fases_polos",
         make_categorical_extractor(fases_re, "fases_polos")),
    ]

    results = []
    for attr_name, label, pattern_str, json_path, extractor in attr_specs:
        print(f"\n{json_path}: {pattern_str}")
        result = run_attribute_analysis(
            attr_name=attr_name, label=label, extract_values=extractor,
            items=items, benchmark=benchmark, codigo_to_topic=codigo_to_topic,
            topic_keywords=topic_keywords, map_by_topic=map_by_topic,
        )
        result["pattern"] = pattern_str
        result["json_path"] = json_path
        results.append(result)

    md = []
    md.append("# Regras eletricas restantes via param_3.json -- Resultados\n")
    md.append(
        "Fecha a categoria `eletrico` (`tensao.r1` e `potencia_eletrica.r1` ja testados em "
        "`eletrico_resultados.md`). Inclui 3 regras NUMERICAS (`corrente`, `frequencia`, "
        "`vias_condutoras`) e 3 regras CATEGORICAS/BOOLEANAS (`categoria_rede` -- codigo tipo "
        "\"CAT5E\"; `tensao.r2_bivolt` -- so presenca da palavra; `tensao.r3_fases_polos` -- "
        "monofasico/bifasico/trifasico/monopolar/bipolar/tripolar). As categoricas/booleanas usam a "
        "mesma mecanica de match por interseccao de conjunto, so que comparando strings em vez de "
        "valores numericos.\n"
    )
    md.append("## Resumo\n")
    md.append("| Atributo | Regra | Consultas | MAP baseline | MAP ingenuo | MAP gateado | Delta gateado |")
    md.append("|---|---|---|---|---|---|---|")
    for r in results:
        if r.get("no_data"):
            md.append(f"| {r['label']} | `{r['json_path']}` | 0 | - | - | - | **sem dados** |")
        else:
            ressalva = " *(n=1, pouco confiavel)*" if r["n"] == 1 else ""
            md.append(
                f"| {r['label']}{ressalva} | `{r['json_path']}` | {r['n']} | {r['overall_b']:.4f} | "
                f"{r['overall_naive']:.4f} | {r['overall_gated']:.4f} | {r['overall_gated'] - r['overall_b']:+.4f} |"
            )

    for r in results:
        md.append(f"\n## {r['label']} (`{r['json_path']}`)\n")
        md.append(f"Regra: `{r['pattern']}`\n")
        md.append(f"- Itens do catalogo com valor: **{r['n_items']}** de {r['n_items_total']}")
        if r.get("no_data"):
            md.append("- Consultas com valor extraido no benchmark: **0** -- nao ha como avaliar reranking aqui.\n")
            continue
        md.append(f"- Consultas com valor extraido: **{r['n']}**" + (" *(amostra muito pequena, interpretar com cautela)*" if r["n"] <= 3 else "") + "\n")
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

    md_path = OUT_DIR / "eletrico_remaining_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
