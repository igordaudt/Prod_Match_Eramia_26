"""Mesma correcao aplicada a 'mpa' isolado (results/resistencia_mpa_analysis/
combo_resultados.md), agora para 'pressao hidraulica' (hidraulico.pressao.r1:
bar/psi/pa/kpa/mpa) -- que deu resultado quase identico e negativo ao de
resistencia.r1 porque, nesse benchmark, a maioria das consultas de pressao
SAO as mesmas consultas de bloco estrutural (T2) que ja vimos, so que
capturadas via a unidade compartilhada 'mpa'.

Combina pressao.r1 com as 6 regras dimensionais (comprimento, espessura,
raio, multidimensional_2d x2, multidimensional_3d), igual foi feito para
resistencia. Escopo: as mesmas 17 consultas de
results/mecanico_hidraulico_analysis/pressao_rerank_per_query.csv.

Nao modifica nenhum script anterior -- le class_match/param_3.json read-only.

Uso:
    python scripts/analyze_pressao_dimensional_combo.py

Saida (results/mecanico_hidraulico_analysis/):
    pressao_combo_rerank_per_query.csv
    pressao_combo_resultados.md
"""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
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

UNIT_CANON = {
    "mm": "mm", "milimetro": "mm", "milimetros": "mm",
    "cm": "cm", "centimetro": "cm", "centimetros": "cm",
    "m": "m", "metro": "m", "metros": "m",
    '"': "pol", "pol": "pol", "pol.": "pol",
    "polegada": "pol", "polegadas": "pol",
}
VULGAR_FRACTIONS = {"¾": 0.75, "½": 0.5, "¼": 0.25, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875}
FRACTION_RE = re.compile(r"^(?:(\d+)\s+)?(\d+)\s*[/⁄]\s*(\d+)$")


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canon_unit(raw_unit: str) -> str | None:
    return UNIT_CANON.get(strip_accents(raw_unit.strip().lower()))


def parse_number(raw: str) -> float | None:
    raw = raw.strip()
    if raw in VULGAR_FRACTIONS:
        return VULGAR_FRACTIONS[raw]
    m = FRACTION_RE.match(raw)
    if m:
        whole = int(m.group(1)) if m.group(1) else 0
        num, den = int(m.group(2)), int(m.group(3))
        if den == 0:
            return None
        return round(whole + num / den, 4)
    try:
        return round(float(raw.replace(",", ".")), 2)
    except ValueError:
        return None


def load_param3_pattern(*path: str) -> str:
    with PARAM3_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    node = data["parametros"]
    for key in path:
        node = node[key]
    return node


def extract_simple(match: re.Match) -> list[tuple[float, str]]:
    raw_value, raw_unit = match.group(1), match.group(2)
    if not raw_value or not raw_unit:
        return []
    unit = canon_unit(raw_unit)
    value = parse_number(raw_value)
    if unit is None or value is None:
        return []
    return [(value, unit)]


def extract_multi_2d_metrico(match: re.Match) -> list[tuple[float, str]]:
    raw_v1, raw_v2, raw_unit = match.group(1), match.group(2), match.group(3)
    unit = canon_unit(raw_unit) if raw_unit else None
    if unit is None:
        return []
    out = []
    for raw_v in (raw_v1, raw_v2):
        v = parse_number(raw_v) if raw_v else None
        if v is not None:
            out.append((v, unit))
    return out


def extract_multi_2d_misto(match: re.Match) -> list[tuple[float, str]]:
    raw_pol_value, _marker, raw_metric_value, raw_metric_unit = (
        match.group(1), match.group(2), match.group(3), match.group(4)
    )
    out = []
    pol_value = parse_number(raw_pol_value) if raw_pol_value else None
    if pol_value is not None:
        out.append((pol_value, "pol"))
    metric_unit = canon_unit(raw_metric_unit) if raw_metric_unit else None
    metric_value = parse_number(raw_metric_value) if raw_metric_value else None
    if metric_unit is not None and metric_value is not None:
        out.append((metric_value, metric_unit))
    return out


def extract_multi_3d_metrico(match: re.Match) -> list[tuple[float, str]]:
    raw_v1, raw_u1, raw_v2, raw_u2, raw_v3, raw_u3, raw_u_final = (
        match.group(1), match.group(2), match.group(3),
        match.group(4), match.group(5), match.group(6), match.group(7),
    )
    fallback_unit = canon_unit(raw_u_final) if raw_u_final else None
    out = []
    for raw_v, raw_u in ((raw_v1, raw_u1), (raw_v2, raw_u2), (raw_v3, raw_u3)):
        if not raw_v:
            continue
        v = parse_number(raw_v)
        unit = canon_unit(raw_u) if raw_u else fallback_unit
        if v is not None and unit is not None:
            out.append((v, unit))
    return out


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


def load_topic_keywords() -> dict[int, str]:
    keywords: dict[int, str] = {}
    with TOPIC_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        for row in reader:
            topic_id = coerce_item_id(row.get("topic_id"))
            if topic_id is not None:
                keywords[topic_id] = row.get("keywords", "")
    return keywords


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pressao_pattern = load_param3_pattern("hidraulico", "pressao", "r1")
    pressao_re = re.compile(pressao_pattern, re.IGNORECASE)

    dim_rule_specs = [
        (("dimensional", "comprimento", "r1_metricos"), extract_simple),
        (("dimensional", "espessura", "r1_contextual"), extract_simple),
        (("dimensional", "raio", "r1"), extract_simple),
        (("dimensional", "multidimensional_2d", "r1_metricos"), extract_multi_2d_metrico),
        (("dimensional", "multidimensional_2d", "r2_misto_polegada_metrico"), extract_multi_2d_misto),
        (("dimensional", "multidimensional_3d", "r1_metricos"), extract_multi_3d_metrico),
    ]
    dim_rules = [(re.compile(load_param3_pattern(*path), re.IGNORECASE), extractor) for path, extractor in dim_rule_specs]

    def extract_pressao(text: str) -> frozenset:
        values = set()
        for match in pressao_re.finditer(text or ""):
            raw_value, raw_unit = match.group(1), match.group(2)
            if not raw_value or not raw_unit:
                continue
            v = parse_number(raw_value)
            if v is not None:
                values.add(("pressao", v, raw_unit.lower()))
        return frozenset(values)

    def extract_dim(text: str) -> frozenset:
        values = set()
        for compiled, extractor in dim_rules:
            for match in compiled.finditer(text or ""):
                for value, unit in extractor(match):
                    values.add(("dim", value, unit))
        return frozenset(values)

    items = read_sinapi_items()
    desc_by_item = {int(it["item_id"]): str(it["description"]) for it in items}
    pressao_by_item: dict[int, frozenset] = {}
    dim_by_item: dict[int, frozenset] = {}
    for item in items:
        iid = int(item["item_id"])
        p = extract_pressao(str(item["description"]))
        d = extract_dim(str(item["description"]))
        if p:
            pressao_by_item[iid] = p
        if d:
            dim_by_item[iid] = d
    combo_by_item = {
        iid: pressao_by_item.get(iid, frozenset()) | dim_by_item.get(iid, frozenset())
        for iid in set(pressao_by_item) | set(dim_by_item)
    }
    print(f"Itens com pressao: {len(pressao_by_item)}; com dimensao: {len(dim_by_item)}; combinado: {len(combo_by_item)}")

    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords = load_topic_keywords()

    queries = []
    for product in benchmark:
        text = str(product["product_description"])
        pressao_values = extract_pressao(text)
        if not pressao_values:
            continue
        dim_values = extract_dim(text)
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        primary_item_id = min(relevant_ids) if relevant_ids else None
        topic_id = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None
        queries.append(
            {
                "product": product, "pressao_values": pressao_values, "dim_values": dim_values,
                "combo_values": pressao_values | dim_values, "topic": topic_id,
                "keywords": topic_keywords.get(topic_id, "") if topic_id is not None else "",
            }
        )
    print(f"Consultas no escopo (mesmas do teste de pressao anterior): {len(queries)}")

    rows = []
    for entry in queries:
        product = entry["product"]
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        query_topic = entry["topic"]

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)

        pressao_gated = rerank_by_match_same_topic(baseline_ranked, entry["pressao_values"], pressao_by_item, codigo_to_topic, query_topic)
        dim_gated = rerank_by_match_same_topic(baseline_ranked, entry["dim_values"], dim_by_item, codigo_to_topic, query_topic)
        combo_gated = rerank_by_match_same_topic(baseline_ranked, entry["combo_values"], combo_by_item, codigo_to_topic, query_topic)

        baseline_ap = average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        pressao_ap = average_precision(build_relevance_flags(pressao_gated, relevant_ids), relevant_count)
        dim_ap = average_precision(build_relevance_flags(dim_gated, relevant_ids), relevant_count)
        combo_ap = average_precision(build_relevance_flags(combo_gated, relevant_ids), relevant_count)

        rows.append(
            {
                "product_id": product["product_id"], "topic": query_topic, "keywords": entry["keywords"],
                "pressao_values": ",".join(f"{v:g}{u}" for _t, v, u in sorted(entry["pressao_values"])),
                "dim_values": ",".join(f"{v:g}{u}" for _t, v, u in sorted(entry["dim_values"])),
                "baseline_ap": baseline_ap, "pressao_only_ap": pressao_ap, "dim_only_ap": dim_ap, "combo_ap": combo_ap,
                "query_text": search_terms,
            }
        )

    with (OUT_DIR / "pressao_combo_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["product_id", "topic", "keywords", "pressao_values", "dim_values", "baseline_ap",
                          "pressao_only_ap", "dim_only_ap", "combo_ap", "query_text"])
        for r in rows:
            writer.writerow([r["product_id"], r["topic"], r["keywords"], r["pressao_values"], r["dim_values"],
                              f"{r['baseline_ap']:.6f}", f"{r['pressao_only_ap']:.6f}", f"{r['dim_only_ap']:.6f}",
                              f"{r['combo_ap']:.6f}", r["query_text"]])

    def agg(key):
        return sum(r[key] for r in rows) / len(rows)

    overall_b = agg("baseline_ap")
    overall_pressao = agg("pressao_only_ap")
    overall_dim = agg("dim_only_ap")
    overall_combo = agg("combo_ap")

    print(f"\nMAP baseline (n={len(rows)}): {overall_b:.4f}")
    print(f"MAP so pressao (gateado):     {overall_pressao:.4f} (delta {overall_pressao - overall_b:+.4f})")
    print(f"MAP so dimensional (gateado): {overall_dim:.4f} (delta {overall_dim - overall_b:+.4f})")
    print(f"MAP pressao+dim (gateado):    {overall_combo:.4f} (delta {overall_combo - overall_b:+.4f})")

    md = []
    md.append("# pressao + dimensional combinados (gateado por topico) -- Resultados\n")
    md.append(
        "Continuacao de `mecanico_hidraulico_resultados.md`: `hidraulico.pressao.r1` sozinho deu "
        "resultado quase identico a `mecanico.resistencia.r1` (MAP -0,0056 vs -0,0064), porque a "
        "maioria das consultas de pressao neste benchmark SAO as mesmas consultas de bloco estrutural "
        "(T2), capturadas via a unidade compartilhada `mpa`. Mesma correcao aplicada: combinar com as "
        "6 regras dimensionais.\n"
    )
    md.append(f"Escopo: as mesmas **{len(rows)}** consultas do teste anterior de pressao.\n")
    md.append("## Resultado\n")
    md.append("| Variante (todas gateadas por topico) | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline (hibrido publicado) | {overall_b:.4f} | - |")
    md.append(f"| So `pressao` (teste anterior) | {overall_pressao:.4f} | {overall_pressao - overall_b:+.4f} |")
    md.append(f"| So dimensional (ablation) | {overall_dim:.4f} | {overall_dim - overall_b:+.4f} |")
    md.append(f"| **`pressao` + dimensional combinados** | **{overall_combo:.4f}** | **{overall_combo - overall_b:+.4f}** |")

    md.append("\n## Por consulta\n")
    md.append("| product_id | Topico | pressao | dim | AP baseline | AP so pressao | AP so dim | AP combo |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        md.append(
            f"| {r['product_id']} | {topic_label(r['topic'])} | {r['pressao_values']} | {r['dim_values'][:40]} | "
            f"{r['baseline_ap']:.4f} | {r['pressao_only_ap']:.4f} | {r['dim_only_ap']:.4f} | {r['combo_ap']:.4f} |"
        )

    md_path = OUT_DIR / "pressao_combo_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
