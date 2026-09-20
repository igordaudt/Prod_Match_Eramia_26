# Analise de 'mm' (dimensional) via param_3.json -- Resultados (rodada 2, 6 regras)

Mesma metodologia de `results/param3_regex_validation/` (kg, cv/hp), aplicada as regras dimensionais de `class_match/param_3.json`. **Completa a rodada 1** (que usou so `comprimento.r1_metricos` + `espessura.r1_contextual`, MAP gateado 0,8313) adicionando `raio.r1`, `multidimensional_2d.r1_metricos`, `multidimensional_2d.r2_misto_polegada_metrico` e `multidimensional_3d.r1_metricos` -- por pedido explicito, ainda SEM `diametro` nem `area`/`volume`.

## Regras usadas (6)

- `dimensional.comprimento.r1_metricos`: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(mm|mil[ií]metro(?:s)?|cm|cent[ií]metro(?:s)?|m|metro(?:s)?)(?!\w)`
- `dimensional.espessura.r1_contextual`: `(?:esp(?:essura)?\s*[:=]?\s*)\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(mm|cm|m|\"|pol\b|pol\.|polegada(?:s)?)`
- `dimensional.raio.r1`: `(?:\br\b|raio)\s*[:=]?\s?(\d+(?:[\.,]\d+)?)(?:\s?)(mm|cm|m)?`
- `dimensional.multidimensional_2d.r1_metricos`: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(?:mm|cm|m)?\s?[x×]\s?\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(mm|cm|m)(?!\w)`
- `dimensional.multidimensional_2d.r2_misto_polegada_metrico`: `(?<!\w)\*?(\d+(?:[\.,]\d+)?|(?:\d+\s+)?\d+\s*[/\u2044]\s*\d+|¾|½|¼|⅛|⅜|⅝|⅞)\*?(?:\s?)(\"|pol\b|pol\.|polegada(?:s)?)\s?[x×]\s?\*?(\d+(?:[\.,]\d+)?)\*?(mm|cm|m)(?!\w)`
- `dimensional.multidimensional_3d.r1_metricos`: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(mm|cm|m)?\s?[x×]\s?\*?(\d+(?:[\.,]\d+)?)\*?(mm|cm|m)?\s?[x×]\s?\*?(\d+(?:[\.,]\d+)?)\*?(mm|cm|m)?(?:\s?)(mm|cm|m)?(?!\w)`

As duas regras `multidimensional_*` foram adicionadas justamente para cobrir o caso "600 X 2100 MM" que a rodada 1 perdia parcialmente (so capturava o 2100, colado a unidade -- o 600 ficava de fora). Isso motivou essa rodada 2: a regressao encontrada em T61 (portas) na rodada 1 era exatamente esse padrao.

Unidades (`mm`, `cm`, `m`, `pol`) NAO sao intercambiaveis entre si -- match exige mesmo valor E mesma unidade, canonicalizando formas por extenso/acentuadas (ex. "milímetros" -> `mm`). Em `raio.r1` (unidade opcional na regra), descartamos ocorrencias sem unidade explicita -- sem ela nao da pra saber a escala.

## Resultado principal

- Itens do catalogo com valor: **3231** de 5813
- Consultas com valor extraido: **548** de 852 (64.3%)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline (hibrido publicado) | 0.7906 | - |
| Reranking ingenuo (ignora topico) | 0.8214 | +0.0309 |
| **Reranking gateado por topico (adotado)** | **0.8342** | **+0.0437** |

0 de 548 consultas tem o item relevante fora do top-100 candidato -- reranking nao pode corrigir esses casos.

Topicos "fracos" definidos dinamicamente como MAP medio do topico < 0.6 (diferente de kg/cv-hp, que usaram T101/T73 fixos -- `mm` se espalha por muito mais topicos).

| Segmento | N | Baseline | Ingenuo | Gateado por topico |
|---|---|---|---|---|
| Topicos fracos (MAP<0.6) | 141 | 0.5653 | 0.6014 | 0.6228 |
| Topicos fortes | 407 | 0.8686 | 0.8977 | 0.9075 |

## Comparacao com a rodada 1 (so comprimento + espessura)

| Rodada | Regras | N consultas | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|
| 1 | comprimento + espessura (2) | 546 | 0.7931 | 0.8313 | +0.0383 |
| 2 (esta) | + raio + multidim_2d(x2) + multidim_3d (6) | 548 | 0.7906 | 0.8342 | +0.0437 |

**T61 (portas), a unica regressao da rodada 1** (0,3263 -> 0,2875, delta -0,0388): nesta rodada, com `multidimensional_2d` cobrindo "AxB mm" por completo, MAP baseline=0.3263 -> gateado=0.2875 (delta -0.0388, n=10).


## Intrusos do reranking ingenuo

- Total de intrusos (itens promovidos por match dimensional, nao relevantes): **6604**
- De topico DIFERENTE da consulta: **5195/6604** (79%)
- 'Mesmo topico' mas ambos outliers (nao e match categorico real): **197**


## MAP por topico (top 20 por N de consultas; ver mm_por_topico.csv para a lista completa)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 122 | nao | 0.8653 | 0.8653 | +0.0000 |
| T21 | agua esgoto, densidade pead, polietileno alta, alta densidade, densidade, pn | 48 | **sim** | 0.6753 | 0.6823 | +0.0069 |
| T22 | janela, brilhante, bandeira, aluminio, vidro, janela correr | 25 | nao | 0.7923 | 0.8036 | +0.0113 |
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 25 | **sim** | 0.6439 | 0.7867 | +0.1427 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm, tubo concreto | 23 | nao | 0.7640 | 0.9710 | +0.2070 |
| T90 | resistencia dan, dan, extensao resistencia, armado secao, extensao, poste concreto | 22 | nao | 0.9545 | 1.0000 | +0.0455 |
| T81 | resistencia dan, dan, extensao resistencia, armado secao, extensao, poste concreto | 21 | nao | 0.9444 | 1.0000 | +0.0556 |
| T75 | forma, madeira, mm sinapi, 11, concreto, mm chapa | 20 | nao | 0.6056 | 0.8053 | +0.1997 |
| T55 | circular, dan, resistencia dan, extensao resistencia, armado secao, poste concreto | 15 | nao | 1.0000 | 1.0000 | +0.0000 |
| T125 | termoplastica, manta, mm nbr, lisa, pead, nbr | 14 | **sim** | 0.5000 | 0.5000 | +0.0000 |
| T83 | faces, termoplastica, bolsa bolsa, manta, mm nbr, bolsa | 14 | nao | 1.0000 | 1.0000 | +0.0000 |
| T101 | kg, cabine, cv inclui, peso bruto, total, chassi | 11 | **sim** | 0.4280 | 0.5076 | +0.0795 |
| T7 | motor, cv, capacidade, motor diesel, diesel, potencia | 11 | nao | 1.0000 | 1.0000 | +0.0000 |
| T100 | fogo, bandeira, mm sinapi, mecanica, 15 mm, aco galvanizado | 11 | nao | 1.0000 | 1.0000 | +0.0000 |
| T61 | capa, marco, folha, dobradicas, pronta, alizares | 10 | **sim** | 0.3263 | 0.2875 | -0.0388 |
| T59 | mm amianto, amianto, ondulada, fibrocimento, telha, telha fibrocimento | 10 | **sim** | 0.4500 | 0.4500 | +0.0000 |
| T3 | angelim, regiao, regiao bruta, bruta, 25, 75 | 9 | nao | 0.8419 | 0.8611 | +0.0192 |
| T32 | tubo pvc, corrugado, 5688, nbr 5688, luva correr, rede coletora | 9 | nao | 0.8419 | 1.0000 | +0.1581 |
| T24 | polido, granito, cm, regiao, marmore, andorinha | 8 | nao | 0.6250 | 0.6250 | +0.0000 |
| T107 | forro, forro pvc, regua, cm espessura, borda, mineral | 8 | nao | 0.8958 | 0.8958 | +0.0000 |
