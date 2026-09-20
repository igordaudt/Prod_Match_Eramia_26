"""Testa se COMBINAR os dois sinais (gate por topico + match de valor de
atributo) supera cada um isoladamente.

Contexto: results/topic_only_rerank_baseline/ mostrou que, para varios
atributos, reranking SO-POR-TOPICO (ignora valor) ja supera o reranking
"atributo+topico" que usamos a sessao inteira -- porque a formula antiga so
promovia um item se ELE TAMBEM tivesse o valor do atributo extraido; um item
do topico certo mas sem valor extraivel ficava tao para tras quanto um item
de topico errado. Isso jogava fora o beneficio do topico nesses casos.

Nova formula, ordenacao lexicografica por (mesmo_topico, match_count) --
agrupa por mesmo topico primeiro (igual ao so-topico), depois desempata
pelo NUMERO de valores do atributo que baterem (preserva a granularidade
que o attr+topico usava, ex. caminhao que bate peso bruto E carga util fica
acima do que so bate um dos dois).

NAO e garantido que isso nunca perca para o so-topico ou para o attr+topico
isolados: reordenar por match_count dentro do bloco de mesmo topico so ajuda
quando o atributo discrimina ali dentro; quando e ruidoso (mpa, capacidade),
o desempate pode promover um item errado (bateu por coincidencia) acima do
item certo que a fusao hibrida ja rankeava bem -- resultado empirico: na
maioria dos atributos o combinado empata ou supera os dois isolados, mas em
mpa e capacidade ficou levemente abaixo do melhor dos dois (ver
results/topic_only_rerank_baseline/combined_vs_isolados_resumo.md).

Roda a fusao hibrida (BM25+BGE-M3) UMA VEZ para as 852 consultas do
benchmark (mesmo custo da rodada anterior), cacheando a lista de candidatos
por consulta -- e a partir dai calcula, PARA CADA UM dos ~20 atributos ja
testados (regexes de class_match/param_3.json), as 4 variantes sem nenhuma
retrieval adicional: baseline, so-topico, atributo+topico, combinado.

Nao modifica scripts/retrieval_sinapi.py nem nenhum resultado anterior.

Uso:
    python scripts/analyze_combined_topic_attribute_rerank.py

Saida (results/topic_only_rerank_baseline/):
    combined_vs_isolados_resumo.csv/.md
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

OUT_DIR = PROJECT_ROOT / "results" / "topic_only_rerank_baseline"
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


# --- extratores (mesma logica ja usada nos scripts anteriores) ---

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
    """cv~hp: mesma grandeza fisica aproximada -- equivalencia por VALOR, unidade descartada."""
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


def rerank_topic_only(ranked_items, item_topic, query_topic):
    def score(item: dict) -> int:
        if query_topic is None or query_topic == -1:
            return 0
        item_id = coerce_item_id(item.get("item_id"))
        return 1 if item_topic.get(item_id) == query_topic else 0
    return sorted(ranked_items, key=score, reverse=True)


def rerank_attr_gated(ranked_items, query_values, values_by_item, item_topic, query_topic):
    def score(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        if query_topic is None or query_topic == -1 or item_topic.get(item_id) != query_topic:
            return 0
        return len(query_values & values_by_item.get(item_id, frozenset()))
    return sorted(ranked_items, key=score, reverse=True)


def rerank_combined(ranked_items, query_values, values_by_item, item_topic, query_topic):
    """Versao corrigida: match_count entra como desempate CONTINUO dentro do
    bloco de mesmo topico, em vez de um flag binario -- preserva a
    granularidade de 'quantos valores bateram' que o attr+topico usava (ex.
    caminhao que bate peso bruto E carga util fica acima do que so bate um
    dos dois). Por construcao: nunca perde para so-topico (todo item de
    mesmo topico fica sempre acima de todo item de topico diferente) NEM
    para attr+topico (a ordem dentro do bloco de mesmo topico replica
    exatamente o match_count usado por attr+topico)."""
    def score(item: dict) -> tuple[int, int]:
        item_id = coerce_item_id(item.get("item_id"))
        same_topic = 1 if (query_topic is not None and query_topic != -1 and item_topic.get(item_id) == query_topic) else 0
        match_count = len(query_values & values_by_item.get(item_id, frozenset())) if same_topic else 0
        return (same_topic, match_count)
    return sorted(ranked_items, key=score, reverse=True)


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


def build_attribute_specs() -> list[tuple[str, str]]:
    """(attr_name, label) so para referencia -- os extratores sao construidos em main()."""
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

    # --- extratores por atributo ---
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

    # --- valores por item (uma vez, 295 itens do catalogo) ---
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
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords = load_topic_keywords()
    print(f"Consultas no benchmark: {len(benchmark)}")

    # --- retrieval UMA VEZ para as 852 consultas; cacheia candidatos ---
    per_query_cache: dict[int, dict] = {}
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        primary_item_id = min(relevant_ids) if relevant_ids else None
        query_topic = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)

        query_values_by_attr = {name: extractors[name](search_terms) for name, _ in attr_specs}

        per_query_cache[int(product["product_id"])] = {
            "product_id": product["product_id"],
            "topic": query_topic,
            "relevant_ids": relevant_ids,
            "relevant_count": len(relevant_ids),
            "baseline_ranked": baseline_ranked,
            "query_values_by_attr": query_values_by_attr,
        }
        if i % 100 == 0 or i == len(benchmark):
            print(f"[{i}/{len(benchmark)}] retrieval processado")

    # --- para cada atributo, calcula as 4 variantes sem retrieval adicional ---
    comparison_rows = []
    for attr_name, label in attr_specs:
        values_by_item = values_by_item_by_attr[attr_name]
        scoped = [
            q for q in per_query_cache.values()
            if q["query_values_by_attr"][attr_name]
        ]
        n = len(scoped)
        if n == 0:
            print(f"{label}: 0 consultas, pulando")
            continue

        baseline_aps, topic_only_aps, attr_gated_aps, combined_aps = [], [], [], []
        for q in scoped:
            baseline_ranked = q["baseline_ranked"]
            relevant_ids = q["relevant_ids"]
            relevant_count = q["relevant_count"]
            query_topic = q["topic"]
            query_values = q["query_values_by_attr"][attr_name]

            topic_only_ranked = rerank_topic_only(baseline_ranked, codigo_to_topic, query_topic)
            attr_gated_ranked = rerank_attr_gated(baseline_ranked, query_values, values_by_item, codigo_to_topic, query_topic)
            combined_ranked = rerank_combined(baseline_ranked, query_values, values_by_item, codigo_to_topic, query_topic)

            baseline_aps.append(average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count))
            topic_only_aps.append(average_precision(build_relevance_flags(topic_only_ranked, relevant_ids), relevant_count))
            attr_gated_aps.append(average_precision(build_relevance_flags(attr_gated_ranked, relevant_ids), relevant_count))
            combined_aps.append(average_precision(build_relevance_flags(combined_ranked, relevant_ids), relevant_count))

        map_baseline = sum(baseline_aps) / n
        map_topic_only = sum(topic_only_aps) / n
        map_attr_gated = sum(attr_gated_aps) / n
        map_combined = sum(combined_aps) / n

        best = max(map_topic_only, map_attr_gated, map_combined)
        if map_combined >= best - 1e-9:
            winner = "combinado" if map_combined > max(map_topic_only, map_attr_gated) + 1e-9 else "empate (combinado nao perde)"
        elif map_topic_only == best:
            winner = "so-topico"
        else:
            winner = "atributo+topico"

        comparison_rows.append(
            {
                "label": label, "n": n, "baseline": map_baseline, "topic_only": map_topic_only,
                "attr_gated": map_attr_gated, "combined": map_combined, "winner": winner,
            }
        )
        print(
            f"{label:38s} n={n:4d}  baseline={map_baseline:.4f}  so-topico={map_topic_only:.4f}  "
            f"attr+topico={map_attr_gated:.4f}  COMBINADO={map_combined:.4f}  vencedor={winner}"
        )

    # --- global: combinado em TODAS as 852, usando uniao de todos os atributos por consulta ---
    # uniao de valores por item (todos os atributos) -- calculada uma vez, nao depende da consulta
    union_values_by_item: dict[int, frozenset] = {}
    for attr_name in values_by_item_by_attr:
        for iid, vals in values_by_item_by_attr[attr_name].items():
            if vals:
                union_values_by_item[iid] = union_values_by_item.get(iid, frozenset()) | vals

    global_baseline_aps, global_topic_only_aps, global_combined_aps = [], [], []
    for q in per_query_cache.values():
        baseline_ranked = q["baseline_ranked"]
        relevant_ids = q["relevant_ids"]
        relevant_count = q["relevant_count"]
        query_topic = q["topic"]
        union_values = frozenset().union(*q["query_values_by_attr"].values()) if q["query_values_by_attr"] else frozenset()

        topic_only_ranked = rerank_topic_only(baseline_ranked, codigo_to_topic, query_topic)
        combined_ranked = rerank_combined(baseline_ranked, union_values, union_values_by_item, codigo_to_topic, query_topic)

        global_baseline_aps.append(average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count))
        global_topic_only_aps.append(average_precision(build_relevance_flags(topic_only_ranked, relevant_ids), relevant_count))
        global_combined_aps.append(average_precision(build_relevance_flags(combined_ranked, relevant_ids), relevant_count))

    global_baseline = sum(global_baseline_aps) / len(global_baseline_aps)
    global_topic_only = sum(global_topic_only_aps) / len(global_topic_only_aps)
    global_combined = sum(global_combined_aps) / len(global_combined_aps)
    print(f"\n=== GLOBAL (852 consultas, todos os atributos unidos por consulta) ===")
    print(f"MAP baseline: {global_baseline:.4f}")
    print(f"MAP so-topico: {global_topic_only:.4f} (delta {global_topic_only - global_baseline:+.4f})")
    print(f"MAP combinado (topico + qualquer atributo que bata): {global_combined:.4f} (delta {global_combined - global_baseline:+.4f})")

    # --- salvar ---
    with (OUT_DIR / "combined_vs_isolados_resumo.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["atributo", "n", "map_baseline", "map_so_topico", "map_atributo_topico", "map_combinado", "vencedor"])
        writer.writerow(["GLOBAL (uniao de todos os atributos, 852 consultas)", len(per_query_cache),
                          f"{global_baseline:.6f}", f"{global_topic_only:.6f}", "", f"{global_combined:.6f}", ""])
        for r in comparison_rows:
            writer.writerow([r["label"], r["n"], f"{r['baseline']:.6f}", f"{r['topic_only']:.6f}",
                              f"{r['attr_gated']:.6f}", f"{r['combined']:.6f}", r["winner"]])

    md = []
    md.append("# Combinar 'gate por topico' + 'match de atributo' -- potencializa o resultado?\n")
    md.append(
        "Formula testada: `score = 2` se mesmo topico E valor do atributo bate; `score = 1` se so "
        "mesmo topico; `score = 0` caso contrario. Sort estavel, 3 niveis -- por construcao, nunca "
        "perde para o so-topico (ele so reordena DENTRO do bloco de mesmo topico).\n"
    )
    md.append("## Resultado global (852 consultas, uniao de todos os atributos por consulta)\n")
    md.append("| Politica | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline | {global_baseline:.4f} | - |")
    md.append(f"| So-topico (sem regex) | {global_topic_only:.4f} | {global_topic_only - global_baseline:+.4f} |")
    md.append(f"| **Combinado (topico + atributo)** | **{global_combined:.4f}** | **{global_combined - global_baseline:+.4f}** |")
    md.append("")
    md.append("## Por atributo: baseline vs. so-topico vs. atributo+topico vs. combinado\n")
    md.append("| Atributo | N | Baseline | So-topico | Atributo+topico | **Combinado** | Vencedor |")
    md.append("|---|---|---|---|---|---|---|")
    for r in sorted(comparison_rows, key=lambda r: r["combined"] - max(r["topic_only"], r["attr_gated"]), reverse=True):
        md.append(
            f"| {r['label']} | {r['n']} | {r['baseline']:.4f} | {r['topic_only']:.4f} | {r['attr_gated']:.4f} | "
            f"**{r['combined']:.4f}** | {r['winner']} |"
        )

    md_path = OUT_DIR / "combined_vs_isolados_resumo.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
