# Os intrusos do reranking por 'kg' sao de topicos/categorias diferentes? -- Resultados

Verificacao da afirmacao: nos casos de valor UNICO de `kg` (os 16 mais arriscados, MAP -0,0645 no agregado em `kg_rerank_resultados.md`), os itens que sobem de posicao por coincidencia numerica pertencem a um topico BERTopic diferente do topico da consulta?

## Resultado
- Consultas analisadas (valor unico de kg): **16**
- Consultas com pelo menos 1 intruso (item promovido por match de kg): **9**
- Total de intrusos: **11**
- Intrusos de **topico diferente** da consulta: **10/11** (91%)
- O(s) 1 caso(s) de 'mesmo topico' e, na verdade, 1 caso(s) onde AMBOS caem em 'outliers' (topico -1, o cesto de itens que o BERTopic nao conseguiu agrupar de forma coerente) -- ou seja, nao e uma categoria real compartilhada, e sim ausencia de categoria dos dois lados. Descontando isso, **100% dos intrusos genuinamente categorizados vem de um topico diferente**.

**Confirma a afirmacao**: os itens que entram por coincidencia de valor de `kg` sao, de fato, de categorias/topicos diferentes -- o match numerico nao tem nenhum vinculo semantico com o produto da consulta.

## Detalhe por consulta

| product_id | Topico consulta | Item intruso | Topico intruso | Mesmo topico? | kg | rank antes->depois |
|---|---|---|---|---|---|---|
| 2398 | T101 | [123500] PERFURATRIZ SOBRE ESTEIRA, TORQUE MAXIMO 600 KGF, PESO MEDIO | T10 | NAO | 1000 | 98->3 |
| 6521 | T111 | [123174] MOLA HIDRAULICA AEREA, PARA PORTAS DE ATE 850 MM E PESO DE A | T13 | NAO | 50 | 33->2 |
| 6613 | T88 | [152368] CARRINHO PLATAFORMA EM MADEIRA COM ESTRUTURA EM ACO, 1500 X  | T101 | NAO | 600 | 58->2 |
| 6613 | T88 | [123168] MISTURADOR DE ARGAMASSA, EIXO HORIZONTAL, CAPACIDADE DE MIST | T7 | NAO | 600 | 63->3 |
| 28014 | outliers | [123827] REBITE DE ALUMINIO VAZADO DE REPUXO, 3,2 X 8 MM (1KG = 1025  | T22 | NAO | 1 | 29->1 |
| 35019 | T101 | [123500] PERFURATRIZ SOBRE ESTEIRA, TORQUE MAXIMO 600 KGF, PESO MEDIO | T10 | NAO | 1000 | 98->3 |
| 46153 | T12 | [122058] EXTINTOR DE INCENDIO PORTATIL COM CARGA DE GAS CARBONICO CO2 | T31 | NAO | 6 | 60->1 |
| 46153 | T12 | [122061] EXTINTOR DE INCENDIO PORTATIL COM CARGA DE PO QUIMICO SECO ( | outliers | NAO | 6 | 81->2 |
| 47089 | outliers | [123097] MARTELO PERFURADOR PNEUMATICO MANUAL, PESO DE 25 KG, COM SIL | outliers | **sim** (mas ambos outliers) | 25 | 100->1 |
| 47189 | T111 | [123174] MOLA HIDRAULICA AEREA, PARA PORTAS DE ATE 850 MM E PESO DE A | T13 | NAO | 50 | 35->2 |
| 47965 | T111 | [123174] MOLA HIDRAULICA AEREA, PARA PORTAS DE ATE 850 MM E PESO DE A | T13 | NAO | 50 | 36->2 |
