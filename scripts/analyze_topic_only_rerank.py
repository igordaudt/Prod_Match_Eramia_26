"""Ablation: e se a gente IGNORASSE todas as regexes de atributo e so
rerankeasse promovendo itens do MESMO topico BERTopic da consulta, sem checar
nenhum valor?

score(item) = 1 se topico(item) == topico(consulta) (e topico != -1/outliers) senao 0

Isso isola o efeito puro do "gate por topico" (a parte que se repetiu em
TODOS os testes desta sessao) do efeito do "match de valor especifico do
atributo" (a parte que mudava a cada regex testada). Se o topic-only
reranking ja capturar a maior parte do ganho, o valor incremental de
extrair/comparar o atributo especifico fica menor do que parecia.

Metodologia:
  1. Roda baseline (hibrido publicado) + reranking SO-POR-TOPICO para as 852
     consultas do benchmark, UMA VEZ (nao depende de regex nenhuma).
  2. Para cada teste de atributo ja feito nesta sessao (results/.../*_rerank_
     per_query.csv, que ja tem baseline_ap e same_topic_ap = MAP gateado por
     atributo+topico), localiza as MESMAS consultas (por product_id) e
     recorta o MAP so-por-topico dessas mesmas consultas -- comparacao direta,
     sem reduplicar retrieval (cada consulta so passa pelo hibrido uma vez
     nesta rodada, reaproveitado para todas as fatias por atributo).

Nao modifica scripts/retrieval_sinapi.py nem nenhum resultado anterior -- so
leitura dos CSVs ja gerados.

Uso:
    python scripts/analyze_topic_only_rerank.py

Saida (results/topic_only_rerank_baseline/):
    topic_only_per_query_852.csv   Baseline vs so-por-topico, todas as 852 consultas.
    topic_only_vs_atributo_resumo.csv/.md   Comparacao lado a lado por atributo ja testado.
"""

from __future__ import annotations

import csv
import sys
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
    retrieve_bge_m3_sinapi,
    retrieve_bm25,
)

OUT_DIR = PROJECT_ROOT / "results" / "topic_only_rerank_baseline"
RESULTS_DIR = PROJECT_ROOT / "results"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
RRF_K = 60
PREFETCH_LIMIT = 100


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


def rerank_by_topic_only(ranked_items, item_topic, query_topic):
    """Promove QUALQUER item do mesmo topico da consulta, sem checar valor de
    atributo nenhum. Sort estavel preserva a ordem original da fusao hibrida
    dentro de cada grupo (mesmo topico / topico diferente)."""
    def score(item: dict) -> int:
        if query_topic is None or query_topic == -1:
            return 0
        item_id = coerce_item_id(item.get("item_id"))
        return 1 if item_topic.get(item_id) == query_topic else 0

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


# (rotulo, caminho do CSV ja gerado, "gateado" = coluna same_topic_ap = MAP com match de atributo)
ATTRIBUTE_TESTS = [
    ("Peso (kg/g/mg/t)", "param3_regex_validation/kg_param3_rerank_per_query.csv"),
    ("Dimensional (mm/cm/m/pol, 6 regras)", "mm_regex_analysis/mm_rerank_per_query.csv"),
    ("Potencia mecanica (cv/hp)", "param3_regex_validation/power_param3_rerank_per_query.csv"),
    ("Diametro nominal (DN)", "param3_remaining_analysis/diametro_dn_rerank_per_query.csv"),
    ("Isolacao eletrica", "param3_remaining_analysis/isolacao_eletrica_rerank_per_query.csv"),
    ("Vias condutoras", "eletrico_analysis/vias_condutoras_rerank_per_query.csv"),
    ("Categoria de rede (CAT5...)", "eletrico_analysis/categoria_rede_rerank_per_query.csv"),
    ("Material base", "param3_remaining_analysis/material_base_rerank_per_query.csv"),
    ("Corrente eletrica", "eletrico_analysis/corrente_rerank_per_query.csv"),
    ("Resistencia estrutural (mpa)", "mecanico_hidraulico_analysis/resistencia_rerank_per_query.csv"),
    ("Pressao hidraulica", "mecanico_hidraulico_analysis/pressao_rerank_per_query.csv"),
    ("Norma NBR", "param3_remaining_analysis/normativo_nbr_rerank_per_query.csv"),
    ("Cor base", "param3_remaining_analysis/cor_base_rerank_per_query.csv"),
    ("Tensao (v/kv)", "eletrico_analysis/tensao_rerank_per_query.csv"),
    ("Potencia eletrica (w/kw/kva)", "eletrico_analysis/potencia_eletrica_rerank_per_query.csv"),
    ("Capacidade (litros)", "termico_hidraulico_capacidade_analysis/capacidade_litros_rerank_per_query.csv"),
    ("Comprimento/diametro em polegadas", "param3_remaining_analysis/comprimento_polegadas_rerank_per_query.csv"),
    ("Area (mm2/cm2/m2)", "param3_remaining_analysis/area_rerank_per_query.csv"),
    ("Volume (mm3/cm3/m3)", "param3_remaining_analysis/volume_rerank_per_query.csv"),
    ("Concentracao quimica (%)", "param3_remaining_analysis/concentracao_rerank_per_query.csv"),
    ("Bitola AWG/MCM", "param3_remaining_analysis/bitola_awg_rerank_per_query.csv"),
    ("Classe CA do aco", "param3_remaining_analysis/ca_aco_rerank_per_query.csv"),
    ("Classe (A-D)", "param3_remaining_analysis/classe_rerank_per_query.csv"),
    ("Embalagem (caixa/pct/kit com N)", "param3_remaining_analysis/embalagem_r1_rerank_per_query.csv"),
    ("Embalagem (N unidades/pecas)", "param3_remaining_analysis/embalagem_r2_rerank_per_query.csv"),
    ("Frequencia (hz)", "eletrico_analysis/frequencia_rerank_per_query.csv"),
    ("Bivolt", "eletrico_analysis/bivolt_rerank_per_query.csv"),
    ("Fases/polos", "eletrico_analysis/fases_polos_rerank_per_query.csv"),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords, map_by_topic = load_topic_meta()

    print(f"Consultas no benchmark: {len(benchmark)}")

    per_query: dict[int, dict] = {}
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        primary_item_id = min(relevant_ids) if relevant_ids else None
        query_topic = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)
        topic_only_ranked = rerank_by_topic_only(baseline_ranked, codigo_to_topic, query_topic)

        baseline_ap = average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        topic_only_ap = average_precision(build_relevance_flags(topic_only_ranked, relevant_ids), relevant_count)

        per_query[int(product["product_id"])] = {
            "product_id": product["product_id"],
            "topic": query_topic,
            "keywords": topic_keywords.get(query_topic, "") if query_topic is not None else "",
            "baseline_ap": baseline_ap,
            "topic_only_ap": topic_only_ap,
            "delta": topic_only_ap - baseline_ap,
        }

        if i % 100 == 0 or i == len(benchmark):
            print(f"[{i}/{len(benchmark)}] processado")

    with (OUT_DIR / "topic_only_per_query_852.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["product_id", "topic", "keywords", "baseline_ap", "topic_only_ap", "delta"])
        for row in per_query.values():
            writer.writerow(
                [row["product_id"], row["topic"], row["keywords"], f"{row['baseline_ap']:.6f}",
                 f"{row['topic_only_ap']:.6f}", f"{row['delta']:+.6f}"]
            )

    overall_baseline = sum(r["baseline_ap"] for r in per_query.values()) / len(per_query)
    overall_topic_only = sum(r["topic_only_ap"] for r in per_query.values()) / len(per_query)
    print(f"\n=== TODAS AS 852 CONSULTAS ===")
    print(f"MAP baseline: {overall_baseline:.4f}")
    print(f"MAP so-por-topico (sem regex nenhuma): {overall_topic_only:.4f} (delta {overall_topic_only - overall_baseline:+.4f})")

    # --- comparacao por atributo ja testado ---
    comparison_rows = []
    for label, rel_path in ATTRIBUTE_TESTS:
        csv_path = RESULTS_DIR / rel_path
        if not csv_path.exists():
            print(f"AVISO: {csv_path} nao encontrado, pulando '{label}'")
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            attr_rows = list(reader)
        if not attr_rows:
            continue

        product_ids = [int(r["product_id"]) for r in attr_rows]
        n = len(product_ids)
        attr_baseline = sum(float(r["baseline_ap"]) for r in attr_rows) / n
        attr_gated = sum(float(r["same_topic_ap"]) for r in attr_rows) / n
        topic_only_vals = [per_query[pid]["topic_only_ap"] for pid in product_ids if pid in per_query]
        topic_only_baseline_check = [per_query[pid]["baseline_ap"] for pid in product_ids if pid in per_query]
        n_found = len(topic_only_vals)
        topic_only_map = sum(topic_only_vals) / n_found if n_found else 0.0
        baseline_check = sum(topic_only_baseline_check) / n_found if n_found else 0.0

        winner = "atributo" if attr_gated > topic_only_map else ("topico-so" if topic_only_map > attr_gated else "empate")

        comparison_rows.append(
            {
                "label": label, "n": n, "n_found": n_found,
                "baseline": attr_baseline, "baseline_check": baseline_check,
                "attr_gated": attr_gated, "topic_only": topic_only_map,
                "delta_attr": attr_gated - attr_baseline, "delta_topic_only": topic_only_map - attr_baseline,
                "winner": winner,
            }
        )
        print(
            f"{label:38s} n={n:4d}  baseline={attr_baseline:.4f}  "
            f"attr+topico={attr_gated:.4f}  so-topico={topic_only_map:.4f}  vencedor={winner}"
        )

    with (OUT_DIR / "topic_only_vs_atributo_resumo.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["atributo", "n", "map_baseline", "map_attr_mais_topico", "map_so_topico",
                          "delta_attr_mais_topico", "delta_so_topico", "vencedor"])
        for r in comparison_rows:
            writer.writerow(
                [r["label"], r["n"], f"{r['baseline']:.6f}", f"{r['attr_gated']:.6f}", f"{r['topic_only']:.6f}",
                 f"{r['delta_attr']:+.6f}", f"{r['delta_topic_only']:+.6f}", r["winner"]]
            )

    n_attr_wins = sum(1 for r in comparison_rows if r["winner"] == "atributo")
    n_topic_wins = sum(1 for r in comparison_rows if r["winner"] == "topico-so")
    n_ties = sum(1 for r in comparison_rows if r["winner"] == "empate")

    md = []
    md.append("# Reranking so-por-topico (ignorando toda regex de atributo) -- Resultados\n")
    md.append(
        "Pergunta: e se, em vez de extrair e comparar o valor especifico de cada atributo (kg, mm, "
        "cv/hp, mpa...), a gente simplesmente promovesse qualquer item do MESMO topico BERTopic da "
        "consulta, sem checar valor nenhum? Isola o efeito do 'gate por topico' (repetido em todos os "
        "testes anteriores) do efeito do 'match de atributo especifico' (o que mudava a cada regex).\n"
    )
    md.append("## Resultado geral (todas as 852 consultas do benchmark)\n")
    md.append(f"- MAP baseline (hibrido publicado): **{overall_baseline:.4f}**")
    md.append(f"- MAP reranking so-por-topico (sem nenhuma regex de atributo): **{overall_topic_only:.4f}** "
               f"(delta {overall_topic_only - overall_baseline:+.4f})\n")
    md.append(
        "## Comparacao consulta a consulta: 'atributo + topico' (ja testado) vs. 'so topico' (esta analise)\n"
    )
    md.append(
        f"Resumo: em **{n_attr_wins}** dos {len(comparison_rows)} atributos, o match especifico do "
        f"atributo (combinado com o gate) superou o reranking so-por-topico; em **{n_topic_wins}**, o "
        f"reranking so-por-topico foi igual ou melhor; **{n_ties}** empates exatos.\n"
    )
    md.append(
        "| Atributo | N | MAP baseline | MAP atributo+topico | MAP so-topico | Delta atributo+topico | Delta so-topico | Vencedor |"
    )
    md.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(comparison_rows, key=lambda r: r["delta_attr"] - r["delta_topic_only"], reverse=True):
        marker = "**atributo**" if r["winner"] == "atributo" else ("**só-tópico**" if r["winner"] == "topico-so" else "empate")
        md.append(
            f"| {r['label']} | {r['n']} | {r['baseline']:.4f} | {r['attr_gated']:.4f} | {r['topic_only']:.4f} | "
            f"{r['delta_attr']:+.4f} | {r['delta_topic_only']:+.4f} | {marker} |"
        )

    md_path = OUT_DIR / "topic_only_vs_atributo_resumo.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
