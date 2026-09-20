# V5 -- Fusao hibrida adaptativa por densidade numerica da query

Conjunto real, 852 consultas, `limit=100`, `k=60`.
Score: `1.0 / (k + rank_BGE-M3) + w_esparso / (k + rank_BM25)`, onde `w_esparso = boost` se `densidade_numerica(query) >= threshold`, senao `1.0`.
Baseline (`w_esparso=1.0` sempre) e identico ao RRF hybrid publicado (MAP esperado ~0,7932).

| Config | threshold | boost | % consultas atributo-pesadas | MAP | Delta MAP vs. baseline | Recall@10 |
|---|---|---|---|---|---|---|
| baseline_1.0_1.0 (atual) | - | 1.0 | 0.0% | 0.7932 | +0.0000 | 0.9767 |
| adaptativo_thr0.00_boost1.5x | 0.00 | 1.5 | 100.0% | 0.7909 | -0.0023 | 0.9744 |
| adaptativo_thr0.00_boost2.0x | 0.00 | 2.0 | 100.0% | 0.7970 | +0.0038 | 0.9767 |
| adaptativo_thr0.00_boost3.0x | 0.00 | 3.0 | 100.0% | 0.7981 | +0.0048 | 0.9714 |
| adaptativo_thr0.00_boost4.0x | 0.00 | 4.0 | 100.0% | 0.7980 | +0.0048 | 0.9714 |
| adaptativo_thr0.00_boost5.0x | 0.00 | 5.0 | 100.0% | 0.7976 | +0.0043 | 0.9726 |
| adaptativo_thr0.10_boost1.5x | 0.10 | 1.5 | 85.6% | 0.7899 | -0.0033 | 0.9744 |
| adaptativo_thr0.10_boost2.0x | 0.10 | 2.0 | 85.6% | 0.7944 | +0.0012 | 0.9767 |
| adaptativo_thr0.10_boost3.0x | 0.10 | 3.0 | 85.6% | 0.7952 | +0.0020 | 0.9714 |
| adaptativo_thr0.10_boost4.0x | 0.10 | 4.0 | 85.6% | 0.7951 | +0.0019 | 0.9714 |
| adaptativo_thr0.10_boost5.0x | 0.10 | 5.0 | 85.6% | 0.7948 | +0.0016 | 0.9726 |
| adaptativo_thr0.15_boost1.5x | 0.15 | 1.5 | 74.4% | 0.7904 | -0.0028 | 0.9744 |
| adaptativo_thr0.15_boost2.0x | 0.15 | 2.0 | 74.4% | 0.7960 | +0.0028 | 0.9767 |
| adaptativo_thr0.15_boost3.0x | 0.15 | 3.0 | 74.4% | 0.7970 | +0.0037 | 0.9726 |
| adaptativo_thr0.15_boost4.0x | 0.15 | 4.0 | 74.4% | 0.7975 | +0.0043 | 0.9726 |
| adaptativo_thr0.15_boost5.0x | 0.15 | 5.0 | 74.4% | 0.7972 | +0.0040 | 0.9738 |
| adaptativo_thr0.20_boost1.5x | 0.20 | 1.5 | 67.1% | 0.7904 | -0.0029 | 0.9744 |
| adaptativo_thr0.20_boost2.0x | 0.20 | 2.0 | 67.1% | 0.7962 | +0.0029 | 0.9767 |
| adaptativo_thr0.20_boost3.0x | 0.20 | 3.0 | 67.1% | 0.7974 | +0.0042 | 0.9750 |
| adaptativo_thr0.20_boost4.0x **<- melhor** | 0.20 | 4.0 | 67.1% | 0.7982 | +0.0050 | 0.9773 |
| adaptativo_thr0.20_boost5.0x | 0.20 | 5.0 | 67.1% | 0.7979 | +0.0047 | 0.9785 |
| adaptativo_thr0.30_boost1.5x | 0.30 | 1.5 | 35.1% | 0.7908 | -0.0024 | 0.9732 |
| adaptativo_thr0.30_boost2.0x | 0.30 | 2.0 | 35.1% | 0.7950 | +0.0017 | 0.9732 |
| adaptativo_thr0.30_boost3.0x | 0.30 | 3.0 | 35.1% | 0.7933 | +0.0000 | 0.9738 |
| adaptativo_thr0.30_boost4.0x | 0.30 | 4.0 | 35.1% | 0.7929 | -0.0003 | 0.9738 |
| adaptativo_thr0.30_boost5.0x | 0.30 | 5.0 | 35.1% | 0.7926 | -0.0007 | 0.9738 |
| adaptativo_thr0.40_boost1.5x | 0.40 | 1.5 | 9.3% | 0.7931 | -0.0001 | 0.9755 |
| adaptativo_thr0.40_boost2.0x | 0.40 | 2.0 | 9.3% | 0.7931 | -0.0001 | 0.9755 |
| adaptativo_thr0.40_boost3.0x | 0.40 | 3.0 | 9.3% | 0.7925 | -0.0007 | 0.9761 |
| adaptativo_thr0.40_boost4.0x | 0.40 | 4.0 | 9.3% | 0.7924 | -0.0008 | 0.9761 |
| adaptativo_thr0.40_boost5.0x | 0.40 | 5.0 | 9.3% | 0.7924 | -0.0008 | 0.9761 |
