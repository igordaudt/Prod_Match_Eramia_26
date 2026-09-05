"""Constroi a base de dados combinada (fixa) dos dois conjuntos usados no
estudo — conjunto real (fornecedor 295) e conjunto sintetico controlado
(ppc_weak) — para uso em EDA sobre "todos os dados".

Gera dois arquivos em data/:

  combined_items_all.tsv
    Uniao deduplicada dos dois corpora de itens (5.813 do fornecedor 295 +
    4.851 do corpus curado), casando por descricao normalizada identica.
    Colunas: description, codigo_295, codigo_4851, source
    (source = "real_295" | "synthetic_4851" | "both")

  combined_queries_all.tsv
    Uniao das 948 correlacoes reais (fornecedor 295) + 48 consultas
    sinteticas (ppc_weak) em um esquema comum.
    Colunas: source, query_id, query_text, target_text, target_id
    (target_id fica no espaco de codigo nativo de cada fonte — os dois
    espacos de codigo NAO sao compativeis entre si, ver nota no artigo)

Este script nao altera nem re-executa retrieval — e apenas para consolidar
os dados de texto/EDA em uma base fixa e auditavel.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ITEMS_295_TSV = BASE_DIR / "data" / "sinapi-items-295.tsv"
ITEMS_4851_TSV = BASE_DIR / "data" / "sinapi_texto_jan26_4851.tsv"
CORR_295_TSV = BASE_DIR / "data" / "ground_truth" / "correlations-295-different-948.tsv"
PPC_WEAK_JSON = BASE_DIR / "data" / "ground_truth" / "ppc_weak_48.json"

OUT_ITEMS = BASE_DIR / "data" / "combined_items_all.tsv"
OUT_QUERIES = BASE_DIR / "data" / "combined_queries_all.tsv"


def norm(text: str) -> str:
    return " ".join((text or "").strip().upper().split())


def build_combined_items() -> None:
    with ITEMS_295_TSV.open(encoding="utf-8", newline="") as f:
        items_295 = [(int(row["codigo"]), row["descricao"]) for row in csv.DictReader(f, delimiter="\t")]

    with ITEMS_4851_TSV.open(encoding="latin-1", newline="") as f:
        items_4851 = [(int(row["codigo"]), row["descricao"]) for row in csv.DictReader(f, delimiter="\t")]

    by_desc: dict[str, dict] = {}

    for codigo, desc in items_295:
        key = norm(desc)
        row = by_desc.setdefault(key, {"description": desc.strip(), "codigo_295": None, "codigo_4851": None})
        if row["codigo_295"] is None:
            row["codigo_295"] = codigo

    for codigo, desc in items_4851:
        key = norm(desc)
        row = by_desc.setdefault(key, {"description": desc.strip(), "codigo_295": None, "codigo_4851": None})
        if row["codigo_4851"] is None:
            row["codigo_4851"] = codigo

    rows = []
    for row in by_desc.values():
        has_295 = row["codigo_295"] is not None
        has_4851 = row["codigo_4851"] is not None
        source = "both" if (has_295 and has_4851) else ("real_295" if has_295 else "synthetic_4851")
        rows.append({**row, "source": source})

    rows.sort(key=lambda r: (r["source"], r["description"]))

    OUT_ITEMS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_ITEMS.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["description", "codigo_295", "codigo_4851", "source"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "description": row["description"],
                    "codigo_295": row["codigo_295"] if row["codigo_295"] is not None else "",
                    "codigo_4851": row["codigo_4851"] if row["codigo_4851"] is not None else "",
                    "source": row["source"],
                }
            )

    n_both = sum(1 for r in rows if r["source"] == "both")
    n_295_only = sum(1 for r in rows if r["source"] == "real_295")
    n_4851_only = sum(1 for r in rows if r["source"] == "synthetic_4851")
    print(f"[items] total combinado (deduplicado): {len(rows)}")
    print(f"[items]   em ambos os corpora: {n_both}")
    print(f"[items]   so no corpus real (295): {n_295_only}")
    print(f"[items]   so no corpus sintetico (4851): {n_4851_only}")
    print(f"[items] salvo em: {OUT_ITEMS}")


def build_combined_queries() -> None:
    rows = []

    with CORR_295_TSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t", quotechar='"'):
            rows.append(
                {
                    "source": "real_295",
                    "query_id": row["ID_Prod"],
                    "query_text": " ".join((row["Prod_Desc"] or "").split()),
                    "target_text": " ".join((row["Itm_Desc"] or "").split()),
                    "target_id": row["ID_Itm"],
                }
            )

    with PPC_WEAK_JSON.open(encoding="utf-8") as f:
        ppc = json.load(f)
    for item in ppc["items"]:
        original = " ".join((item["descricao_original"] or "").split())
        for mut in item["mutations"]:
            rows.append(
                {
                    "source": "synthetic_4851",
                    "query_id": mut["mut_ID"],
                    "query_text": " ".join((mut["descricao_mutada"] or "").split()),
                    "target_text": original,
                    "target_id": item["codigo"],
                }
            )

    OUT_QUERIES.parent.mkdir(parents=True, exist_ok=True)
    with OUT_QUERIES.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["source", "query_id", "query_text", "target_text", "target_id"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    n_real = sum(1 for r in rows if r["source"] == "real_295")
    n_synth = sum(1 for r in rows if r["source"] == "synthetic_4851")
    print(f"\n[queries] total combinado: {len(rows)} ({n_real} reais + {n_synth} sinteticas)")
    print(f"[queries] salvo em: {OUT_QUERIES}")


def main() -> None:
    build_combined_items()
    build_combined_queries()


if __name__ == "__main__":
    main()
