"""Prepara corpus e benchmark de retrieval a partir das correlações SINAPI."""

from __future__ import annotations

import csv
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE_TSV = BASE_DIR / "data" / "correlations-295.tsv"
DIFFERENT_TSV = BASE_DIR / "data" / "correlations-295-different.tsv"
ITEMS_TSV = BASE_DIR / "data" / "sinapi-items-295.tsv"
BENCHMARK_JSON = BASE_DIR / "data" / "retrieval-benchmark-295.json"
CORRELATION_FIELDS = ("ID_Sup", "ID_Prod", "Prod_Desc", "ID_Itm", "Itm_Desc")


def clean_text(value: str) -> str:
    return " ".join((value or "").replace("\t", " ").split()).strip()


def load_correlations(path: Path = SOURCE_TSV) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t", quotechar='"')
        missing = set(CORRELATION_FIELDS).difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Colunas ausentes em {path}: {sorted(missing)}")
        rows = [dict(row) for row in reader]

    for row_number, row in enumerate(rows, start=2):
        if row["ID_Sup"] != "295":
            raise ValueError(f"ID_Sup diferente de 295 na linha {row_number}.")
        for field in ("ID_Sup", "ID_Prod", "ID_Itm"):
            try:
                int(row[field])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"{field} inválido na linha {row_number}: {row[field]!r}"
                ) from error
        row["_different_literal"] = str(
            row["Prod_Desc"] != row["Itm_Desc"]
        )
        row["Prod_Desc"] = clean_text(row["Prod_Desc"])
        row["Itm_Desc"] = clean_text(row["Itm_Desc"])
    return rows


def different_correlations(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {field: row[field] for field in CORRELATION_FIELDS}
        for row in rows
        if row["_different_literal"] == "True"
    ]


def write_different_tsv(rows: list[dict[str, str]], path: Path = DIFFERENT_TSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=CORRELATION_FIELDS,
            delimiter="\t",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            lineterminator="\r\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_item_corpus(rows: list[dict[str, str]]) -> list[dict[str, int | str]]:
    descriptions_by_id: dict[int, str] = {}
    for row in rows:
        item_id = int(row["ID_Itm"])
        description = row["Itm_Desc"]
        existing = descriptions_by_id.get(item_id)
        if existing is not None and existing != description:
            raise ValueError(
                f"ID_Itm {item_id} possui descrições divergentes: "
                f"{existing!r} e {description!r}."
            )
        descriptions_by_id[item_id] = description

    return [
        {"codigo": item_id, "descricao": descriptions_by_id[item_id]}
        for item_id in sorted(descriptions_by_id)
    ]


def write_item_corpus(
    items: list[dict[str, int | str]], path: Path = ITEMS_TSV
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("codigo", "descricao"),
            delimiter="\t",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\r\n",
        )
        writer.writeheader()
        writer.writerows(items)


def build_benchmark(rows: list[dict[str, str]]) -> dict[str, object]:
    grouped: dict[tuple[int, str], dict[str, object]] = {}
    for row in rows:
        product_id = int(row["ID_Prod"])
        product_description = row["Prod_Desc"]
        key = (product_id, product_description)
        group = grouped.setdefault(
            key,
            {
                "item_ids": set(),
                "item_descriptions": {},
            },
        )
        item_id = int(row["ID_Itm"])
        group["item_ids"].add(item_id)
        group["item_descriptions"][item_id] = row["Itm_Desc"]

    items: list[dict[str, object]] = []
    for (product_id, product_description), group in sorted(grouped.items()):
        relevant_item_ids = sorted(group["item_ids"])
        original_description = group["item_descriptions"][relevant_item_ids[0]]
        items.append(
            {
                "codigo": product_id,
                "descricao_original": original_description,
                "mutations": [
                    {
                        "mut_ID": product_id,
                        "descricao_mutada": product_description,
                        "relevant_item_ids": relevant_item_ids,
                    }
                ],
            }
        )

    return {
        "metadata": {
            "source_tsv": str(SOURCE_TSV.resolve()),
            "supplier_id": 295,
            "comparison": "desigualdade literal entre Prod_Desc e Itm_Desc",
            "source_correlations": len(load_correlations()),
            "different_correlations": len(rows),
            "benchmark_queries": len(items),
        },
        "items": items,
    }


def write_benchmark(payload: dict[str, object], path: Path = BENCHMARK_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    correlations = load_correlations()
    different = different_correlations(correlations)
    items = build_item_corpus(correlations)
    benchmark = build_benchmark(different)

    write_different_tsv(different)
    write_item_corpus(items)
    write_benchmark(benchmark)

    print(f"Correlações de origem: {len(correlations)}")
    print(f"Correlações diferentes: {len(different)}")
    print(f"Itens únicos no corpus: {len(items)}")
    print(f"Consultas agrupadas no benchmark: {len(benchmark['items'])}")
    print(f"TSV filtrado: {DIFFERENT_TSV.resolve()}")
    print(f"Corpus: {ITEMS_TSV.resolve()}")
    print(f"Benchmark: {BENCHMARK_JSON.resolve()}")


if __name__ == "__main__":
    main()
