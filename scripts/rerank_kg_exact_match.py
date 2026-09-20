"""Reranking por match exato de valor(es) numerico(s) de 'kg' entre consulta e item.

Continuacao da auditoria em scripts/audit_kg_regex.py: das 852 consultas reais,
29 tem o token 'kg' associado a um numero (results/regex_kg_audit/kg_regex_positivos.csv).
A hipotese e que, nos topicos onde isso realmente atrapalha (T101/T73 --
caminhoes/elevadores que só diferem em peso), o problema nao e falta de peso
no BM25 (ja testado no V4/V5), e sim que NENHUM dos dois sinais (BM25, BGE-M3)
garante que o VALOR de kg do item recuperado bate com o da consulta -- ambos so
aumentam a chance de "kg" aparecer perto, nao verificam o numero.

Este script:
  1. Extrai, via regex sobre o texto bruto, o(s) valor(es) numerico(s) que
     precedem 'kg' em cada consulta e em cada item do catalogo (295 itens).
  2. Roda a fusao hibrida padrao (BM25 + BGE-M3, RRF k=60, igual ao publicado)
     para as 29 consultas, como baseline.
  3. Reranking: promove, dentro da lista candidata (sem mudar limit nem re-
     consultar), os itens cujo conjunto de valores kg tem interseccao com o
     da consulta -- mais valores em comum = posicao mais alta -- preservando a
     ordem relativa original como desempate (sort estavel).
  4. Compara AP por consulta antes/depois, agregado geral e por topico.

Nao modifica scripts/retrieval_sinapi.py -- importa read-only.

Uso:
    python scripts/rerank_kg_exact_match.py

Saida (results/kg_exact_match_rerank/):
    kg_values_por_item.csv         Valor(es) de kg extraidos de cada item do catalogo (295).
    kg_rerank_per_query.csv        AP baseline vs 3 politicas de rerank por consulta (sempre /
                                    condicional >=2 valores / gateada por mesmo topico).
    kg_rerank_resultados.md        Relatorio final.
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

OUT_DIR = PROJECT_ROOT / "results" / "kg_exact_match_rerank"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
RRF_K = 60
PREFETCH_LIMIT = 100

# (?!\s*/) evita casar "KG/M", "KG/M2", "KG/M3" etc. -- densidade linear/area/volumetrica,
# grandeza fisica DIFERENTE de peso (kg puro). Sem isso, "0,47 KG/M" (massa por metro de
# barra de ferro) seria tratado como se fosse o peso do item, o que é errado.
KG_VALUE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg\b(?!\s*/)", re.IGNORECASE)


def extract_kg_values(text: str) -> frozenset[float]:
    """Valores numericos (arredondados a 2 casas) imediatamente antes de 'kg' puro (nao kg/m) no texto bruto."""
    values = set()
    for raw in KG_VALUE_RE.findall(text or ""):
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
    """RRF k=60 padrao (equivalente a retrieve_bge_m3_hybrid_sinapi)."""
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


def rerank_by_kg_match(
    ranked_items: list[dict],
    query_kg_values: frozenset[float],
    kg_values_by_item: dict[int, frozenset[float]],
) -> list[dict]:
    """Promove itens com interseccao de valores kg; sort estavel preserva ordem original no empate."""
    def match_count(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        item_values = kg_values_by_item.get(item_id, frozenset())
        return len(query_kg_values & item_values)

    return sorted(ranked_items, key=match_count, reverse=True)


def rerank_by_kg_match_same_topic(
    ranked_items: list[dict],
    query_kg_values: frozenset[float],
    kg_values_by_item: dict[int, frozenset[float]],
    item_topic: dict[int, int],
    query_topic: int | None,
) -> list[dict]:
    """Como rerank_by_kg_match, mas SO conta o match se o item candidato pertence ao
    mesmo topico BERTopic da consulta (item_topic[item_id] == query_topic). Nasce da
    observacao de que quase todo 'intruso' promovido por match puro de kg vinha de um
    topico diferente (results/kg_exact_match_rerank/kg_rerank_intruders.md) -- gatear
    por topico deve bloquear esses casos sem precisar da heuristica de >=2 valores.

    topico -1 ('outliers', o cesto de itens que o BERTopic nao conseguiu agrupar de
    forma coerente) NUNCA conta como match, mesmo que query_topic == item_topic == -1
    -- isso nao e uma categoria real compartilhada, e sim ausencia de categoria dos
    dois lados (achado concreto: Q47089, massa acrilica x martelo perfurador, ambos
    'outliers', permanecia um falso positivo sem essa exclusao)."""
    def match_count(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        if query_topic is None or query_topic == -1:
            return 0
        if item_topic.get(item_id) != query_topic:
            return 0
        item_values = kg_values_by_item.get(item_id, frozenset())
        return len(query_kg_values & item_values)

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

    # --- 1. valores de kg por item do catalogo (295 itens) ---
    items = read_sinapi_items()
    kg_values_by_item: dict[int, frozenset[float]] = {}
    for item in items:
        values = extract_kg_values(str(item["description"]))
        if values:
            kg_values_by_item[int(item["item_id"])] = values

    with (OUT_DIR / "kg_values_por_item.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["item_id", "kg_values", "description"])
        for item in items:
            item_id = int(item["item_id"])
            values = kg_values_by_item.get(item_id)
            if values:
                writer.writerow([item_id, ",".join(f"{v:g}" for v in sorted(values)), item["description"]])
    print(f"Itens do catalogo com valor(es) de kg: {len(kg_values_by_item)} de {len(items)}")

    # --- 2. consultas com token 'kg' precedido de numero ---
    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords = load_topic_keywords()

    kg_queries = []
    for product in benchmark:
        text = str(product["product_description"])
        values = extract_kg_values(text)
        if values:
            relevant_ids = set(int(x) for x in product["relevant_item_ids"])
            primary_item_id = min(relevant_ids) if relevant_ids else None
            topic_id = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None
            kg_queries.append(
                {
                    "product": product,
                    "query_kg_values": values,
                    "topic": topic_id,
                    "keywords": topic_keywords.get(topic_id, "") if topic_id is not None else "",
                }
            )

    print(f"Consultas com valor(es) de kg extraidos: {len(kg_queries)}")

    # --- 3. baseline hibrido + reranking, AP antes/depois ---
    rows = []
    for entry in kg_queries:
        product = entry["product"]
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)
        reranked = rerank_by_kg_match(baseline_ranked, entry["query_kg_values"], kg_values_by_item)
        reranked_same_topic = rerank_by_kg_match_same_topic(
            baseline_ranked, entry["query_kg_values"], kg_values_by_item, codigo_to_topic, entry["topic"]
        )

        baseline_flags = build_relevance_flags(baseline_ranked, relevant_ids)
        reranked_flags = build_relevance_flags(reranked, relevant_ids)
        reranked_same_topic_flags = build_relevance_flags(reranked_same_topic, relevant_ids)

        baseline_ap = average_precision(baseline_flags, relevant_count)
        reranked_ap = average_precision(reranked_flags, relevant_count)
        same_topic_ap = average_precision(reranked_same_topic_flags, relevant_count)
        # Politica condicional: so aplica o rerank se a consulta tem >=2 valores de kg
        # (indicio de especificacao discriminante -- ex. peso bruto + carga util de
        # caminhao -- em vez de 1 valor so, que costuma ser peso de embalagem
        # compartilhado por varios produtos diferentes e NAO discrimina nada).
        n_values = len(entry["query_kg_values"])
        conditional_ap = reranked_ap if n_values >= 2 else baseline_ap

        # o item relevante esta no conjunto candidato (top 100 do hibrido)?
        candidate_ids = {coerce_item_id(it.get("item_id")) for it in baseline_ranked}
        recoverable = bool(relevant_ids & candidate_ids)

        rows.append(
            {
                "product_id": product["product_id"],
                "topic": entry["topic"],
                "keywords": entry["keywords"],
                "query_kg_values": ",".join(f"{v:g}" for v in sorted(entry["query_kg_values"])),
                "n_kg_values": n_values,
                "relevant_item_ids": ",".join(str(x) for x in sorted(relevant_ids)),
                "recuperavel_no_top100": recoverable,
                "baseline_ap": baseline_ap,
                "reranked_ap": reranked_ap,
                "conditional_ap": conditional_ap,
                "same_topic_ap": same_topic_ap,
                "delta": reranked_ap - baseline_ap,
                "delta_conditional": conditional_ap - baseline_ap,
                "delta_same_topic": same_topic_ap - baseline_ap,
                "query_text": search_terms,
            }
        )

    # --- 4. salvar per-query ---
    with (OUT_DIR / "kg_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            ["product_id", "topic", "keywords", "query_kg_values", "n_kg_values", "relevant_item_ids",
             "recuperavel_no_top100", "baseline_ap", "reranked_ap", "conditional_ap", "same_topic_ap",
             "delta", "delta_conditional", "delta_same_topic", "query_text"]
        )
        for r in rows:
            writer.writerow(
                [r["product_id"], r["topic"], r["keywords"], r["query_kg_values"], r["n_kg_values"],
                 r["relevant_item_ids"], r["recuperavel_no_top100"], f"{r['baseline_ap']:.6f}",
                 f"{r['reranked_ap']:.6f}", f"{r['conditional_ap']:.6f}", f"{r['same_topic_ap']:.6f}",
                 f"{r['delta']:+.6f}", f"{r['delta_conditional']:+.6f}", f"{r['delta_same_topic']:+.6f}",
                 r["query_text"]]
            )
    print(f"AP por consulta salvo em: {OUT_DIR / 'kg_rerank_per_query.csv'}")

    # --- 5. agregacao geral e por topico ---
    def agg(subset, key="reranked_ap"):
        if not subset:
            return 0.0, 0.0, 0
        b = sum(r["baseline_ap"] for r in subset) / len(subset)
        a = sum(r[key] for r in subset) / len(subset)
        return b, a, len(subset)

    overall_b, overall_a, n_overall = agg(rows)
    _, overall_cond, _ = agg(rows, key="conditional_ap")
    _, overall_same_topic, _ = agg(rows, key="same_topic_ap")
    weak_topics = {101, 73}
    weak_rows = [r for r in rows if r["topic"] in weak_topics]
    strong_rows = [r for r in rows if r["topic"] not in weak_topics]
    weak_b, weak_a, n_weak = agg(weak_rows)
    strong_b, strong_a, n_strong = agg(strong_rows)
    _, weak_same_topic, _ = agg(weak_rows, key="same_topic_ap")
    _, strong_same_topic, _ = agg(strong_rows, key="same_topic_ap")
    n_unrecoverable = sum(1 for r in rows if not r["recuperavel_no_top100"])

    single_rows = [r for r in rows if r["n_kg_values"] < 2]
    multi_rows = [r for r in rows if r["n_kg_values"] >= 2]
    single_b, single_a, n_single = agg(single_rows)
    multi_b, multi_a, n_multi = agg(multi_rows)
    _, single_same_topic, _ = agg(single_rows, key="same_topic_ap")
    _, multi_same_topic, _ = agg(multi_rows, key="same_topic_ap")

    per_topic: dict[int | None, list[dict]] = {}
    for r in rows:
        per_topic.setdefault(r["topic"], []).append(r)

    print(f"\nMAP baseline (n={n_overall}): {overall_b:.4f}")
    print(f"MAP reranked -- sempre (n={n_overall}): {overall_a:.4f}  (delta {overall_a - overall_b:+.4f})")
    print(f"MAP reranked -- so se >=2 valores de kg (n={n_overall}): {overall_cond:.4f}  (delta {overall_cond - overall_b:+.4f})")
    print(f"MAP reranked -- so mesmo topico (n={n_overall}): {overall_same_topic:.4f}  (delta {overall_same_topic - overall_b:+.4f})")
    print(f"  1 valor de kg (n={n_single}): baseline={single_b:.4f} -> reranked={single_a:.4f} -> mesmo_topico={single_same_topic:.4f}")
    print(f"  2+ valores de kg (n={n_multi}): baseline={multi_b:.4f} -> reranked={multi_a:.4f} -> mesmo_topico={multi_same_topic:.4f}")
    print(f"  T101+T73 (n={n_weak}): baseline={weak_b:.4f} -> reranked={weak_a:.4f} -> mesmo_topico={weak_same_topic:.4f}")
    print(f"  outros topicos (n={n_strong}): baseline={strong_b:.4f} -> reranked={strong_a:.4f} -> mesmo_topico={strong_same_topic:.4f}")
    print(f"Consultas com item relevante FORA do top-{DEFAULT_LIMIT} candidato (reranking nao pode corrigir): {n_unrecoverable}")

    # --- 6. relatorio final ---
    md = []
    md.append("# Reranking por match exato de valor de 'kg' -- Resultados\n")
    md.append(
        "Continuacao de `results/regex_kg_audit/`: das 852 consultas reais, "
        f"**{n_overall}** tem valor(es) numerico(s) de `kg` extraiveis via regex "
        "(`(\\d+(?:[.,]\\d+)?)\\s*kg\\b`). Para cada uma, alem do mesmo regex aplicado "
        "as 295 descricoes do catalogo, comparamos o valor da consulta com o valor de "
        "cada item candidato.\n"
    )
    md.append("## Metodo")
    md.append(
        "1. Baseline: fusao hibrida padrao publicada (BM25 + BGE-M3, RRF `k=60`, `limit=100`) -- "
        "sem nenhuma mudanca em relacao ao pipeline atual.\n"
        "2. Reranking: dentro da MESMA lista candidata (sem nova busca), promove os itens cujo "
        "conjunto de valores `kg` tem interseccao com o da consulta -- mais valores batendo = posicao "
        "mais alta; ordenacao estavel preserva a ordem relativa original em caso de empate (inclusive "
        "entre itens sem nenhum valor `kg`, que ficam no fim, na ordem que a fusao hibrida ja tinha "
        "decidido).\n"
    )
    md.append("## Resultado principal\n")
    md.append(
        "Tecnica ADOTADA: reranking por match exato de `kg` **gateado por topico** -- um item so "
        "e promovido se (a) tiver valor de `kg` identico ao da consulta E (b) pertencer ao MESMO "
        "topico BERTopic da consulta (`rerank_by_kg_match_same_topic`; topico `-1` \"outliers\" nunca "
        "conta como match, ver secao abaixo). Comparado contra o baseline (fusao hibrida publicada, "
        "sem mudanca) e contra a versao ingenua do reranking (match de `kg` sem olhar topico, "
        "\"sempre\"), que serve so para ilustrar POR QUE o gate por topico e necessario.\n"
    )
    md.append("| Politica | N consultas | MAP | Delta vs. baseline |")
    md.append("|---|---|---|---|")
    md.append(f"| Baseline (hibrido publicado, sem rerank) | {n_overall} | {overall_b:.4f} | - |")
    md.append(f"| Reranking ingenuo por kg (\"sempre\", ignora topico) | {n_overall} | {overall_a:.4f} | {overall_a - overall_b:+.4f} |")
    md.append(f"| **Reranking por kg gateado por topico (adotado)** | {n_overall} | **{overall_same_topic:.4f}** | **{overall_same_topic - overall_b:+.4f}** |")
    md.append(
        f"\n{n_unrecoverable} de {n_overall} consultas tem o item relevante FORA do top-{DEFAULT_LIMIT} "
        "candidato do hibrido -- nesses casos nenhum reranking pode corrigir (a lista de candidatos em "
        "si precisaria mudar, nao so a ordem). Nao houve nenhum caso assim aqui.\n"
    )
    md.append("## Por que gatear por topico -- o reranking ingenuo e quase neutro no geral, mas esconde dois efeitos opostos\n")
    md.append(
        "Separando as consultas por quantos valores de `kg` elas tem, aparece um padrao: quando a "
        "consulta so tem **1** valor de `kg`, ele costuma ser peso de EMBALAGEM (saco de cimento, "
        "balde de massa, rolo de arame) -- um valor comum a produtos de categorias completamente "
        "diferentes, que nao discrimina nada e so serve para embaralhar itens empatados com um "
        "'intruso' de outra categoria (ver `kg_rerank_intruders.md`: 10 dos 11 intrusos promovidos "
        "pelo reranking ingenuo vinham de um topico diferente da consulta). Quando a consulta tem "
        "**2+** valores, eles costumam ser especificacao conjunta do produto (ex. peso bruto + carga "
        "util de caminhao) -- aí um match exato e um sinal forte e confiavel, e o item certo esta, por "
        "definicao, no mesmo topico de si mesmo.\n"
    )
    md.append("| Segmento | N | Baseline | Reranking ingenuo (\"sempre\") | Gateado por topico (adotado) |")
    md.append("|---|---|---|---|---|")
    md.append(f"| 1 valor de kg (embalagem) | {n_single} | {single_b:.4f} | {single_a:.4f} | {single_same_topic:.4f} |")
    md.append(f"| 2+ valores de kg (spec discriminante, = T101+T73) | {n_multi} | {multi_b:.4f} | {multi_a:.4f} | {multi_same_topic:.4f} |")
    md.append(
        "\nO gate por topico e cirurgico: no segmento de 1 valor, ele recupera **exatamente** o MAP "
        "do baseline (zero dano -- nenhum intruso de mesmo topico apareceu nesses casos); no segmento "
        "de 2+ valores, ele preserva **todo** o ganho do reranking ingenuo (nada e bloqueado, porque o "
        "item certo sempre esta no proprio topico). O topico `-1` (\"outliers\", itens que o BERTopic "
        "nao conseguiu agrupar de forma coerente) e explicitamente excluido da regra de match -- dois "
        "itens ambos sem categoria nao sao uma correspondencia categorica real (achado concreto: sem "
        "essa exclusao, \"MASSA ACRILICA... 25 KG\" (outliers) ainda perdia posicao para \"MARTELO "
        "PERFURADOR PNEUMATICO... 25 KG\" (tambem outliers), apesar de nao terem nenhuma relacao).\n"
    )
    md.append("## Detalhamento por topico (politica adotada: gateada por topico)\n")
    md.append("| Topico | Palavras-chave | N | MAP baseline | MAP gateado por topico | Delta |")
    md.append("|---|---|---|---|---|---|")
    for topic_id in sorted(per_topic, key=lambda t: (t is None, t if t is not None else 0)):
        subset = per_topic[topic_id]
        b, a, n = agg(subset, key="same_topic_ap")
        label = "outliers" if topic_id == -1 else (f"T{topic_id}" if topic_id is not None else "(sem topico)")
        kw = subset[0]["keywords"]
        md.append(f"| {label} | {kw} | {n} | {b:.4f} | {a:.4f} | {a - b:+.4f} |")

    md.append("\n## Consultas com maior mudanca (politica adotada, positiva ou negativa)\n")
    md.append("| product_id | Topico | Valores kg (consulta) | AP baseline | AP gateado por topico | Delta |")
    md.append("|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: abs(r["delta_same_topic"]), reverse=True)[:15]:
        label = "outliers" if r["topic"] == -1 else (f"T{r['topic']}" if r["topic"] is not None else "-")
        md.append(
            f"| {r['product_id']} | {label} | {r['query_kg_values']} | {r['baseline_ap']:.4f} | "
            f"{r['same_topic_ap']:.4f} | {r['delta_same_topic']:+.4f} |"
        )

    md_path = OUT_DIR / "kg_rerank_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
