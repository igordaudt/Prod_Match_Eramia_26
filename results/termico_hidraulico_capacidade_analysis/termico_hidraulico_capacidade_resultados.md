# Analise de temperatura/vazao/pressao/capacidade via param_3.json -- Resultados

Testa `termico.temperatura.r1`, `hidraulico.vazao.r1`, `hidraulico.pressao.r1` (reincluido para o resumo consolidado -- ja testado em `results/mecanico_hidraulico_analysis/`) e `dimensional.capacidade.r1_litros`. Todos unit-aware.

## Resumo

| Atributo | Regra | Consultas | MAP baseline | MAP ingenuo | MAP gateado | Delta gateado |
|---|---|---|---|---|---|---|
| Temperatura (graus C / graus F) | `termico.temperatura.r1` | 0 | - | - | - | **sem dados** |
| Vazao hidraulica (l/min, l/h, m3/h, m3/s) | `hidraulico.vazao.r1` | 0 | - | - | - | **sem dados** |
| Pressao hidraulica (bar/psi/pa/kpa/mpa) | `hidraulico.pressao.r1` | 17 | 0.6877 | 0.6804 | 0.6820 | -0.0056 |
| Capacidade (l/litros/ml) | `dimensional.capacidade.r1_litros` | 27 | 0.8657 | 0.8652 | 0.8657 | +0.0000 |

## Temperatura (graus C / graus F) (`termico.temperatura.r1`)

Regra: `(?<!\w)(-?\d+(?:[\.,]\d+)?)(?:\s?)(°c|°f)(?!\w)`

- Itens do catalogo com valor: **0** de 5813
- Consultas com valor extraido no benchmark: **0** -- nao ha como avaliar reranking aqui.


## Vazao hidraulica (l/min, l/h, m3/h, m3/s) (`hidraulico.vazao.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(l\/min|l\/h|m3\/h|m³\/h|m3\/s|m³\/s)(?!\w)`

- Itens do catalogo com valor: **55** de 5813
- Consultas com valor extraido no benchmark: **0** -- nao ha como avaliar reranking aqui.


## Pressao hidraulica (bar/psi/pa/kpa/mpa) (`hidraulico.pressao.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(bar|psi|pa|kpa|mpa)(?!\w)`

- Itens do catalogo com valor: **107** de 5813
- Consultas com valor extraido: **17**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.6877 | - |
| Reranking ingenuo | 0.6804 | -0.0073 |
| **Gateado por topico (adotado)** | **0.6820** | **-0.0056** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 8 | 0.7326 | 0.7171 | 0.7206 |
| Fortes | 9 | 0.6477 | 0.6477 | 0.6477 |

Intrusos: **38**, de topico diferente: **4** (11%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 8 | **sim** | 0.7326 | 0.7206 | -0.0120 |
| outliers | outliers (sem tópico coerente) | 5 | nao | 1.0000 | 1.0000 | +0.0000 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm, tubo concreto | 3 | nao | 0.0682 | 0.0682 | +0.0000 |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 1 | nao | 0.6250 | 0.6250 | +0.0000 |

## Capacidade (l/litros/ml) (`dimensional.capacidade.r1_litros`)

Regra: `(?<!\w)\*?(\d+(?:[\.,]\d+)*)\*?(?:\s?)(l|litro(?:s)?|ml)(?!\w)`

- Itens do catalogo com valor: **88** de 5813
- Consultas com valor extraido: **27**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.8657 | - |
| Reranking ingenuo | 0.8652 | -0.0005 |
| **Gateado por topico (adotado)** | **0.8657** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 27 | 0.8657 | 0.8652 | 0.8657 |

Intrusos: **9**, de topico diferente: **7** (78%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T7 | motor, cv, capacidade, motor diesel, diesel, potencia | 7 | nao | 0.8571 | 0.8571 | +0.0000 |
| outliers | outliers (sem tópico coerente) | 5 | nao | 0.7333 | 0.7333 | +0.0000 |
| T122 | fibra vidro, litros tampa, fibra, reforcado, reservatorio, litros | 5 | nao | 1.0000 | 1.0000 | +0.0000 |
| T9 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua, soldavel | 4 | nao | 1.0000 | 1.0000 | +0.0000 |
| T42 | litros, litros tampa, tampa caixa, asfaltica, caixa dagua, dagua | 2 | nao | 0.7917 | 0.7917 | +0.0000 |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 1 | nao | 0.6250 | 0.6250 | +0.0000 |
| T68 | corte, galvanizada, calha, rufo, chapa aco, lajes | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T114 | impermeabilizante, liquido, epoxi, base resina, resina, adesivo | 1 | nao | 0.5000 | 0.5000 | +0.0000 |
