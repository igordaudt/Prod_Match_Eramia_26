# Validacao de class_match/param_3.json -- kg e cv/hp refeitos com as regras oficiais

Reproduz `results/kg_exact_match_rerank/` e `results/power_cv_hp_analysis/`, mas usando `massa.peso.r1` e `mecanico.potencia_mecanica.r1` de `class_match/param_3.json` (v1.1.0) em vez das regexes ad-hoc (`KG_VALUE_RE`/`POWER_VALUE_RE`) construidas antes nesta sessao.

## Regras usadas

- `massa.peso.r1`: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(kg|g|mg|t)(?!\w)(?!\s*\/)`
  - Agora cobre `kg`, `g`, `mg`, `t` (a regex ad-hoc so cobria `kg`). Match exige **mesmo valor E mesma unidade** (1kg != 1g != 1mg != 1t -- unidades NAO sao intercambiaveis).

- `mecanico.potencia_mecanica.r1`: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(cv|hp)(?!\w)`
  - Cobre `cv` e `hp`. Mantida a equivalencia por VALOR (sem exigir mesma unidade), como na analise anterior -- cv e hp sao usados de forma intercambiavel no catalogo para a mesma grandeza fisica aproximada.


## Peso (massa.peso.r1: kg/g/mg/t, unit-aware)

- Itens do catalogo com valor: **209** de 5813
- Consultas com valor extraido: **46** (regex ad-hoc anterior: 27)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7623 | - |
| Reranking ingenuo (ignora topico) | 0.7670 | +0.0046 |
| **Gateado por topico (adotado)** | **0.8003** | **+0.0379** |

| Segmento | N | Baseline | Ingenuo | Gateado por topico |
|---|---|---|---|---|
| T101+T73 | 17 | 0.5253 | 0.5839 | 0.5839 |
| Outros topicos | 29 | 0.9012 | 0.8743 | 0.9271 |

Intrusos do reranking ingenuo: **59**, de topico diferente da consulta: **44** (75%)

**Comparacao com a regex ad-hoc anterior**: baseline 0.6599 -> gateado 0.6967 (delta +0.0368) usando `KG_VALUE_RE`/`POWER_VALUE_RE`; aqui, baseline 0.7623 -> gateado 0.8003 (delta +0.0379) usando `param_3.json`.


## Potencia mecanica (mecanico.potencia_mecanica.r1: cv/hp, valor apenas)

- Itens do catalogo com valor: **216** de 5813
- Consultas com valor extraido: **22** (regex ad-hoc anterior: 22)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.6162 | - |
| Reranking ingenuo (ignora topico) | 0.6344 | +0.0182 |
| **Gateado por topico (adotado)** | **0.6383** | **+0.0221** |

| Segmento | N | Baseline | Ingenuo | Gateado por topico |
|---|---|---|---|---|
| T101+T73 | 11 | 0.5391 | 0.5769 | 0.5833 |
| Outros topicos | 11 | 0.6932 | 0.6919 | 0.6932 |

Intrusos do reranking ingenuo: **22**, de topico diferente da consulta: **13** (59%)

**Comparacao com a regex ad-hoc anterior**: baseline 0.6162 -> gateado 0.6389 (delta +0.0227) usando `KG_VALUE_RE`/`POWER_VALUE_RE`; aqui, baseline 0.6162 -> gateado 0.6383 (delta +0.0221) usando `param_3.json`.

