"""Auditoria dos tokens de unidade de potencia 'cv' (cavalo-vapor) e 'hp'
(horsepower) -- mesma metodologia de scripts/audit_kg_regex.py, aplicada a
'cv'/'hp' em vez de 'kg'.

Escopo: as 852 consultas reais do benchmark
(data/ground_truth/retrieval-benchmark-295.json), cruzadas com:
  - o topico BERTopic de cada consulta (herdado do item relevante, via
    eda/item_topics.csv);
  - o MAP medio do topico (eda/categ_map/topic_map_results.csv), para
    distinguir 'cv'/'hp' disparando em topico que precisa de ajuda (MAP
    baixo) de topico que ja vai bem (MAP alto).

Nao depende de sentence-transformers/qdrant -- roda com Python padrao.

Uso:
    python scripts/audit_power_regex.py

Saida (results/power_cv_hp_analysis/):
    power_regex_positivos.csv                    Toda consulta com token 'cv'/'hp', com topico/MAP/classificacao.
    power_regex_por_topico.csv                    Contagem de acertos por topico, com MAP do topico.
    power_regex_falsos_negativos_colado.csv       'NNNcv'/'NNNhp' colado sem espaco (tokenizer funde em 1 token).
    power_regex_falsos_negativos_potencia_sem_unidade.csv  Consultas com 'potencia' mas sem token 'cv'/'hp'.
    power_regex_unidades_vizinhas.csv             Unidades de potencia correlatas (kw, w, hz -- fora do escopo).
    power_regex_resultados.md                     Relatorio final.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_JSON = PROJECT_ROOT / "data" / "ground_truth" / "retrieval-benchmark-295.json"
ITEM_TOPICS_CSV = PROJECT_ROOT / "eda" / "item_topics.csv"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
OUT_DIR = PROJECT_ROOT / "results" / "power_cv_hp_analysis"

TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9]+(?:[.,/][0-9]+)*")
NUMERIC_RE = re.compile(r"\d")

POWER_WORD_RE = re.compile(r"\bpot[eê]ncia\b", re.IGNORECASE)
NOSPACE_POWER_RE = re.compile(r"\d(?:cv|hp)\b", re.IGNORECASE)
OTHER_POWER_RE = re.compile(r"\b(kw|watts?|w|hz|rpm)\b", re.IGNORECASE)

WEAK_TOPIC_MAP_THRESHOLD = 0.60


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def load_query_texts() -> dict[int, str]:
    with BENCHMARK_JSON.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    texts: dict[int, str] = {}
    for entry in payload["items"]:
        for mut in entry.get("mutations", []):
            mut_id = mut.get("mut_ID")
            desc = mut.get("descricao_mutada")
            if mut_id is None or not desc:
                continue
            texts[int(mut_id)] = desc.strip()
    return texts


def load_query_relevant_and_topic() -> tuple[dict[int, set[int]], dict[int, int | None]]:
    """Topico da consulta = topico do item relevante (min dos relevant_item_ids),
    igual convencao usada em scripts/rerank_kg_exact_match.py."""
    codigo_to_topic: dict[int, int] = {}
    with ITEM_TOPICS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            codigo = row.get("codigo_295")
            topic = row.get("topic")
            if codigo and topic not in (None, ""):
                try:
                    codigo_to_topic[int(float(codigo))] = int(topic)
                except ValueError:
                    continue

    with BENCHMARK_JSON.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)

    relevant_by_id: dict[int, set[int]] = {}
    topic_by_id: dict[int, int | None] = {}
    for entry in payload["items"]:
        for mut in entry.get("mutations", []):
            mut_id = mut.get("mut_ID")
            if mut_id is None:
                continue
            rel_ids = {int(x) for x in (mut.get("relevant_item_ids") or []) if str(x).strip()}
            relevant_by_id[int(mut_id)] = rel_ids
            primary = min(rel_ids) if rel_ids else None
            topic_by_id[int(mut_id)] = codigo_to_topic.get(primary) if primary is not None else None
    return relevant_by_id, topic_by_id


def load_topic_meta() -> tuple[dict[int, str], dict[int, float]]:
    keywords: dict[int, str] = {}
    map_medio: dict[int, float] = {}
    with TOPIC_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            topic_id = int(row["topic_id"])
            keywords[topic_id] = row["keywords"]
            map_medio[topic_id] = float(row["map_medio"])
    return keywords, map_medio


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    query_text_by_id = load_query_texts()
    _, topic_by_id = load_query_relevant_and_topic()
    keywords_by_topic, map_by_topic = load_topic_meta()

    print(f"Consultas carregadas do benchmark: {len(query_text_by_id)}")

    power_hits: list[dict] = []
    no_space_near_misses: list[dict] = []
    power_without_unit: list[dict] = []
    other_power_units: list[dict] = []

    for qid, text in query_text_by_id.items():
        tokens = tokenize(text)
        topic = topic_by_id.get(qid)

        has_unit_token = ("cv" in tokens) or ("hp" in tokens)
        if has_unit_token:
            contexts = []
            for i, tok in enumerate(tokens):
                if tok in ("cv", "hp"):
                    prev_tok = tokens[i - 1] if i > 0 else None
                    prev_is_number = bool(prev_tok and NUMERIC_RE.search(prev_tok))
                    contexts.append({"unit": tok, "prev_is_number": prev_is_number})
            topic_map = map_by_topic.get(topic) if topic is not None else None
            power_hits.append(
                {
                    "query_id": qid,
                    "topic": topic,
                    "keywords": keywords_by_topic.get(topic, "") if topic is not None else "",
                    "topic_map": topic_map,
                    "query_text": text,
                    "n_ocorrencias": len(contexts),
                    "unidades": sorted(set(c["unit"] for c in contexts)),
                    "todas_precedidas_por_numero": all(c["prev_is_number"] for c in contexts),
                    "topico_fraco": (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD),
                }
            )

        if not has_unit_token and NOSPACE_POWER_RE.search(text):
            no_space_near_misses.append({"query_id": qid, "topic": topic, "query_text": text})

        if not has_unit_token and POWER_WORD_RE.search(text):
            power_without_unit.append({"query_id": qid, "topic": topic, "query_text": text})

        om = OTHER_POWER_RE.findall(text)
        if om and not has_unit_token:
            other_power_units.append(
                {"query_id": qid, "topic": topic, "unidades": sorted(set(u.lower() for u in om)), "query_text": text}
            )

    true_positives = [h for h in power_hits if h["todas_precedidas_por_numero"]]
    false_positives = [h for h in power_hits if not h["todas_precedidas_por_numero"]]
    useful_hits = [h for h in power_hits if h["topico_fraco"]]
    non_useful_hits = [h for h in power_hits if not h["topico_fraco"]]

    print(f"Consultas com token 'cv'/'hp': {len(power_hits)}")
    print(f"  -> TP (precedido de numero): {len(true_positives)}")
    print(f"  -> FP (solto, sem numero antes): {len(false_positives)}")
    print(f"  -> em topico fraco (MAP < {WEAK_TOPIC_MAP_THRESHOLD}): {len(useful_hits)}")
    print(f"  -> em topico ja forte (MAP >= {WEAK_TOPIC_MAP_THRESHOLD}): {len(non_useful_hits)}")
    print(f"Falsos-negativos candidatos (colado sem espaco): {len(no_space_near_misses)}")
    print(f"Falsos-negativos candidatos ('potencia' sem token cv/hp): {len(power_without_unit)}")
    print(f"Unidades de potencia vizinhas (kw/w/hz/rpm): {len(other_power_units)}")

    topic_counts = Counter(h["topic"] for h in power_hits)

    with (OUT_DIR / "power_regex_positivos.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            ["query_id", "topic", "topic_map", "keywords", "unidades", "n_ocorrencias",
             "classificacao_token", "topico_fraco_precisa_ajuda", "query_text"]
        )
        for h in power_hits:
            classe = "TP (precedido de numero)" if h["todas_precedidas_por_numero"] else "FP (solto)"
            topic_map_str = f"{h['topic_map']:.4f}" if h["topic_map"] is not None else ""
            writer.writerow(
                [h["query_id"], h["topic"], topic_map_str, h["keywords"], ",".join(h["unidades"]),
                 h["n_ocorrencias"], classe, "sim" if h["topico_fraco"] else "nao", h["query_text"]]
            )

    with (OUT_DIR / "power_regex_por_topico.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["topic_id", "keywords", "map_medio_topico", "n_hits", "fraco_precisa_ajuda"])
        for topic_id in sorted(topic_counts, key=lambda t: (t is None, t if t is not None else 0)):
            topic_map = map_by_topic.get(topic_id) if topic_id is not None else None
            writer.writerow(
                [
                    topic_id,
                    keywords_by_topic.get(topic_id, "") if topic_id is not None else "(sem topico)",
                    f"{topic_map:.4f}" if topic_map is not None else "",
                    topic_counts[topic_id],
                    "sim" if (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD) else "nao",
                ]
            )

    with (OUT_DIR / "power_regex_falsos_negativos_colado.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["query_id", "topic", "query_text"])
        for h in no_space_near_misses:
            writer.writerow([h["query_id"], h["topic"], h["query_text"]])

    with (OUT_DIR / "power_regex_falsos_negativos_potencia_sem_unidade.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["query_id", "topic", "query_text"])
        for h in power_without_unit:
            writer.writerow([h["query_id"], h["topic"], h["query_text"]])

    with (OUT_DIR / "power_regex_unidades_vizinhas.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["query_id", "topic", "unidades", "query_text"])
        for h in other_power_units:
            writer.writerow([h["query_id"], h["topic"], ",".join(h["unidades"]), h["query_text"]])

    md = []
    md.append("# Auditoria dos tokens 'cv'/'hp' (potencia) -- Resultados\n")
    md.append(
        f"Escopo: as {len(query_text_by_id)} consultas reais do benchmark, tokenizadas com a mesma "
        "regex de `scripts/retrieval_adaptive_fusion_v5.py` (`TOKEN_RE`), procurando os tokens isolados "
        "`cv` (cavalo-vapor) e `hp` (horsepower) -- mesma metodologia de `scripts/audit_kg_regex.py`.\n"
    )
    md.append("## Positivos (token 'cv'/'hp' disparado)")
    md.append(f"- Total de consultas com token `cv` ou `hp`: **{len(power_hits)}** de {len(query_text_by_id)} ({100*len(power_hits)/len(query_text_by_id):.1f}%)")
    md.append(
        f"- **Verdadeiro positivo a nivel de token** (sempre precedido de numero, ex. \"326 CV\"): "
        f"**{len(true_positives)}/{len(power_hits)}**"
    )
    md.append(f"- **Falso positivo a nivel de token** (solto, sem numero antes): **{len(false_positives)}/{len(power_hits)}**")
    md.append("")
    md.append(
        f"- **Util para o objetivo da tecnica** (dispara num topico com MAP < {WEAK_TOPIC_MAP_THRESHOLD}): "
        f"**{len(useful_hits)}/{len(power_hits)}** ({100*len(useful_hits)/max(len(power_hits),1):.1f}%)"
    )
    md.append(
        f"- **\"Falso positivo de utilidade\"** (match real, mas topico ja com MAP >= {WEAK_TOPIC_MAP_THRESHOLD}): "
        f"**{len(non_useful_hits)}/{len(power_hits)}** ({100*len(non_useful_hits)/max(len(power_hits),1):.1f}%)\n"
    )

    md.append("## Distribuicao por topico\n")
    md.append("| Topico | Palavras-chave | MAP do topico | N hits | Topico fraco (precisa ajuda)? |")
    md.append("|---|---|---|---|---|")
    for topic_id in sorted(topic_counts, key=lambda t: (t is None, t if t is not None else 0)):
        topic_map = map_by_topic.get(topic_id) if topic_id is not None else None
        label = "outliers" if topic_id == -1 else (f"T{topic_id}" if topic_id is not None else "(sem topico)")
        fraco = "**SIM**" if (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD) else "nao"
        map_str = f"{topic_map:.4f}" if topic_map is not None else "-"
        kw = keywords_by_topic.get(topic_id, "") if topic_id is not None else ""
        md.append(f"| {label} | {kw} | {map_str} | {topic_counts[topic_id]} | {fraco} |")

    md.append("\n## Falsos negativos\n")
    md.append(
        f"1. **Colado ao numero, sem espaco** (ex. `20cv`, `160hp`): **{len(no_space_near_misses)}** caso(s)."
    )
    for h in no_space_near_misses:
        md.append(f"   - Q{h['query_id']} (T{h['topic']}): \"{h['query_text']}\"")
    md.append(f"2. **Menciona 'potencia' mas usa outra unidade** (kw, w, etc.): **{len(power_without_unit)}** caso(s).")
    for h in power_without_unit:
        md.append(f"   - Q{h['query_id']} (T{h['topic']}): \"{h['query_text']}\"")
    md.append(f"3. **Unidades de potencia/eletricas vizinhas** (`kw`, `w`, `hz`, `rpm`): **{len(other_power_units)}** caso(s).")
    for h in other_power_units:
        md.append(f"   - Q{h['query_id']} (T{h['topic']}), unidades={h['unidades']}: \"{h['query_text']}\"")

    md.append("\n## Conclusao")
    md.append(
        f"- Os tokens `cv`/`hp`, isoladamente, tem **{len(false_positives)} falsos positivos de "
        f"tokenizacao** em {len(power_hits)} ocorrencias.\n"
        f"- **{len(useful_hits)} das {len(power_hits)}** ocorrencias caem em topicos que de fato "
        "precisam de ajuda (MAP baixo).\n"
        "- Falsos negativos por concatenacao sem espaco e por uso de unidade alternativa (kw) seguem o "
        "mesmo padrao observado para `kg`."
    )

    md_path = OUT_DIR / "power_regex_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")
    print(f"CSVs salvos em: {OUT_DIR}")


if __name__ == "__main__":
    main()
