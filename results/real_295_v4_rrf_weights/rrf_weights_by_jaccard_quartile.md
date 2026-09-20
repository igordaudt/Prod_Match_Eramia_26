# V4 por quartil de Jaccard -- peso denso x esparso na fusao RRF

Mesma metodologia de quartis de `scripts/jaccard_vs_performance.py` (media de Jaccard por consulta, `pd.qcut` em 4 grupos de tamanho igual).

| Quartil | N | Jaccard (min-max, media) | baseline_1.0_1.0 (atual) | denso_1.5x | denso_2x | denso_3x | esparso_1.5x | esparso_2x | esparso_3x |
|---|---|---|---|---|---|---|---|---|---|
| Q1 (menor) | 218 | 0.000-0.500 (0.285) | 0.7137 | 0.7054 | 0.7038 | 0.7037 | 0.7175 | 0.7217 | 0.7173 |
| Q2 | 222 | 0.519-0.765 (0.670) | 0.7822 | 0.7676 | 0.7633 | 0.7589 | 0.7715 | 0.7745 | 0.7733 |
| Q3 | 202 | 0.767-0.810 (0.793) | 0.8657 | 0.8328 | 0.8162 | 0.7993 | 0.8671 | 0.8768 | 0.8834 |
| Q4 (maior) | 210 | 0.812-1.000 (0.866) | 0.8177 | 0.7975 | 0.7943 | 0.7956 | 0.8143 | 0.8223 | 0.8261 |

## Delta de MAP vs. baseline (1:1), por quartil

| Quartil | denso_1.5x | denso_2x | denso_3x | esparso_1.5x | esparso_2x | esparso_3x |
|---|---|---|---|---|---|---|
| Q1 (menor) | -0.0084 | -0.0100 | -0.0101 | +0.0037 | +0.0080 | +0.0035 |
| Q2 | -0.0145 | -0.0188 | -0.0232 | -0.0106 | -0.0077 | -0.0089 |
| Q3 | -0.0330 | -0.0495 | -0.0664 | +0.0014 | +0.0111 | +0.0177 |
| Q4 (maior) | -0.0202 | -0.0234 | -0.0221 | -0.0034 | +0.0046 | +0.0084 |
