"""Regex de atributo (class_match/param_3.json, ~20 regras) + gate por
SUBCATEGORIA (SINAPI), isolado (sem topico BERTopic por enquanto -- a
pedido do usuario) -- fecha o ciclo iniciado em results/subcategoria_rerank/
(so gate de categoria, sem atributo) e em results/topic_only_rerank_baseline/
(atributo + gate de topico, sem subcategoria).

Formula (mesma estrutura ja validada para atributo+topico):
    score = (mesma_subcategoria, match_count_se_mesma_subcategoria)

Subcategoria da consulta = a do proprio item relevante (ORACULO, mesma
convencao da sessao inteira -- ver ressalva de inferencia em
results/hierarchical_topic_rerank/).

Roda a fusao hibrida (BM25+BGE-M3) UMA VEZ para as 852 consultas do
benchmark, cacheando os candidatos -- e a partir dai calcula, para cada um
dos ~20 atributos, baseline vs. atributo+subcategoria, sem retrieval
adicional.

Nao modifica scripts/retrieval_sinapi.py nem nenhum resultado anterior --
so leitura do CSV de subcategorias (class_match) e de class_match/param_3.json.

Uso:
    python scripts/analyze_attr_subcategoria_rerank.py

Saida (results/subcategoria_rerank/):
    attr_subcategoria_por_atributo.csv/.md
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

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

OUT_DIR = PROJECT_ROOT / "results" / "subcategoria_rerank"
SUBCATEGORIA_CSV = PROJECT_ROOT.parent / "class_match" / "results" / "regex_subcategories" / "sinapi-295-regex-subcategories.csv"
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


# --- extratores (identicos aos scripts anteriores) ---

def make_numeric_extractor(compiled: re.Pattern, canon: bool = True):
    def extract(text: str) -> frozenset:
        values = set()
        for match in compiled.finditer(text or ""):
            raw_value, raw_unit = match.group(1), match.group(2)
            if not raw_value or not raw_unit:
                continue
            v = parse_number(raw_value)
            if v is None:
                continue
            unit = canon_unit(raw_unit) if canon else raw_unit.lower()
            if canon and unit is None:
                unit = raw_unit.lower()
            values.add((v, unit))
        return frozenset(values)
    return extract


def make_value_only_extractor(compiled: re.Pattern, tag: str):
    def extract(text: str) -> frozenset:
        values = set()
        for match in compiled.finditer(text or ""):
            raw_value = match.group(1)
            if not raw_value:
                continue
            v = parse_number(raw_value)
            if v is not None:
                values.add((v, tag))
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


def make_tensao_extractor(compiled: re.Pattern):
    def extract(text: str) -> frozenset:
        values = set()
        for match in compiled.finditer(text or ""):
            raw_value, raw_unit = match.group(1), match.group(2)
            if not raw_value or not raw_unit:
                continue
            unit = raw_unit.lower()
            for part in raw_value.split("/"):
                v = parse_number(part)
                if v is not None:
                    values.add((v, unit))
        return frozenset(values)
    return extract


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


def make_dimensional_combo_extractor():
    specs = [
        (("dimensional", "comprimento", "r1_metricos"), None),
        (("dimensional", "espessura", "r1_contextual"), None),
        (("dimensional", "raio", "r1"), None),
        (("dimensional", "multidimensional_2d", "r1_metricos"), extract_multi_2d_metrico),
        (("dimensional", "multidimensional_2d", "r2_misto_polegada_metrico"), extract_multi_2d_misto),
        (("dimensional", "multidimensional_3d", "r1_metricos"), extract_multi_3d_metrico),
    ]
    compiled_rules = []
    for json_path, custom_extractor in specs:
        pattern = re.compile(load_param3_pattern(*json_path), re.IGNORECASE)
        compiled_rules.append((pattern, custom_extractor))

    def extract(text: str) -> frozenset:
        values = set()
        for pattern, custom_extractor in compiled_rules:
            for match in pattern.finditer(text or ""):
                if custom_extractor is None:
                    raw_value, raw_unit = match.group(1), match.group(2)
                    if not raw_value or not raw_unit:
                        continue
                    unit = canon_unit(raw_unit)
                    v = parse_number(raw_value)
                    if unit is not None and v is not None:
                        values.add((v, unit))
                else:
                    for v, u in custom_extractor(match):
                        values.add((v, u))
        return frozenset(values)
    return extract


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


def rerank_attr_gated_single(ranked_items, query_values, values_by_item, item_label, query_label):
    def score(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        if query_label is None or query_label == "" or str(query_label) == "-1" or item_label.get(item_id) != query_label:
            return 0
        return len(query_values & values_by_item.get(item_id, frozenset()))
    return sorted(ranked_items, key=score, reverse=True)


def load_subcategoria_by_item() -> dict[int, str]:
    sub_by_item: dict[int, str] = {}
    with SUBCATEGORIA_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            item_id = coerce_item_id(row.get("id_itm"))
            sub_id = row.get("subcategoria_id")
            if item_id is not None and sub_id and item_id not in sub_by_item:
                sub_by_item[item_id] = sub_id
    return sub_by_item


def build_attribute_specs() -> list[tuple[str, str]]:
    return [
        ("peso", "Peso (kg/g/mg/t)"),
        ("dimensional", "Dimensional (mm/cm/m/pol, 6 regras)"),
        ("potencia_mecanica", "Potencia mecanica (cv/hp)"),
        ("diametro_dn", "Diametro nominal (DN)"),
        ("isolacao_eletrica", "Isolacao eletrica"),
        ("vias_condutoras", "Vias condutoras"),
        ("categoria_rede", "Categoria de rede (CAT5...)"),
        ("material_base", "Material base"),
        ("corrente", "Corrente eletrica"),
        ("resistencia", "Resistencia estrutural (mpa)"),
        ("pressao", "Pressao hidraulica"),
        ("normativo_nbr", "Norma NBR"),
        ("cor_base", "Cor base"),
        ("tensao", "Tensao (v/kv)"),
        ("potencia_eletrica", "Potencia eletrica (w/kw/kva)"),
        ("capacidade_litros", "Capacidade (litros)"),
        ("comprimento_polegadas", "Comprimento/diametro em polegadas"),
        ("area", "Area (mm2/cm2/m2)"),
        ("volume", "Volume (mm3/cm3/m3)"),
        ("concentracao", "Concentracao quimica (%)"),
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    extractors: dict[str, callable] = {}
    extractors["peso"] = make_numeric_extractor(re.compile(load_param3_pattern("massa", "peso", "r1"), re.IGNORECASE))
    extractors["dimensional"] = make_dimensional_combo_extractor()
    extractors["potencia_mecanica"] = make_value_only_extractor(
        re.compile(load_param3_pattern("mecanico", "potencia_mecanica", "r1"), re.IGNORECASE), "power"
    )
    extractors["diametro_dn"] = make_numeric_extractor(re.compile(load_param3_pattern("dimensional", "diametro", "r2_dn"), re.IGNORECASE))
    extractors["isolacao_eletrica"] = make_categorical_extractor(
        re.compile(load_param3_pattern("material", "isolacao_eletrica", "r1"), re.IGNORECASE), "isolacao_eletrica"
    )
    extractors["vias_condutoras"] = make_numeric_extractor(re.compile(load_param3_pattern("eletrico", "vias_condutoras", "r1_quantidade"), re.IGNORECASE))
    extractors["categoria_rede"] = make_categorical_extractor(
        re.compile(load_param3_pattern("eletrico", "categoria_rede", "r1"), re.IGNORECASE), "categoria_rede"
    )
    extractors["material_base"] = make_categorical_extractor(
        re.compile(load_param3_pattern("material", "material_base", "r1"), re.IGNORECASE), "material_base"
    )
    extractors["corrente"] = make_numeric_extractor(re.compile(load_param3_pattern("eletrico", "corrente", "r1"), re.IGNORECASE))
    extractors["resistencia"] = make_numeric_extractor(re.compile(load_param3_pattern("mecanico", "resistencia", "r1"), re.IGNORECASE))
    extractors["pressao"] = make_numeric_extractor(re.compile(load_param3_pattern("hidraulico", "pressao", "r1"), re.IGNORECASE))
    extractors["normativo_nbr"] = make_categorical_extractor(
        re.compile(load_param3_pattern("normativo", "nbr", "r1"), re.IGNORECASE), "nbr"
    )
    extractors["cor_base"] = make_categorical_extractor(
        re.compile(load_param3_pattern("cor", "cor_base", "r1"), re.IGNORECASE), "cor_base"
    )
    extractors["tensao"] = make_tensao_extractor(re.compile(load_param3_pattern("eletrico", "tensao", "r1"), re.IGNORECASE))
    extractors["potencia_eletrica"] = make_numeric_extractor(re.compile(load_param3_pattern("eletrico", "potencia_eletrica", "r1"), re.IGNORECASE))
    extractors["capacidade_litros"] = make_numeric_extractor(re.compile(load_param3_pattern("dimensional", "capacidade", "r1_litros"), re.IGNORECASE))
    extractors["comprimento_polegadas"] = make_numeric_extractor(re.compile(load_param3_pattern("dimensional", "comprimento", "r2_polegadas"), re.IGNORECASE))
    extractors["area"] = make_numeric_extractor(re.compile(load_param3_pattern("dimensional", "area", "r1"), re.IGNORECASE))
    extractors["volume"] = make_numeric_extractor(re.compile(load_param3_pattern("dimensional", "volume", "r1"), re.IGNORECASE))
    extractors["concentracao"] = make_numeric_extractor(re.compile(load_param3_pattern("quimico", "concentracao", "r1"), re.IGNORECASE))

    attr_specs = build_attribute_specs()

    items = read_sinapi_items()
    values_by_item_by_attr: dict[str, dict[int, frozenset]] = {name: {} for name, _ in attr_specs}
    for item in items:
        item_id = int(item["item_id"])
        desc = str(item["description"])
        for attr_name, _ in attr_specs:
            values = extractors[attr_name](desc)
            if values:
                values_by_item_by_attr[attr_name][item_id] = values

    benchmark = load_benchmark(INPUT_JSON)
    sub_by_item = load_subcategoria_by_item()
    print(f"Consultas no benchmark: {len(benchmark)}")
    print(f"Itens com subcategoria: {len(sub_by_item)}")

    # --- retrieval UMA VEZ para as 852 consultas; cacheia candidatos ---
    per_query_cache: dict[int, dict] = {}
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        primary_item_id = min(relevant_ids) if relevant_ids else None
        query_sub = sub_by_item.get(primary_item_id) if primary_item_id is not None else None

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)

        query_values_by_attr = {name: extractors[name](search_terms) for name, _ in attr_specs}

        per_query_cache[int(product["product_id"])] = {
            "product_id": product["product_id"], "subcategoria": query_sub,
            "relevant_ids": relevant_ids, "relevant_count": len(relevant_ids),
            "baseline_ranked": baseline_ranked, "query_values_by_attr": query_values_by_attr,
        }
        if i % 100 == 0 or i == len(benchmark):
            print(f"[{i}/{len(benchmark)}] retrieval processado")

    # --- por atributo: baseline vs. attr+subcategoria ---
    comparison_rows = []
    for attr_name, label in attr_specs:
        values_by_item = values_by_item_by_attr[attr_name]
        scoped = [q for q in per_query_cache.values() if q["query_values_by_attr"][attr_name]]
        n = len(scoped)
        if n == 0:
            print(f"{label}: 0 consultas, pulando")
            continue

        baseline_aps, attr_sub_aps = [], []
        for q in scoped:
            baseline_ranked = q["baseline_ranked"]
            relevant_ids, relevant_count = q["relevant_ids"], q["relevant_count"]
            query_sub = q["subcategoria"]
            query_values = q["query_values_by_attr"][attr_name]

            attr_sub_ranked = rerank_attr_gated_single(baseline_ranked, query_values, values_by_item, sub_by_item, query_sub)

            baseline_aps.append(average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count))
            attr_sub_aps.append(average_precision(build_relevance_flags(attr_sub_ranked, relevant_ids), relevant_count))

        map_baseline = sum(baseline_aps) / n
        map_attr_sub = sum(attr_sub_aps) / n

        comparison_rows.append({"label": label, "n": n, "baseline": map_baseline, "attr_sub": map_attr_sub})
        print(f"{label:38s} n={n:4d}  baseline={map_baseline:.4f}  attr+subcategoria={map_attr_sub:.4f}  delta={map_attr_sub-map_baseline:+.4f}")

    # --- global: uniao de todos os atributos por consulta ---
    union_values_by_item: dict[int, frozenset] = {}
    for attr_name in values_by_item_by_attr:
        for iid, vals in values_by_item_by_attr[attr_name].items():
            if vals:
                union_values_by_item[iid] = union_values_by_item.get(iid, frozenset()) | vals

    g_baseline, g_attr_sub = [], []
    for q in per_query_cache.values():
        baseline_ranked = q["baseline_ranked"]
        relevant_ids, relevant_count = q["relevant_ids"], q["relevant_count"]
        query_sub = q["subcategoria"]
        union_values = frozenset().union(*q["query_values_by_attr"].values()) if q["query_values_by_attr"] else frozenset()

        attr_sub_ranked = rerank_attr_gated_single(baseline_ranked, union_values, union_values_by_item, sub_by_item, query_sub)

        g_baseline.append(average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count))
        g_attr_sub.append(average_precision(build_relevance_flags(attr_sub_ranked, relevant_ids), relevant_count))

    def avg(xs):
        return sum(xs) / len(xs)

    print(f"\n=== GLOBAL (852 consultas, uniao de todos os atributos) ===")
    print(f"Baseline:                 {avg(g_baseline):.4f}")
    print(f"Atributo + subcategoria:  {avg(g_attr_sub):.4f}  (delta {avg(g_attr_sub)-avg(g_baseline):+.4f})")

    # --- salvar ---
    with (OUT_DIR / "attr_subcategoria_por_atributo.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["atributo", "n", "map_baseline", "map_attr_subcategoria", "delta"])
        writer.writerow(
            ["GLOBAL (uniao de todos os atributos)", len(per_query_cache), f"{avg(g_baseline):.6f}",
             f"{avg(g_attr_sub):.6f}", f"{avg(g_attr_sub)-avg(g_baseline):.6f}"]
        )
        for r in comparison_rows:
            writer.writerow([r["label"], r["n"], f"{r['baseline']:.6f}", f"{r['attr_sub']:.6f}",
                              f"{r['attr_sub']-r['baseline']:.6f}"])

    md = []
    md.append("# Regex de atributo + gate por subcategoria (SINAPI) -- Resultados\n")
    md.append(
        "Mesma formula ja validada para atributo+topico "
        "(`results/topic_only_rerank_baseline/combined_vs_isolados_resumo.md`), agora usando a "
        "subcategoria SINAPI como gate no lugar do topico BERTopic: "
        "`score = (mesma_subcategoria, match_count_se_mesma_subcategoria)`. "
        "Sem topico nesta rodada (a pedido do usuario). Subcategoria da consulta = a do proprio "
        "item relevante (ORACULO, mesma convencao da sessao -- ver ressalva de inferencia em "
        "`results/hierarchical_topic_rerank/`).\n"
    )
    md.append("## Resultado global (852 consultas, uniao de todos os atributos)\n")
    md.append("| Politica | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline | {avg(g_baseline):.4f} | - |")
    md.append(f"| **Atributo + subcategoria** | **{avg(g_attr_sub):.4f}** | **{avg(g_attr_sub)-avg(g_baseline):+.4f}** |")
    md.append(
        "\nPara referencia (ja calculado em `subcategoria_rerank_resultados.md`, sem atributo): "
        "flat subcategoria = 0.8016 (+0.0084); flat topico = 0.8109 (+0.0177); "
        "combinado topico+subcategoria = 0.8143 (+0.0211).\n"
    )

    md.append("\n## Por atributo\n")
    md.append("| Atributo | N | Baseline | **Atributo + subcategoria** | Delta |")
    md.append("|---|---|---|---|---|")
    for r in sorted(comparison_rows, key=lambda r: r["attr_sub"] - r["baseline"], reverse=True):
        md.append(f"| {r['label']} | {r['n']} | {r['baseline']:.4f} | **{r['attr_sub']:.4f}** | {r['attr_sub']-r['baseline']:+.4f} |")

    md_path = OUT_DIR / "attr_subcategoria_por_atributo.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
