"""Gera a envoltória interpolada completa da curva Precision x Recall."""

from __future__ import annotations

import argparse
from bisect import bisect_left
import csv
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_JSON = (
    BASE_DIR
    / "retrieval-results-bge-m3-hybrid"
    / "sinapi_llm_retrieval_results.json"
)
DEFAULT_OUTPUT_PNG = (
    BASE_DIR
    / "retrieval-results-bge-m3-hybrid"
    / "sinapi_llm_precision_recall_interpolated.png"
)

METHOD_LABELS = {
    "bm25": "BM25",
    "e5": "E5 puro",
    "e5_hybrid": "E5 hybrid",
    "bge_m3": "BGE-M3 (denso)",
    "bge_m3_hybrid": "BGE-M3 hybrid",
}

METHOD_COLORS = {
    "bm25": "#dc2626",
    "e5": "#2563eb",
    "e5_hybrid": "#16a34a",
    "bge_m3": "#9333ea",
    "bge_m3_hybrid": "#c026d3",
}


def interpolate_at_recall_levels(
    points: list[dict[str, Any]],
    recall_levels: list[float],
) -> list[dict[str, float]]:
    """Aplica p_interp(j) = max p(r), para todo r >= j."""
    precision_by_recall: dict[float, float] = {}
    for point in points:
        try:
            recall = float(point["recall"])
            precision = float(point["precision"])
        except (KeyError, TypeError, ValueError):
            continue

        recall = min(max(recall, 0.0), 1.0)
        precision = min(max(precision, 0.0), 1.0)
        precision_by_recall[recall] = max(
            precision,
            precision_by_recall.get(recall, 0.0),
        )

    observed_recalls = sorted(precision_by_recall)
    suffix_maximums = [0.0] * len(observed_recalls)
    maximum = 0.0
    for index in range(len(observed_recalls) - 1, -1, -1):
        maximum = max(maximum, precision_by_recall[observed_recalls[index]])
        suffix_maximums[index] = maximum

    return [
        {
            "recall": level,
            "precision_interpolated": (
                suffix_maximums[index]
                if (index := bisect_left(observed_recalls, level))
                < len(observed_recalls)
                else 0.0
            ),
        }
        for level in recall_levels
    ]


def collect_recall_levels(
    curves: dict[str, list[dict[str, Any]]],
) -> list[float]:
    """Retorna todos os pontos distintos em que alguma curva pode mudar."""
    levels = {0.0, 1.0}
    for points in curves.values():
        for point in points:
            try:
                recall = float(point["recall"])
            except (KeyError, TypeError, ValueError):
                continue
            levels.add(min(max(recall, 0.0), 1.0))
    return sorted(levels)


def load_curves(results_json: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(results_json.read_text(encoding="utf-8"))
    curves = payload.get("precision_recall_curves")
    if not isinstance(curves, dict) or not curves:
        raise ValueError(f"Curvas Precision x Recall ausentes em {results_json}")
    return curves


def write_interpolated_csv(
    curves: dict[str, list[dict[str, Any]]],
    output_csv: Path,
) -> dict[str, list[dict[str, float]]]:
    recall_levels = collect_recall_levels(curves)
    interpolated = {
        method: interpolate_at_recall_levels(points, recall_levels)
        for method, points in curves.items()
    }
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["recall", *interpolated])
        for index, recall in enumerate(recall_levels):
            writer.writerow(
                [
                    f"{recall:.9f}",
                    *[
                        f"{interpolated[method][index]['precision_interpolated']:.6f}"
                        for method in interpolated
                    ],
                ]
            )
    return interpolated


def plot_interpolated_curves(
    interpolated: dict[str, list[dict[str, float]]],
    output_png: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    figure, axis = plt.subplots(figsize=(12, 8))
    for method, points in interpolated.items():
        recalls = [point["recall"] for point in points]
        precisions = [point["precision_interpolated"] for point in points]
        interpolated_auc = sum(
            (recalls[index] - recalls[index - 1]) * precisions[index]
            for index in range(1, len(recalls))
        )
        axis.step(
            recalls,
            precisions,
            where="pre",
            linewidth=2.4,
            color=METHOD_COLORS.get(method),
            label=(
                f"{METHOD_LABELS.get(method, method)} "
                f"(AUC-int={interpolated_auc:.3f})"
            ),
        )

    axis.set_title("Precisão interpolada × Recall — Retrieval SINAPI", fontsize=15)
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precisão interpolada")
    axis.set_xlim(0.0, 1.0)
    axis.set_ylim(0.0, 1.02)
    axis.set_xticks([index / 10 for index in range(11)])
    axis.set_yticks([index / 10 for index in range(11)])
    axis.xaxis.set_major_formatter(PercentFormatter(1.0))
    axis.yaxis.set_major_formatter(PercentFormatter(1.0))
    axis.grid(True, alpha=0.3)
    axis.legend(loc="lower left")
    figure.tight_layout()

    output_png.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_png, dpi=180, bbox_inches="tight")
    plt.close(figure)


def generate_interpolated_plot(
    results_json: str | Path,
    output_png: str | Path,
) -> tuple[Path, Path]:
    results_path = Path(results_json).resolve()
    png_path = Path(output_png).resolve()
    csv_path = png_path.with_suffix(".csv")
    curves = load_curves(results_path)
    interpolated = write_interpolated_csv(curves, csv_path)
    plot_interpolated_curves(interpolated, png_path)
    return png_path, csv_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plota a envoltória PR usando todos os níveis de recall observados."
    )
    parser.add_argument("--results-json", type=Path, default=DEFAULT_RESULTS_JSON)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PNG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    png_path, csv_path = generate_interpolated_plot(args.results_json, args.output)
    print(f"Gráfico interpolado: {png_path}")
    print(f"Pontos interpolados: {csv_path}")


if __name__ == "__main__":
    main()
