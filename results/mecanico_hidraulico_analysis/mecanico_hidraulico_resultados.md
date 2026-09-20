# Analise de pressao/rpm/resistencia/torque via param_3.json -- Resultados

Testa `hidraulico.pressao.r1`, `mecanico.rpm.r1`, `mecanico.resistencia.r1` (reincluido para comparacao -- ja testado isoladamente em `results/resistencia_mpa_analysis/`) e `mecanico.torque.r1`. Todos unit-aware (unidades dentro de cada regra NAO sao intercambiaveis entre si).

**Nota de ambiguidade**: `pressao.r1` e `resistencia.r1` compartilham a unidade `mpa` -- a mesma grandeza textual pode significar pressao hidraulica (bomba/compressor) OU resistencia estrutural (concreto/aco) dependendo do produto. Testados aqui como parametros separados (conforme o schema), sem desambiguacao contextual.

## Resumo

| Atributo | Regra | Consultas | MAP baseline | MAP ingenuo | MAP gateado | Delta gateado |
|---|---|---|---|---|---|---|
| Pressao hidraulica (bar/psi/pa/kpa/mpa) | `hidraulico.pressao.r1` | 17 | 0.6877 | 0.6804 | 0.6820 | -0.0056 |
| RPM (rotacoes por minuto) | `mecanico.rpm.r1` | 0 | - | - | - | **sem dados** |
| Resistencia estrutural (mpa) | `mecanico.resistencia.r1` | 15 | 0.6711 | 0.6628 | 0.6647 | -0.0064 |
| Torque (nm) | `mecanico.torque.r1` | 0 | - | - | - | **sem dados** |

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

## RPM (rotacoes por minuto) (`mecanico.rpm.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(rpm)(?!\w)`

- Itens do catalogo com valor: **15** de 5813
- Consultas com valor extraido no benchmark: **0** -- nenhuma das 852 consultas contem esse atributo, entao nao ha como avaliar reranking aqui (mesmo havendo itens no catalogo com esse valor).


## Resistencia estrutural (mpa) (`mecanico.resistencia.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(mpa)(?!\w)`

- Itens do catalogo com valor: **75** de 5813
- Consultas com valor extraido: **15**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.6711 | - |
| Reranking ingenuo | 0.6628 | -0.0083 |
| **Gateado por topico (adotado)** | **0.6647** | **-0.0064** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 8 | 0.7326 | 0.7171 | 0.7206 |
| Fortes | 7 | 0.6007 | 0.6007 | 0.6007 |

Intrusos: **38**, de topico diferente: **4** (11%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 8 | **sim** | 0.7326 | 0.7206 | -0.0120 |
| outliers | outliers (sem tópico coerente) | 4 | nao | 1.0000 | 1.0000 | +0.0000 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm, tubo concreto | 3 | nao | 0.0682 | 0.0682 | +0.0000 |

## Torque (nm) (`mecanico.torque.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(nm)(?!\w)`

- Itens do catalogo com valor: **0** de 5813
- Consultas com valor extraido no benchmark: **0** -- nenhuma das 852 consultas contem esse atributo, entao nao ha como avaliar reranking aqui (mesmo havendo itens no catalogo com esse valor).

