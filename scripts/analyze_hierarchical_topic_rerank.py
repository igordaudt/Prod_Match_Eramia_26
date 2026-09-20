"""Reranking por DISTANCIA HIERARQUICA entre topicos (em vez do gate binario
mesmo-topico/topico-diferente usado em todos os testes anteriores).

Usa a arvore de clustering hierarquico ja construida em
'Topic Modeling/EDA_hierarchy/eda_hierarchy_merges.csv' -- BERTopic.
hierarchical_topics() (ward linkage, 1 - similaridade de cosseno sobre
c-TF-IDF dos 128 topicos-folha; MESMA config/corpus do item_topics.csv usado
a sessao inteira, concordancia de 100% confirmada em EDA_hierarchy_
resultados.md).

SO reranking por topico (nenhuma regex de atributo) -- por pedido explicito,
para isolar o efeito da hierarquia antes de combinar com match de valor.

Duas hipoteses testadas:
  H1: um item de topico "proximo" (baixa distancia hierarquica) ao topico da
      consulta deveria pontuar melhor que um de topico distante, mesmo sem
      ser o topico exato -- recuperando parte do sinal que o gate binario
      (so mesmo-topico) descarta.
  H2: hierarquia resolveria topicos outliers (-1).

Achado estrutural ANTES de rodar: o topico -1 NAO participa da arvore
hierarquica (confirmado em EDA_hierarchy_resultados.md: "-1 nao participa
dessa fusao"). Ou seja, nao existe distancia hierarquica definida entre -1 e
qualquer outro topico -- H2 e estruturalmente improvavel com este dado, mas
testamos mesmo assim para confirmar empiricamente (fatia especifica das
consultas com topico -1).

Duas variantes de pontuacao por distancia:
  - CONTINUA: ordena por distancia hierarquica ascendente (quanto mais perto
    na arvore, melhor -- distancia 0 = mesmo topico).
  - EM NIVEIS (3 niveis, usando o proprio threshold do EDA_hierarchy = 0.35,
    o corte que o EDA_hierarchy usou para definir 'topicos redundantes'):
    mesmo topico > topico a distancia <= 0.35 > resto.

topico -1 nunca participa de nenhum bonus (nem em si mesmo -- dois itens
"outliers" nao sao uma categoria real compartilhada, mesma convencao ja
usada nos testes anteriores).

Nao modifica scripts/retrieval_sinapi.py nem nenhum resultado anterior --
so leitura de Topic Modeling/EDA_hierarchy/eda_hierarchy_merges.csv e do
benchmark.

Uso:
    python scripts/analyze_hierarchical_topic_rerank.py

Saida (results/hierarchical_topic_rerank/):
    topic_distance_matrix.csv        Distancia hierarquica entre todos os pares de topicos-folha.
    hierarchical_rerank_per_query.csv  Baseline vs topico-flat vs hierarquico (continuo e em niveis), por consulta.
    hierarchical_rerank_resultados.md  Relatorio final, com foco nas duas hipoteses.
"""

from __future__ import annotations

import ast
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

OUT_DIR = PROJECT_ROOT / "results" / "hierarchical_topic_rerank"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
HIERARCHY_MERGES_TSV = PROJECT_ROOT.parent / "Topic Modeling" / "EDA_hierarchy" / "eda_hierarchy_merges.csv"
RRF_K = 60
PREFETCH_LIMIT = 100
NIVEL_THRESHOLD = 0.35  # mesmo threshold usado em EDA_hierarchy.py para "topicos redundantes"
INF = float("inf")


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


def load_hierarchy_nodes() -> list[dict]:
    """Le a arvore de merges (BERTopic.hierarchical_topics(), TSV apesar do .csv).
    Cada linha = 1 no interno, com o conjunto de topicos-folha (0..127) sob ele."""
    with HIERARCHY_MERGES_TSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    nodes = []
    for row in rows:
        topics = set(ast.literal_eval(row["Topics"]))
        nodes.append({"id": int(row["Parent_ID"]), "distance": float(row["Distance"]), "topics": topics})
    # menor conjunto primeiro = ancestral mais especifico (LCA) encontrado primeiro na busca
    nodes.sort(key=lambda n: len(n["topics"]))
    return nodes


def build_topic_distance_matrix(nodes: list[dict], leaf_topics: list[int]) -> dict[tuple[int, int], float]:
    dist: dict[tuple[int, int], float] = {}
    for i, a in enumerate(leaf_topics):
        dist[(a, a)] = 0.0
        for b in leaf_topics[i + 1:]:
            found = INF
            for node in nodes:
                if a in node["topics"] and b in node["topics"]:
                    found = node["distance"]
                    break
            dist[(a, b)] = found
            dist[(b, a)] = found
    return dist


def topic_distance(dist_matrix: dict[tuple[int, int], float], a: int | None, b: int | None,
                    undefined_value: float = INF) -> float:
    if a is None or b is None or a == -1 or b == -1:
        return undefined_value
    if a == b:
        return 0.0
    return dist_matrix.get((a, b), undefined_value)


def rerank_by_distance(ranked_items, item_topic, query_topic, dist_matrix, undefined_value=INF):
    def key(item: dict):
        item_id = coerce_item_id(item.get("item_id"))
        return topic_distance(dist_matrix, query_topic, item_topic.get(item_id), undefined_value)
    return sorted(ranked_items, key=key)  # ascendente: menor distancia primeiro


def rerank_by_level(ranked_items, item_topic, query_topic, dist_matrix, threshold):
    def key(item: dict) -> int:
        item_id = coerce_item_id(item.get("item_id"))
        d = topic_distance(dist_matrix, query_topic, item_topic.get(item_id))
        if d == 0.0:
            return 2  # mesmo topico
        if d <= threshold:
            return 1  # topico "vizinho" na hierarquia
        return 0  # resto
    return sorted(ranked_items, key=key, reverse=True)


def rerank_flat_topic_only(ranked_items, item_topic, query_topic):
    def score(item: dict) -> int:
        if query_topic is None or query_topic == -1:
            return 0
        item_id = coerce_item_id(item.get("item_id"))
        return 1 if item_topic.get(item_id) == query_topic else 0
    return sorted(ranked_items, key=score, reverse=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    nodes = load_hierarchy_nodes()
    all_topics_in_tree: set[int] = set()
    for node in nodes:
        all_topics_in_tree |= node["topics"]
    leaf_topics = sorted(all_topics_in_tree)
    print(f"Nos internos na arvore: {len(nodes)} | Topicos-folha cobertos: {len(leaf_topics)} "
          f"(min={min(leaf_topics)}, max={max(leaf_topics)})")

    dist_matrix = build_topic_distance_matrix(nodes, leaf_topics)
    with (OUT_DIR / "topic_distance_matrix.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["topic_a", "topic_b", "distancia"])
        for (a, b), d in sorted(dist_matrix.items()):
            if a <= b:
                writer.writerow([a, b, f"{d:.6f}"])
    print(f"Matriz de distancia entre topicos salva ({len(dist_matrix)} pares).")

    benchmark = load_benchmark(INPUT_JSON)
    codigo_to_topic = load_codigo_to_topic()
    topic_keywords, map_by_topic = load_topic_meta()
    print(f"Consultas no benchmark: {len(benchmark)}")

    rows = []
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        primary_item_id = min(relevant_ids) if relevant_ids else None
        query_topic = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)
        baseline_ranked = hybrid_rank(bm25_items, dense_items, DEFAULT_LIMIT)

        flat_ranked = rerank_flat_topic_only(baseline_ranked, codigo_to_topic, query_topic)
        continuous_ranked = rerank_by_distance(baseline_ranked, codigo_to_topic, query_topic, dist_matrix)
        level_ranked = rerank_by_level(baseline_ranked, codigo_to_topic, query_topic, dist_matrix, NIVEL_THRESHOLD)

        baseline_ap = average_precision(build_relevance_flags(baseline_ranked, relevant_ids), relevant_count)
        flat_ap = average_precision(build_relevance_flags(flat_ranked, relevant_ids), relevant_count)
        continuous_ap = average_precision(build_relevance_flags(continuous_ranked, relevant_ids), relevant_count)
        level_ap = average_precision(build_relevance_flags(level_ranked, relevant_ids), relevant_count)

        rows.append(
            {
                "product_id": product["product_id"],
                "topic": query_topic,
                "keywords": topic_keywords.get(query_topic, "") if query_topic is not None else "",
                "is_outlier": query_topic == -1,
                "baseline_ap": baseline_ap,
                "flat_topic_ap": flat_ap,
                "hierarchical_continuous_ap": continuous_ap,
                "hierarchical_level_ap": level_ap,
            }
        )
        if i % 100 == 0 or i == len(benchmark):
            print(f"[{i}/{len(benchmark)}] processado")

    with (OUT_DIR / "hierarchical_rerank_per_query.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["product_id", "topic", "keywords", "is_outlier", "baseline_ap", "flat_topic_ap",
                          "hierarchical_continuous_ap", "hierarchical_level_ap"])
        for r in rows:
            writer.writerow(
                [r["product_id"], r["topic"], r["keywords"], r["is_outlier"], f"{r['baseline_ap']:.6f}",
                 f"{r['flat_topic_ap']:.6f}", f"{r['hierarchical_continuous_ap']:.6f}", f"{r['hierarchical_level_ap']:.6f}"]
            )

    def agg(subset, key):
        if not subset:
            return 0.0
        return sum(r[key] for r in subset) / len(subset)

    all_rows = rows
    outlier_rows = [r for r in rows if r["is_outlier"]]
    non_outlier_rows = [r for r in rows if not r["is_outlier"]]

    print(f"\n=== TODAS AS {len(all_rows)} CONSULTAS ===")
    for label, subset in (("Geral", all_rows), ("So outliers (-1)", outlier_rows), ("Sem outliers", non_outlier_rows)):
        b = agg(subset, "baseline_ap")
        flat = agg(subset, "flat_topic_ap")
        cont = agg(subset, "hierarchical_continuous_ap")
        lvl = agg(subset, "hierarchical_level_ap")
        print(f"{label:20s} n={len(subset):4d}  baseline={b:.4f}  flat-topico={flat:.4f}  "
              f"hier-continuo={cont:.4f}  hier-niveis={lvl:.4f}")

    md = []
    md.append("# Reranking por distancia hierarquica de topico -- Resultados\n")
    md.append(
        "Usa a arvore de `Topic Modeling/EDA_hierarchy/eda_hierarchy_merges.csv` (BERTopic."
        "hierarchical_topics(), ward linkage sobre c-TF-IDF dos 128 topicos-folha -- mesma config/"
        "corpus do `item_topics.csv` usado a sessao inteira). SO reranking por topico, sem regex de "
        "atributo nenhuma.\n"
    )
    md.append(
        f"**Achado estrutural antes de rodar**: o topico -1 (outliers, {len(outlier_rows)} consultas "
        "no benchmark) NAO participa da arvore hierarquica -- confirmado em `EDA_hierarchy_"
        "resultados.md` ('-1 nao participa dessa fusao'). Ou seja, nao existe distancia hierarquica "
        "definida entre -1 e qualquer outro topico. **H2 (hierarquia resolveria outliers) e "
        "estruturalmente improvavel com este dado** -- testado mesmo assim abaixo, isolando a fatia "
        "de consultas com topico -1.\n"
    )
    md.append("## Duas variantes de pontuacao testadas\n")
    md.append(
        "- **Continua**: ordena os candidatos por distancia hierarquica ascendente ao topico da "
        "consulta (distancia 0 = mesmo topico; quanto mais perto na arvore, melhor).\n"
        f"- **Em niveis**: 3 niveis -- mesmo topico > topico a distancia <= {NIVEL_THRESHOLD} "
        "(o mesmo threshold que `EDA_hierarchy.py` usa para definir 'topicos redundantes') > resto.\n"
    )
    md.append("## Resultado principal (todas as 852 consultas)\n")
    md.append("| Politica | MAP | Delta vs. baseline |")
    md.append("|---|---|---|")
    md.append(f"| Baseline | {agg(all_rows,'baseline_ap'):.4f} | - |")
    md.append(f"| Flat topico (so mesmo/diferente, ja testado antes) | {agg(all_rows,'flat_topic_ap'):.4f} | {agg(all_rows,'flat_topic_ap')-agg(all_rows,'baseline_ap'):+.4f} |")
    md.append(f"| **Hierarquico continuo** | **{agg(all_rows,'hierarchical_continuous_ap'):.4f}** | **{agg(all_rows,'hierarchical_continuous_ap')-agg(all_rows,'baseline_ap'):+.4f}** |")
    md.append(f"| **Hierarquico em niveis (threshold {NIVEL_THRESHOLD})** | **{agg(all_rows,'hierarchical_level_ap'):.4f}** | **{agg(all_rows,'hierarchical_level_ap')-agg(all_rows,'baseline_ap'):+.4f}** |")

    md.append("\n## H1 -- topico hierarquicamente proximo ajuda?\n")
    md.append(
        f"Comparando hierarquico vs. flat nas {len(all_rows)} consultas: "
        f"delta continuo vs. flat = {agg(all_rows,'hierarchical_continuous_ap')-agg(all_rows,'flat_topic_ap'):+.4f}; "
        f"delta niveis vs. flat = {agg(all_rows,'hierarchical_level_ap')-agg(all_rows,'flat_topic_ap'):+.4f}.\n"
    )

    md.append("\n## H2 -- hierarquia resolve outliers (-1)?\n")
    md.append("| Segmento | N | Baseline | Flat topico | Hier. continuo | Hier. niveis |")
    md.append("|---|---|---|---|---|---|")
    for label, subset in (("So outliers (-1)", outlier_rows), ("Sem outliers", non_outlier_rows)):
        md.append(
            f"| {label} | {len(subset)} | {agg(subset,'baseline_ap'):.4f} | {agg(subset,'flat_topic_ap'):.4f} | "
            f"{agg(subset,'hierarchical_continuous_ap'):.4f} | {agg(subset,'hierarchical_level_ap'):.4f} |"
        )

    md_path = OUT_DIR / "hierarchical_rerank_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
