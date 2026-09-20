# Regras eletricas restantes via param_3.json -- Resultados

Fecha a categoria `eletrico` (`tensao.r1` e `potencia_eletrica.r1` ja testados em `eletrico_resultados.md`). Inclui 3 regras NUMERICAS (`corrente`, `frequencia`, `vias_condutoras`) e 3 regras CATEGORICAS/BOOLEANAS (`categoria_rede` -- codigo tipo "CAT5E"; `tensao.r2_bivolt` -- so presenca da palavra; `tensao.r3_fases_polos` -- monofasico/bifasico/trifasico/monopolar/bipolar/tripolar). As categoricas/booleanas usam a mesma mecanica de match por interseccao de conjunto, so que comparando strings em vez de valores numericos.

## Resumo

| Atributo | Regra | Consultas | MAP baseline | MAP ingenuo | MAP gateado | Delta gateado |
|---|---|---|---|---|---|---|
| Corrente eletrica (a/ma) | `eletrico.corrente.r1` | 52 | 0.8136 | 0.8143 | 0.8161 | +0.0025 |
| Frequencia (hz) *(n=1, pouco confiavel)* | `eletrico.frequencia.r1` | 1 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| Vias condutoras (N condutor/par/fio) | `eletrico.vias_condutoras.r1_quantidade` | 9 | 0.7315 | 0.6362 | 1.0000 | +0.2685 |
| Categoria de rede (CAT5, CAT6A...) | `eletrico.categoria_rede.r1` | 8 | 0.8438 | 0.8854 | 1.0000 | +0.1562 |
| Bivolt (presenca da palavra) *(n=1, pouco confiavel)* | `eletrico.tensao.r2_bivolt` | 1 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| Fases/polos (monofasico...tripolar) | `eletrico.tensao.r3_fases_polos` | 3 | 0.8333 | 0.8333 | 0.8333 | +0.0000 |

## Corrente eletrica (a/ma) (`eletrico.corrente.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(a|ma)(?!\w)`

- Itens do catalogo com valor: **302** de 5813
- Consultas com valor extraido: **52**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.8136 | - |
| Reranking ingenuo | 0.8143 | +0.0007 |
| **Gateado por topico (adotado)** | **0.8161** | **+0.0025** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 1 | 1.0000 | 1.0000 | 1.0000 |
| Fortes | 51 | 0.8100 | 0.8107 | 0.8125 |

Intrusos: **108**, de topico diferente: **64** (59%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T22 | janela, brilhante, bandeira, aluminio, vidro, janela correr | 20 | nao | 0.7403 | 0.7384 | -0.0019 |
| T107 | forro, forro pvc, regua, cm espessura, borda, mineral | 8 | nao | 0.8958 | 0.8958 | +0.0000 |
| outliers | outliers (sem tópico coerente) | 4 | nao | 0.5417 | 0.5417 | +0.0000 |
| T17 | eucalipto, tratamento, regiao, preto, cm mm, painel | 4 | nao | 1.0000 | 1.0000 | +0.0000 |
| T75 | forma, madeira, mm sinapi, 11, concreto, mm chapa | 3 | nao | 0.6120 | 0.6120 | +0.0000 |
| T50 | perfil aco, espelho, laminado, dobradica, mm anel, perfil | 2 | nao | 0.6667 | 0.7500 | +0.0833 |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T69 | moldado, comp, contribuintes, guia, concreto premoldado, mm malha | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T48 | mpa nbr, mpa, estrutural, bloco, canaleta, nbr | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T37 | cobre anel, tubulacao, disjuntor, espuma polietileno, polietileno expandido, mm luva | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T7 | motor, cv, capacidade, motor diesel, diesel, potencia | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 1 | **sim** | 1.0000 | 1.0000 | +0.0000 |
| T47 | perfurada, mm virola, virola tampa, galvanizado espessura, removivel, virola | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T29 | disjuntor, ac, tripolar, corrente, vazao maxima, plana | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Frequencia (hz) (`eletrico.frequencia.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(hz)(?!\w)`

- Itens do catalogo com valor: **39** de 5813
- Consultas com valor extraido: **1** *(amostra muito pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 1.0000 | - |
| Reranking ingenuo | 1.0000 | +0.0000 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 1 | 1.0000 | 1.0000 | 1.0000 |

Intrusos: **0**, de topico diferente: **0**

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T29 | disjuntor, ac, tripolar, corrente, vazao maxima, plana | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Vias condutoras (N condutor/par/fio) (`eletrico.vias_condutoras.r1_quantidade`)

Regra: `(?<!\w)(\d+)(?:\s?)(condutor(?:es)?|par(?:es)?|fio(?:s)?)(?!\w)`

- Itens do catalogo com valor: **125** de 5813
- Consultas com valor extraido: **9**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7315 | - |
| Reranking ingenuo | 0.6362 | -0.0952 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.2685** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 9 | 0.7315 | 0.6362 | 1.0000 |

Intrusos: **15**, de topico diferente: **13** (87%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T85 | cat, categoria, 5e, pares, par, patch | 7 | nao | 0.6548 | 1.0000 | +0.3452 |
| T30 | bsp, rosca bsp, galvanizado rosca, ferro, ferro galvanizado, curva graus | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T48 | mpa nbr, mpa, estrutural, bloco, canaleta, nbr | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Categoria de rede (CAT5, CAT6A...) (`eletrico.categoria_rede.r1`)

Regra: `(?<!\w)cat(?:egoria)?\s?([0-9][a-zA-Z]?)(?!\w)`

- Itens do catalogo com valor: **20** de 5813
- Consultas com valor extraido: **8**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.8438 | - |
| Reranking ingenuo | 0.8854 | +0.0417 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.1562** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 8 | 0.8438 | 0.8854 | 1.0000 |

Intrusos: **33**, de topico diferente: **20** (61%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T85 | cat, categoria, 5e, pares, par, patch | 5 | nao | 0.7500 | 1.0000 | +0.2500 |
| T48 | mpa nbr, mpa, estrutural, bloco, canaleta, nbr | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T30 | bsp, rosca bsp, galvanizado rosca, ferro, ferro galvanizado, curva graus | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Bivolt (presenca da palavra) (`eletrico.tensao.r2_bivolt`)

Regra: `(?<!\w)bivolt(?!\w)`

- Itens do catalogo com valor: **31** de 5813
- Consultas com valor extraido: **1** *(amostra muito pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 1.0000 | - |
| Reranking ingenuo | 1.0000 | +0.0000 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 1 | 1.0000 | 1.0000 | 1.0000 |

Intrusos: **24**, de topico diferente: **24** (100%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T123 | lavatorio, mesa lavatorio, mesa, cromada, cromada mesa, torneira | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Fases/polos (monofasico...tripolar) (`eletrico.tensao.r3_fases_polos`)

Regra: `(?<!\w)(monof(?:a|\u00e1)sico|bif(?:a|\u00e1)sico|trif(?:a|\u00e1)sico|monopolar|bipolar|tripolar)(?!\w)`

- Itens do catalogo com valor: **143** de 5813
- Consultas com valor extraido: **3** *(amostra muito pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.8333 | - |
| Reranking ingenuo | 0.8333 | +0.0000 |
| **Gateado por topico (adotado)** | **0.8333** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 3 | 0.8333 | 0.8333 | 0.8333 |

Intrusos: **9**, de topico diferente: **6** (67%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T7 | motor, cv, capacidade, motor diesel, diesel, potencia | 1 | nao | 0.5000 | 0.5000 | +0.0000 |
| T37 | cobre anel, tubulacao, disjuntor, espuma polietileno, polietileno expandido, mm luva | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T71 | tensao, isolante, kv, transformador, potencia kva, mineral | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
