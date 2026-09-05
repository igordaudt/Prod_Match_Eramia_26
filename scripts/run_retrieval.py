"""Ponto de entrada unico para reproduzir o experimento de retrieval deste repositorio.

Executa os 4 metodos (BM25, E5, E5 hybrid, BGE-M3 hybrid) sobre o benchmark de
852 consultas (948 correlacoes reais fornecedor->SINAPI, data/ground_truth/) e
gera o grafico de Precisao x Recall interpolado.

Uso:
    python scripts/run_retrieval.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "real_295"


def run_retrieval() -> None:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "retrieval_sinapi.py"),
            "--methods",
            "bm25,e5,e5_hybrid,bge_m3_hybrid",
            "--max-products",
            "0",
            "--output-dir",
            str(RESULTS_DIR),
        ],
        check=True,
    )


def plot_interpolated() -> None:
    sys.path.insert(0, str(SCRIPT_DIR))
    from plot_interpolated_pr import generate_interpolated_plot

    results_json = RESULTS_DIR / "sinapi_llm_retrieval_results.json"
    output_png = RESULTS_DIR / "sinapi_precision_recall_interpolated.png"
    png_path, csv_path = generate_interpolated_plot(results_json, output_png)
    print(f"Grafico PR interpolado: {png_path}")
    print(f"Pontos PR interpolados: {csv_path}")


def main() -> None:
    run_retrieval()
    plot_interpolated()


if __name__ == "__main__":
    main()
