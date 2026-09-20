# pressao + dimensional combinados (gateado por topico) -- Resultados

Continuacao de `mecanico_hidraulico_resultados.md`: `hidraulico.pressao.r1` sozinho deu resultado quase identico a `mecanico.resistencia.r1` (MAP -0,0056 vs -0,0064), porque a maioria das consultas de pressao neste benchmark SAO as mesmas consultas de bloco estrutural (T2), capturadas via a unidade compartilhada `mpa`. Mesma correcao aplicada: combinar com as 6 regras dimensionais.

Escopo: as mesmas **17** consultas do teste anterior de pressao.

## Resultado

| Variante (todas gateadas por topico) | MAP | Delta vs. baseline |
|---|---|---|
| Baseline (hibrido publicado) | 0.6877 | - |
| So `pressao` (teste anterior) | 0.6820 | -0.0056 |
| So dimensional (ablation) | 0.8407 | +0.1530 |
| **`pressao` + dimensional combinados** | **0.8440** | **+0.1563** |

## Por consulta

| product_id | Topico | pressao | dim | AP baseline | AP so pressao | AP so dim | AP combo |
|---|---|---|---|---|---|---|---|
| 3613 | T2 | 6mpa | 14cm,19cm | 0.3333 | 0.0909 | 0.3333 | 0.1111 |
| 3614 | T2 | 6mpa | 14cm,19cm | 0.3333 | 0.0909 | 0.3333 | 0.1111 |
| 6503 | T2 | 4mpa | 14cm,19cm,29cm | 0.5833 | 0.7500 | 0.7500 | 1.0000 |
| 6504 | T2 | 3mpa | 14cm,19cm,29cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 6517 | T2 | 4mpa | 14cm,19cm,29cm | 0.6111 | 0.8333 | 0.7500 | 1.0000 |
| 6518 | T2 | 4mpa | 14cm,19cm,39cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 6523 | T10 | 9.7bar |  | 0.6250 | 0.6250 | 0.6250 | 0.6250 |
| 6593 | T2 | 4mpa | 14cm,19cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 6594 | T2 | 4mpa | 14cm,19cm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8617 | outliers | 1mpa | 100mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8618 | outliers | 1mpa | 150mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8619 | outliers | 1mpa | 200mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 8620 | outliers | 1mpa | 250mm | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 11872 | T23 | 20mpa | 0.1m,0.3m,0.8m,10cm,30cm | 0.0833 | 0.0833 | 1.0000 | 1.0000 |
| 11873 | T23 | 20mpa | 0.1m,0.5m,0.6m,10cm,50cm | 0.0625 | 0.0625 | 1.0000 | 1.0000 |
| 11874 | T23 | 20mpa | 0.1m,0.3m,0.6m,10cm,30cm | 0.0588 | 0.0588 | 0.5000 | 0.5000 |
| 12299 | outliers | 400psi |  | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
