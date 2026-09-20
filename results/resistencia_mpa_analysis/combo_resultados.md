# mpa + dimensional combinados (gateado por topico) -- Resultados

Continuacao de `mpa_resultados.md`: 'mpa' sozinho (mesmo gateado por topico) piorou o MAP (-0,0064) porque resistencia estrutural e um pequeno conjunto de classes padronizadas compartilhadas por varias pecas do mesmo topico com dimensoes diferentes -- o gate por topico nao ajuda porque a confusao e DENTRO do topico. Hipotese: combinar `mecanico.resistencia.r1` com as 6 regras dimensionais (`comprimento`, `espessura`, `raio`, `multidimensional_2d`x2, `multidimensional_3d`) deve resolver, ja que pecas da mesma classe de resistencia mas dimensao diferente deixam de empatar.

Escopo: as mesmas **15** consultas do teste anterior (todas tem valor de mpa).

## Resultado

| Variante (todas gateadas por topico) | MAP | Delta vs. baseline |
|---|---|---|
| Baseline (hibrido publicado) | 0.6711 | - |
| So `mpa` (teste anterior) | 0.6647 | -0.0064 |
| So dimensional (ablation) | 0.8444 | +0.1734 |
| **`mpa` + dimensional combinados** | **0.8481** | **+0.1771** |

## Por consulta

| product_id | Topico | mpa | dim | AP baseline | AP so mpa | AP so dim | AP combo |
|---|---|---|---|---|---|---|---|
| 3613 | T2 | 6 | 14cm,19cm | 0.3333 | 0.0909 | 0.3333 | 0.1111 |
| 3614 | T2 | 6 | 14cm,19cm | 0.3333 | 0.0909 | 0.3333 | 0.1111 |
| 6503 | T2 | 4 | 14cm,19cm,29cm | 0.5833 | 0.7500 | 0.7500 | 1.0000 |
| 6504 | T2 | 3 | 14cm,19cm,29cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 6517 | T2 | 4 | 14cm,19cm,29cm | 0.6111 | 0.8333 | 0.7500 | 1.0000 |
| 6518 | T2 | 4 | 14cm,19cm,39cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 6593 | T2 | 4 | 14cm,19cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 6594 | T2 | 4 | 14cm,19cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8617 | outliers | 1 | 100mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8618 | outliers | 1 | 150mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8619 | outliers | 1 | 200mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8620 | outliers | 1 | 250mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 11872 | T23 | 20 | 0.1m,0.3m,0.8m,10cm,30cm | 0.0833 | 0.0833 | 1.0000 | 1.0000 |
| 11873 | T23 | 20 | 0.1m,0.5m,0.6m,10cm,50cm | 0.0625 | 0.0625 | 1.0000 | 1.0000 |
| 11874 | T23 | 20 | 0.1m,0.3m,0.6m,10cm,30cm | 0.0588 | 0.0588 | 0.5000 | 0.5000 |
