"""Executa o retrieval sobre o benchmark sintetico controlado 'ppc_weak' (48
consultas, 16 itens, geradas por labeling functions de notacao DN/polegada e
conexao soldavel/roscavel).

Diferente do conjunto real (fornecedor 295, 852 consultas), este usa o corpus
curado de 4.851 itens (data/sinapi_texto_jan26_4851.tsv), pois os codigos de
item deste benchmark seguem a numeracao oficial do SINAPI, nao a numeracao
interna (ID_Itm) do fornecedor 295 — os dois espacos de codigo nao sao
compativeis, entao os dois conjuntos sao executados sobre seus corpora
nativos e comparados a posteriori (ver scripts/jaccard_vs_performance.py).

Reaproveita um cache de embeddings BGE-M3 ja computado para este corpus,
copiado para cache/sinapi_bge_m3_4851/.

Gera os mesmos artefatos que run_retrieval.py, incluindo a curva
Precisao x Recall interpolada (sinapi_llm_precision_recall_interpolated.png).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RETRIEVAL_SCRIPT = SCRIPT_DIR / "retrieval_sinapi.py"
DATA_DIR = PROJECT_ROOT / "data"


def load_retrieval_module():
    spec = importlib.util.spec_from_file_location("retrieval_sinapi_ppc_weak", RETRIEVAL_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Nao foi possivel carregar {RETRIEVAL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_interpolated_plot_module():
    script_path = SCRIPT_DIR / "plot_interpolated_pr.py"
    spec = importlib.util.spec_from_file_location("plot_interpolated_pr", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Nao foi possivel carregar {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    retrieval = load_retrieval_module()

    retrieval.INPUT_JSON = DATA_DIR / "ground_truth" / "ppc_weak_48.json"
    retrieval.SINAPI_ITEMS_TSV = DATA_DIR / "sinapi_texto_jan26_4851.tsv"
    retrieval.OUTPUT_DIR = PROJECT_ROOT / "results" / "ppc_weak"
    retrieval.SINAPI_BGE_M3_CACHE_DIR = PROJECT_ROOT / "cache" / "sinapi_bge_m3_4851"
    retrieval.DEFAULT_MAX_PRODUCTS = 0
    retrieval.DEFAULT_METHODS = ("bm25", "e5", "e5_hybrid", "bge_m3", "bge_m3_hybrid")

    original_read_sinapi_items = retrieval.read_sinapi_items

    def read_current_sinapi_items(path=retrieval.SINAPI_ITEMS_TSV):
        return original_read_sinapi_items(path)

    retrieval.read_sinapi_items = read_current_sinapi_items

    retrieval.load_sinapi_bm25.cache_clear()
    retrieval.load_sinapi_e5.cache_clear()
    retrieval.load_sinapi_bge_m3.cache_clear()
    retrieval.main()

    plotter = load_interpolated_plot_module()
    png_path, csv_path = plotter.generate_interpolated_plot(
        retrieval.RESULTS_JSON,
        retrieval.OUTPUT_DIR / "sinapi_llm_precision_recall_interpolated.png",
    )
    print(f"Grafico PR interpolado: {png_path}")
    print(f"Pontos PR interpolados: {csv_path}")


if __name__ == "__main__":
    main()
