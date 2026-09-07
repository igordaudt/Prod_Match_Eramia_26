# Reprodutibilidade — o que versionar e o que não

Este documento classifica cada pasta/arquivo do repositório em três grupos:

1. **Essenciais e não regeneráveis** — dados-fonte e código; sem eles, nada mais pode ser recriado.
2. **Resultados finais essenciais** — pequenos, citados diretamente no artigo (tabelas, figuras, `.md` de resultado); tecnicamente regeneráveis, mas versionados para que o artigo seja verificável sem reexecutar o pipeline inteiro.
3. **Derivados/regeneráveis, não versionar** — caches e saídas brutas grandes, recriáveis a partir do grupo 1 pelos próprios scripts.

**Atenção antes do primeiro push:** `results/real_295/sinapi_llm_candidates.jsonl` tem **121 MB**, acima do limite rígido de 100 MB por arquivo do GitHub — um `git push` com esse arquivo adicionado será rejeitado pelo servidor. Ele está listado no grupo 3 e deve ficar no `.gitignore`.

## 1. Essenciais e não regeneráveis (preservar sempre)

| Caminho | O que é | Por que não é regenerável |
|---|---|---|
| `data/sinapi-items-295.tsv` | Corpus real, 5.813 itens SINAPI (fornecedor 295) | Extração da base de produção; não há como recriá-la sem acesso ao banco de origem |
| `data/sinapi_texto_jan26_4851.tsv` | Corpus nativo do benchmark sintético, 4.851 itens | Idem — export do catálogo SINAPI usado como base do `ppc_weak` |
| `data/ground_truth/correlations-295-different-948.tsv` | As 948 correlações produto↔item reais | Subproduto do uso da plataforma PainelConstru; é o *ground truth* real em si |
| `data/ground_truth/retrieval-benchmark-295.json` | As 948 correlações agrupadas em 852 consultas | Idem — gerado uma vez a partir do TSV acima por `prepare_retrieval_data.py`, mas como é o *ground truth* citado no artigo, mantém-se congelado |
| `data/ground_truth/ppc_weak_48.json` | As 48 consultas sintéticas + funções de rotulagem | Definição do benchmark controlado; não é uma amostra aleatória recriável |
| `scripts/*.py` (todos) | Todo o pipeline: preparo de dados, retrieval, EDA, BERTopic, Jaccard, NDCG | É o código-fonte da reprodução — sem ele nada dos outros grupos existe |
| `normalization.py` | Normalização de texto usada pelos scripts de retrieval/EDA | Dependência direta do código acima |
| `requirements.txt` | Dependências Python | Necessário para recriar o ambiente |
| `README.md` | Documentação do repositório e ordem de execução | Guia de reprodução |
| `paper_v2/artigo_eramia_2026.md` | Versão longa do artigo | Fonte primária do texto |
| `paper_v2/latex/artigo_eramia_2026.tex`, `references.bib`, `sbc-template.sty`, `sbc.bst` | Versão SBC (4 páginas) e template | Fonte + template de compilação — sem eles o PDF não é reproduzível |
| `paper_v2/latex/artigo_eramia_2026.pdf` | PDF compilado final | Pequeno (168 KB); manter a versão submetida evita depender de recompilar para conferir o texto exato |
| `paper_v2/latex/artigo_eramia_2026.bbl` | Bibliografia pré-compilada | Pequeno (4 KB); garante que o PDF recompile mesmo sem rodar `bibtex` |
| `paper_v2/latex/figs/*.png` | Figuras usadas no `.tex` | Cópias das figuras finais de `eda/`/`results/` já selecionadas para o artigo |

`data/combined_items_all.tsv` e `data/combined_queries_all.tsv` são, em teoria, regeneráveis por `scripts/build_combined_dataset.py` a partir dos arquivos acima (junção determinística, sem aleatoriedade). Estão listados aqui porque são pequenos (< 1 MB juntos) e alimentam diretamente `eda_bertopic.py`, `categ_map_analysis.py` e os scripts de Jaccard — versioná-los evita ter que refazer a etapa de junção antes de qualquer outra análise.

## 2. Resultados finais essenciais (pequenos, citados no artigo — versionar)

Métricas agregadas, tabelas e figuras que sustentam diretamente números/tabelas/figuras do artigo. Todos pequenos (a maioria < 200 KB):

- `results/real_295/sinapi_llm_metrics.csv`, `sinapi_llm_precision_recall_interpolated.png` (Tabela 1)
- `results/ppc_weak/sinapi_llm_metrics.csv`, `sinapi_llm_precision_recall_interpolated.png` (comparação conjunto sintético)
- `results/combined_900/combined_metrics.csv` e os dois `.png` (MAP combinado, base de 900 consultas)
- `results/jaccard_split/jaccard_split_metrics.csv`, `jaccard_split_resultados.md`, `jaccard_split_map.png`, `precision_recall_by_half.png`, `ndcg_by_half.md`, `ndcg_by_half.png` (Tabelas 3 e 4, Figuras 5 e 6)
- `eda/eda_corpus_ground_truth.png`, `eda_corpus_resultados.md`, `jaccard_por_correlacao.csv` (EDA de Jaccard)
- `eda/bertopic_top30_topicos.png`, `map_delta_por_topico.png`, `map_por_topico_metodo.tsv`, `eda_bertopic_resultados.md`, `item_topics.csv` (EDA BERTopic — inclui o mapeamento item→tópico usado nas respostas sobre T20/T21)
- `eda/categ_map/topic_map_results.csv`, `topic_map_top_bottom.png`, `topic_map_resultados.md` (MAP por tópico)

`results/jaccard_split/jaccard_split_per_query.csv` e `ndcg_per_query.csv` (52 KB e 184 KB) também entram aqui: são o nível per-consulta por trás das Tabelas 3/4 e permitem auditoria sem reprocessar os `.jsonl` brutos do grupo 3.

## 3. Derivados/regeneráveis — não versionar

| Caminho | Tamanho | Como recriar | Por que excluir |
|---|---|---|---|
| `results/real_295/sinapi_llm_candidates.jsonl` | **121 MB** | `python scripts/run_retrieval.py` | Acima do limite de 100 MB do GitHub; é dump bruto de candidatos por consulta/método, insumo intermediário para os scripts de Jaccard/NDCG, não citado diretamente no artigo |
| `results/real_295/sinapi_llm_retrieval_results.json` | 23 MB | idem | Mesmo motivo (redundante com o `.jsonl` acima + `sinapi_llm_metrics.csv`) |
| `results/ppc_weak/sinapi_llm_candidates.jsonl` | 7,7 MB | `python scripts/run_retrieval_ppc_weak.py` | Mesmo papel do equivalente em `real_295`, mantido fora por consistência |
| `results/ppc_weak/sinapi_llm_retrieval_results.json` | 3,1 MB | idem | idem |
| `results/*/sinapi_llm_precision_recall.csv` e `*_by_rank.csv`/`.png`/`_vs_threshold.png` | até 4,8 MB | gerados junto com o retrieval | Curva pooled por threshold — explicitamente **não usada** para comparar métodos no artigo (viés contra BM25, ver Seção de limitações); mantida localmente só para depuração |
| `cache/sinapi_bge_m3/` (embeddings + index) | 23 MB | recalculado automaticamente por `retrieval_sinapi.py` ao rodar sobre o corpus real | Cache de embeddings do BGE-M3; caro em tempo de CPU (sem GPU), mas determinístico — pode ser reconstruído |
| `cache/sinapi_bge_m3_4851/` | 19 MB | idem, sobre o corpus sintético | idem |
| `eda/combined_items_all_embeddings.npy` | 11 MB | recalculado por `eda_bertopic.py`/`categ_map_analysis.py` (cache é reaproveitado entre os dois, ~30s se já existir o modelo baixado) | Cache de embeddings do BERTopic |
| `scripts/__pycache__/` | — | gerado automaticamente pelo Python | Nunca deve ser versionado |
| `results/ppc_weak/run.log` | 32 KB | gerado ao rodar `run_retrieval_ppc_weak.py` | Log de execução, não é resultado analítico |

Nenhum desses arquivos, se apagado, causa perda de informação: todos são recriáveis a partir do código em `scripts/` aplicado sobre os dados do grupo 1, na ordem descrita no `README.md` (`prepare_retrieval_data.py` → `run_retrieval.py`/`run_retrieval_ppc_weak.py` → `build_combined_dataset.py` → `eda_corpus.py`/`eda_bertopic.py`/`categ_map_analysis.py` → `jaccard_median_split.py` → `jaccard_split_precision_recall.py`/`jaccard_split_ndcg.py` → `merge_datasets_analysis.py`).

## Resumo em números

| Grupo | Tamanho aproximado |
|---|---|
| 1 + 2 (o que versionar) | ~17 MB |
| 3 (o que excluir) | ~205 MB |
| Total atual do diretório | ~222 MB |

Versionar apenas os grupos 1 e 2 reduz o repositório de ~222 MB para ~17 MB e evita o bloqueio do GitHub pelo arquivo de 121 MB.
