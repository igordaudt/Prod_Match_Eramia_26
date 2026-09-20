"""Identifica correlacoes do ground truth real (295) em que a descricao do
item SINAPI e identica a do produto, diferindo apenas pelo sufixo mecanico
"[SINAPI NNNNN]" concatenado ao final -- casos triviais para qualquer metodo
lexical, que o filtro original (Prod_Desc != Itm_Desc) nao pega porque
compara as strings brutas, sem remover esse sufixo.

Gera:
  - data/ground_truth/trivial_sinapi_tag_correlations.csv: as correlacoes
    identificadas como triviais (para auditoria).
  - data/ground_truth/retrieval-benchmark-295-no-trivial505.json: copia do
    benchmark de 852 consultas, excluindo as consultas cujo product_id
    (== mut_ID == ID_Prod) esta entre as triviais.

Uso:
    python scripts/filter_trivial_correlations.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CORRELATIONS_TSV = BASE_DIR / "data" / "ground_truth" / "correlations-295-different-948.tsv"
BENCHMARK_JSON = BASE_DIR / "data" / "ground_truth" / "retrieval-benchmark-295.json"
OUT_TRIVIAL_CSV = BASE_DIR / "data" / "ground_truth" / "trivial_sinapi_tag_correlations.csv"
OUT_FILTERED_JSON = BASE_DIR / "data" / "ground_truth" / "retrieval-benchmark-295-no-trivial505.json"

TAG_RE_END = re.compile(r"\s*\[SINAPI\s+\d+\]\s*$", re.IGNORECASE)


def norm(s: str) -> str:
    return " ".join(s.strip().upper().split())


def find_trivial_product_ids() -> list[dict]:
    trivial: list[dict] = []
    with open(CORRELATIONS_TSV, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            prod_raw = row["Prod_Desc"]
            itm_raw = row["Itm_Desc"]
            if not TAG_RE_END.search(itm_raw):
                continue
            stripped = TAG_RE_END.sub("", itm_raw)
            if norm(stripped) == norm(prod_raw):
                trivial.append(
                    {
                        "ID_Prod": row["ID_Prod"],
                        "ID_Itm": row["ID_Itm"],
                        "Prod_Desc": prod_raw,
                        "Itm_Desc": itm_raw,
                    }
                )
    return trivial


def main() -> None:
    trivial = find_trivial_product_ids()
    print(f"Correlacoes triviais encontradas (descricao identica + tag [SINAPI NNNNN]): {len(trivial)}")

    with open(OUT_TRIVIAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ID_Prod", "ID_Itm", "Prod_Desc", "Itm_Desc"], delimiter="\t")
        writer.writeheader()
        writer.writerows(trivial)
    print(f"Lista salva em: {OUT_TRIVIAL_CSV}")

    trivial_product_ids = {int(row["ID_Prod"]) for row in trivial}
    print(f"IDs de produto unicos a excluir: {len(trivial_product_ids)}")

    with open(BENCHMARK_JSON, encoding="utf-8-sig") as f:
        payload = json.load(f)

    original_items = payload["items"]
    filtered_items = [item for item in original_items if item.get("codigo") not in trivial_product_ids]
    removed = len(original_items) - len(filtered_items)
    print(f"Consultas no benchmark original: {len(original_items)}")
    print(f"Consultas removidas (codigo em trivial_product_ids): {removed}")
    print(f"Consultas restantes: {len(filtered_items)}")

    filtered_payload = {
        "metadata": {
            **payload["metadata"],
            "filter_note": (
                "Excluidas consultas cuja Itm_Desc e identica a Prod_Desc apos remover "
                "o sufixo mecanico '[SINAPI NNNNN]' -- casos triviais para retrieval lexical."
            ),
            "trivial_excluded": removed,
            "benchmark_queries": len(filtered_items),
        },
        "items": filtered_items,
    }

    with open(OUT_FILTERED_JSON, "w", encoding="utf-8") as f:
        json.dump(filtered_payload, f, ensure_ascii=False, indent=2)
    print(f"Benchmark filtrado salvo em: {OUT_FILTERED_JSON}")


if __name__ == "__main__":
    main()
