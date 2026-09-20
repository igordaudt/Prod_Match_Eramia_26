# Reranking por match exato de valor de potencia ('cv'/'hp') -- Resultados

Mesma metodologia de `results/kg_exact_match_rerank/`, aplicada as unidades de potencia `cv` (cavalo-vapor) e `hp` (horsepower) -- tratadas como a mesma grandeza (sem conversao cv<->hp, so igualdade numerica do valor). Das 852 consultas reais, **22** tem valor(es) de potencia extraiveis via regex (`(\d+(?:[.,]\d+)?)\s*(?:cv|hp)\b`).

## Metodo
1. Baseline: fusao hibrida padrao publicada (BM25 + BGE-M3, RRF `k=60`, `limit=100`).
2. Reranking ingenuo: promove itens com valor de potencia identico, ignorando topico (so para evidenciar o problema).
3. **Reranking gateado por topico (adotado)**: so promove se, alem do valor bater, o item pertencer ao MESMO topico BERTopic da consulta (topico -1 'outliers' nunca conta como match).

## Resultado principal

| Politica | N consultas | MAP | Delta vs. baseline |
|---|---|---|---|
| Baseline (hibrido publicado) | 22 | 0.6162 | - |
| Reranking ingenuo (ignora topico) | 22 | 0.6350 | +0.0189 |
| **Reranking gateado por topico (adotado)** | 22 | **0.6389** | **+0.0227** |

0 de 22 consultas tem o item relevante fora do top-100 candidato -- reranking nao pode corrigir esses casos.

| Segmento | N | Baseline | Ingenuo | Gateado por topico |
|---|---|---|---|---|
| T101+T73 (topicos fracos) | 11 | 0.5391 | 0.5781 | 0.5846 |
| Outros topicos | 11 | 0.6932 | 0.6919 | 0.6932 |

## Intrusos do reranking ingenuo (mesma verificacao feita para 'kg')

- Total de intrusos (itens promovidos por match de potencia, nao relevantes): **21**
- De topico DIFERENTE da consulta: **13/21** (62%)
- 'Mesmo topico' mas na verdade ambos outliers (nao e match categorico real): **0**

| product_id | Topico consulta | Item intruso | Topico intruso | Mesmo topico? | Valor | rank antes->depois |
|---|---|---|---|---|---|---|
| 1447 | T73 | [120986] CAMINHAO TRUCADO, PESO BRUTO TOTAL 23000 KG, CARGA UTIL MAXI | T101 | NAO | 275 | 13->3 |
| 1448 | T73 | [123190] MOTONIVELADORA POTENCIA BASICA LIQUIDA (PRIMEIRA MARCHA) 186 | T10 | NAO | 186 | 38->2 |
| 1458 | T101 | [120975] CAMINHAO TOCO, PESO BRUTO TOTAL 16000 KG, CARGA UTIL MAXIMA  | T73 | NAO | 230 | 8->2 |
| 2316 | T7 | [120535] BOMBA CENTRIFUGA MOTOR ELETRICO TRIFASICO 5HP, DIAMETRO DE S | T72 | NAO | 5 | 5->3 |
| 2316 | T7 | [123167] MISTURADOR DE ARGAMASSA, EIXO HORIZONTAL, CAPACIDADE DE MIST | T7 | sim | 5 | 9->4 |
| 2316 | T7 | [123166] MISTURADOR DE ARGAMASSA, EIXO HORIZONTAL, CAPACIDADE DE MIST | T7 | sim | 3 | 11->5 |
| 2316 | T7 | [122730] LOCACAO DE BOMBA SUBMERSIVEL PARA DRENAGEM E ESGOTAMENTO, MO | T72 | NAO | 3 | 23->6 |
| 2316 | T7 | [123991] SERRA CIRCULAR DE BANCADA, MODELO PICA-PAU, DIAMETRO DE 350  | T7 | sim | 5 | 34->7 |
| 2316 | T7 | [123145] MESA VIBRATORIA COM DIMENSOES DE 2,0 X 1,0 M, COM MOTOR ELET | T7 | sim | 3 | 44->8 |
| 2316 | T7 | [123170] MISTURADOR DUPLO HORIZONTAL DE ALTA TURBULENCIA, CAPACIDADE  | T7 | sim | 5 | 86->9 |
| 5553 | T10 | [124582] TRATOR DE ESTEIRAS, POTENCIA DE 100 HP, PESO OPERACIONAL DE  | T10 | sim | 100 | 16->3 |
| 5553 | T10 | [152289] PERFURATRIZ PARA FURO DIRECIONAL HORIZONTAL (HDD) COM CAPACI | T79 | NAO | 100 | 83->4 |
| 6199 | T10 | [124582] TRATOR DE ESTEIRAS, POTENCIA DE 100 HP, PESO OPERACIONAL DE  | T10 | sim | 100 | 16->3 |
| 6199 | T10 | [152289] PERFURATRIZ PARA FURO DIRECIONAL HORIZONTAL (HDD) COM CAPACI | T79 | NAO | 100 | 83->4 |
| 6523 | T10 | [125068] VIBRADOR DE IMERSAO, DIAMETRO DA PONTEIRA DE *45* MM, COM MO | T7 | NAO | 2 | 20->2 |
| 6608 | T7 | [121995] ESCAVADEIRA HIDRAULICA SOBRE ESTEIRAS, CACAMBA 0,80 M3, PESO | T10 | NAO | 110 | 12->2 |
| 6608 | T7 | [125072] VIBROACABADORA DE ASFALTO SOBRE ESTEIRAS, LARG. PAVIM. 2,60  | T10 | NAO | 110 | 16->3 |
| 6608 | T7 | [121224] COMPRESSOR DE AR REBOCAVEL VAZAO 400 PCM, PRESSAO EFETIVA DE | outliers | NAO | 110 | 22->4 |
| 6608 | T7 | [123927] ROLO COMPACTADOR DE PNEUS, ESTATICO, PRESSAO VARIAVEL, POTEN | T10 | NAO | 110 | 38->5 |
| 35700 | T10 | [124582] TRATOR DE ESTEIRAS, POTENCIA DE 100 HP, PESO OPERACIONAL DE  | T10 | sim | 100 | 16->3 |
| 35700 | T10 | [152289] PERFURATRIZ PARA FURO DIRECIONAL HORIZONTAL (HDD) COM CAPACI | T79 | NAO | 100 | 83->4 |

## Detalhamento por topico (politica adotada: gateada por topico)

| Topico | Palavras-chave | N | MAP baseline | MAP gateado por topico | Delta |
|---|---|---|---|---|---|
| T7 | motor, cv, capacidade, motor diesel, diesel, potencia | 4 | 0.6250 | 0.6250 | +0.0000 |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 6 | 0.6875 | 0.6875 | +0.0000 |
| T42 | litros, litros tampa, tampa caixa, asfaltica, caixa dagua, dagua | 1 | 1.0000 | 1.0000 | +0.0000 |
| T73 | distancia, kg, carroceria, eixos, cv inclui, peso bruto | 6 | 0.7037 | 0.7037 | +0.0000 |
| T101 | kg, cabine, cv inclui, peso bruto, total, chassi | 5 | 0.3417 | 0.4417 | +0.1000 |

## Todas as consultas (baseline vs. politica adotada)

| product_id | Topico | Valores potencia | AP baseline | AP gateado por topico | Delta |
|---|---|---|---|---|---|
| 6702 | T101 | 256 | 0.5000 | 1.0000 | +0.5000 |
| 923 | T7 | 10 | 0.5000 | 0.5000 | +0.0000 |
| 1447 | T73 | 275 | 0.1111 | 0.1111 | +0.0000 |
| 1448 | T73 | 186 | 0.1111 | 0.1111 | +0.0000 |
| 1457 | T101 | 326 | 0.3333 | 0.3333 | +0.0000 |
| 1458 | T101 | 230 | 0.2917 | 0.2917 | +0.0000 |
| 2316 | T7 | 3,5 | 0.5000 | 0.5000 | +0.0000 |
| 5553 | T10 | 100 | 0.5000 | 0.5000 | +0.0000 |
| 6027 | T7 | 10 | 0.5000 | 0.5000 | +0.0000 |
| 6198 | T10 | 134 | 1.0000 | 1.0000 | +0.0000 |
| 6199 | T10 | 100 | 0.5000 | 0.5000 | +0.0000 |
| 6444 | T73 | 175 | 1.0000 | 1.0000 | +0.0000 |
| 6462 | T42 | 140 | 1.0000 | 1.0000 | +0.0000 |
| 6463 | T10 | 99 | 1.0000 | 1.0000 | +0.0000 |
| 6523 | T10 | 2 | 0.6250 | 0.6250 | +0.0000 |
| 6608 | T7 | 110 | 1.0000 | 1.0000 | +0.0000 |
| 6698 | T73 | 175 | 1.0000 | 1.0000 | +0.0000 |
| 6699 | T73 | 226 | 1.0000 | 1.0000 | +0.0000 |
| 6700 | T73 | 167 | 1.0000 | 1.0000 | +0.0000 |
| 6701 | T101 | 286 | 0.2917 | 0.2917 | +0.0000 |
| 14452 | T101 | 326 | 0.2917 | 0.2917 | +0.0000 |
| 35700 | T10 | 100 | 0.5000 | 0.5000 | +0.0000 |
