# Auditoria do token 'kg' em numeric_attribute_density() -- Resultados

Escopo: as 852 consultas reais do benchmark (`data/ground_truth/retrieval-benchmark-295.json`), tokenizadas com a mesma regex de `scripts/retrieval_adaptive_fusion_v5.py` (`TOKEN_RE`), procurando o token isolado `kg`.

## Positivos (token 'kg' disparado)
- Total de consultas com token `kg`: **29** de 852 (3.4%)
- **Verdadeiro positivo a nivel de token** (o `kg` esta sempre precedido de um numero, ex. "23000 KG" -- e genuinamente um valor de peso): **29/29**
- **Falso positivo a nivel de token** (`kg` solto, sem numero antes): **0/29**

- **Util para o objetivo da tecnica** (dispara num topico com MAP < 0.6, ou seja, um topico que realmente precisa de ajuda): **17/29** (58.6%)
- **"Falso positivo de utilidade"** (dispara corretamente -- e um `kg` real -- mas num topico que ja tem MAP >= 0.6, ou seja, o boost ali e desnecessario para o objetivo original): **12/29** (41.4%)

## Distribuicao por topico

| Topico | Palavras-chave | MAP do topico | N hits 'kg' | Topico fraco (precisa ajuda)? |
|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 0.8053 | 2 | nao |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 0.7838 | 2 | nao |
| T18 | conexao crimpagem, crimpagem, plastico, conexao, tubo pex, pex | 1.0000 | 1 | nao |
| T47 | perfurada, mm virola, virola tampa, galvanizado espessura, removivel, virola | 1.0000 | 1 | nao |
| T73 | distancia, kg, carroceria, eixos, cv inclui, peso bruto | 0.5431 | 6 | **SIM** |
| T88 | poste, poste concreto, kg, circular, bolsa, bolsa bolsa | 0.6751 | 2 | nao |
| T101 | kg, cabine, cv inclui, peso bruto, total, chassi | 0.4453 | 11 | **SIM** |
| T111 | roscavel flanges, vedacao mm, flanges anel, anel vedacao, flanges, mm caixa | 0.8168 | 3 | nao |
| T114 | impermeabilizante, liquido, epoxi, base resina, resina, adesivo | 0.9062 | 1 | nao |

## Falsos negativos (o token 'kg' deveria ter disparado, mas nao disparou)

1. **'kg' colado ao numero, sem espaco** (o tokenizer funde tudo em um so token, ex. `35kg`, `1kg`, `20kg`, que nao bate com o token isolado `kg`): **3** casos.
   - Q16719 (T8): "TELHA GALVALUME COM ISOLAMENTO TERMOACUSTICO EM ESPUMA RIGIDA DE POLIURETANO INJETADO ESPESSURA DE 30MM, DENSIDADE DE 35KG/M3 REVESTIMENTO EM TELHA TRAPEZOIDAL NAS DUAS FACES COM ESPESSURA DE 0,50MM CADA, PINTADA NA COR BRANCA"
   - Q28014 (T-1): "Arame galvanizado liso n°16, Bitóla 1,65 mm – rolo de 1kg"
   - Q42035 (T12): "Argamassa para uso interno, embalagem de 20Kg."
2. **Menciona 'peso' mas usa outra unidade** (ex. toneladas, nao capturado por este regex): **1** caso(s).
   - Q6463 (T10): "ESCAVADEIRA HIDRAULICA SOBRE ESTEIRAS DE 99 HP, PESO OPERACIONAL DE *16* T E CAPACIDADE DE 0,85 A 1,00 M3 (LOCACAO COM OPERADOR, COMBUSTIVEL E MANUTENCAO)"
3. **Unidades de massa/torque vizinhas** (`kgf`, `kgm`, `ton`, `grama` -- fisicamente distintas de `kg`, mas relacionadas; note que `kgf`/`kgm` ja estao cobertas por `UNIT_TOKENS` no regex mais amplo de densidade numerica, so nao contam como `kg` nesta auditoria especifica): **1** caso(s).
   - Q6608 (T7), unidades=['kgm']: "PERFURATRIZ ROTATIVA SOBRE ESTEIRA, TORQUE MAXIMO 2500 KGM, POTENCIA 110 HP, MOTOR DIESEL (COLETADO CAIXA)"

## Conclusao
- O token `kg`, isoladamente, **nao tem falsos positivos de tokenizacao** no benchmark: toda ocorrencia esta genuinamente ligada a um valor numerico de peso.
- Mas so **17 das 29** ocorrencias caem em topicos que de fato precisam de ajuda (MAP baixo) -- concentradas em T101 (caminhoes/elevadores, MAP 0,4453) e T73 (caminhoes, MAP 0,5431). As outras 12 disparam em topicos ja saudaveis (T18, T47 com MAP 1,0; T114 com 0,91; T111 com 0,82; outliers com 0,81; T12 com 0,78) -- o boost ali nao é 'errado', so nao ataca o problema que motivou a tecnica.
- Os falsos negativos encontrados sao pontuais mas sistemáticos: valores colados sem espaco ('35KG/M3', '1kg', '20Kg.') exigiriam trocar a deteccao de tokenizacao pura por uma regex sobre o texto bruto (`\d[.,]?\d*\s*kg\b`), e peso em toneladas ('16 T') exigiria adicionar essa unidade ao vocabulario -- mas com risco de ambiguidade ('T' e uma letra muito comum sozinha).
