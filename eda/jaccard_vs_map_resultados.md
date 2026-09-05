# Jaccard × Desempenho por Método — fornecedor 295 (real) vs. ppc_weak (sintético)

## (a) Fornecedor 295 (real, 852 consultas) — MAP por quartil de Jaccard

| Quartil | Jaccard (faixa) | Jaccard médio | N consultas | bm25 | e5 | e5_hybrid | bge_m3_hybrid |
|---|---|---|---|---|---|---|---|
| Q1 (menor) | 0.000–0.500 | 0.285 | 218 | 0.709 | 0.628 | 0.704 | 0.714 |
| Q2 | 0.519–0.765 | 0.670 | 222 | 0.776 | 0.745 | 0.767 | 0.782 |
| Q3 | 0.767–0.810 | 0.793 | 202 | 0.886 | 0.780 | 0.833 | 0.866 |
| Q4 (maior) | 0.812–1.000 | 0.866 | 210 | 0.823 | 0.698 | 0.756 | 0.818 |

- Correlação de Spearman entre Jaccard e (MAP BGE-M3 hybrid − MAP BM25), por consulta: **-0.070**
  (negativa = quanto menor o Jaccard, maior a vantagem do BGE-M3 hybrid sobre o BM25)

## (b) ppc_weak (sintético, 48 consultas, 16 itens)

- Jaccard médio (consulta × descrição original do item): **0.403**
- Jaccard mediano: 0.380

| Método | MAP |
|---|---|
| bm25 | 0.559 |
| e5 | 0.580 |
| e5_hybrid | 0.675 |
| bge_m3_hybrid | 0.711 |
| bge_m3 | 0.723 |

## (c) Visão combinada — Jaccard médio × MAP por método

| Conjunto | N | Jaccard médio | bm25 | e5 | e5_hybrid | bge_m3_hybrid |
|---|---|---|---|---|---|---|
| ppc_weak (sintético) | 48 | 0.403 | 0.559 | 0.580 | 0.675 | 0.711 |
| fornecedor 295 — Q1 (menor) | 218 | 0.285 | 0.709 | 0.628 | 0.704 | 0.714 |
| fornecedor 295 — Q2 | 222 | 0.670 | 0.776 | 0.745 | 0.767 | 0.782 |
| fornecedor 295 — Q3 | 202 | 0.793 | 0.886 | 0.780 | 0.833 | 0.866 |
| fornecedor 295 — Q4 (maior) | 210 | 0.866 | 0.823 | 0.698 | 0.756 | 0.818 |
| fornecedor 295 — geral | 852 | 0.649 | 0.797 | 0.712 | 0.764 | 0.793 |
