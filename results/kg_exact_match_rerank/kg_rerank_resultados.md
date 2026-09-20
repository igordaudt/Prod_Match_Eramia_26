# Reranking por match exato de valor de 'kg' -- Resultados

Continuacao de `results/regex_kg_audit/`: das 852 consultas reais, **27** tem valor(es) numerico(s) de `kg` extraiveis via regex (`(\d+(?:[.,]\d+)?)\s*kg\b`). Para cada uma, alem do mesmo regex aplicado as 295 descricoes do catalogo, comparamos o valor da consulta com o valor de cada item candidato.

## Metodo
1. Baseline: fusao hibrida padrao publicada (BM25 + BGE-M3, RRF `k=60`, `limit=100`) -- sem nenhuma mudanca em relacao ao pipeline atual.
2. Reranking: dentro da MESMA lista candidata (sem nova busca), promove os itens cujo conjunto de valores `kg` tem interseccao com o da consulta -- mais valores batendo = posicao mais alta; ordenacao estavel preserva a ordem relativa original em caso de empate (inclusive entre itens sem nenhum valor `kg`, que ficam no fim, na ordem que a fusao hibrida ja tinha decidido).

## Resultado principal

Tecnica ADOTADA: reranking por match exato de `kg` **gateado por topico** -- um item so e promovido se (a) tiver valor de `kg` identico ao da consulta E (b) pertencer ao MESMO topico BERTopic da consulta (`rerank_by_kg_match_same_topic`; topico `-1` "outliers" nunca conta como match, ver secao abaixo). Comparado contra o baseline (fusao hibrida publicada, sem mudanca) e contra a versao ingenua do reranking (match de `kg` sem olhar topico, "sempre"), que serve so para ilustrar POR QUE o gate por topico e necessario.

| Politica | N consultas | MAP | Delta vs. baseline |
|---|---|---|---|
| Baseline (hibrido publicado, sem rerank) | 27 | 0.6599 | - |
| Reranking ingenuo por kg ("sempre", ignora topico) | 27 | 0.6585 | -0.0013 |
| **Reranking por kg gateado por topico (adotado)** | 27 | **0.6967** | **+0.0369** |

0 de 27 consultas tem o item relevante FORA do top-100 candidato do hibrido -- nesses casos nenhum reranking pode corrigir (a lista de candidatos em si precisaria mudar, nao so a ordem). Nao houve nenhum caso assim aqui.

## Por que gatear por topico -- o reranking ingenuo e quase neutro no geral, mas esconde dois efeitos opostos

Separando as consultas por quantos valores de `kg` elas tem, aparece um padrao: quando a consulta so tem **1** valor de `kg`, ele costuma ser peso de EMBALAGEM (saco de cimento, balde de massa, rolo de arame) -- um valor comum a produtos de categorias completamente diferentes, que nao discrimina nada e so serve para embaralhar itens empatados com um 'intruso' de outra categoria (ver `kg_rerank_intruders.md`: 10 dos 11 intrusos promovidos pelo reranking ingenuo vinham de um topico diferente da consulta). Quando a consulta tem **2+** valores, eles costumam ser especificacao conjunta do produto (ex. peso bruto + carga util de caminhao) -- aí um match exato e um sinal forte e confiavel, e o item certo esta, por definicao, no mesmo topico de si mesmo.

| Segmento | N | Baseline | Reranking ingenuo ("sempre") | Gateado por topico (adotado) |
|---|---|---|---|---|
| 1 valor de kg (embalagem) | 16 | 0.7429 | 0.6784 | 0.7429 |
| 2+ valores de kg (spec discriminante, = T101+T73) | 11 | 0.5391 | 0.6297 | 0.6297 |

O gate por topico e cirurgico: no segmento de 1 valor, ele recupera **exatamente** o MAP do baseline (zero dano -- nenhum intruso de mesmo topico apareceu nesses casos); no segmento de 2+ valores, ele preserva **todo** o ganho do reranking ingenuo (nada e bloqueado, porque o item certo sempre esta no proprio topico). O topico `-1` ("outliers", itens que o BERTopic nao conseguiu agrupar de forma coerente) e explicitamente excluido da regra de match -- dois itens ambos sem categoria nao sao uma correspondencia categorica real (achado concreto: sem essa exclusao, "MASSA ACRILICA... 25 KG" (outliers) ainda perdia posicao para "MARTELO PERFURADOR PNEUMATICO... 25 KG" (tambem outliers), apesar de nao terem nenhuma relacao).

## Detalhamento por topico (politica adotada: gateada por topico)

| Topico | Palavras-chave | N | MAP baseline | MAP gateado por topico | Delta |
|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 2 | 1.0000 | 1.0000 | +0.0000 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 3 | 0.4619 | 0.4619 | +0.0000 |
| T73 | distancia, kg, carroceria, eixos, cv inclui, peso bruto | 6 | 0.7037 | 0.7222 | +0.0185 |
| T88 | poste, poste concreto, kg, circular, bolsa, bolsa bolsa | 2 | 1.0000 | 1.0000 | +0.0000 |
| T101 | kg, cabine, cv inclui, peso bruto, total, chassi | 10 | 0.4208 | 0.5093 | +0.0885 |
| T111 | roscavel flanges, vedacao mm, flanges anel, anel vedacao, flanges, mm caixa | 3 | 1.0000 | 1.0000 | +0.0000 |
| T114 | impermeabilizante, liquido, epoxi, base resina, resina, adesivo | 1 | 1.0000 | 1.0000 | +0.0000 |

## Consultas com maior mudanca (politica adotada, positiva ou negativa)

| product_id | Topico | Valores kg (consulta) | AP baseline | AP gateado por topico | Delta |
|---|---|---|---|---|---|
| 6702 | T101 | 16540,23000 | 0.5000 | 1.0000 | +0.5000 |
| 6701 | T101 | 15460,23000 | 0.2917 | 0.6429 | +0.3512 |
| 1447 | T73 | 10780,16000 | 0.1111 | 0.1667 | +0.0556 |
| 1448 | T73 | 11030,16000 | 0.1111 | 0.1667 | +0.0556 |
| 1458 | T101 | 15935,23000 | 0.2917 | 0.3250 | +0.0333 |
| 1457 | T101 | 15378,23000 | 0.3333 | 0.3333 | +0.0000 |
| 2398 | T101 | 1000 | 0.5000 | 0.5000 | +0.0000 |
| 2399 | T101 | 1200 | 0.5000 | 0.5000 | +0.0000 |
| 6444 | T73 | 9200,13200 | 1.0000 | 1.0000 | +0.0000 |
| 6521 | T111 | 50 | 1.0000 | 1.0000 | +0.0000 |
| 6586 | T101 | 1000 | 0.5000 | 0.5000 | +0.0000 |
| 6613 | T88 | 600 | 1.0000 | 1.0000 | +0.0000 |
| 6614 | T88 | 500 | 1.0000 | 1.0000 | +0.0000 |
| 6698 | T73 | 7400,10700 | 1.0000 | 1.0000 | +0.0000 |
| 6699 | T73 | 10830,16000 | 1.0000 | 1.0000 | +0.0000 |
