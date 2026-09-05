from __future__ import annotations

"""
Compara tecnicas de retrieval para SINAPI e gera curva Precision x Recall.

Uso principal (Windows):
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py

Uso principal (Linux/macOS):
    venv/bin/python SINAPI/retrieval/retrieval_sinapi_new.py

Executar todos os produtos (remove o default de 100):
    # Windows
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py --max-products 0

    # Linux
    venv/bin/python SINAPI/retrieval/retrieval_sinapi_new.py --max-products 0

Datasets alternativos com saida em pasta propria:
    # sintetico_ppc (consultas com parametro ausente — testa degradacao do reranking)
    # Windows
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py ^
        --input-json SINAPI/Data/sintetico/sintetico_ppc/sinapi_mutations_ppc.json ^
        --output-dir SINAPI/retrieval/results_ppc --methods bm25,e5,e5_hybrid

    # Linux
    venv/bin/python SINAPI/retrieval/retrieval_sinapi_new.py \
        --input-json SINAPI/Data/sintetico/sintetico_ppc/sinapi_mutations_ppc.json \
        --output-dir SINAPI/retrieval/results_ppc --methods bm25,e5,e5_hybrid

    # weak supervision (funcoes de rotulagem: notacao DN/mm/pol, series PVC, sinonimia)
    # Windows
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py ^
        --input-json SINAPI/Data/sintetico/sintetico_ppc/sinapi_mutations_weak_supervision.json ^
        --output-dir SINAPI/retrieval/results_ppc_weak --methods bm25,e5,e5_hybrid

    # Linux
    venv/bin/python SINAPI/retrieval/retrieval_sinapi_new.py \
        --input-json SINAPI/Data/sintetico/sintetico_ppc/sinapi_mutations_weak_supervision.json \
        --output-dir SINAPI/retrieval/results_ppc_weak --methods bm25,e5,e5_hybrid

Executar menos consultas:
    # Executa apenas as 100 primeiras mutacoes LLM
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py --max-products 100

    # Executa apenas produtos especificos pelo product_id
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py --product-ids 101,205,309

    # Tambem pode combinar com metodos/limite de candidatos
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py --max-products 5 --methods bm25,e5_hybrid --limit 20

    # Metodos disponiveis:
    # bert,e5,e5_hybrid,bm25,minilm,mpnet,bertimbau,bge_m3,bge_m3_hybrid,bge_hybrid_mix,e5_large

    # Se algum metodo travar ou estiver sem collection, exclua da execucao:
    venv\\Scripts\\python.exe SINAPI\\retrieval\\retrieval_sinapi_new.py --max-products 50 --exclude-methods e5_large,bert

Saidas (configuravel via --output-dir, default: SINAPI/retrieval/results_llm/):
    sinapi_llm_candidates.jsonl       Candidatos detalhados, consumidos pelo reranking.
    sinapi_llm_retrieval_results.json Resultados completos por produto.
    sinapi_llm_metrics.csv            CSV cumulativo com metricas agregadas por metodo.
    sinapi_llm_precision_recall.csv   Curva Precision x Recall por threshold de score.
    sinapi_llm_precision_recall.png   Grafico PR por threshold de score.
    sinapi_llm_precision_recall_vs_threshold.png
                                      Precision e Recall por threshold, um painel por metodo.
    sinapi_llm_precision_recall_by_rank.csv
                                      Curva acumulada por cutoff k do ranking (legado).
    sinapi_llm_precision_recall_by_rank.png
                                      Grafico acumulado por cutoff k do ranking (legado).
"""

import argparse
from collections import defaultdict
import csv
import importlib.util
import json
from functools import lru_cache
import math
import multiprocessing
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent


def ensure_project_venv() -> None:
    """Relaunch with the project venv when the current Python lacks dependencies."""
    required_modules = ("qdrant_client", "matplotlib", "sentence_transformers")
    missing_modules = [
        module
        for module in required_modules
        if importlib.util.find_spec(module) is None
    ]
    if not missing_modules:
        return

    # Try both Windows and Linux paths
    venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if not venv_python.exists():
        raise ModuleNotFoundError(
            "Dependencias ausentes no interpretador atual: "
            f"{', '.join(missing_modules)}. Ambiente virtual nao encontrado em "
            f"{venv_python}."
        )

    current_python = Path(sys.executable).resolve()
    target_python = venv_python.resolve()
    if current_python == target_python:
        raise ModuleNotFoundError(
            "Dependencias ausentes no ambiente virtual: "
            f"{', '.join(missing_modules)}. Execute "
            "venv\\Scripts\\python.exe -m pip install -r requirements.txt."
        )

    print(
        f"Interpretador atual sem {', '.join(missing_modules)}: {current_python}",
        flush=True,
    )
    print(f"Reiniciando com o ambiente do projeto: {target_python}", flush=True)
    os.execv(str(target_python), [str(target_python), *sys.argv])


ensure_project_venv()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


INPUT_JSON = PROJECT_ROOT / "data" / "ground_truth" / "retrieval-benchmark-295.json"
SINAPI_ITEMS_TSV = PROJECT_ROOT / "data" / "sinapi-items-295.tsv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "real_295"
METRICS_CSV = OUTPUT_DIR / "sinapi_llm_metrics.csv"
PR_CURVE_CSV = OUTPUT_DIR / "sinapi_llm_precision_recall.csv"
PR_CURVE_PNG = OUTPUT_DIR / "sinapi_llm_precision_recall.png"
PR_CURVE_SVG = OUTPUT_DIR / "sinapi_llm_precision_recall.svg"
PR_THRESHOLD_PNG = OUTPUT_DIR / "sinapi_llm_precision_recall_vs_threshold.png"
PR_RANK_CURVE_CSV = OUTPUT_DIR / "sinapi_llm_precision_recall_by_rank.csv"
PR_RANK_CURVE_PNG = OUTPUT_DIR / "sinapi_llm_precision_recall_by_rank.png"
CANDIDATES_JSONL = OUTPUT_DIR / "sinapi_llm_candidates.jsonl"
RESULTS_JSON = OUTPUT_DIR / "sinapi_llm_retrieval_results.json"
BGE_M3_LOCAL_ARTIFACT_DIR = PROJECT_ROOT / "cache" / "bge_m3_local_artifacts"
DENSE_TEXT_MODE = "raw"


def configure_output_dir(output_dir: str | Path) -> None:
    global OUTPUT_DIR
    global METRICS_CSV
    global PR_CURVE_CSV
    global PR_CURVE_PNG
    global PR_CURVE_SVG
    global PR_THRESHOLD_PNG
    global PR_RANK_CURVE_CSV
    global PR_RANK_CURVE_PNG
    global CANDIDATES_JSONL
    global RESULTS_JSON

    path = Path(output_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    OUTPUT_DIR = path
    METRICS_CSV = path / "sinapi_llm_metrics.csv"
    PR_CURVE_CSV = path / "sinapi_llm_precision_recall.csv"
    PR_CURVE_PNG = path / "sinapi_llm_precision_recall.png"
    PR_CURVE_SVG = path / "sinapi_llm_precision_recall.svg"
    PR_THRESHOLD_PNG = path / "sinapi_llm_precision_recall_vs_threshold.png"
    PR_RANK_CURVE_CSV = path / "sinapi_llm_precision_recall_by_rank.csv"
    PR_RANK_CURVE_PNG = path / "sinapi_llm_precision_recall_by_rank.png"
    CANDIDATES_JSONL = path / "sinapi_llm_candidates.jsonl"
    RESULTS_JSON = path / "sinapi_llm_retrieval_results.json"

DEFAULT_LIMIT = 100
DEFAULT_TOP_K = 20
DEFAULT_MAX_PRODUCTS = 100
DEFAULT_METHODS = (
    "bm25",
    "e5",
    "e5_hybrid",
    "bge_hybrid_mix",
)


METHOD_LABELS = {
    "bert": "BERT",
    "e5": "E5 puro",
    "e5_hybrid": "E5 hybrid",
    "bm25": "BM25",
    "minilm": "MiniLM",
    "mpnet": "MPNet",
    "bertimbau": "BERTimbau",
    "bge_m3": "BGE-M3",
    "bge_m3_hybrid": "BGE-M3 hybrid",
    "bge_hybrid_mix": "BGE hybrid mix",
    "e5_large": "E5 large",
}


METRICS_FIELDNAMES = [
    "run_id",
    "started_at",
    "method",
    "products_tested",
    "avg_retrieval_time_ms",
    "avg_MAP",
    "avg_P@5",
    "avg_P@10",
    "avg_P_5",
    "avg_P_10",
    "retrieval_limit",
    "avg_Recall@10",
    "avg_Recall@50",
    "avg_Recall@100",
]


def coerce_item_id(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def load_benchmark(input_json: str | Path) -> list[dict[str, Any]]:
    path = Path(input_json)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    with path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError(
            f"Ground truth LLM invalido: esperado objeto com lista 'items' em {path}"
        )

    benchmark: list[dict[str, Any]] = []
    for index, row in enumerate(payload["items"]):
        if not isinstance(row, dict):
            raise ValueError(f"Entrada invalida na posicao {index}: esperado objeto JSON.")

        codigo = coerce_item_id(row.get("codigo"))
        original_description = row.get("descricao_original")
        mutations = row.get("mutations", [])
        if codigo is None:
            raise ValueError(f"codigo invalido na posicao {index}.")
        if not isinstance(original_description, str) or not original_description.strip():
            raise ValueError(f"descricao_original invalida na posicao {index}.")
        if not isinstance(mutations, list):
            raise ValueError(f"mutations invalido na posicao {index}.")

        for mutation in mutations:
            if not isinstance(mutation, dict):
                continue
            mutation_id = coerce_item_id(mutation.get("mut_ID"))
            mutated_description = mutation.get("descricao_mutada")
            raw_relevant_item_ids = mutation.get("relevant_item_ids", [codigo])
            if not isinstance(raw_relevant_item_ids, list):
                raw_relevant_item_ids = [codigo]
            relevant_item_ids = [
                item_id
                for item_id in (
                    coerce_item_id(value)
                    for value in raw_relevant_item_ids
                )
                if item_id is not None
            ]
            if (
                mutation_id is None
                or not isinstance(mutated_description, str)
                or not mutated_description.strip()
                or not relevant_item_ids
            ):
                continue
            benchmark.append(
                {
                    "product_id": mutation_id,
                    "mutation_id": mutation_id,
                    "codigo": codigo,
                    "product_description": mutated_description.strip(),
                    "original_description": original_description.strip(),
                    "relevant_item_ids": sorted(set(relevant_item_ids)),
                }
            )

    if not benchmark:
        raise ValueError(f"Nenhuma mutacao valida encontrada em {path}.")
    return benchmark


def read_sinapi_items(path: Path = SINAPI_ITEMS_TSV) -> list[dict[str, Any]]:
    last_decode_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                reader = csv.DictReader(file, delimiter="\t")
                if reader.fieldnames is None:
                    raise ValueError(f"TSV SINAPI sem cabecalho: {path}")
                missing = {"codigo", "descricao"} - set(reader.fieldnames)
                if missing:
                    raise ValueError(
                        "Colunas ausentes no TSV SINAPI: " + ", ".join(sorted(missing))
                    )

                items = []
                for row in reader:
                    item_id = coerce_item_id(row.get("codigo"))
                    description = str(row.get("descricao") or "").strip()
                    if item_id is None or not description:
                        continue
                    items.append(
                        {
                            "item_id": item_id,
                            "description": description,
                            "supplier_id": None,
                        }
                    )
                if not items:
                    raise ValueError(f"Nenhum item SINAPI valido encontrado em {path}.")
                return items
        except UnicodeDecodeError as error:
            last_decode_error = error

    raise ValueError(f"Nao foi possivel decodificar o TSV SINAPI: {path}") from last_decode_error


def filter_benchmark(
    benchmark: list[dict[str, Any]],
    *,
    product_ids: list[int] | None,
    max_products: int | None,
) -> list[dict[str, Any]]:
    selected = benchmark
    if product_ids:
        wanted_ids = set(product_ids)
        selected = [
            row
            for row in selected
            if coerce_item_id(row.get("codigo")) in wanted_ids
        ]
    if max_products is not None and max_products > 0:
        selected_codes: list[int] = []
        seen_codes: set[int] = set()
        for row in selected:
            codigo = coerce_item_id(row.get("codigo"))
            if codigo is None or codigo in seen_codes:
                continue
            seen_codes.add(codigo)
            selected_codes.append(codigo)
            if len(selected_codes) >= max_products:
                break
        selected_code_set = set(selected_codes)
        selected = [
            row
            for row in selected
            if coerce_item_id(row.get("codigo")) in selected_code_set
        ]
    return selected


def parse_int_list(raw_value: str | None) -> list[int] | None:
    if raw_value is None or not raw_value.strip():
        return None
    return [int(part.strip()) for part in raw_value.split(",") if part.strip()]


class SinapiBm25Index:
    def __init__(self, tokenized_corpus: list[list[str]], *, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.document_lengths = [len(tokens) for tokens in tokenized_corpus]
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths)
            if self.document_lengths
            else 0.0
        )
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for document_index, tokens in enumerate(tokenized_corpus):
            frequencies: dict[str, int] = defaultdict(int)
            for token in tokens:
                frequencies[token] += 1
            for token, frequency in frequencies.items():
                self.postings[token].append((document_index, frequency))

        document_count = len(tokenized_corpus)
        self.idf = {
            token: math.log(
                1.0 + (document_count - len(entries) + 0.5) / (len(entries) + 0.5)
            )
            for token, entries in self.postings.items()
        }

    def top_indices(self, query_tokens: list[str], limit: int) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for token in set(query_tokens):
            token_idf = self.idf.get(token)
            if token_idf is None:
                continue
            for document_index, frequency in self.postings[token]:
                length = self.document_lengths[document_index]
                normalization = 1.0 - self.b
                if self.average_document_length:
                    normalization += self.b * length / self.average_document_length
                denominator = frequency + self.k1 * normalization
                scores[document_index] += token_idf * (
                    frequency * (self.k1 + 1.0) / denominator
                )

        return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]


@lru_cache(maxsize=1)
def load_sinapi_bm25() -> tuple[Any, list[int], list[str], list[int | None]]:
    from normalization import TextNormalizer

    items_by_id = {
        int(item["item_id"]): (
            str(item["description"]),
            coerce_item_id(item.get("supplier_id")),
        )
        for item in read_sinapi_items()
    }
    normalizer = TextNormalizer()
    item_ids = list(items_by_id)
    descriptions = [items_by_id[item_id][0] for item_id in item_ids]
    supplier_ids = [items_by_id[item_id][1] for item_id in item_ids]
    tokenized_corpus = [normalizer.normalize(text).split() for text in descriptions]
    return SinapiBm25Index(tokenized_corpus), item_ids, descriptions, supplier_ids


def retrieve_bm25(search_terms: str, limit: int) -> list[dict[str, Any]]:
    from normalization import TextNormalizer

    index, item_ids, descriptions, supplier_ids = load_sinapi_bm25()
    query_tokens = TextNormalizer().normalize(search_terms).split()
    ranked_indices = index.top_indices(query_tokens, limit)
    return [
        {
            "item_id": item_ids[idx],
            "description": descriptions[idx],
            "description_norm": descriptions[idx],
            "supplier_id": supplier_ids[idx],
            "retrieval_score": float(score),
            "retrieval_backend": "bm25",
        }
        for idx, score in ranked_indices
    ]


@lru_cache(maxsize=1)
def load_sinapi_e5() -> tuple[Any, list[int], list[str], Any]:
    from sentence_transformers import SentenceTransformer

    items = read_sinapi_items()
    item_ids = [int(item["item_id"]) for item in items]
    descriptions = [str(item["description"]) for item in items]
    passages = [
        f"passage: {description}"
        for description in descriptions
    ]
    model = SentenceTransformer("intfloat/multilingual-e5-small")
    embeddings = model.encode(
        passages,
        batch_size=64,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    return model, item_ids, descriptions, embeddings


def retrieve_e5(search_terms: str, limit: int) -> list[dict[str, Any]]:
    import numpy as np

    model, item_ids, descriptions, embeddings = load_sinapi_e5()

    query_text = (search_terms or "").strip()
    if not query_text:
        return []
    query_embedding = model.encode(
        [f"query: {query_text}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    scores = embeddings @ query_embedding
    resolved_limit = min(max(int(limit), 0), len(item_ids))
    if resolved_limit <= 0:
        return []
    top_indices = np.argpartition(scores, -resolved_limit)[-resolved_limit:]
    top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
    return [
        {
            "item_id": item_ids[int(index)],
            "description": descriptions[int(index)],
            "description_norm": descriptions[int(index)],
            "supplier_id": None,
            "retrieval_score": float(scores[int(index)]),
            "retrieval_backend": "local_e5_sinapi",
        }
        for index in top_indices
    ]


@lru_cache(maxsize=1)
def load_sinapi_bge_m3_local() -> tuple[Any, list[int], list[str], Any]:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    embeddings_path = BGE_M3_LOCAL_ARTIFACT_DIR / "item_embeddings.npy"
    index_path = BGE_M3_LOCAL_ARTIFACT_DIR / "item_index.json"
    if not embeddings_path.exists() or not index_path.exists():
        raise FileNotFoundError(
            "Artifacts locais BGE-M3 nao encontrados em "
            f"{BGE_M3_LOCAL_ARTIFACT_DIR}."
        )

    with index_path.open("r", encoding="utf-8") as file:
        index_data = json.load(file)

    items = index_data.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError(f"Indice BGE-M3 invalido: {index_path}")

    item_ids = [int(item["item_id"]) for item in items]
    descriptions = [str(item.get("description_norm") or "") for item in items]
    embeddings = np.load(embeddings_path)
    model = SentenceTransformer(os.getenv("BGE_M3_MODEL_NAME", "BAAI/bge-m3"))
    return model, item_ids, descriptions, embeddings


def retrieve_bge_m3_local(search_terms: str, limit: int) -> list[dict[str, Any]]:
    import numpy as np

    model, item_ids, descriptions, embeddings = load_sinapi_bge_m3_local()

    query_text = (search_terms or "").strip()
    if not query_text:
        return []
    query_embedding = model.encode(
        [query_text],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    scores = embeddings @ query_embedding
    resolved_limit = min(max(int(limit), 0), len(item_ids))
    if resolved_limit <= 0:
        return []
    top_indices = np.argpartition(scores, -resolved_limit)[-resolved_limit:]
    top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
    return [
        {
            "item_id": item_ids[int(index)],
            "description": descriptions[int(index)],
            "description_norm": descriptions[int(index)],
            "supplier_id": None,
            "retrieval_score": float(scores[int(index)]),
            "retrieval_backend": "local_bge_m3_sinapi",
        }
        for index in top_indices
    ]


def retrieve_e5_hybrid(search_terms: str, limit: int) -> list[dict[str, Any]]:
    prefetch_limit = max(limit, 100)
    bm25_items = retrieve_bm25(search_terms, prefetch_limit)
    e5_items = retrieve_e5(search_terms, prefetch_limit)
    items_by_id: dict[int, dict[str, Any]] = {}
    rrf_scores: dict[int, float] = defaultdict(float)
    rrf_k = 60

    for ranked_items in (bm25_items, e5_items):
        for rank, item in enumerate(ranked_items, start=1):
            item_id = coerce_item_id(item.get("item_id"))
            if item_id is None:
                continue
            items_by_id.setdefault(item_id, item)
            rrf_scores[item_id] += 1.0 / (rrf_k + rank)

    ranked_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:limit]
    return [
        {
            **items_by_id[item_id],
            "retrieval_score": rrf_scores[item_id],
            "retrieval_backend": "local_rrf_e5_bm25_sinapi",
        }
        for item_id in ranked_ids
    ]


SINAPI_BGE_M3_CACHE_DIR = PROJECT_ROOT / "cache" / "sinapi_bge_m3"
SINAPI_E5_LARGE_CACHE_DIR = PROJECT_ROOT / "cache" / "sinapi_e5_large_cache"


@lru_cache(maxsize=1)
def load_sinapi_bge_m3() -> tuple[Any, list[int], list[str], Any]:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    items = read_sinapi_items()
    item_ids = [int(item["item_id"]) for item in items]
    descriptions = [str(item["description"]) for item in items]

    emb_path = SINAPI_BGE_M3_CACHE_DIR / "embeddings.npy"
    idx_path = SINAPI_BGE_M3_CACHE_DIR / "index.json"

    if emb_path.exists() and idx_path.exists():
        saved = json.load(open(idx_path, encoding="utf-8"))
        if saved.get("item_ids") == item_ids and saved.get("text_mode") == DENSE_TEXT_MODE:
            embeddings = np.load(str(emb_path))
            model = SentenceTransformer("BAAI/bge-m3")
            return model, item_ids, descriptions, embeddings

    passages = descriptions
    model = SentenceTransformer("BAAI/bge-m3")
    embeddings = model.encode(
        passages,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    SINAPI_BGE_M3_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(emb_path), embeddings)
    json.dump(
        {"item_ids": item_ids, "text_mode": DENSE_TEXT_MODE},
        open(idx_path, "w", encoding="utf-8"),
    )
    return model, item_ids, descriptions, embeddings


def retrieve_bge_m3_sinapi(search_terms: str, limit: int) -> list[dict[str, Any]]:
    import numpy as np

    model, item_ids, descriptions, embeddings = load_sinapi_bge_m3()
    query_text = (search_terms or "").strip()
    if not query_text:
        return []
    query_embedding = model.encode(
        [query_text],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    scores = embeddings @ query_embedding
    resolved_limit = min(max(int(limit), 0), len(item_ids))
    if resolved_limit <= 0:
        return []
    top_indices = np.argpartition(scores, -resolved_limit)[-resolved_limit:]
    top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
    return [
        {
            "item_id": item_ids[int(index)],
            "description": descriptions[int(index)],
            "description_norm": descriptions[int(index)],
            "supplier_id": None,
            "retrieval_score": float(scores[int(index)]),
            "retrieval_backend": "local_bge_m3_sinapi",
        }
        for index in top_indices
    ]


def retrieve_bge_m3_hybrid_sinapi(search_terms: str, limit: int) -> list[dict[str, Any]]:
    prefetch_limit = max(limit, 100)
    bm25_items = retrieve_bm25(search_terms, prefetch_limit)
    bge_m3_items = retrieve_bge_m3_sinapi(search_terms, prefetch_limit)
    items_by_id: dict[int, dict[str, Any]] = {}
    rrf_scores: dict[int, float] = defaultdict(float)
    rrf_k = 60

    for ranked_items in (bm25_items, bge_m3_items):
        for rank, item in enumerate(ranked_items, start=1):
            item_id = coerce_item_id(item.get("item_id"))
            if item_id is None:
                continue
            items_by_id.setdefault(item_id, item)
            rrf_scores[item_id] += 1.0 / (rrf_k + rank)

    ranked_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:limit]
    return [
        {
            **items_by_id[item_id],
            "retrieval_score": rrf_scores[item_id],
            "retrieval_backend": "local_rrf_bge_m3_bm25_sinapi",
        }
        for item_id in ranked_ids
    ]


@lru_cache(maxsize=1)
def load_sinapi_e5_large() -> tuple[Any, list[int], list[str], Any]:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    items = read_sinapi_items()
    item_ids = [int(item["item_id"]) for item in items]
    descriptions = [str(item["description"]) for item in items]

    emb_path = SINAPI_E5_LARGE_CACHE_DIR / "embeddings.npy"
    idx_path = SINAPI_E5_LARGE_CACHE_DIR / "index.json"
    model_name = os.getenv("E5_LARGE_MODEL_NAME", "intfloat/multilingual-e5-large")

    if emb_path.exists() and idx_path.exists():
        saved = json.load(open(idx_path, encoding="utf-8"))
        if (
            saved.get("item_ids") == item_ids
            and saved.get("model_name") == model_name
            and saved.get("text_mode") == DENSE_TEXT_MODE
        ):
            embeddings = np.load(str(emb_path))
            model = SentenceTransformer(model_name)
            return model, item_ids, descriptions, embeddings

    passages = [
        f"passage: {description}"
        for description in descriptions
    ]
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        passages,
        batch_size=16,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    SINAPI_E5_LARGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(emb_path), embeddings)
    json.dump(
        {"item_ids": item_ids, "model_name": model_name, "text_mode": DENSE_TEXT_MODE},
        open(idx_path, "w", encoding="utf-8"),
    )
    return model, item_ids, descriptions, embeddings


def retrieve_e5_large_sinapi(search_terms: str, limit: int) -> list[dict[str, Any]]:
    import numpy as np

    model, item_ids, descriptions, embeddings = load_sinapi_e5_large()
    query_text = (search_terms or "").strip()
    if not query_text:
        return []
    query_embedding = model.encode(
        [f"query: {query_text}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    scores = embeddings @ query_embedding
    resolved_limit = min(max(int(limit), 0), len(item_ids))
    if resolved_limit <= 0:
        return []
    top_indices = np.argpartition(scores, -resolved_limit)[-resolved_limit:]
    top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
    return [
        {
            "item_id": item_ids[int(index)],
            "description": descriptions[int(index)],
            "description_norm": descriptions[int(index)],
            "supplier_id": None,
            "retrieval_score": float(scores[int(index)]),
            "retrieval_backend": "local_e5_large_sinapi",
        }
        for index in top_indices
    ]


def retrieve_bertimbau(search_terms: str, limit: int) -> list[dict[str, Any]]:
    from qdrant.bertimbau.retrieval_qdrant import retrieve_candidates_qdrant

    return retrieve_candidates_qdrant(
        product_description=search_terms,
        limit=limit,
        debug=False,
    )


def retrieve_minilm(search_terms: str, limit: int) -> list[dict[str, Any]]:
    from qdrant.minilm.retrieval_qdrant import retrieve_candidates_qdrant

    return retrieve_candidates_qdrant(
        product_description=search_terms,
        limit=limit,
        debug=False,
    )


def retrieve_mpnet(search_terms: str, limit: int) -> list[dict[str, Any]]:
    from qdrant.mpnet.retrieval_qdrant import retrieve_candidates_qdrant

    return retrieve_candidates_qdrant(
        product_description=search_terms,
        limit=limit,
        debug=False,
    )


def retrieve_bert(search_terms: str, limit: int) -> list[dict[str, Any]]:
    from qdrant.bertimbau.retrieval_qdrant import retrieve_candidates_qdrant

    return retrieve_candidates_qdrant(
        product_description=search_terms,
        limit=limit,
        debug=False,
        collection_name=os.getenv("QDRANT_BERT_COLLECTION", "produtos_bert"),
        model_name=os.getenv("BERT_MODEL_NAME", "bert-base-multilingual-cased"),
    )


def retrieve_bge_m3(search_terms: str, limit: int) -> list[dict[str, Any]]:
    embeddings_path = BGE_M3_LOCAL_ARTIFACT_DIR / "item_embeddings.npy"
    index_path = BGE_M3_LOCAL_ARTIFACT_DIR / "item_index.json"
    if embeddings_path.exists() and index_path.exists():
        return retrieve_bge_m3_local(search_terms, limit)

    from qdrant.bge_m3.retrieval_qdrant import retrieve_candidates_qdrant

    return retrieve_candidates_qdrant(
        product_description=search_terms,
        limit=limit,
        debug=False,
        collection_name=os.getenv("QDRANT_BGE_M3_COLLECTION", "produtos_bge_m3"),
        model_name=os.getenv("BGE_M3_MODEL_NAME", "BAAI/bge-m3"),
    )


def retrieve_bge_m3_hybrid(search_terms: str, limit: int) -> list[dict[str, Any]]:
    embeddings_path = BGE_M3_LOCAL_ARTIFACT_DIR / "item_embeddings.npy"
    index_path = BGE_M3_LOCAL_ARTIFACT_DIR / "item_index.json"
    if embeddings_path.exists() and index_path.exists():
        return retrieve_bge_m3_hybrid_local(search_terms, limit)

    from qdrant.bge_m3.retrieval_hybrid import (
        retrieve_candidates_bge_m3_hybrid,
    )

    return retrieve_candidates_bge_m3_hybrid(
        product_description=search_terms,
        limit=limit,
        debug=False,
    )


@lru_cache(maxsize=1)
def load_bge_hybrid_mix_dependencies() -> tuple[Any, Any, Any]:
    from normalization import TextNormalizer
    from qdrant.bge_m3.retrieval_qdrant import build_client
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("BGE_HYBRID_MIX_MODEL_NAME", "BAAI/bge-m3")
    return SentenceTransformer(model_name), TextNormalizer(), build_client()


def retrieve_bge_hybrid_mix(search_terms: str, limit: int) -> list[dict[str, Any]]:
    """Consulta a collection mista BGE-M3 + BM25, restringindo o benchmark a itens."""
    from qdrant_client import models

    query_raw = (search_terms or "").strip()
    if not query_raw:
        return []

    model, normalizer, client = load_bge_hybrid_mix_dependencies()
    query_norm = normalizer.normalize(query_raw)
    if not query_norm:
        return []

    query_vector = model.encode(
        [query_raw],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0].tolist()
    collection_name = os.getenv("QDRANT_BGE_HYBRID_MIX_COLLECTION", "bge_hybrid_mix")
    dense_vector_name = os.getenv("QDRANT_BGE_HYBRID_MIX_DENSE_VECTOR", "dense")
    sparse_vector_name = os.getenv("QDRANT_BGE_HYBRID_MIX_SPARSE_VECTOR", "sparse")
    sparse_model = os.getenv("QDRANT_BGE_HYBRID_MIX_SPARSE_MODEL", "Qdrant/bm25")
    candidate_limit = max(limit * 2, limit)
    item_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="type",
                match=models.MatchValue(value="item"),
            )
        ]
    )

    response = client.query_points(
        collection_name=collection_name,
        prefetch=[
            models.Prefetch(
                query=query_vector,
                using=dense_vector_name,
                limit=candidate_limit,
            ),
            models.Prefetch(
                query=models.Document(text=query_norm, model=sparse_model),
                using=sparse_vector_name,
                limit=candidate_limit,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=item_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    points = list(response.points) if hasattr(response, "points") else list(response or [])

    candidates: list[dict[str, Any]] = []
    for point in points:
        payload = point.payload or {}
        item_id = coerce_item_id(payload.get("id_item"))
        if item_id is None:
            item_id = coerce_item_id(point.id)
        if item_id is None:
            continue
        description_norm = str(payload.get("desc_norm") or payload.get("description_norm") or "")
        description = str(payload.get("desc") or payload.get("description") or description_norm)
        subcategory = payload.get("subcategory")
        if not isinstance(subcategory, dict):
            subcategory = None
        sinapi_match = re.search(r"\[\s*SINAPI\s+(\d+)\s*\]", description, flags=re.IGNORECASE)
        evaluation_item_id = int(sinapi_match.group(1)) if sinapi_match else None
        candidates.append(
            {
                "item_id": item_id,
                "evaluation_item_id": evaluation_item_id,
                "description": description,
                "description_norm": description_norm,
                "supplier_id": payload.get("supplier_id") or payload.get("id_sup"),
                "manufacturer_id": payload.get("manufacturer_id") or payload.get("id_man"),
                "subcategory_id": (
                    payload.get("subcategory_id")
                    or (subcategory or {}).get("id_sub")
                    or (subcategory or {}).get("id")
                ),
                "subcategory": subcategory,
                "retrieval_score": (
                    float(point.score) if getattr(point, "score", None) is not None else None
                ),
                "retrieval_backend": "qdrant_bge_hybrid_mix",
            }
        )

    return candidates


def retrieve_e5_large(search_terms: str, limit: int) -> list[dict[str, Any]]:
    return retrieve_e5_large_sinapi(search_terms, limit)


RETRIEVERS: dict[str, Callable[[str, int], list[dict[str, Any]]]] = {
    "bert": retrieve_bert,
    "e5": retrieve_e5,
    "e5_hybrid": retrieve_e5_hybrid,
    "bm25": retrieve_bm25,
    "minilm": retrieve_minilm,
    "mpnet": retrieve_mpnet,
    "bertimbau": retrieve_bertimbau,
    "bge_m3": retrieve_bge_m3_sinapi,
    "bge_m3_hybrid": retrieve_bge_m3_hybrid_sinapi,
    "bge_hybrid_mix": retrieve_bge_hybrid_mix,
    "e5_large": retrieve_e5_large,
}


def get_evaluation_item_id(item: dict[str, Any]) -> int | None:
    if "evaluation_item_id" in item:
        return coerce_item_id(item.get("evaluation_item_id"))
    return coerce_item_id(item.get("item_id"))


def build_relevance_flags(items: list[dict[str, Any]], relevant_ids: set[int]) -> list[int]:
    flags: list[int] = []
    seen_ids: set[int] = set()
    for item in items:
        item_id = get_evaluation_item_id(item)
        if item_id is None or item_id in seen_ids:
            flags.append(0)
            continue
        seen_ids.add(item_id)
        flags.append(1 if item_id in relevant_ids else 0)
    return flags


def precision_at_k(flags: list[int], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(flags[:k]) / k


def recall_at_k(flags: list[int], relevant_count: int, k: int) -> float:
    if relevant_count <= 0 or k <= 0:
        return 0.0
    return sum(flags[:k]) / relevant_count


def calculate_metrics(items: list[dict[str, Any]], relevant_ids: set[int], *, top_k: int) -> dict[str, Any]:
    flags = build_relevance_flags(items, relevant_ids)
    hit_count = sum(flags)
    precision_sum = 0.0
    hits_so_far = 0
    first_relevant_rank: int | None = None

    for rank, flag in enumerate(flags, start=1):
        if not flag:
            continue
        hits_so_far += 1
        precision_sum += hits_so_far / rank
        if first_relevant_rank is None:
            first_relevant_rank = rank

    relevant_count = len(relevant_ids)
    return {
        "relevant_count": relevant_count,
        "returned_count": len(items),
        "hit_count": hit_count,
        "recall": (hit_count / relevant_count) if relevant_count else 0.0,
        "precision_at_1": precision_at_k(flags, 1),
        "precision_at_5": precision_at_k(flags, 5),
        "precision_at_10": precision_at_k(flags, 10),
        "precision_at_k": precision_at_k(flags, top_k),
        "recall_at_10": recall_at_k(flags, relevant_count, 10),
        "recall_at_50": recall_at_k(flags, relevant_count, 50),
        "recall_at_100": recall_at_k(flags, relevant_count, 100),
        "map": (precision_sum / relevant_count) if relevant_count else 0.0,
        "mrr": (1 / first_relevant_rank) if first_relevant_rank else 0.0,
        "first_relevant_rank": first_relevant_rank,
        "relevance_flags": flags,
    }


def run_method(
    *,
    run_id: str,
    started_at: str,
    product: dict[str, Any],
    method: str,
    limit: int,
    top_k: int,
) -> dict[str, Any]:
    search_terms = str(product["product_description"])
    relevant_ids = set(int(item_id) for item_id in product["relevant_item_ids"])
    retriever = RETRIEVERS[method]
    started = time.perf_counter()

    try:
        items = retriever(search_terms, limit)
        elapsed_ms = (time.perf_counter() - started) * 1000
        metrics = calculate_metrics(items, relevant_ids, top_k=top_k)
        return {
            "run_id": run_id,
            "started_at": started_at,
            "product_id": product["product_id"],
            "search_terms": search_terms,
            "relevant_item_ids": sorted(relevant_ids),
            "method": method,
            "success": True,
            "error": "",
            "elapsed_ms": elapsed_ms,
            "items": items,
            **metrics,
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "run_id": run_id,
            "started_at": started_at,
            "product_id": product["product_id"],
            "search_terms": search_terms,
            "relevant_item_ids": sorted(relevant_ids),
            "method": method,
            "success": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "relevant_count": len(relevant_ids),
            "returned_count": 0,
            "hit_count": 0,
            "recall": 0.0,
            "precision_at_1": 0.0,
            "precision_at_5": 0.0,
            "precision_at_10": 0.0,
            "precision_at_k": 0.0,
            "recall_at_10": 0.0,
            "recall_at_50": 0.0,
            "recall_at_100": 0.0,
            "map": 0.0,
            "mrr": 0.0,
            "first_relevant_rank": None,
            "elapsed_ms": elapsed_ms,
            "relevance_flags": [],
            "items": [],
        }


def _run_method_process_worker(output_queue: multiprocessing.Queue, kwargs: dict[str, Any]) -> None:
    output_queue.put(run_method(**kwargs))


def build_timeout_result(
    *,
    run_id: str,
    started_at: str,
    product: dict[str, Any],
    method: str,
    timeout_seconds: float,
    elapsed_ms: float,
) -> dict[str, Any]:
    relevant_ids = set(int(item_id) for item_id in product["relevant_item_ids"])
    return {
        "run_id": run_id,
        "started_at": started_at,
        "product_id": product["product_id"],
        "search_terms": str(product["product_description"]),
        "relevant_item_ids": sorted(relevant_ids),
        "method": method,
        "success": False,
        "error": f"TimeoutError: metodo excedeu {timeout_seconds:.1f}s e foi interrompido.",
        "relevant_count": len(relevant_ids),
        "returned_count": 0,
        "hit_count": 0,
        "recall": 0.0,
        "precision_at_1": 0.0,
        "precision_at_5": 0.0,
        "precision_at_10": 0.0,
        "precision_at_k": 0.0,
        "recall_at_10": 0.0,
        "recall_at_50": 0.0,
        "recall_at_100": 0.0,
        "map": 0.0,
        "mrr": 0.0,
        "first_relevant_rank": None,
        "elapsed_ms": elapsed_ms,
        "relevance_flags": [],
        "items": [],
    }


def run_method_with_timeout(
    *,
    timeout_seconds: float | None,
    **kwargs: Any,
) -> dict[str, Any]:
    if timeout_seconds is None or timeout_seconds <= 0:
        return run_method(**kwargs)

    started = time.perf_counter()
    context = multiprocessing.get_context("spawn")
    output_queue: multiprocessing.Queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_run_method_process_worker,
        args=(output_queue, kwargs),
    )
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return build_timeout_result(
            run_id=kwargs["run_id"],
            started_at=kwargs["started_at"],
            product=kwargs["product"],
            method=kwargs["method"],
            timeout_seconds=timeout_seconds,
            elapsed_ms=elapsed_ms,
        )

    if process.exitcode != 0:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return build_timeout_result(
            run_id=kwargs["run_id"],
            started_at=kwargs["started_at"],
            product=kwargs["product"],
            method=kwargs["method"],
            timeout_seconds=timeout_seconds,
            elapsed_ms=elapsed_ms,
        ) | {"error": f"ProcessError: metodo encerrou com exitcode={process.exitcode}."}

    try:
        return output_queue.get(timeout=5)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return build_timeout_result(
            run_id=kwargs["run_id"],
            started_at=kwargs["started_at"],
            product=kwargs["product"],
            method=kwargs["method"],
            timeout_seconds=timeout_seconds,
            elapsed_ms=elapsed_ms,
        ) | {"error": "ProcessError: metodo encerrou sem retornar resultado."}


def write_candidates_jsonl(
    results: list[dict[str, Any]],
    path: Path | None = None,
) -> None:
    path = path or CANDIDATES_JSONL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in results:
            if not row.get("success"):
                continue

            candidates = []
            for rank, item in enumerate(row.get("items") or [], start=1):
                if not isinstance(item, dict):
                    continue
                candidates.append(
                    {
                        **item,
                        "retrieval_rank": rank,
                        "item_id": coerce_item_id(item.get("item_id")),
                    }
                )

            payload = {
                "run_id": row["run_id"],
                "started_at": row["started_at"],
                "product_id": row["product_id"],
                "search_terms": row["search_terms"],
                "method": row["method"],
                "relevant_item_ids": row.get("relevant_item_ids") or [],
                "elapsed_ms": row.get("elapsed_ms"),
                "candidates": candidates,
            }
            file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def append_metrics_csv(
    rows: list[dict[str, Any]],
    path: Path | None = None,
) -> None:
    path = path or METRICS_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.stat().st_size > 0
    write_header = True

    if file_exists:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file, delimiter=";")
            existing_header = next(reader, [])
        write_header = existing_header != METRICS_FIELDNAMES

    mode = "a" if file_exists and not write_header else "w"

    with path.open(mode, encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=METRICS_FIELDNAMES, delimiter=";")
        if mode == "w":
            writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "run_id": row["run_id"],
                    "started_at": row["started_at"],
                    "method": row["method"],
                    "products_tested": int(row.get("products_tested") or 0),
                    "avg_retrieval_time_ms": f"{float(row.get('avg_retrieval_time_ms') or 0.0):.3f}",
                    "avg_MAP": f"{float(row.get('avg_MAP') or 0.0):.6f}",
                    "avg_P@5": f"{float(row.get('avg_P@5') or 0.0):.6f}",
                    "avg_P@10": f"{float(row.get('avg_P@10') or 0.0):.6f}",
                    "avg_P_5": f"{float(row.get('avg_P_5') or 0.0):.6f}",
                    "avg_P_10": f"{float(row.get('avg_P_10') or 0.0):.6f}",
                    "retrieval_limit": int(row.get("retrieval_limit") or 0),
                    "avg_Recall@10": f"{float(row.get('avg_Recall@10') or 0.0):.6f}",
                    "avg_Recall@50": f"{float(row.get('avg_Recall@50') or 0.0):.6f}",
                    "avg_Recall@100": f"{float(row.get('avg_Recall@100') or 0.0):.6f}",
                }
            )


def aggregate_precision_recall_by_rank(
    results: list[dict[str, Any]],
    method: str,
    *,
    max_rank: int,
) -> list[dict[str, float | int | str]]:
    method_results = [
        row
        for row in results
        if row.get("method") == method and row.get("success")
    ]
    total_relevant = sum(int(row.get("relevant_count") or 0) for row in method_results)
    if total_relevant <= 0:
        return []

    points: list[dict[str, float | int | str]] = [
        {"method": method, "rank": 0, "precision": 1.0, "recall": 0.0, "hits": 0, "returned": 0}
    ]
    for cutoff in range(1, max_rank + 1):
        total_hits = 0
        total_returned = 0
        for row in method_results:
            flags = row.get("relevance_flags") or []
            if not isinstance(flags, list):
                continue
            usable_flags = flags[:cutoff]
            total_hits += sum(int(flag) for flag in usable_flags)
            total_returned += len(usable_flags)

        points.append(
            {
                "method": method,
                "rank": cutoff,
                "precision": (total_hits / total_returned) if total_returned else 0.0,
                "recall": total_hits / total_relevant,
                "hits": total_hits,
                "returned": total_returned,
            }
        )

    return points


def aggregate_precision_recall_by_threshold(
    results: list[dict[str, Any]],
    method: str,
) -> list[dict[str, float | int | str | None]]:
    """Calcula uma curva PR micro-agregada variando o score minimo aceito.

    Apenas candidatos efetivamente recuperados possuem score. O denominador do
    recall, porem, inclui todos os itens relevantes do ground truth. Assim, se o
    retrieval nao trouxe um item relevante dentro do limite avaliado, a curva
    termina com recall menor que 1 em vez de ocultar esse falso negativo.
    """
    method_results = [
        row
        for row in results
        if row.get("method") == method and row.get("success")
    ]
    total_relevant = sum(int(row.get("relevant_count") or 0) for row in method_results)
    if total_relevant <= 0:
        return []

    scored_candidates: list[tuple[float, int]] = []
    for row in method_results:
        relevant_ids = {
            item_id
            for value in (row.get("relevant_item_ids") or [])
            if (item_id := coerce_item_id(value)) is not None
        }
        seen_ids: set[int] = set()
        for item in row.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_id = get_evaluation_item_id(item)
            if item_id is None or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            try:
                score = float(item.get("retrieval_score"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(score):
                continue
            scored_candidates.append((score, 1 if item_id in relevant_ids else 0))

    if not scored_candidates:
        return []

    scored_candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    points: list[dict[str, float | int | str | None]] = [
        {
            "method": method,
            "threshold": None,
            "precision": 1.0,
            "recall": 0.0,
            "hits": 0,
            "returned": 0,
            "total_relevant": total_relevant,
        }
    ]
    total_hits = 0
    total_returned = 0
    index = 0

    # Scores empatados formam um unico threshold/operating point.
    while index < len(scored_candidates):
        threshold = scored_candidates[index][0]
        group_returned = 0
        group_hits = 0
        while index < len(scored_candidates) and scored_candidates[index][0] == threshold:
            group_returned += 1
            group_hits += scored_candidates[index][1]
            index += 1

        total_returned += group_returned
        total_hits += group_hits
        points.append(
            {
                "method": method,
                "threshold": threshold,
                "precision": total_hits / total_returned,
                "recall": total_hits / total_relevant,
                "hits": total_hits,
                "returned": total_returned,
                "total_relevant": total_relevant,
            }
        )

    return points


def average_precision_from_curve(points: list[dict[str, Any]]) -> float:
    """Area em degraus da curva PR; positivos nao recuperados contribuem zero."""
    average_precision = 0.0
    previous_recall = 0.0
    for point in points:
        recall = float(point.get("recall") or 0.0)
        precision = float(point.get("precision") or 0.0)
        if recall > previous_recall:
            average_precision += (recall - previous_recall) * precision
            previous_recall = recall
    return average_precision


def write_precision_recall_csv(points_by_method: dict[str, list[dict[str, Any]]]) -> None:
    PR_CURVE_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "method",
        "threshold",
        "precision",
        "recall",
        "hits",
        "returned",
        "total_relevant",
    ]
    with PR_CURVE_CSV.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for method in points_by_method:
            for point in points_by_method[method]:
                writer.writerow(
                    {
                        "method": method,
                        "threshold": (
                            ""
                            if point.get("threshold") is None
                            else f"{float(point['threshold']):.12g}"
                        ),
                        "precision": f"{float(point['precision']):.6f}",
                        "recall": f"{float(point['recall']):.6f}",
                        "hits": int(point["hits"]),
                        "returned": int(point["returned"]),
                        "total_relevant": int(point["total_relevant"]),
                    }
                )


def write_rank_precision_recall_csv(points_by_method: dict[str, list[dict[str, Any]]]) -> None:
    PR_RANK_CURVE_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["method", "rank", "precision", "recall", "hits", "returned"]
    with PR_RANK_CURVE_CSV.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for method, points in points_by_method.items():
            for point in points:
                writer.writerow(
                    {
                        "method": method,
                        "rank": int(point["rank"]),
                        "precision": f"{float(point['precision']):.6f}",
                        "recall": f"{float(point['recall']):.6f}",
                        "hits": int(point["hits"]),
                        "returned": int(point["returned"]),
                    }
                )


def write_precision_recall_plot(points_by_method: dict[str, list[dict[str, Any]]]) -> Path | None:
    PR_CURVE_PNG.parent.mkdir(parents=True, exist_ok=True)

    if not any(points for points in points_by_method.values()):
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return write_precision_recall_svg(points_by_method)

    colors = {
        "bert": "#7c3aed",
        "e5": "#2563eb",
        "e5_hybrid": "#16a34a",
        "bm25": "#dc2626",
        "minilm": "#ea580c",
        "mpnet": "#0891b2",
        "bertimbau": "#4b5563",
        "bge_m3": "#9333ea",
        "bge_m3_hybrid": "#c026d3",
        "bge_hybrid_mix": "#7c3aed",
        "e5_large": "#0f766e",
    }

    plt.figure(figsize=(11, 8))
    for method, points in points_by_method.items():
        if not points:
            continue
        recall_values = [float(point["recall"]) for point in points]
        precision_values = [float(point["precision"]) for point in points]
        average_precision = average_precision_from_curve(points)
        plt.step(
            recall_values,
            precision_values,
            where="post",
            label=f"{METHOD_LABELS.get(method, method)} (AP={average_precision:.3f})",
            color=colors.get(method),
            linewidth=2.0,
        )

    plt.title("Precision x Recall por threshold - Retrieval SINAPI")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PR_CURVE_PNG, dpi=160)
    plt.close()
    return PR_CURVE_PNG


def write_precision_recall_vs_threshold_plot(
    points_by_method: dict[str, list[dict[str, Any]]],
) -> Path | None:
    PR_THRESHOLD_PNG.parent.mkdir(parents=True, exist_ok=True)
    populated = [(method, points) for method, points in points_by_method.items() if len(points) > 1]
    if not populated:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return None

    figure, axes = plt.subplots(len(populated), 1, figsize=(11, 4 * len(populated)), squeeze=False)
    for axis, (method, points) in zip(axes[:, 0], populated):
        scored_points = [point for point in points if point.get("threshold") is not None]
        scored_points.reverse()  # threshold crescente no eixo X
        thresholds = [float(point["threshold"]) for point in scored_points]
        precision_values = [float(point["precision"]) for point in scored_points]
        recall_values = [float(point["recall"]) for point in scored_points]
        axis.plot(thresholds, precision_values, label="Precision", linewidth=1.8)
        axis.plot(thresholds, recall_values, label="Recall", linewidth=1.8)
        axis.set_title(METHOD_LABELS.get(method, method))
        axis.set_xlabel("Threshold de retrieval_score")
        axis.set_ylabel("Metrica")
        axis.set_ylim(0, 1.05)
        axis.grid(True, alpha=0.3)
        axis.legend()

    figure.suptitle("Precision e Recall x threshold - Retrieval SINAPI")
    figure.tight_layout()
    figure.savefig(PR_THRESHOLD_PNG, dpi=160)
    plt.close(figure)
    return PR_THRESHOLD_PNG


def write_rank_precision_recall_plot(
    points_by_method: dict[str, list[dict[str, Any]]],
) -> Path | None:
    PR_RANK_CURVE_PNG.parent.mkdir(parents=True, exist_ok=True)
    if not any(points for points in points_by_method.values()):
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return None

    colors = {
        "e5": "#2563eb",
        "e5_hybrid": "#16a34a",
        "bm25": "#dc2626",
        "bge_hybrid_mix": "#7c3aed",
    }
    plt.figure(figsize=(11, 8))
    for method, points in points_by_method.items():
        if not points:
            continue
        plt.plot(
            [float(point["recall"]) for point in points],
            [float(point["precision"]) for point in points],
            label=METHOD_LABELS.get(method, method),
            color=colors.get(method),
            linewidth=2.0,
        )
    plt.title("Precision x Recall por cutoff k - Retrieval SINAPI")
    plt.xlabel("Recall acumulado ate k")
    plt.ylabel("Precision acumulada ate k")
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PR_RANK_CURVE_PNG, dpi=160)
    plt.close()
    return PR_RANK_CURVE_PNG


def write_precision_recall_svg(
    points_by_method: dict[str, list[dict[str, Any]]],
) -> Path:
    width = 1000
    height = 720
    margin_left = 90
    margin_right = 40
    margin_top = 70
    margin_bottom = 80
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    colors = {
        "e5": "#2563eb",
        "e5_hybrid": "#16a34a",
        "bm25": "#dc2626",
        "bge_hybrid_mix": "#7c3aed",
    }

    def x_position(recall: float) -> float:
        return margin_left + max(0.0, min(1.0, recall)) * plot_width

    def y_position(precision: float) -> float:
        return margin_top + (1.0 - max(0.0, min(1.0, precision))) * plot_height

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="500" y="35" text-anchor="middle" font-family="Arial" font-size="24">Precision x Recall - Retrieval SINAPI</text>',
    ]
    for tick in range(11):
        value = tick / 10
        x = x_position(value)
        y = y_position(value)
        lines.append(
            f'<line x1="{x:.1f}" y1="{margin_top}" x2="{x:.1f}" y2="{margin_top + plot_height}" stroke="#e5e7eb"/>'
        )
        lines.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb"/>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="{margin_top + plot_height + 25}" text-anchor="middle" font-family="Arial" font-size="12">{value:.1f}</text>'
        )
        lines.append(
            f'<text x="{margin_left - 15}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="12">{value:.1f}</text>'
        )

    lines.extend(
        [
            f'<line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#111827" stroke-width="2"/>',
            f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#111827" stroke-width="2"/>',
            f'<text x="{margin_left + plot_width / 2:.1f}" y="{height - 20}" text-anchor="middle" font-family="Arial" font-size="16">Recall</text>',
            f'<text x="25" y="{margin_top + plot_height / 2:.1f}" text-anchor="middle" font-family="Arial" font-size="16" transform="rotate(-90 25 {margin_top + plot_height / 2:.1f})">Precision</text>',
        ]
    )

    legend_x = width - 210
    legend_y = 90
    for legend_index, (method, points) in enumerate(points_by_method.items()):
        if not points:
            continue
        coordinates = " ".join(
            f"{x_position(float(point['recall'])):.1f},{y_position(float(point['precision'])):.1f}"
            for point in points
        )
        color = colors.get(method, "#4b5563")
        lines.append(
            f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="3"/>'
        )
        item_y = legend_y + legend_index * 24
        lines.append(
            f'<line x1="{legend_x}" y1="{item_y}" x2="{legend_x + 28}" y2="{item_y}" stroke="{color}" stroke-width="3"/>'
        )
        lines.append(
            f'<text x="{legend_x + 36}" y="{item_y + 5}" font-family="Arial" font-size="14">{METHOD_LABELS.get(method, method)}</text>'
        )

    lines.append("</svg>")
    PR_CURVE_SVG.write_text("\n".join(lines), encoding="utf-8")
    return PR_CURVE_SVG


def summarize(
    results: list[dict[str, Any]],
    methods: list[str],
    *,
    run_id: str,
    started_at: str,
    retrieval_limit: int,
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for method in methods:
        rows = [row for row in results if row.get("method") == method]
        successful = [row for row in rows if row.get("success")]
        denominator = len(successful) or 1
        avg_retrieval_time_ms = sum(float(row["elapsed_ms"]) for row in successful) / denominator
        summary.append(
            {
                "run_id": run_id,
                "started_at": started_at,
                "method": method,
                "products_tested": len(rows),
                "successful_products": len(successful),
                "failed_products": len(rows) - len(successful),
                "avg_retrieval_time_ms": avg_retrieval_time_ms,
                "avg_execution_time_ms": avg_retrieval_time_ms,
                "avg_MAP": sum(float(row["map"]) for row in successful) / denominator,
                "avg_P@5": sum(float(row["precision_at_5"]) for row in successful) / denominator,
                "avg_P@10": sum(float(row["precision_at_10"]) for row in successful) / denominator,
                "avg_P_5": sum(float(row["precision_at_5"]) for row in successful) / denominator,
                "avg_P_10": sum(float(row["precision_at_10"]) for row in successful) / denominator,
                "eval_metrics": ["map", "P_5", "P_10"],
                "retrieval_limit": retrieval_limit,
                "avg_Recall@10": sum(float(row["recall_at_10"]) for row in successful) / denominator,
                "avg_Recall@50": sum(float(row["recall_at_50"]) for row in successful) / denominator,
                "avg_Recall@100": sum(float(row["recall_at_100"]) for row in successful) / denominator,
            }
        )
        summary[-1]["avg_eval_metrics"] = {
            "map": summary[-1]["avg_MAP"],
            "P_5": summary[-1]["avg_P_5"],
            "P_10": summary[-1]["avg_P_10"],
        }
    return summary


def round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [round_floats(item) for item in value]
    if isinstance(value, dict):
        return {key: round_floats(item) for key, item in value.items()}
    return value


def write_results_json(
    results: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    points_by_method: dict[str, list[dict[str, Any]]],
    rank_points_by_method: dict[str, list[dict[str, Any]]],
    *,
    input_json: str | Path,
) -> None:
    compact_results = []
    for row in results:
        compact_results.append(
            {
                key: value
                for key, value in row.items()
                if key not in {"items", "relevance_flags"}
            }
        )

    payload = {
        "metadata": {
            "input_json": str(Path(input_json).resolve()),
            "generated_at": datetime.now().astimezone().isoformat(),
            "methods": [row["method"] for row in summary_rows],
            "precision_recall_curve_type": "micro_averaged_score_threshold",
            "precision_recall_note": (
                "O recall usa todos os positivos do ground truth; positivos ausentes dos "
                "candidatos recuperados limitam o recall maximo da curva."
            ),
        },
        "summaries": {
            row["method"]: round_floats(row)
            for row in summary_rows
        },
        "results": round_floats(compact_results),
        "average_precision_by_method": {
            method: round(average_precision_from_curve(points), 6)
            for method, points in points_by_method.items()
        },
        "precision_recall_curves": round_floats(points_by_method),
        "rank_cutoff_precision_recall_curves": round_floats(rank_points_by_method),
    }
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_JSON.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def parse_methods(raw_value: str | None) -> list[str]:
    if raw_value is None or not raw_value.strip():
        return list(DEFAULT_METHODS)

    methods = [part.strip().lower() for part in raw_value.split(",") if part.strip()]
    invalid = [method for method in methods if method not in RETRIEVERS]
    if invalid:
        raise ValueError(
            "Metodos invalidos: "
            + ", ".join(invalid)
            + ". Use: "
            + ", ".join(DEFAULT_METHODS)
        )
    return methods


def apply_excluded_methods(methods: list[str], raw_value: str | None) -> list[str]:
    excluded = parse_methods(raw_value) if raw_value else []
    if not excluded:
        return methods

    excluded_set = set(excluded)
    filtered_methods = [method for method in methods if method not in excluded_set]
    if not filtered_methods:
        raise ValueError("Todos os metodos foram excluidos. Ajuste --methods ou --exclude-methods.")
    return filtered_methods


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara metodos de retrieval SINAPI."
    )
    parser.add_argument("--input-json", default=str(INPUT_JSON))
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Diretorio para metricas, resultados e grafico.",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--max-products",
        type=int,
        default=DEFAULT_MAX_PRODUCTS,
        help=(
            f"Quantidade maxima de produtos. Default: {DEFAULT_MAX_PRODUCTS}. "
            "Use 0 para executar todos."
        ),
    )
    parser.add_argument("--product-ids", default=None, help="product_id separados por virgula.")
    parser.add_argument(
        "--methods",
        default=None,
        help=(
            "Metodos separados por virgula. Default: "
            + ",".join(DEFAULT_METHODS)
            + "."
        ),
    )
    parser.add_argument(
        "--exclude-methods",
        default=None,
        help="Metodos separados por virgula para remover da execucao, ex: e5_large,bert.",
    )
    parser.add_argument(
        "--method-timeout-seconds",
        type=float,
        default=None,
        help=(
            "Timeout opcional por produto/metodo. Se exceder, o metodo e marcado como erro "
            "e a execucao continua. Use apenas para diagnostico, pois isola cada chamada em outro processo."
        ),
    )
    return parser.parse_args()


def print_output_files(
    plot_path: Path | None,
    threshold_plot_path: Path | None,
    rank_plot_path: Path | None,
) -> None:
    output_files: list[tuple[str, Path | None]] = [
        ("Metricas acumuladas CSV", METRICS_CSV),
        ("Resultados completos JSON", RESULTS_JSON),
        ("Candidatos detalhados JSONL", CANDIDATES_JSONL),
        ("Curva Precision x Recall por threshold CSV", PR_CURVE_CSV),
        ("Grafico Precision x Recall por threshold PNG", plot_path),
        ("Grafico Precision/Recall x threshold PNG", threshold_plot_path),
        ("Curva Precision x Recall por cutoff k CSV", PR_RANK_CURVE_CSV),
        ("Grafico Precision x Recall por cutoff k PNG", rank_plot_path),
    ]

    print("\nArquivos de comparacao gerados/atualizados:")
    for label, path in output_files:
        if path is None:
            print(f"- {label}: nao gerado")
            continue

        resolved_path = path.resolve()
        if resolved_path.exists():
            print(f"- {label}: {resolved_path}")
            print(f"  Link: {resolved_path.as_uri()}")
        else:
            print(f"- {label}: esperado em {resolved_path}, mas o arquivo nao foi encontrado")


def main() -> None:
    args = parse_args()
    configure_output_dir(args.output_dir)
    run_id = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    started_at = datetime.now().astimezone().isoformat()
    methods = apply_excluded_methods(parse_methods(args.methods), args.exclude_methods)
    benchmark = filter_benchmark(
        load_benchmark(args.input_json),
        product_ids=parse_int_list(args.product_ids),
        max_products=args.max_products,
    )

    if not benchmark:
        print("Nenhum produto selecionado.")
        return

    source_product_count = len(
        {
            coerce_item_id(row.get("codigo"))
            for row in benchmark
            if coerce_item_id(row.get("codigo")) is not None
        }
    )
    print("Comparando retrieval SINAPI")
    print(f"Produtos SINAPI: {source_product_count}")
    print(f"Consultas mutadas: {len(benchmark)}")
    print(f"Metodos: {', '.join(methods)}")
    print(f"Limit: {args.limit}")

    results: list[dict[str, Any]] = []
    for product_index, product in enumerate(benchmark, start=1):
        print(f"\n[{product_index}/{len(benchmark)}] product_id={product['product_id']}")
        for method in methods:
            print(f"  {method:<10} iniciando...", flush=True)
            row = run_method_with_timeout(
                timeout_seconds=args.method_timeout_seconds,
                run_id=run_id,
                started_at=started_at,
                product=product,
                method=method,
                limit=args.limit,
                top_k=args.top_k,
            )
            results.append(row)
            status = "ok" if row["success"] else "erro"
            print(
                f"  {method:<10} {status:<4} "
                f"MAP={float(row['map']):.6f} "
                f"Recall={float(row['recall']):.6f} "
                f"P@10={float(row['precision_at_10']):.6f}"
            )
            if not row["success"]:
                print(f"    {row['error']}")

    summary_rows = summarize(
        results,
        methods,
        run_id=run_id,
        started_at=started_at,
        retrieval_limit=args.limit,
    )
    write_candidates_jsonl(results)
    append_metrics_csv(summary_rows)
    points_by_method = {
        method: aggregate_precision_recall_by_threshold(results, method)
        for method in methods
    }
    rank_points_by_method = {
        method: aggregate_precision_recall_by_rank(results, method, max_rank=args.limit)
        for method in methods
    }
    write_results_json(
        results,
        summary_rows,
        points_by_method,
        rank_points_by_method,
        input_json=args.input_json,
    )
    write_precision_recall_csv(points_by_method)
    write_rank_precision_recall_csv(rank_points_by_method)
    plot_path = write_precision_recall_plot(points_by_method)
    threshold_plot_path = write_precision_recall_vs_threshold_plot(points_by_method)
    rank_plot_path = write_rank_precision_recall_plot(rank_points_by_method)

    print("\nResumo da execucao:")
    for row in summary_rows:
        print(
            f"- {METHOD_LABELS.get(row['method'], row['method'])}: "
            f"products_tested={row['products_tested']} "
            f"erro={row['failed_products']} "
            f"MAP={row['avg_MAP']:.6f} "
            f"P@5={row['avg_P@5']:.6f} "
            f"P@10={row['avg_P@10']:.6f} "
            f"Recall@10={row['avg_Recall@10']:.6f} "
            f"Recall@50={row['avg_Recall@50']:.6f} "
            f"Recall@100={row['avg_Recall@100']:.6f} "
            f"tempo_ms={row['avg_retrieval_time_ms']:.1f}"
        )

    print_output_files(plot_path, threshold_plot_path, rank_plot_path)


if __name__ == "__main__":
    main()
