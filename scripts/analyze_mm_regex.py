"""Analise de 'mm' (comprimento/espessura) -- mesma metodologia aplicada a
'kg' e 'cv'/'hp' em scripts/validate_param3_regex.py, usando as regras
OFICIAIS de class_match/param_3.json:

  - parametros.dimensional.comprimento.r1_metricos  (mm, cm, m -- e formas
    por extenso: milimetro(s), centimetro(s), metro(s) -- sem exigir contexto)
  - parametros.dimensional.espessura.r1_contextual  (mm, cm, m, "/pol --
    exige contexto 'esp'/'espessura' antes do numero; e a UNICA das duas que
    cobre polegadas)

Por pedido explicito, SO essas duas regras (nao inclui diametro, area,
volume nem multidimensional_2d/3d ainda). Isso tem uma limitacao conhecida:
em dimensoes compostas tipo "600 X 2100 MM", so o numero imediatamente colado
a unidade e capturado (2100mm) -- o 600 fica de fora, porque nenhuma das duas
regras usadas cobre o padrao "NxN unidade". As regras multidimensional_2d/3d
do param_3.json resolveriam isso, mas ficam fora do escopo desta rodada.

Unidades (mm, cm, m, pol) NAO sao intercambiaveis entre si (10mm != 10cm !=
10m) -- canonicalizadas (inclui formas por extenso e variantes com/sem
acento) e comparadas com match exigindo mesmo valor E mesma unidade, igual
foi feito para peso (kg/g/mg/t) em validate_param3_regex.py.

Diferente de kg/cv-hp (topicos fracos fixos T101/T73), aqui os topicos
"fracos" sao calculados dinamicamente (MAP medio do topico < 0.60), porque
'mm' e muito mais disperso pelo catalogo do que peso/potencia.

Nao modifica scripts/retrieval_sinapi.py nem os scripts anteriores -- so
leitura de class_match/param_3.json e do benchmark.

Uso:
    python scripts/analyze_mm_regex.py

Saida (results/mm_regex_analysis/):
    mm_values_por_item.csv          Valor(es) dimensionais extraidos de cada item do catalogo.
    mm_rerank_per_query.csv         AP baseline vs ingenuo vs gateado por topico, por consulta.
    mm_rerank_intruders.csv         Itens promovidos por match ingenuo, com topico da consulta x do item.
    mm_por_topico.csv               MAP por topico (baseline vs gateado), com flag de topico fraco.
    mm_resultados.md                Relatorio final.
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

OUT_DIR = PROJECT_ROOT / "results" / "mm_regex_analysis"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
PARAM3_JSON = PROJECT_ROOT.parent / "class_match" / "param_3.json"
RRF_K = 60
PREFETCH_LIMIT = 100
WEAK_TOPIC_MAP_THRESHOLD = 0.60

UNIT_CANON = {
    "mm": "mm", "milimetro": "mm", "milimetros": "mm",
    "cm": "cm", "centimetro": "cm", "centimetros": "cm",
    "m": "m", "metro": "m", "metros": "m",
    '"': "pol", "pol": "pol", "pol.": "pol",
    "polegada": "pol", "polegadas": "pol",
}


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canon_unit(raw_unit: str) -> str | None:
    key = strip_accents(raw_unit.strip().lower())
    return UNIT_CANON.get(key)


VULGAR_FRACTIONS = {"¾": 0.75, "½": 0.5, "¼": 0.25, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875}
FRACTION_RE = re.compile(r"^(?:(\d+)\s+)?(\d+)\s*[/⁄]\s*(\d+)$")


def parse_number(raw: str) -> float | None:
    """Numero decimal (virgula ou ponto), fracao vulgar (¾ etc.) ou fracao 'N/D'
    / mista 'W N/D' (usado por r2_polegadas/r2_misto_polegada_metrico)."""
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


# --- extratores por regra: cada um recebe o re.Match e devolve 0+ pares (valor, unidade) ---


def extract_simple(match: re.Match) -> list[tuple[float, str]]:
    """comprimento.r1_metricos / espessura.r1_contextual / raio.r1 -- grupos (valor, unidade).
    raio.r1 tem unidade opcional (pode vir None); descartamos se nao houver unidade explicita
    (sem ela nao da pra saber a escala -- mm vs cm vs m)."""
    raw_value, raw_unit = match.group(1), match.group(2)
    if not raw_value or not raw_unit:
        return []
    unit = canon_unit(raw_unit)
    value = parse_number(raw_value)
    if unit is None or value is None:
        return []
    return [(value, unit)]


def extract_multi_2d_metrico(match: re.Match) -> list[tuple[float, str]]:
    """multidimensional_2d.r1_metricos -- "AxB unidade": grupos (num1, num2, unidade).
    A unidade do primeiro numero, se escrita explicitamente (ex. "60cm x 2100mm"), nao e
    capturada pela regra (grupo nao-capturador) -- assumimos que os dois numeros
    compartilham a unidade final, que e o padrao dominante no catalogo ("AxB mm")."""
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
    """multidimensional_2d.r2_misto_polegada_metrico -- "A pol x B unidade":
    grupos (valor_pol, marcador_pol, valor_metrico, unidade_metrica)."""
    raw_pol_value, _pol_marker, raw_metric_value, raw_metric_unit = (
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
    """multidimensional_3d.r1_metricos -- "AxBxC unidade": grupos
    (num1, unit1, num2, unit2, num3, unit3, unit_final). Cada numero usa sua propria
    unidade se explicita; senao cai para a unidade final (padrao "19x19x8 CM")."""
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

    rule_specs = [
        ("comprimento.r1_metricos", ("dimensional", "comprimento", "r1_metricos"), extract_simple),
        ("espessura.r1_contextual", ("dimensional", "espessura", "r1_contextual"), extract_simple),
        ("raio.r1", ("dimensional", "raio", "r1"), extract_simple),
        ("multidimensional_2d.r1_metricos", ("dimensional", "multidimensional_2d", "r1_metricos"), extract_multi_2d_metrico),
        ("multidimensional_2d.r2_misto_polegada_metrico", ("dimensional", "multidimensional_2d", "r2_misto_polegada_metrico"), extract_multi_2d_misto),
        ("multidimensional_3d.r1_metricos", ("dimensional", "multidimensional_3d", "r1_metricos"), extract_multi_3d_metrico),
    ]
    compiled_rules = []
    for name, json_path, extractor in rule_specs:
        pattern_str = load_param3_pattern(*json_path)
        compiled_rules.append((name, pattern_str, re.compile(pattern_str, re.IGNORECASE), extractor))
        print(f"Regra carregada: {name}")

    def extract_values(text: str) -> frozenset[tuple[float, str]]:
        values = set()
        for _name, _pattern_str, compiled, extractor in compiled_rules:
            for match in compiled.finditer(text or ""):
                for value, unit in extractor(match):
                    values.add((value, unit))
        return frozenset(values)

    items = read_sinapi_items()
    desc_by_item = {int(it["item_id"]): str(it["description"]) for it in items}
    values_by_item: dict[int, frozenset] = {}
    for item in items:
        values = extract_values(str(item["description"]))
        if values:
            values_by_item[int(item["item_id"])] = values
    print(f"Itens do catalogo com valor dimensional: {len(values_by_item)} de {len(items)}")

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
    print(f"Consultas com valor dimensional extraido: {len(queries)} de {len(benchmark)}")

    rows = []
    intruder_rows = []
    started_count = 0
    for entry in queries:
        started_count += 1
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

        qv_str = ",".join(f"{v:g}{u}" for v, u in sorted(entry["query_values"]))

        rows.append(
            {
                "product_id": product["product_id"],
                "topic": query_topic,
                "keywords": entry["keywords"],
                "query_values": qv_str,
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
                match_str = ",".join(f"{v:g}{u}" for v, u in sorted(match))
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

        if started_count % 100 == 0 or started_count == len(queries):
            print(f"[{started_count}/{len(queries)}] processado")

    with (OUT_DIR / "mm_values_por_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["item_id", "values", "description"])
        for item in items:
            item_id = int(item["item_id"])
            values = values_by_item.get(item_id)
            if values:
                writer.writerow([item_id, ",".join(f"{v:g}{u}" for v, u in sorted(values)), item["description"]])

    with (OUT_DIR / "mm_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
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

    with (OUT_DIR / "mm_rerank_intruders.csv").open("w", encoding="utf-8", newline="") as f:
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
    print(f"  topicos fracos (MAP<{WEAK_TOPIC_MAP_THRESHOLD}, n={n_weak}): baseline={weak_b:.4f} ingenuo={weak_naive:.4f} gateado={weak_gated:.4f}")
    print(f"  topicos fortes (n={n_strong}): baseline={strong_b:.4f} ingenuo={strong_naive:.4f} gateado={strong_gated:.4f}")
    print(f"Intrusos: {n_intruders}, de topico diferente: {n_diff_topic} ({100*n_diff_topic/max(n_intruders,1):.0f}%)")
    print(f"Consultas com item relevante fora do top-{DEFAULT_LIMIT}: {n_unrecoverable}")

    with (OUT_DIR / "mm_por_topico.csv").open("w", encoding="utf-8", newline="") as f:
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
    md.append("# Analise de 'mm' (dimensional) via param_3.json -- Resultados (rodada 2, 6 regras)\n")
    md.append(
        "Mesma metodologia de `results/param3_regex_validation/` (kg, cv/hp), aplicada as regras "
        "dimensionais de `class_match/param_3.json`. **Completa a rodada 1** (que usou so "
        "`comprimento.r1_metricos` + `espessura.r1_contextual`, MAP gateado 0,8313) adicionando "
        "`raio.r1`, `multidimensional_2d.r1_metricos`, `multidimensional_2d.r2_misto_polegada_metrico` "
        "e `multidimensional_3d.r1_metricos` -- por pedido explicito, ainda SEM `diametro` nem "
        "`area`/`volume`.\n"
    )
    md.append("## Regras usadas (6)\n")
    for name, pattern_str, _compiled, _extractor in compiled_rules:
        md.append(f"- `dimensional.{name}`: `{pattern_str}`")
    md.append(
        "\nAs duas regras `multidimensional_*` foram adicionadas justamente para cobrir o caso "
        "\"600 X 2100 MM\" que a rodada 1 perdia parcialmente (so capturava o 2100, colado a unidade "
        "-- o 600 ficava de fora). Isso motivou essa rodada 2: a regressao encontrada em T61 (portas) "
        "na rodada 1 era exatamente esse padrao.\n"
    )
    md.append(
        "Unidades (`mm`, `cm`, `m`, `pol`) NAO sao intercambiaveis entre si -- match exige mesmo valor "
        "E mesma unidade, canonicalizando formas por extenso/acentuadas (ex. \"milímetros\" -> `mm`). "
        "Em `raio.r1` (unidade opcional na regra), descartamos ocorrencias sem unidade explicita -- sem "
        "ela nao da pra saber a escala.\n"
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
    md.append(
        f"Topicos \"fracos\" definidos dinamicamente como MAP medio do topico < {WEAK_TOPIC_MAP_THRESHOLD} "
        "(diferente de kg/cv-hp, que usaram T101/T73 fixos -- `mm` se espalha por muito mais topicos).\n"
    )
    md.append("| Segmento | N | Baseline | Ingenuo | Gateado por topico |")
    md.append("|---|---|---|---|---|")
    md.append(f"| Topicos fracos (MAP<{WEAK_TOPIC_MAP_THRESHOLD}) | {n_weak} | {weak_b:.4f} | {weak_naive:.4f} | {weak_gated:.4f} |")
    md.append(f"| Topicos fortes | {n_strong} | {strong_b:.4f} | {strong_naive:.4f} | {strong_gated:.4f} |")

    md.append("\n## Comparacao com a rodada 1 (so comprimento + espessura)\n")
    md.append("| Rodada | Regras | N consultas | MAP baseline | MAP gateado | Delta |")
    md.append("|---|---|---|---|---|---|")
    md.append("| 1 | comprimento + espessura (2) | 546 | 0.7931 | 0.8313 | +0.0383 |")
    md.append(f"| 2 (esta) | + raio + multidim_2d(x2) + multidim_3d (6) | {n} | {overall_b:.4f} | {overall_gated:.4f} | {overall_gated - overall_b:+.4f} |")
    t61_rows = per_topic.get(61, [])
    if t61_rows:
        t61_b, t61_a, t61_n = agg(t61_rows, "same_topic_ap")
        md.append(
            f"\n**T61 (portas), a unica regressao da rodada 1** (0,3263 -> 0,2875, delta -0,0388): "
            f"nesta rodada, com `multidimensional_2d` cobrindo \"AxB mm\" por completo, "
            f"MAP baseline={t61_b:.4f} -> gateado={t61_a:.4f} (delta {t61_a - t61_b:+.4f}, n={t61_n}).\n"
        )

    md.append("\n## Intrusos do reranking ingenuo\n")
    md.append(
        f"- Total de intrusos (itens promovidos por match dimensional, nao relevantes): **{n_intruders}**\n"
        f"- De topico DIFERENTE da consulta: **{n_diff_topic}/{n_intruders}** "
        f"({100*n_diff_topic/max(n_intruders,1):.0f}%)\n"
        f"- 'Mesmo topico' mas ambos outliers (nao e match categorico real): **{n_same_but_outliers}**\n"
    )

    md.append("\n## MAP por topico (top 20 por N de consultas; ver mm_por_topico.csv para a lista completa)\n")
    md.append("| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |")
    md.append("|---|---|---|---|---|---|---|")
    topic_rows_sorted = sorted(per_topic.items(), key=lambda kv: -len(kv[1]))[:20]
    for topic_id, subset in topic_rows_sorted:
        b, a, cnt = agg(subset, "same_topic_ap")
        topic_map = map_by_topic.get(topic_id)
        fraco = "**sim**" if (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD) else "nao"
        md.append(f"| {topic_label(topic_id)} | {subset[0]['keywords']} | {cnt} | {fraco} | {b:.4f} | {a:.4f} | {a - b:+.4f} |")

    md_path = OUT_DIR / "mm_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
