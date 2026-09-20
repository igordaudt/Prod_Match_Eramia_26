# V4 -- Peso denso x esparso na fusao RRF do BGE-M3 hybrid

Conjunto real, 852 consultas, `limit=100`, `k=60` (mesmo k do RRF atual).
Score ponderado: `w_denso / (k + rank_BGE-M3) + w_esparso / (k + rank_BM25)`.
Baseline (`w_denso=w_esparso=1.0`) e matematicamente identico ao RRF hybrid usado em todos os resultados publicados (MAP esperado ~0,7932).

| Config | w_denso | w_esparso | MAP | Delta MAP vs. baseline | Recall@10 |
|---|---|---|---|---|---|
| baseline_1.0_1.0 (atual) | 1.0 | 1.0 | 0.7932 | +0.0000 | 0.9767 |
| denso_1.5x | 1.5 | 1.0 | 0.7745 | -0.0187 | 0.9734 |
| denso_2x | 2.0 | 1.0 | 0.7683 | -0.0250 | 0.9722 |
| denso_3x | 3.0 | 1.0 | 0.7634 | -0.0298 | 0.9654 |
| esparso_1.5x | 1.0 | 1.5 | 0.7909 | -0.0023 | 0.9744 |
| esparso_2x | 1.0 | 2.0 | 0.7970 | +0.0038 | 0.9767 |
| esparso_3x | 1.0 | 3.0 | 0.7981 | +0.0048 | 0.9714 |
