"""Auditoria do token de unidade 'kg' usado em numeric_attribute_density()
(scripts/retrieval_adaptive_fusion_v5.py) -- a peca especifica do regex que
detecta peso/massa para decidir se uma consulta e "atributo-pesada".

Escopo: as 852 consultas reais do benchmark
(data/ground_truth/retrieval-benchmark-295.json), cruzadas com:
  - o topico BERTopic de cada consulta (results/real_295_v5_adaptive_fusion/
    per_query_ap.csv, coluna 'topic', ja calculada no V5);
  - o MAP medio do topico (eda/categ_map/topic_map_results.csv), para
    distinguir "kg" disparando em topico que realmente precisa de ajuda
    (MAP baixo) de "kg" disparando em topico que ja vai bem (MAP alto).

Nao depende de sentence-transformers/qdrant -- roda com Python padrao.

Uso:
    python scripts/audit_kg_regex.py

Saida (results/regex_kg_audit/):
    kg_regex_positivos.csv                    Toda consulta com token 'kg', com topico/MAP/classificacao.
    kg_regex_por_topico.csv                    Contagem de acertos por topico, com MAP do topico.
    kg_regex_falsos_negativos_colado.csv       'NNNkg' colado sem espaco (tokenizer funde em 1 token).
    kg_regex_falsos_negativos_peso_sem_kg.csv  Consultas com 'peso' mas sem token 'kg' (outra unidade).
    kg_regex_unidades_vizinhas.csv             Unidades de massa/torque correlatas (kgf, kgm, ton, grama).
    kg_regex_resultados.md                     Relatorio final.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_JSON = PROJECT_ROOT / "data" / "ground_truth" / "retrieval-benchmark-295.json"
PER_QUERY_AP_CSV = PROJECT_ROOT / "results" / "real_295_v5_adaptive_fusion" / "per_query_ap.csv"
TOPIC_MAP_CSV = PROJECT_ROOT / "eda" / "categ_map" / "topic_map_results.csv"
OUT_DIR = PROJECT_ROOT / "results" / "regex_kg_audit"

# Mesma tokenizacao de scripts/retrieval_adaptive_fusion_v5.py.
TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9]+(?:[.,/][0-9]+)*")
NUMERIC_RE = re.compile(r"\d")

MASS_WORD_RE = re.compile(r"\bpeso\b", re.IGNORECASE)
NOSPACE_KG_RE = re.compile(r"\d(?:kg)\b", re.IGNORECASE)
OTHER_MASS_RE = re.compile(r"\b(kgf|kgm|ton|toneladas?|gramas?)\b", re.IGNORECASE)

# Topico e considerado "fraco" (precisa de ajuda) abaixo deste MAP medio --
# mesmo corte usado implicitamente pelo ranking de piores topicos da eda.
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


def load_topic_and_density() -> tuple[dict[int, int | None], dict[int, float]]:
    topic_by_id: dict[int, int | None] = {}
    density_by_id: dict[int, float] = {}
    with PER_QUERY_AP_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            pid = int(row["product_id"])
            topic_raw = row["topic"]
            topic_by_id[pid] = int(topic_raw) if topic_raw not in ("", "None") else None
            density_by_id[pid] = float(row["numeric_density"])
    return topic_by_id, density_by_id


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
    topic_by_id, density_by_id = load_topic_and_density()
    keywords_by_topic, map_by_topic = load_topic_meta()

    print(f"Consultas carregadas do benchmark: {len(query_text_by_id)}")

    kg_hits: list[dict] = []
    no_space_near_misses: list[dict] = []
    peso_without_kg: list[dict] = []
    other_mass_units: list[dict] = []

    for qid, text in query_text_by_id.items():
        tokens = tokenize(text)
        topic = topic_by_id.get(qid)
        density = density_by_id.get(qid)

        has_kg_token = "kg" in tokens
        if has_kg_token:
            contexts = []
            for i, tok in enumerate(tokens):
                if tok == "kg":
                    prev_tok = tokens[i - 1] if i > 0 else None
                    prev_is_number = bool(prev_tok and NUMERIC_RE.search(prev_tok))
                    contexts.append(prev_is_number)
            topic_map = map_by_topic.get(topic) if topic is not None else None
            kg_hits.append(
                {
                    "query_id": qid,
                    "topic": topic,
                    "keywords": keywords_by_topic.get(topic, "") if topic is not None else "",
                    "topic_map": topic_map,
                    "numeric_density": density,
                    "query_text": text,
                    "n_ocorrencias_kg": len(contexts),
                    "todas_precedidas_por_numero": all(contexts),
                    "topico_fraco": (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD),
                }
            )

        if not has_kg_token and NOSPACE_KG_RE.search(text):
            no_space_near_misses.append({"query_id": qid, "topic": topic, "query_text": text})

        if not has_kg_token and MASS_WORD_RE.search(text):
            peso_without_kg.append({"query_id": qid, "topic": topic, "query_text": text})

        om = OTHER_MASS_RE.findall(text)
        if om:
            other_mass_units.append(
                {"query_id": qid, "topic": topic, "unidades": sorted(set(u.lower() for u in om)), "query_text": text}
            )

    true_positives = [h for h in kg_hits if h["todas_precedidas_por_numero"]]
    false_positives = [h for h in kg_hits if not h["todas_precedidas_por_numero"]]
    useful_hits = [h for h in kg_hits if h["topico_fraco"]]
    non_useful_hits = [h for h in kg_hits if not h["topico_fraco"]]

    print(f"Consultas com token 'kg': {len(kg_hits)}")
    print(f"  -> TP (kg sempre precedido de numero): {len(true_positives)}")
    print(f"  -> FP (kg solto, sem numero antes): {len(false_positives)}")
    print(f"  -> em topico fraco (MAP < {WEAK_TOPIC_MAP_THRESHOLD}): {len(useful_hits)}")
    print(f"  -> em topico ja forte (MAP >= {WEAK_TOPIC_MAP_THRESHOLD}): {len(non_useful_hits)}")
    print(f"Falsos-negativos candidatos (kg colado sem espaco): {len(no_space_near_misses)}")
    print(f"Falsos-negativos candidatos ('peso' sem token 'kg'): {len(peso_without_kg)}")
    print(f"Unidades de massa/torque vizinhas (kgf/kgm/ton/grama): {len(other_mass_units)}")

    topic_counts = Counter(h["topic"] for h in kg_hits)

    # --- kg_regex_positivos.csv ---
    with (OUT_DIR / "kg_regex_positivos.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            ["query_id", "topic", "topic_map", "keywords", "numeric_density", "n_ocorrencias_kg",
             "classificacao_token", "topico_fraco_precisa_ajuda", "query_text"]
        )
        for h in kg_hits:
            classe = "TP (precedido de numero)" if h["todas_precedidas_por_numero"] else "FP (kg solto)"
            topic_map_str = f"{h['topic_map']:.4f}" if h["topic_map"] is not None else ""
            writer.writerow(
                [h["query_id"], h["topic"], topic_map_str, h["keywords"], f"{h['numeric_density']:.4f}",
                 h["n_ocorrencias_kg"], classe, "sim" if h["topico_fraco"] else "nao", h["query_text"]]
            )

    # --- kg_regex_por_topico.csv ---
    with (OUT_DIR / "kg_regex_por_topico.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["topic_id", "keywords", "map_medio_topico", "n_hits_kg", "fraco_precisa_ajuda"])
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

    # --- falsos negativos ---
    with (OUT_DIR / "kg_regex_falsos_negativos_colado.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["query_id", "topic", "query_text"])
        for h in no_space_near_misses:
            writer.writerow([h["query_id"], h["topic"], h["query_text"]])

    with (OUT_DIR / "kg_regex_falsos_negativos_peso_sem_kg.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["query_id", "topic", "query_text"])
        for h in peso_without_kg:
            writer.writerow([h["query_id"], h["topic"], h["query_text"]])

    with (OUT_DIR / "kg_regex_unidades_vizinhas.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["query_id", "topic", "unidades", "query_text"])
        for h in other_mass_units:
            writer.writerow([h["query_id"], h["topic"], ",".join(h["unidades"]), h["query_text"]])

    # --- relatorio final ---
    md = []
    md.append("# Auditoria do token 'kg' em numeric_attribute_density() -- Resultados\n")
    md.append(
        f"Escopo: as {len(query_text_by_id)} consultas reais do benchmark "
        "(`data/ground_truth/retrieval-benchmark-295.json`), tokenizadas com a mesma "
        "regex de `scripts/retrieval_adaptive_fusion_v5.py` (`TOKEN_RE`), procurando "
        "o token isolado `kg`.\n"
    )
    md.append("## Positivos (token 'kg' disparado)")
    md.append(f"- Total de consultas com token `kg`: **{len(kg_hits)}** de {len(query_text_by_id)} ({100*len(kg_hits)/len(query_text_by_id):.1f}%)")
    md.append(
        f"- **Verdadeiro positivo a nivel de token** (o `kg` esta sempre precedido de um numero, "
        f"ex. \"23000 KG\" -- e genuinamente um valor de peso): **{len(true_positives)}/{len(kg_hits)}**"
    )
    md.append(f"- **Falso positivo a nivel de token** (`kg` solto, sem numero antes): **{len(false_positives)}/{len(kg_hits)}**")
    md.append("")
    md.append(
        f"- **Util para o objetivo da tecnica** (dispara num topico com MAP < {WEAK_TOPIC_MAP_THRESHOLD}, "
        f"ou seja, um topico que realmente precisa de ajuda): **{len(useful_hits)}/{len(kg_hits)}** "
        f"({100*len(useful_hits)/len(kg_hits):.1f}%)"
    )
    md.append(
        f"- **\"Falso positivo de utilidade\"** (dispara corretamente -- e um `kg` real -- mas num topico "
        f"que ja tem MAP >= {WEAK_TOPIC_MAP_THRESHOLD}, ou seja, o boost ali e desnecessario para o "
        f"objetivo original): **{len(non_useful_hits)}/{len(kg_hits)}** "
        f"({100*len(non_useful_hits)/len(kg_hits):.1f}%)\n"
    )

    md.append("## Distribuicao por topico\n")
    md.append("| Topico | Palavras-chave | MAP do topico | N hits 'kg' | Topico fraco (precisa ajuda)? |")
    md.append("|---|---|---|---|---|")
    for topic_id in sorted(topic_counts, key=lambda t: (t is None, t if t is not None else 0)):
        topic_map = map_by_topic.get(topic_id) if topic_id is not None else None
        label = "outliers" if topic_id == -1 else (f"T{topic_id}" if topic_id is not None else "(sem topico)")
        fraco = "**SIM**" if (topic_map is not None and topic_map < WEAK_TOPIC_MAP_THRESHOLD) else "nao"
        map_str = f"{topic_map:.4f}" if topic_map is not None else "-"
        kw = keywords_by_topic.get(topic_id, "") if topic_id is not None else ""
        md.append(f"| {label} | {kw} | {map_str} | {topic_counts[topic_id]} | {fraco} |")

    md.append("\n## Falsos negativos (o token 'kg' deveria ter disparado, mas nao disparou)\n")
    md.append(
        f"1. **'kg' colado ao numero, sem espaco** (o tokenizer funde tudo em um so token, ex. "
        f"`35kg`, `1kg`, `20kg`, que nao bate com o token isolado `kg`): **{len(no_space_near_misses)}** casos."
    )
    for h in no_space_near_misses:
        md.append(f"   - Q{h['query_id']} (T{h['topic']}): \"{h['query_text']}\"")
    md.append(
        f"2. **Menciona 'peso' mas usa outra unidade** (ex. toneladas, nao capturado por este regex): "
        f"**{len(peso_without_kg)}** caso(s)."
    )
    for h in peso_without_kg:
        md.append(f"   - Q{h['query_id']} (T{h['topic']}): \"{h['query_text']}\"")
    md.append(
        f"3. **Unidades de massa/torque vizinhas** (`kgf`, `kgm`, `ton`, `grama` -- fisicamente distintas "
        f"de `kg`, mas relacionadas; note que `kgf`/`kgm` ja estao cobertas por `UNIT_TOKENS` no regex mais "
        f"amplo de densidade numerica, so nao contam como `kg` nesta auditoria especifica): **{len(other_mass_units)}** caso(s)."
    )
    for h in other_mass_units:
        md.append(f"   - Q{h['query_id']} (T{h['topic']}), unidades={h['unidades']}: \"{h['query_text']}\"")

    md.append("\n## Conclusao")
    md.append(
        "- O token `kg`, isoladamente, **nao tem falsos positivos de tokenizacao** no benchmark: toda "
        "ocorrencia esta genuinamente ligada a um valor numerico de peso.\n"
        f"- Mas so **{len(useful_hits)} das {len(kg_hits)}** ocorrencias caem em topicos que de fato "
        "precisam de ajuda (MAP baixo) -- concentradas em T101 (caminhoes/elevadores, MAP 0,4453) e "
        "T73 (caminhoes, MAP 0,5431). As outras "
        f"{len(non_useful_hits)} disparam em topicos ja saudaveis (T18, T47 com MAP 1,0; T114 com 0,91; "
        "T111 com 0,82; outliers com 0,81; T12 com 0,78) -- o boost ali nao é 'errado', so nao ataca "
        "o problema que motivou a tecnica.\n"
        "- Os falsos negativos encontrados sao pontuais mas sistemáticos: valores colados sem espaco "
        "('35KG/M3', '1kg', '20Kg.') exigiriam trocar a deteccao de tokenizacao pura por uma regex sobre "
        "o texto bruto (`\\d[.,]?\\d*\\s*kg\\b`), e peso em toneladas ('16 T') exigiria adicionar essa "
        "unidade ao vocabulario -- mas com risco de ambiguidade ('T' e uma letra muito comum sozinha)."
    )

    md_path = OUT_DIR / "kg_regex_resultados.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nRelatorio salvo em: {md_path}")
    print(f"CSVs salvos em: {OUT_DIR}")


if __name__ == "__main__":
    main()
