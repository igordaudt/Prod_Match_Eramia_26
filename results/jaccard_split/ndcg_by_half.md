# NDCG por Metade de Jaccard — Comparação com MAP e com a Curva Pooled

NDCG calculado por consulta (relevância binária, desconto log2(rank+1)), depois macro-agregado por método e metade — mesma lógica do MAP, sem misturar scores de consultas diferentes.


## NDCG@10

| Metade | BM25 | E5 puro | E5 hybrid | BGE-M3 hybrid | Vant. sem. (BGE-M3 h. − BM25) |
|---|---|---|---|---|---|
| Inferior | 0.7769 | 0.7323 | 0.7816 | 0.7962 | +0.0192 |
| Superior | 0.8914 | 0.7993 | 0.8485 | 0.8813 | -0.0101 |

## NDCG@100

| Metade | BM25 | E5 puro | E5 hybrid | BGE-M3 hybrid | Vant. sem. (BGE-M3 h. − BM25) |
|---|---|---|---|---|---|
| Inferior | 0.7891 | 0.7492 | 0.7936 | 0.8082 | +0.0191 |
| Superior | 0.8921 | 0.8072 | 0.8496 | 0.8821 | -0.0100 |
