"""V5: fusao hibrida ADAPTATIVA por densidade numerica da query.

Contexto (ver eda/categ_map/topic_map_resultados.md): os topicos BERTopic com
MENOR MAP medio sao dominados por especificacoes tecnicas/atributos numericos
-- T101 ("kg, cabine, cv inclui, peso bruto, total, chassi"), T73 ("distancia,
kg, carroceria, eixos, cv inclui, peso bruto"), T59/T125 (amianto/fibrocimento
/manta termoplastica, "mm nbr"), T94 (fita aco/eletroduto, "diametro
nominal"), T2 (bloco/vedacao, "cm, mpa"), T21 (pead, "densidade, pn") -- cujas
keywords sao pouco discriminativas para o modelo denso (BGE-M3), que tende a
"borrar" atributos numericos em favor de similaridade semantica geral.

Hipotese: para consultas "atributo-pesadas" (alta densidade de tokens
numericos/unidades de medida), o BM25 (sparse, exato em tokens) e uma sinal
mais confiavel que o embedding denso. O V4 (retrieval_weighted_rrf_v4.py) ja
mostrou que um boost ESTATICO e global do peso esparso (esparso_3x) melhora o
MAP global (0,7932 -> 0,7981). Este script testa se detectar a query
"atributo-pesada" via regex e aplicar o boost apenas a ela (fusao adaptativa)
supera tanto o baseline quanto o boost estatico global -- sem penalizar as
consultas "normais" que nao precisam do reforco.

    is_atributo_pesada(query) = (nº tokens numericos/unidade) / (nº tokens) >= threshold
    score(d) = 1.0 / (k + rank_denso(d)) + w_esparso / (k + rank_bm25(d))
        onde w_esparso = boost se is_atributo_pesada(query) senao 1.0

Nao modifica scripts/retrieval_sinapi.py nem scripts/retrieval_weighted_rrf_v4.py
-- apenas importa (read-only) retrieve_bm25/retrieve_bge_m3_sinapi/load_benchmark
de retrieval_sinapi.py, replicando o padrao ja usado no V4.

Uso:
    python scripts/retrieval_adaptive_fusion_v5.py

Saida (results/real_295_v5_adaptive_fusion/):
    adaptive_fusion_grid.csv / .md   Grid threshold x boost, MAP e Recall@10.
    per_query_ap.csv                 AP por consulta: baseline vs melhor config adaptativa.
    map_by_worst_topic.csv / .md     MAP baseline vs melhor config nos 12 topicos de menor MAP.
    adaptive_fusion_resultados.md    Relatorio final.
"""

from __future__ import annotations

import csv
import re
import sys
import time
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
    retrieve_bge_m3_sinapi,
    retrieve_bm25,
)

OUT_DIR = PROJECT_ROOT / "results" / "real_295_v5_adaptive_fusion"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
RRF_K = 60
PREFETCH_LIMIT = 100

# 12 topicos de MENOR MAP em eda/categ_map/topic_map_resultados.md (>= 5 consultas).
WORST_TOPIC_IDS = [41, 61, 125, 70, 20, 101, 59, 94, 15, 73, 2, 21]

# --------------------------------------------------------------------------
# Deteccao "atributo-pesada" via regex: densidade de tokens numericos/unidade.
# --------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9]+(?:[.,/][0-9]+)*")
NUMERIC_RE = re.compile(r"\d")
UNIT_TOKENS = {
    "mm", "cm", "m", "km", "kg", "kgf", "kgm", "g", "t", "ton",
    "kv", "kva", "v", "va", "w", "kw", "hz", "a",
    "dan", "mpa", "pa", "psi", "bar", "atm",
    "pn", "dn", "cv", "hp", "rpm",
    "l", "litros", "lt", "ml", "m2", "m3",
    "pol", "polegada", "polegadas", "graus", "grau",
    "classe", "class", "serie",
}


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def numeric_attribute_density(query: str) -> float:
    """Fracao de tokens da query que contem digito ou sao unidade de medida conhecida."""
    tokens = _tokenize(query)
    if not tokens:
        return 0.0
    hits = sum(1 for tok in tokens if NUMERIC_RE.search(tok) or tok in UNIT_TOKENS)
    return hits / len(tokens)


def is_atributo_pesada(query: str, threshold: float) -> bool:
    return numeric_attribute_density(query) >= threshold


# --------------------------------------------------------------------------
# Fusao RRF ponderada (mesma formula do V4), com peso esparso adaptativo.
# --------------------------------------------------------------------------


def weighted_rrf_rank(
    bm25_items: list[dict],
    dense_items: list[dict],
    w_dense: float,
    w_sparse: float,
    limit: int,
) -> list[dict]:
    items_by_id: dict[int, dict] = {}
    scores: dict[int, float] = {}

    for ranked_items, weight in ((bm25_items, w_sparse), (dense_items, w_dense)):
        for rank, item in enumerate(ranked_items, start=1):
            item_id = coerce_item_id(item.get("item_id"))
            if item_id is None:
                continue
            items_by_id.setdefault(item_id, item)
            scores[item_id] = scores.get(item_id, 0.0) + weight / (RRF_K + rank)

    ranked_ids = sorted(scores, key=scores.get, reverse=True)[:limit]
    return [items_by_id[item_id] for item_id in ranked_ids]


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


def recall_at_k(flags: list[int], relevant_count: int, k: int) -> float:
    if relevant_count <= 0 or k <= 0:
        return 0.0
    return sum(flags[:k]) / relevant_count


# --------------------------------------------------------------------------
# Metadados de topico (para a analise "os piores topicos melhoraram?").
# --------------------------------------------------------------------------


def load_codigo_to_topic() -> dict[int, int]:
    mapping: dict[int, int] = {}
    if not ITEM_TOPICS_CSV.exists():
        return mapping
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
    if not TOPIC_MAP_CSV.exists():
        return keywords
    with TOPIC_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        for row in reader:
            topic_id = coerce_item_id(row.get("topic_id"))
            if topic_id is not None:
                keywords[topic_id] = row.get("keywords", "")
    return keywords


# Grid: thresholds de densidade numerica x fatores de boost do peso esparso.
# Faixa estendida em relacao a primeira rodada (0.20-0.40 / 1.5x-3.0x): o MAP
# ainda estava subindo nas duas bordas (boost=3x e threshold=0.20), entao o
# pico real nao tinha sido encontrado ainda.
THRESHOLDS = [0.0, 0.10, 0.15, 0.20, 0.30, 0.40]
BOOSTS = [1.5, 2.0, 3.0, 4.0, 5.0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    benchmark = load_benchmark(INPUT_JSON)
    print(f"Consultas carregadas de {INPUT_JSON}: {len(benchmark)}")

    codigo_to_topic = load_codigo_to_topic()
    topic_keywords = load_topic_keywords()

    config_names = ["baseline_1.0_1.0 (atual)"] + [
        f"adaptativo_thr{thr:.2f}_boost{boost:.1f}x" for thr in THRESHOLDS for boost in BOOSTS
    ]
    config_specs: dict[str, tuple[float | None, float]] = {"baseline_1.0_1.0 (atual)": (None, 1.0)}
    for thr in THRESHOLDS:
        for boost in BOOSTS:
            config_specs[f"adaptativo_thr{thr:.2f}_boost{boost:.1f}x"] = (thr, boost)

    per_config_aps: dict[str, list[float]] = {name: [] for name in config_names}
    per_config_recall10: dict[str, list[float]] = {name: [] for name in config_names}
    per_query_rows: list[dict] = []
    heavy_flags_by_threshold: dict[float, list[bool]] = {thr: [] for thr in THRESHOLDS}

    started = time.perf_counter()
    for i, product in enumerate(benchmark, start=1):
        search_terms = str(product["product_description"])
        relevant_ids = set(int(x) for x in product["relevant_item_ids"])
        relevant_count = len(relevant_ids)
        # Topico da consulta = topico do item relevante (nao do campo "codigo", que e
        # apenas o id da mutacao/produto original -- mesma convencao de
        # scripts/categ_map_analysis.py, que usa relevant_item_ids[0]).
        primary_item_id = min(relevant_ids) if relevant_ids else None
        topic_id = codigo_to_topic.get(primary_item_id) if primary_item_id is not None else None

        bm25_items = retrieve_bm25(search_terms, PREFETCH_LIMIT)
        dense_items = retrieve_bge_m3_sinapi(search_terms, PREFETCH_LIMIT)

        density = numeric_attribute_density(search_terms)
        for thr in THRESHOLDS:
            heavy_flags_by_threshold[thr].append(density >= thr)

        query_row = {
            "product_id": product["product_id"],
            "codigo": coerce_item_id(product.get("codigo")),
            "topic": topic_id,
            "numeric_density": round(density, 4),
        }
        for name in config_names:
            thr, boost = config_specs[name]
            w_sparse = boost if (thr is not None and density >= thr) else 1.0
            ranked = weighted_rrf_rank(bm25_items, dense_items, 1.0, w_sparse, DEFAULT_LIMIT)
            flags = build_relevance_flags(ranked, relevant_ids)
            ap = average_precision(flags, relevant_count)
            per_config_aps[name].append(ap)
            per_config_recall10[name].append(recall_at_k(flags, relevant_count, 10))
            query_row[name] = ap
        per_query_rows.append(query_row)

        if i % 100 == 0 or i == len(benchmark):
            elapsed = time.perf_counter() - started
            print(f"[{i}/{len(benchmark)}] {elapsed:.1f}s decorridos")

    # --- per_query_ap.csv ---
    per_query_csv = OUT_DIR / "per_query_ap.csv"
    with open(per_query_csv, "w", encoding="utf-8") as f:
        f.write("product_id;codigo;topic;numeric_density;" + ";".join(config_names) + "\n")
        for row in per_query_rows:
            f.write(
                f"{row['product_id']};{row['codigo']};{row['topic']};{row['numeric_density']};"
                + ";".join(f"{row[name]:.6f}" for name in config_names)
                + "\n"
            )
    print(f"AP por consulta salvo em: {per_query_csv}")

    # --- grid summary ---
    rows = []
    for name in config_names:
        thr, boost = config_specs[name]
        aps = per_config_aps[name]
        recalls = per_config_recall10[name]
        map_score = sum(aps) / len(aps)
        recall10 = sum(recalls) / len(recalls)
        pct_heavy = (
            100.0 * sum(heavy_flags_by_threshold[thr]) / len(heavy_flags_by_threshold[thr])
            if thr is not None
            else 0.0
        )
        rows.append(
            {
                "config": name,
                "threshold": thr,
                "boost": boost,
                "pct_atributo_pesada": pct_heavy,
                "MAP": map_score,
                "Recall@10": recall10,
                "n_consultas": len(aps),
            }
        )
        thr_str = f"{thr:.2f}" if thr is not None else "-"
        print(
            f"{name:38s} thr={thr_str} boost={boost:.1f}  pct_heavy={pct_heavy:5.1f}%  "
            f"MAP={map_score:.4f}  Recall@10={recall10:.4f}"
        )

    grid_csv = OUT_DIR / "adaptive_fusion_grid.csv"
    with open(grid_csv, "w", encoding="utf-8") as f:
        f.write("config;threshold;boost;pct_atributo_pesada;MAP;Recall@10;n_consultas\n")
        for row in rows:
            thr_val = f"{row['threshold']:.2f}" if row["threshold"] is not None else ""
            f.write(
                f"{row['config']};{thr_val};{row['boost']};{row['pct_atributo_pesada']:.2f};"
                f"{row['MAP']:.6f};{row['Recall@10']:.6f};{row['n_consultas']}\n"
            )
    print(f"\nGrid CSV salvo em: {grid_csv}")

    baseline_row = rows[0]
    baseline_map = baseline_row["MAP"]
    best_row = max(rows[1:], key=lambda row: row["MAP"])
    best_name = best_row["config"]

    grid_md_lines = [
        "# V5 -- Fusao hibrida adaptativa por densidade numerica da query\n",
        f"Conjunto real, {len(benchmark)} consultas, `limit={DEFAULT_LIMIT}`, `k={RRF_K}`.",
        "Score: `1.0 / (k + rank_BGE-M3) + w_esparso / (k + rank_BM25)`, onde "
        "`w_esparso = boost` se `densidade_numerica(query) >= threshold`, senao `1.0`.",
        f"Baseline (`w_esparso=1.0` sempre) e identico ao RRF hybrid publicado (MAP esperado ~0,7932).\n",
        "| Config | threshold | boost | % consultas atributo-pesadas | MAP | Delta MAP vs. baseline | Recall@10 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        delta = row["MAP"] - baseline_map
        thr_str = f"{row['threshold']:.2f}" if row["threshold"] is not None else "-"
        marker = " **<- melhor**" if row["config"] == best_name else ""
        grid_md_lines.append(
            f"| {row['config']}{marker} | {thr_str} | {row['boost']:.1f} | "
            f"{row['pct_atributo_pesada']:.1f}% | {row['MAP']:.4f} | {delta:+.4f} | {row['Recall@10']:.4f} |"
        )
    grid_md_path = OUT_DIR / "adaptive_fusion_grid.md"
    with open(grid_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(grid_md_lines) + "\n")
    print(f"Relatorio de grid salvo em: {grid_md_path}")

    # --- breakdown por topico (baseline vs melhor config adaptativa) ---
    best_thr, best_boost = config_specs[best_name]
    topic_rows: dict[int, dict] = {}
    for row in per_query_rows:
        topic_id = row["topic"]
        if topic_id is None:
            continue
        bucket = topic_rows.setdefault(
            topic_id, {"baseline_aps": [], "best_aps": []}
        )
        bucket["baseline_aps"].append(row["baseline_1.0_1.0 (atual)"])
        bucket["best_aps"].append(row[best_name])

    topic_csv = OUT_DIR / "map_by_worst_topic.csv"
    topic_md_lines = [
        "# V5 -- MAP por topico (12 piores da eda), baseline vs melhor fusao adaptativa\n",
        f"Melhor config do grid: `{best_name}` (threshold={best_thr}, boost={best_boost}).\n",
        "| Topico | Palavras-chave | N consultas | MAP baseline | MAP adaptativo | Delta |",
        "|---|---|---|---|---|---|",
    ]
    with open(topic_csv, "w", encoding="utf-8") as f:
        f.write("topic_id;keywords;n_consultas;map_baseline;map_adaptativo;delta\n")
        for topic_id in WORST_TOPIC_IDS:
            bucket = topic_rows.get(topic_id)
            keywords = topic_keywords.get(topic_id, "")
            if not bucket or not bucket["baseline_aps"]:
                f.write(f"{topic_id};{keywords};0;;;\n")
                topic_md_lines.append(f"| T{topic_id} | {keywords} | 0 | - | - | - |")
                continue
            n = len(bucket["baseline_aps"])
            map_baseline = sum(bucket["baseline_aps"]) / n
            map_best = sum(bucket["best_aps"]) / n
            delta = map_best - map_baseline
            f.write(f"{topic_id};{keywords};{n};{map_baseline:.6f};{map_best:.6f};{delta:+.6f}\n")
            topic_md_lines.append(
                f"| T{topic_id} | {keywords} | {n} | {map_baseline:.4f} | {map_best:.4f} | {delta:+.4f} |"
            )
    print(f"Breakdown por topico salvo em: {topic_csv}")

    topic_md_path = OUT_DIR / "map_by_worst_topic.md"
    with open(topic_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(topic_md_lines) + "\n")
    print(f"Relatorio por topico salvo em: {topic_md_path}")

    # --- relatorio final ---
    worst_n = sum(len(topic_rows.get(t, {}).get("baseline_aps", [])) for t in WORST_TOPIC_IDS)
    worst_baseline = (
        sum(sum(topic_rows.get(t, {}).get("baseline_aps", [])) for t in WORST_TOPIC_IDS) / worst_n
        if worst_n
        else 0.0
    )
    worst_best = (
        sum(sum(topic_rows.get(t, {}).get("best_aps", [])) for t in WORST_TOPIC_IDS) / worst_n
        if worst_n
        else 0.0
    )

    final_md = [
        "# V5 -- Fusao hibrida adaptativa por densidade numerica da query -- Resultados\n",
        "## Hipotese",
        "Os topicos BERTopic de menor MAP (T101, T73, T59, T125, T94, T2, T21, ...) sao "
        "dominados por atributos numericos/unidades de medida (kg, cm, mm, mpa, pn, ...), "
        "onde o BM25 (match exato de token) tende a superar o embedding denso (BGE-M3), que "
        "'borra' esses atributos em favor de similaridade semantica geral. O V4 "
        "(`retrieval_weighted_rrf_v4.py`) ja mostrou que um boost estatico global do peso "
        "esparso na fusao RRF melhora o MAP (0,7932 -> 0,7981 em `esparso_3x`). Este experimento "
        "testa uma fusao **adaptativa**: o boost so e aplicado quando a query e detectada, via "
        "regex de densidade numerica, como 'atributo-pesada'.\n",
        "## Metodo",
        "- Deteccao: `densidade_numerica(query) = (tokens com digito ou unidade conhecida) / (total de tokens)`.",
        "- Se `densidade_numerica >= threshold`: `w_esparso = boost` (senao `w_esparso = 1.0`); `w_denso = 1.0` sempre.",
        "- Fusao: RRF ponderado, `k=60`, mesma formula do V4.",
        f"- Grid: threshold em {THRESHOLDS}, boost em {BOOSTS} ({len(THRESHOLDS) * len(BOOSTS)} configs) + baseline.\n",
        "## Resultado principal",
        f"- Baseline (RRF 1.0/1.0): **MAP = {baseline_map:.4f}**",
        f"- Melhor config adaptativa: **{best_name}** -> **MAP = {best_row['MAP']:.4f}** "
        f"(delta {best_row['MAP'] - baseline_map:+.4f}, {best_row['pct_atributo_pesada']:.1f}% das consultas classificadas atributo-pesadas)",
        f"- Recall@10: baseline {baseline_row['Recall@10']:.4f} -> melhor config {best_row['Recall@10']:.4f}\n",
        "Ver `adaptive_fusion_grid.md` para o grid completo (comparar com "
        "`results/real_295_v4_rrf_weights/rrf_weights_resultados.md` para o boost estatico global).\n",
        "## Efeito nos 12 topicos de menor MAP (eda/categ_map/topic_map_resultados.md)",
        f"- MAP medio (baseline) nesses {worst_n} consultas: **{worst_baseline:.4f}**",
        f"- MAP medio (melhor config adaptativa): **{worst_best:.4f}** (delta {worst_best - worst_baseline:+.4f})",
        "",
        "Ver `map_by_worst_topic.md` para o detalhamento por topico.\n",
        "## Arquivos gerados",
        "- `adaptive_fusion_grid.csv` / `.md`: MAP e Recall@10 para cada combinacao threshold x boost.",
        "- `per_query_ap.csv`: AP por consulta em cada config, com densidade numerica e topico BERTopic.",
        "- `map_by_worst_topic.csv` / `.md`: MAP baseline vs melhor config, restrito aos 12 piores topicos.",
    ]
    final_md_path = OUT_DIR / "adaptive_fusion_resultados.md"
    with open(final_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(final_md) + "\n")
    print(f"\nRelatorio final salvo em: {final_md_path}")


if __name__ == "__main__":
    main()
