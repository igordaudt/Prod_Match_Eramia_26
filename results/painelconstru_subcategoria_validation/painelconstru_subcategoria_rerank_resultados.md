# Validacao PainelConstru -- gate por subcategoria

Replica a descoberta de `results/subcategoria_rerank/` (SINAPI) em uma base INDEPENDENTE: 100 consultas amostradas (seed=42) do benchmark PainelConstru (`class_match/ground_truth/benchmark_grouped_v4.json`, escolhido em vez de `t-correlations-full4.tsv` por ja vir agrupado por consulta com `relevant_item_ids`/`subcategory_id` prontos, mesmo formato usado a sessao inteira). Corpus de recuperacao: 12000 itens (itens relevantes das consultas amostradas + distratores aleatorios do catalogo completo de ~110 mil itens, reduzido por custo de indexacao BGE-M3 em CPU).

## Resultado

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline (hibrido BM25+BGE-M3) | 0.7991 | - |
| **Flat subcategoria** | **0.8080** | **+0.0089** |

Para referencia, no SINAPI (852 consultas, oraculo): flat subcategoria = 0.8016 (+0.0084 sobre baseline 0.7932).

