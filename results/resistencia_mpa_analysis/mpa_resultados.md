# Analise de 'mpa' (mecanico.resistencia.r1) via param_3.json -- Resultados

Mesma metodologia de `results/param3_regex_validation/` e `results/mm_regex_analysis/`, aplicada a `mecanico.resistencia.r1` de `class_match/param_3.json` -- resistencia estrutural (concreto, aco), ex. "BLOCO... 6 MPA". Motivacao: `mpa` e keyword do topico T2 na analise original de piores topicos, nunca testado isoladamente.

## Regra usada

`mecanico.resistencia.r1`: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(mpa)(?!\w)`

Nota: `mpa` tambem existe em `hidraulico.pressao.r1` (pressao de bombas/compressores) -- a mesma unidade pode significar resistencia estrutural OU pressao hidraulica dependendo do produto. Este teste usa so `mecanico.resistencia.r1`; a ambiguidade semantica entre as duas leituras de "mpa" fica para um teste futuro.

## Resultado principal

- Itens do catalogo com valor: **75** de 5813
- Consultas com valor extraido: **15** de 852 (1.8%)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline (hibrido publicado) | 0.6711 | - |
| Reranking ingenuo (ignora topico) | 0.6628 | -0.0083 |
| **Reranking gateado por topico (adotado)** | **0.6647** | **-0.0064** |

0 de 15 consultas tem o item relevante fora do top-100 candidato -- reranking nao pode corrigir esses casos.

Topicos "fracos" definidos dinamicamente como MAP medio do topico < 0.6.

| Segmento | N | Baseline | Ingenuo | Gateado por topico |
|---|---|---|---|---|
| Topicos fracos (MAP<0.6) | 8 | 0.7326 | 0.7171 | 0.7206 |
| Topicos fortes | 7 | 0.6007 | 0.6007 | 0.6007 |

## Intrusos do reranking ingenuo

- Total de intrusos: **38**
- De topico DIFERENTE da consulta: **4/38** (11%)
- 'Mesmo topico' mas ambos outliers: **0**


## MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 8 | **sim** | 0.7326 | 0.7206 | -0.0120 |
| outliers | outliers (sem tópico coerente) | 4 | nao | 1.0000 | 1.0000 | +0.0000 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm, tubo concreto | 3 | nao | 0.0682 | 0.0682 | +0.0000 |

## Todos os intrusos

| product_id | Topico consulta | Item intruso | Topico intruso | Mesmo topico? | Valor | rank antes->depois |
|---|---|---|---|---|---|---|
| 3613 | T2 | [120505] BLOCO ESTRUTURAL CERAMICO 14 X 19 X 34 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 4->3 |
| 3613 | T2 | [120504] BLOCO ESTRUTURAL CERAMICO 14 X 19 X 29 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 5->4 |
| 3613 | T2 | [120506] BLOCO ESTRUTURAL CERAMICO 14 X 19 X 39 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 6->5 |
| 3613 | T2 | [120507] BLOCO ESTRUTURAL CERAMICO 19 X 19 X 29 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 8->6 |
| 3613 | T2 | [120508] BLOCO ESTRUTURAL CERAMICO 19 X 19 X 39 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 9->7 |
| 3613 | T2 | [120998] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 19 CM, 6,0 MPA (NBR  | T2 | sim | 6 | 14->8 |
| 3613 | T2 | [120999] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 29 CM, 6,0 MPA (NBR  | T2 | sim | 6 | 17->9 |
| 3613 | T2 | [121000] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 39 CM, 6,0 MPA (NBR  | T2 | sim | 6 | 18->10 |
| 3613 | T2 | [120450] BLOCO DE CONCRETO ESTRUTURAL 14 X 19 X 29 CM, FBK 6 MPA (NBR | T48 | NAO | 6 | 21->11 |
| 3613 | T2 | [120466] BLOCO DE CONCRETO ESTRUTURAL 14 X 19 X 39 CM, FBK 6 MPA (NBR | T48 | NAO | 6 | 28->12 |
| 3614 | T2 | [120505] BLOCO ESTRUTURAL CERAMICO 14 X 19 X 34 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 4->3 |
| 3614 | T2 | [120504] BLOCO ESTRUTURAL CERAMICO 14 X 19 X 29 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 5->4 |
| 3614 | T2 | [120506] BLOCO ESTRUTURAL CERAMICO 14 X 19 X 39 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 6->5 |
| 3614 | T2 | [120507] BLOCO ESTRUTURAL CERAMICO 19 X 19 X 29 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 8->6 |
| 3614 | T2 | [120508] BLOCO ESTRUTURAL CERAMICO 19 X 19 X 39 CM, 6,0 MPA (NBR 1527 | T2 | sim | 6 | 9->7 |
| 3614 | T2 | [120998] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 19 CM, 6,0 MPA (NBR  | T2 | sim | 6 | 13->8 |
| 3614 | T2 | [120999] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 29 CM, 6,0 MPA (NBR  | T2 | sim | 6 | 17->9 |
| 3614 | T2 | [121000] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 39 CM, 6,0 MPA (NBR  | T2 | sim | 6 | 18->10 |
| 3614 | T2 | [120450] BLOCO DE CONCRETO ESTRUTURAL 14 X 19 X 29 CM, FBK 6 MPA (NBR | T48 | NAO | 6 | 20->11 |
| 3614 | T2 | [120466] BLOCO DE CONCRETO ESTRUTURAL 14 X 19 X 39 CM, FBK 6 MPA (NBR | T48 | NAO | 6 | 25->12 |
| 6503 | T2 | [127776] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 14 CM, 4,0 MPA (NBR | T2 | sim | 4 | 5->2 |
| 6503 | T2 | [127777] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 19 CM, 4,0 MPA (NBR | T2 | sim | 4 | 7->3 |
| 6503 | T2 | [127701] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 39 CM, 4,0 MPA (NBR  | T2 | sim | 4 | 23->5 |
| 6517 | T2 | [127701] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 39 CM, 4,0 MPA (NBR  | T2 | sim | 4 | 3->2 |
| 6517 | T2 | [127776] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 14 CM, 4,0 MPA (NBR | T2 | sim | 4 | 15->4 |
| 6517 | T2 | [127777] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 19 CM, 4,0 MPA (NBR | T2 | sim | 4 | 17->5 |
| 6518 | T2 | [127700] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 29 CM, 4,0 MPA (NBR  | T2 | sim | 4 | 3->2 |
| 6518 | T2 | [127686] BLOCO ESTRUTURAL CERAMICO - 14 X 19 X 29 CM - 4,0 MPA - NBR  | T2 | sim | 4 | 10->3 |
| 6518 | T2 | [127776] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 14 CM, 4,0 MPA (NBR | T2 | sim | 4 | 13->4 |
| 6518 | T2 | [127777] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 19 CM, 4,0 MPA (NBR | T2 | sim | 4 | 14->5 |
| 6593 | T2 | [127777] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 19 CM, 4,0 MPA (NBR | T2 | sim | 4 | 3->2 |
| 6593 | T2 | [127686] BLOCO ESTRUTURAL CERAMICO - 14 X 19 X 29 CM - 4,0 MPA - NBR  | T2 | sim | 4 | 5->3 |
| 6593 | T2 | [127700] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 29 CM, 4,0 MPA (NBR  | T2 | sim | 4 | 19->4 |
| 6593 | T2 | [127701] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 39 CM, 4,0 MPA (NBR  | T2 | sim | 4 | 20->5 |
| 6594 | T2 | [127776] MEIO BLOCO ESTRUTURAL CERAMICO 14 X 19 X 14 CM, 4,0 MPA (NBR | T2 | sim | 4 | 3->2 |
| 6594 | T2 | [127686] BLOCO ESTRUTURAL CERAMICO - 14 X 19 X 29 CM - 4,0 MPA - NBR  | T2 | sim | 4 | 6->3 |
| 6594 | T2 | [127701] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 39 CM, 4,0 MPA (NBR  | T2 | sim | 4 | 18->4 |
| 6594 | T2 | [127700] CANALETA ESTRUTURAL CERAMICA, 14 X 19 X 29 CM, 4,0 MPA (NBR  | T2 | sim | 4 | 19->5 |
