# Prod_Match_Eramia_26

Repositório do artigo **ERAMIA 2026**: avaliação de métodos de recuperação de informação (retrieval) para *product matching* de itens técnicos do SINAPI, usando dois conjuntos de dados com perfis lexicais deliberadamente distintos — um **ground truth real de produção** (correlações produto↔SINAPI já validadas em uso) e um **benchmark sintético controlado** (variação de notação técnica). Não aborda reranking — o foco é a etapa de retrieval, complementada por EDA/modelagem de tópicos.

## Versão para submissão (template SBC)

`paper_v2/latex/` contém o artigo formatado no template oficial da SBC (`Template_SBC/template-latex/`, usado pelo ERAMIA), **respeitando o limite de 4 páginas, incluindo referências**, e já compilando para PDF sem erros:

```
paper_v2/latex/
├── artigo_eramia_2026.tex   # artigo completo no formato SBC (4 páginas)
├── references.bib           # bibliografia (BibTeX)
├── sbc-template.sty         # estilo oficial (copiado do template)
├── sbc.bst                  # estilo de bibliografia oficial
├── figs/                    # figuras da versão longa (não usadas na versão de 4 páginas)
└── artigo_eramia_2026.pdf   # PDF compilado (4 páginas)
```

Para recompilar (requer alguma distribuição LaTeX, ex. MiKTeX/TeX Live):

```bash
cd paper_v2/latex
pdflatex artigo_eramia_2026.tex
bibtex artigo_eramia_2026
pdflatex artigo_eramia_2026.tex
pdflatex artigo_eramia_2026.tex
```

**Pendências antes de submeter:**
- Revisão final do texto.

> **Nota sobre anonimato:** `paper/` (primeira versão) e `paper_v2/` (versão atual, anonimizada para revisão cega) foram removidas do repositório remoto — o artigo, em qualquer versão, não fica no GitHub enquanto a revisão estiver em andamento, para não comprometer o anonimato da submissão. Ambas continuam disponíveis apenas localmente, para referência e trabalho contínuo.

## Estrutura do repositório

```
Prod_Match_Eramia_26/
├── README.md
├── requirements.txt
├── normalization.py                  # pipeline de normalização de texto
├── data/
│   ├── sinapi-items-295.tsv          # corpus real: 5.813 itens SINAPI (catálogo interno, fornecedor 295)
│   ├── sinapi_texto_jan26_4851.tsv   # corpus sintético: 4.851 itens curados (base nativa do ppc_weak)
│   ├── combined_items_all.tsv        # corpus COMBINADO deduplicado: 7.252 itens únicos (ver "Base combinada")
│   ├── combined_queries_all.tsv      # consultas COMBINADAS: 996 (948 reais + 48 sintéticas)
│   └── ground_truth/
│       ├── correlations-295-different-948.tsv   # 948 correlações reais produto↔item
│       ├── retrieval-benchmark-295.json          # benchmark real: 852 consultas agrupadas
│       └── ppc_weak_48.json                      # benchmark sintético: 48 consultas (LFs de notação)
├── cache/
│   ├── sinapi_bge_m3/                # embeddings BGE-M3 dos 5.813 itens (corpus real)
│   └── sinapi_bge_m3_4851/           # embeddings BGE-M3 dos 4.851 itens (corpus nativo do ppc_weak)
├── scripts/
│   ├── retrieval_sinapi.py           # implementação de BM25, E5, E5 hybrid, BGE-M3 (+ híbridos via RRF)
│   ├── run_retrieval.py              # roda os 4 métodos sobre o conjunto real → results/real_295/
│   ├── run_retrieval_ppc_weak.py     # roda os 5 métodos sobre o ppc_weak → results/ppc_weak/
│   ├── prepare_retrieval_data.py     # reconstrói o benchmark JSON a partir do TSV bruto de correlações
│   ├── plot_interpolated_pr.py       # envoltória de Precisão x Recall interpolada
│   ├── build_combined_dataset.py     # gera data/combined_items_all.tsv e combined_queries_all.tsv
│   ├── merge_datasets_analysis.py    # MAP e curva pooled combinando os 2 conjuntos → results/combined_900/
│   ├── jaccard_median_split.py       # divide as 900 consultas em metade inf./sup. de Jaccard → results/jaccard_split/
│   ├── eda_corpus.py                 # EDA de texto + Jaccard sobre a base combinada
│   ├── eda_bertopic.py               # BERTopic sobre o corpus combinado + cruzamento tópico×MAP
│   └── jaccard_vs_performance.py     # Jaccard × MAP por quartil (conjunto real) vs. ppc_weak
├── results/                          # TODOS os resultados de retrieval/análise, um subdiretório por estudo
│   ├── real_295/                     # retrieval sobre as 852 consultas reais (4 métodos)
│   ├── real_295_bge_m3_puro/         # BGE-M3 denso puro sobre as mesmas 852 consultas (5º método, rodada separada)
│   ├── ppc_weak/                     # retrieval sobre as 48 consultas sintéticas (5 métodos)
│   ├── combined_900/                 # MAP e curva pooled dos 2 conjuntos juntos (900 consultas)
│   └── jaccard_split/                # MAP por metade inferior/superior de Jaccard (900 consultas)
├── eda/                               # EDA: gráficos, tabelas, item_topics.csv, jaccard_vs_map.*
└── paper_v2/
    ├── artigo_eramia_2026.md         # rascunho do artigo em Markdown (fonte de trabalho)
    └── latex/                         # versão formatada no template SBC — pronta para submissão
```

> **Nota sobre a reorganização:** até a rodada anterior, cada estudo tinha sua própria pasta solta na raiz (`results/`, `results_ppc_weak/`, `results_combined/`). Tudo foi movido para dentro de `results/<nome-do-estudo>/` para evitar pastas espalhadas na raiz. Os scripts já foram atualizados para os novos caminhos.

## Base combinada (`data/combined_*_all.tsv`)

Os dois conjuntos usam espaços de identificador de item **incompatíveis** (código oficial do SINAPI no ppc_weak vs. `ID_Itm` interno do fornecedor 295 no conjunto real) — não dá pra unificá-los num único corpus/benchmark de retrieval. A base combinada junta **texto e estatísticas**, não retrieval:

- `combined_items_all.tsv`: união deduplicada por descrição normalizada dos dois corpora de itens (5.813 + 4.851) → **7.252 itens únicos** (2.401 só no real, 1.442 só no sintético, 3.409 nos dois). Colunas: `description, codigo_295, codigo_4851, source`.
- `combined_queries_all.tsv`: união das 948 correlações reais + 48 consultas sintéticas → **996 registros**, esquema comum `source, query_id, query_text, target_text, target_id`.

Gerar com `scripts/build_combined_dataset.py`. É a base usada por `eda_corpus.py`, `eda_bertopic.py`, `merge_datasets_analysis.py` e `jaccard_median_split.py`.

## Origem dos dados

O ground truth real **não é sintético**. `ID_Sup = 295` é o identificador interno usado, na base de produção da plataforma (`daudtco_BD_Prices`), para o catálogo oficial do SINAPI. A tabela `T_correlations` registra a correlação, já validada em uso real, entre um produto real cadastrado por um usuário (`T_Products`) e o item SINAPI correspondente (`T_Item_Bot`, filtrado por `ID_Sup = 295`).

`data/ground_truth/correlations-295-different-948.tsv` contém as **948 correlações** em que a descrição do produto difere literalmente da descrição do item SINAPI. Agrupadas por `(ID_Prod, Prod_Desc)`, formam **852 consultas** em `retrieval-benchmark-295.json`. Pipeline: `scripts/prepare_retrieval_data.py`.

O conjunto sintético (`ppc_weak`, 48 consultas sobre 16 itens) foi construído por funções de rotulagem que substituem sistematicamente a notação técnica da descrição oficial (DN em mm ↔ polegadas; remoção de "soldável"/"roscável"), produzindo baixa sobreposição lexical de forma deliberada.

## Métodos avaliados

Implementação local (in-memory, CPU, sem servidor externo), idêntica nos dois conjuntos:

| Método | Modelo | Config |
|---|---|---|
| BM25 | — | k₁=1,2, b=0,75 |
| E5 (denso) | `intfloat/multilingual-e5-small`, 384-dim | prefixos `query:`/`passage:`, cosseno |
| E5 hybrid | E5 + BM25 | RRF, k=60 |
| BGE-M3 hybrid | `BAAI/bge-m3` (1024-dim) + BM25 | RRF, k=60 |
| BGE-M3 (denso) | `BAAI/bge-m3` | avaliado nos dois conjuntos — MAP 0,757 no real (`results/real_295_bge_m3_puro/`), 0,723 no ppc_weak |

## Como reproduzir

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
# venv/bin/python -m pip install -r requirements.txt          # Linux/macOS

# Retrieval — conjunto real (852 consultas, 4 métodos) → results/real_295/
venv\Scripts\python.exe scripts\run_retrieval.py

# BGE-M3 denso puro sobre o conjunto real (5º método, reaproveita o cache de embeddings) → results/real_295_bge_m3_puro/
venv\Scripts\python.exe scripts\retrieval_sinapi.py --methods bge_m3 --max-products 0 --output-dir results\real_295_bge_m3_puro

# Retrieval — conjunto sintético (48 consultas, 5 métodos) → results/ppc_weak/
venv\Scripts\python.exe scripts\run_retrieval_ppc_weak.py

# Base combinada (texto) — data/combined_items_all.tsv, combined_queries_all.tsv
venv\Scripts\python.exe scripts\build_combined_dataset.py

# EDA (usa a base combinada) → eda/
venv\Scripts\python.exe scripts\eda_corpus.py
venv\Scripts\python.exe scripts\eda_bertopic.py

# Jaccard × desempenho, por quartil (conjunto real) vs. ppc_weak → eda/
venv\Scripts\python.exe scripts\jaccard_vs_performance.py

# MAP e curva combinando os 2 conjuntos (900 consultas) → results/combined_900/
venv\Scripts\python.exe scripts\merge_datasets_analysis.py

# Divisão por mediana de Jaccard (900 consultas) → results/jaccard_split/
venv\Scripts\python.exe scripts\jaccard_median_split.py
```

O retrieval sobre o conjunto real (852 consultas × 4 métodos) leva ~30–35 min em CPU (Intel i7-10610U, sem GPU) — a maior parte em `bge_m3_hybrid` (~2 s/consulta). A rodada extra de `bge_m3` denso puro leva só alguns minutos, pois reaproveita o cache de embeddings já computado para o `bge_m3_hybrid`. Os demais scripts (EDA, Jaccard, merge) rodam em segundos a poucos minutos, reaproveitando os resultados já computados.

## Resultados principais

**Conjunto real (852 consultas):**

| Método | MAP | Recall@10 | Tempo (ms) |
|---|---|---|---|
| **BM25** | **0,797** | 0,973 | **15,9** |
| BGE-M3 hybrid | 0,793 | 0,977 | 378,6 |
| E5 hybrid | 0,764 | 0,970 | 48,7 |
| BGE-M3 (denso) | 0,757 | 0,962 | 297,1 |
| E5 (denso) | 0,712 | 0,942 | 283,3 |

Sobre ground truth **real**, o BM25 iguala/supera o BGE-M3 hybrid com 24× menos latência — padrão **oposto** ao do conjunto sintético (ppc_weak), onde o BGE-M3 (denso ou hybrid) lidera com folga e o BM25 é o método mais fraco (MAP 0,559).

**BGE-M3 denso vs. hybrid** (`results/real_295_bge_m3_puro/`): isolando o efeito da fusão híbrida com BM25 via RRF, o ganho é **oposto** nos dois conjuntos — no real, a fusão soma **+0,037 MAP** (0,757 → 0,793); no sintético, ela **subtrai 0,012 MAP** (0,723 → 0,711). A fusão só compensa quando o BM25 isoladamente já tem algo de útil a contribuir, o que depende do perfil lexical dos dados.

**Jaccard × desempenho** (`eda/jaccard_vs_map_resultados.md`, por quartil dentro do conjunto real + ppc_weak como ponto externo): o Jaccard médio do conjunto real (0,649) é bem maior que o do ppc_weak (0,403, construído deliberadamente com baixa sobreposição lexical). No ppc_weak, a vantagem do BGE-M3 hybrid sobre o BM25 é a maior do estudo (+0,152 MAP). Detalhes em `paper_v2/artigo_eramia_2026.md` (Seções 4.4 e 5.1).

**Divisão por mediana de Jaccard** (`results/jaccard_split/jaccard_split_resultados.md`, 900 consultas combinadas, corte único na mediana=0,754): **hipótese forte** — a vantagem semântica (MAP BGE-M3 hybrid − MAP BM25) é **+0,023** na metade de Jaccard inferior e **−0,013** na metade superior. O efeito é real mas modesto em magnitude; ver o relatório completo para a distribuição real/sintético em cada metade (a metade superior é quase só consultas reais — só 2 das 48 sintéticas caem ali).

**MAP combinado (900 consultas, `results/combined_900/`):** ponderando os dois conjuntos pelo número de consultas, o BGE-M3 hybrid (0,789) passa a superar levemente o BM25 (0,784) — inversão em relação ao conjunto real isolado, puxada pela queda acentuada do BM25 no subconjunto sintético.

## Referência

Artigo relacionado (metodologia-base, ground truth sintético via LLM, inclui reranking): `../PPGC-constru-IR/paper/artigo_retrieval_sinapi.md`.
