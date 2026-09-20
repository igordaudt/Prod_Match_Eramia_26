# Analise de 'potencia eletrica' e 'tensao' via param_3.json -- Resultados

Fecha o ciclo da divisao `eletrico.potencia` -> `eletrico.potencia_eletrica` (w/kw/kva) + `mecanico.potencia_mecanica` (cv/hp, ja testado) -- so faltava o lado eletrico. Testa tambem `eletrico.tensao.r1` (v/kv), que tem notacao bivolt "A/B" tratada como dois valores separados.

- `eletrico.potencia_eletrica.r1`: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(w|kw|kva)(?!\w)`
- `eletrico.tensao.r1`: `(?<!\w)(\d+(?:[\.,]\d+)?(?:\/\d+(?:[\.,]\d+)?)?)(?:\s?)(v|kv)(?!\w)`

Ambos **unit-aware** (w != kw != kva; v != kv -- ordens de grandeza diferentes, ao contrario de cv~=hp, que foram tratados como equivalentes por serem fisicamente quase iguais).


## Potencia eletrica (w/kw/kva)

- Itens do catalogo com valor: **181** de 5813
- Consultas com valor extraido: **29**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.8046 | - |
| Reranking ingenuo | 0.8103 | +0.0057 |
| **Gateado por topico (adotado)** | **0.8046** | **+0.0000** |

Topicos "fracos" (MAP < 0.6):
| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 29 | 0.8046 | 0.8103 | 0.8046 |

Intrusos: **11**, de topico diferente: **5** (45%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T7 | motor, cv, capacidade, motor diesel, diesel, potencia | 11 | nao | 1.0000 | 1.0000 | +0.0000 |
| outliers | outliers (sem tópico coerente) | 8 | nao | 0.6042 | 0.6042 | +0.0000 |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 8 | nao | 0.6875 | 0.6875 | +0.0000 |
| T16 | lampada, bivolt, luva eletroduto, lampada vapor, base e27, base | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T71 | tensao, isolante, kv, transformador, potencia kva, mineral | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Tensao (v/kv, com bivolt A/B)

- Itens do catalogo com valor: **287** de 5813
- Consultas com valor extraido: **17**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.9779 | - |
| Reranking ingenuo | 0.8762 | -0.1017 |
| **Gateado por topico (adotado)** | **0.9779** | **+0.0000** |

Topicos "fracos" (MAP < 0.6):
| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 17 | 0.9779 | 0.8762 | 0.9779 |

Intrusos: **183**, de topico diferente: **151** (83%)

### MAP por topico

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T121 | unipolar, blindado, cobertura, kv, isolacao, cabo cobre | 5 | nao | 1.0000 | 1.0000 | +0.0000 |
| T14 | cabo, mm cabo, cobre flexivel, secao nominal, nominal mm, nominal | 5 | nao | 1.0000 | 1.0000 | +0.0000 |
| outliers | outliers (sem tópico coerente) | 3 | nao | 1.0000 | 1.0000 | +0.0000 |
| T31 | gas, controle, condicionado, ar condicionado, ar, teto | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 1 | nao | 0.6250 | 0.6250 | +0.0000 |
| T29 | disjuntor, ac, tripolar, corrente, vazao maxima, plana | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
