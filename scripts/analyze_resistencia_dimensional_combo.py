"""Testa a sugestao feita apos results/resistencia_mpa_analysis/: 'mpa'
sozinho PIOROU o MAP (mesmo gateado por topico) porque resistencia estrutural
e um pequeno conjunto de classes padronizadas (6, 8, 10, 12 MPa...)
compartilhadas por varias variantes do MESMO topico (blocos/canaletas de
dimensoes diferentes) -- o gate por topico nao ajuda porque a confusao e
DENTRO do topico, nao entre topicos.

Hipotese: combinar 'mpa' (mecanico.resistencia.r1) com as regras dimensionais
(as 6 de results/mm_regex_analysis/) deve resolver, porque duas pecas da
MESMA classe de resistencia mas dimensoes diferentes deixam de empatar --
so empatam pecas com a MESMA dimensao E a MESMA resistencia.

Escopo: as mesmas 15 consultas de results/resistencia_mpa_analysis/ (as
unicas com valor de mpa extraivel). Compara 4 variantes, todas gateadas por
topico (a politica ja adotada):
  (a) baseline (hibrido publicado, sem rerank)
  (b) so mpa (repete o teste anterior, para referencia)
  (c) so dimensional (ablation -- as 15 consultas tambem tem dimensao no
      texto; isola quanto do ganho vem so de dimensao, sem mpa)
  (d) mpa + dimensional combinados (a hipotese sendo testada)

Nao modifica scripts/retrieval_sinapi.py, analyze_mm_regex.py nem
analyze_resistencia_regex.py -- le class_match/param_3.json read-only e
reimplementa os extratores (mesma logica ja usada nos dois scripts
anteriores).

Uso:
    python scripts/analyze_resistencia_dimensional_combo.py

Saida (results/resistencia_mpa_analysis/):
    combo_rerank_per_query.csv
    combo_resultados.md
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

OUT_DIR = PROJECT_ROOT / "results" / "resistencia_mpa_analysis"
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


# --- extratores dimensionais (identicos a scripts/analyze_mm_regex.py) ---


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

    mpa_pattern = load_param3_pattern("mecanico", "resistencia", "r1")
    mpa_re = re.compile(mpa_pattern, re.IGNORECASE)

    dim_rule_specs = [
        (("dimensional", "comprimento", "r1_metricos"), extract_simple),
        (("dimensional", "espessura", "r1_contextual"), extract_simple),
        (("dimensional", "raio", "r1"), extract_simple),
        (("dimensional", "multidimensional_2d", "r1_metricos"), extract_multi_2d_metrico),
        (("dimensional", "multidimensional_2d", "r2_misto_polegada_metrico"), extract_multi_2d_misto),
        (("dimensional", "multidimensional_3d", "r1_metricos"), extract_multi_3d_metrico),
    ]
    dim_rules = [(re.compile(load_param3_pattern(*path), re.IGNORECASE), extractor) for path, extractor in dim_rule_specs]

    def extract_mpa(text: str) -> frozenset:
        values = set()
        for match in mpa_re.finditer(text or ""):
            v = parse_number(match.group(1)) if match.group(1) else None
            if v is not None:
                values.add(("mpa", v, "mpa"))
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
    mpa_by_item: dict[int, frozenset] = {}
    dim_by_item: dict[int, frozenset] = {}
    for item in items:
        iid = int(item["item_id"])
        m = extract_mpa(str(item["description"]))
        d = extract_dim(str(item["description"]))
        if m:
            mpa_by_item[iid] = m
        if d:
            dim_by_item[iid] = d
    combo_by_item = {
        iid: mpa_by_item.get(iid, frozenset()) | dim_by_item.get(iid, frozenset())
        for iid in set(mpa_by_item) | set(dim_by_item)
    }
    print(f"Itens com valor mpa: {len(mpa_by_item)}; com valor dimensional: {len(dim_by_item)}; combinado: {len(combo_by_item)}")

    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords = load_topic_keywords()

    queries = []
    for product in benchmark:
        text = str(product["product_description"])
        mpa_values = extract_mpa(text)
        if not mpa_values:
            continue  # mesmo escopo do teste anterior: so as consultas com mpa
        dim_values = extract_dim(text)
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        primary_item_id = min(relevant_ids) if relevant_ids else None
        topic_id = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None
        queries.append(
            {
                "product": product,
                "mpa_values": mpa_values,
                "dim_values": dim_values,
                "combo_values": mpa_values | dim_values,
                "topic": topic_id,
                "keywords": topic_keywords.get(topic_id, "") if topic_id is not None else "",
            }
        )
    print(f"Consultas no escopo (mesmas do teste anterior): {len(queries)}")

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

        mpa_gated = rerank_by_match_same_topic(baseline_ranked, entry["mpa_values"], mpa_by_item, codigo_to_topic, query_topic)
        dim_gated = rerank_by_match_same_topic(baseline_ranked, entry["dim_values"], dim_by_item, codigo_to_topic, query_topic)
        combo_gated = rerank_by_match_same_topic(baseline_ranked, entry["combo_values"], combo_by_item, codigo_to_topic, query_topic)

        baseline_ap = average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        mpa_ap = average_precision(build_relevance_flags(mpa_gated, relevant_ids), relevant_count)
        dim_ap = average_precision(build_relevance_flags(dim_gated, relevant_ids), relevant_count)
        combo_ap = average_precision(build_relevance_flags(combo_gated, relevant_ids), relevant_count)

        rows.append(
            {
                "product_id": product["product_id"],
                "topic": query_topic,
                "keywords": entry["keywords"],
                "mpa_values": ",".join(f"{v:g}" for _t, v, _u in sorted(entry["mpa_values"])),
                "dim_values": ",".join(f"{v:g}{u}" for _t, v, u in sorted(entry["dim_values"])),
                "baseline_ap": baseline_ap,
                "mpa_only_ap": mpa_ap,
                "dim_only_ap": dim_ap,
                "combo_ap": combo_ap,
                "query_text": search_terms,
            }
        )

    with (OUT_DIR / "combo_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            ["product_id", "topic", "keywords", "mpa_values", "dim_values", "baseline_ap",
             "mpa_only_ap", "dim_only_ap", "combo_ap", "query_text"]
        )
        for r in rows:
            writer.writerow(
                [r["product_id"], r["topic"], r["keywords"], r["mpa_values"], r["dim_values"],
                 f"{r['baseline_ap']:.6f}", f"{r['mpa_only_ap']:.6f}", f"{r['dim_only_ap']:.6f}",
                 f"{r['combo_ap']:.6f}", r["query_text"]]
            )

    def agg(key):
        return sum(r[key] for r in rows) / len(rows)

    overall_b = agg("baseline_ap")
    overall_mpa = agg("mpa_only_ap")
    overall_dim = agg("dim_only_ap")
    overall_combo = agg("combo_ap")

    print(f"\nMAP baseline (n={len(rows)}): {overall_b:.4f}")
    print(f"MAP so mpa (gateado):          {overall_mpa:.4f} (delta {overall_mpa - overall_b:+.4f})")
    print(f"MAP so dimensional (gateado):  {overall_dim:.4f} (delta {overall_dim - overall_b:+.4f})")
    print(f"MAP mpa+dimensional (gateado): {overall_combo:.4f} (delta {overall_combo - overall_b:+.4f})")

    md = []
    md.append("# mpa + dimensional combinados (gateado por topico) -- Resultados\n")
    md.append(
        "Continuacao de `mpa_resultados.md`: 'mpa' sozinho (mesmo gateado por topico) piorou o MAP "
        "(-0,0064) porque resistencia estrutural e um pequeno conjunto de classes padronizadas "
        "compartilhadas por varias pecas do mesmo topico com dimensoes diferentes -- o gate por topico "
        "nao ajuda porque a confusao e DENTRO do topico. Hipotese: combinar `mecanico.resistencia.r1` "
        "com as 6 regras dimensionais (`comprimento`, `espessura`, `raio`, `multidimensional_2d`x2, "
        "`multidimensional_3d`) deve resolver, ja que pecas da mesma classe de resistencia mas "
        "dimensao diferente deixam de empatar.\n"
    )
    md.append(f"Escopo: as mesmas **{len(rows)}** consultas do teste anterior (todas tem valor de mpa).\n")
    md.append("## Resultado\n")
    md.append("| Variante (todas gateadas por topico) | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline (hibrido publicado) | {overall_b:.4f} | - |")
    md.append(f"| So `mpa` (teste anterior) | {overall_mpa:.4f} | {overall_mpa - overall_b:+.4f} |")
    md.append(f"| So dimensional (ablation) | {overall_dim:.4f} | {overall_dim - overall_b:+.4f} |")
    md.append(f"| **`mpa` + dimensional combinados** | **{overall_combo:.4f}** | **{overall_combo - overall_b:+.4f}** |")

    md.append("\n## Por consulta\n")
    md.append("| product_id | Topico | mpa | dim | AP baseline | AP so mpa | AP so dim | AP combo |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        md.append(
            f"| {r['product_id']} | {topic_label(r['topic'])} | {r['mpa_values']} | {r['dim_values'][:40]} | "
            f"{r['baseline_ap']:.4f} | {r['mpa_only_ap']:.4f} | {r['dim_only_ap']:.4f} | {r['combo_ap']:.4f} |"
        )

    md_path = OUT_DIR / "combo_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
