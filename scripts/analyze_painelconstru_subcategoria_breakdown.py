"""Segmenta o resultado da validacao PainelConstru (300 consultas,
`analyze_painelconstru_subcategoria_rerank_300.py`) por subcategoria: quais
subcategorias tem o gate por subcategoria mais positivo/negativo, e quais
tem o MAP baseline mais alto/baixo.

Le o CSV per-query ja gerado (nao roda retrieval de novo) e agrega por
subcategory_id.

Uso:
    python scripts/analyze_painelconstru_subcategoria_breakdown.py

Saida (results/painelconstru_subcategoria_validation/):
    subcategoria_breakdown.csv/.md
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

PER_QUERY_CSV = PROJECT_ROOT / "results" / "painelconstru_subcategoria_validation" / "painelconstru_subcategoria_rerank_300_per_query.csv"
OUT_DIR = PROJECT_ROOT / "results" / "painelconstru_subcategoria_validation"
SUBCATEGORIA_NAMES_CSV = PROJECT_ROOT.parent / "class_match" / "results" / "regex_subcategories" / "sinapi-295-regex-subcategories.csv"
MIN_N = 3


def load_subcategoria_names() -> dict[str, str]:
    """id_sub -> nome legivel. Mesma taxonomia de subcategoria usada no
    SINAPI e no PainelConstru (confirmado por inspecao cruzada de IDs)."""
    names: dict[str, str] = {}
    with SUBCATEGORIA_NAMES_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            sub_id = row.get("subcategoria_id")
            name = row.get("subcategoria")
            if sub_id and sub_id not in names:
                names[sub_id] = name or ""
    return names


def main() -> None:
    sub_names = load_subcategoria_names()
    rows = []
    with PER_QUERY_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)

    by_sub: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_sub[r["subcategory_id"]].append(r)

    summary = []
    for sub_id, group in by_sub.items():
        n = len(group)
        map_baseline = sum(float(r["baseline_ap"]) for r in group) / n
        map_flat_sub = sum(float(r["flat_subcategoria_ap"]) for r in group) / n
        delta = map_flat_sub - map_baseline
        example_descriptions = [r["product_description"] for r in group[:3]]
        summary.append(
            {
                "subcategory_id": sub_id,
                "subcategory_name": sub_names.get(sub_id, "(desconhecida)"),
                "n": n,
                "map_baseline": map_baseline,
                "map_flat_subcategoria": map_flat_sub,
                "delta": delta,
                "examples": " | ".join(example_descriptions),
            }
        )

    summary.sort(key=lambda r: r["n"], reverse=True)

    with (OUT_DIR / "subcategoria_breakdown.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["subcategory_id", "subcategory_name", "n", "map_baseline", "map_flat_subcategoria", "delta", "examples"], delimiter=";")
        writer.writeheader()
        for r in summary:
            writer.writerow(
                {
                    "subcategory_id": r["subcategory_id"],
                    "subcategory_name": r["subcategory_name"],
                    "n": r["n"],
                    "map_baseline": f"{r['map_baseline']:.4f}",
                    "map_flat_subcategoria": f"{r['map_flat_subcategoria']:.4f}",
                    "delta": f"{r['delta']:.4f}",
                    "examples": r["examples"],
                }
            )

    reliable = [r for r in summary if r["n"] >= MIN_N]
    print(f"Subcategorias distintas: {len(summary)} | com N>={MIN_N}: {len(reliable)}")

    best_delta = sorted(reliable, key=lambda r: r["delta"], reverse=True)[:10]
    worst_delta = sorted(reliable, key=lambda r: r["delta"])[:10]
    best_map = sorted(reliable, key=lambda r: r["map_flat_subcategoria"], reverse=True)[:10]
    worst_map = sorted(reliable, key=lambda r: r["map_flat_subcategoria"])[:10]

    md = []
    md.append("# PainelConstru (300 consultas) -- segmentacao por subcategoria\n")
    md.append(
        f"Agrega `painelconstru_subcategoria_rerank_300_per_query.csv` por `subcategory_id`. "
        f"{len(summary)} subcategorias distintas nas 300 consultas amostradas (media ~{300/len(summary):.1f} "
        f"consultas/subcategoria -- bem fragmentado). Tabelas abaixo usam so subcategorias com "
        f"N>={MIN_N} consultas (N={len(reliable)}) para reduzir ruido de amostra pequena; o CSV completo "
        f"(`subcategoria_breakdown.csv`) tem todas as {len(summary)}, incluindo N=1/2.\n"
    )

    md.append(f"## Top 10 -- gate MAIS ajuda (maior delta, N>={MIN_N})\n")
    md.append("| Subcategoria | N | MAP baseline | MAP flat-sub | Delta | Exemplos |")
    md.append("|---|---|---|---|---|---|")
    for r in best_delta:
        md.append(f"| {r['subcategory_name']} ({r['subcategory_id']}) | {r['n']} | {r['map_baseline']:.4f} | {r['map_flat_subcategoria']:.4f} | {r['delta']:+.4f} | {r['examples']} |")

    md.append(f"\n## Top 10 -- gate MAIS atrapalha (menor delta, N>={MIN_N})\n")
    md.append("| Subcategoria | N | MAP baseline | MAP flat-sub | Delta | Exemplos |")
    md.append("|---|---|---|---|---|---|")
    for r in worst_delta:
        md.append(f"| {r['subcategory_name']} ({r['subcategory_id']}) | {r['n']} | {r['map_baseline']:.4f} | {r['map_flat_subcategoria']:.4f} | {r['delta']:+.4f} | {r['examples']} |")

    md.append(f"\n## Top 10 -- maior MAP absoluto (com gate, N>={MIN_N})\n")
    md.append("| Subcategoria | N | MAP baseline | MAP flat-sub | Delta |")
    md.append("|---|---|---|---|---|")
    for r in best_map:
        md.append(f"| {r['subcategory_name']} ({r['subcategory_id']}) | {r['n']} | {r['map_baseline']:.4f} | {r['map_flat_subcategoria']:.4f} | {r['delta']:+.4f} |")

    md.append(f"\n## Top 10 -- menor MAP absoluto (com gate, N>={MIN_N})\n")
    md.append("| Subcategoria | N | MAP baseline | MAP flat-sub | Delta |")
    md.append("|---|---|---|---|---|")
    for r in worst_map:
        md.append(f"| {r['subcategory_name']} ({r['subcategory_id']}) | {r['n']} | {r['map_baseline']:.4f} | {r['map_flat_subcategoria']:.4f} | {r['delta']:+.4f} |")

    md_path = OUT_DIR / "subcategoria_breakdown.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("\n=== Melhor delta (gate ajuda) ===")
    for r in best_delta[:5]:
        print(f"{r['subcategory_name']} ({r['subcategory_id']}) n={r['n']:2d} baseline={r['map_baseline']:.4f} flat_sub={r['map_flat_subcategoria']:.4f} delta={r['delta']:+.4f}")
    print("\n=== Pior delta (gate atrapalha) ===")
    for r in worst_delta[:5]:
        print(f"{r['subcategory_name']} ({r['subcategory_id']}) n={r['n']:2d} baseline={r['map_baseline']:.4f} flat_sub={r['map_flat_subcategoria']:.4f} delta={r['delta']:+.4f}")
    print("\n=== Maior MAP absoluto ===")
    for r in best_map[:5]:
        print(f"{r['subcategory_name']} ({r['subcategory_id']}) n={r['n']:2d} baseline={r['map_baseline']:.4f} flat_sub={r['map_flat_subcategoria']:.4f}")
    print("\n=== Menor MAP absoluto ===")
    for r in worst_map[:5]:
        print(f"{r['subcategory_name']} ({r['subcategory_id']}) n={r['n']:2d} baseline={r['map_baseline']:.4f} flat_sub={r['map_flat_subcategoria']:.4f}")

    print(f"\nRelatorio salvo em: {md_path}")


if __name__ == "__main__":
    main()
