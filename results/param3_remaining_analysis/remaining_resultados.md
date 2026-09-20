# Regras restantes de param_3.json -- Resultados finais

Fecha o restante das regras de `class_match/param_3.json`. Inclui `diametro`, `area` e `volume` (excluidos so na rodada especifica de teste de `mm`, incluidos agora). `dimensional.diametro.r3_polegadas` tem a MESMA regex de `dimensional.comprimento.r2_polegadas` (texto identico) -- computado uma vez, resultado replicado para as duas.

## Resumo

| Atributo | Regra | Consultas | MAP baseline | MAP ingenuo | MAP gateado | Delta gateado |
|---|---|---|---|---|---|---|
| Comprimento em polegadas | `dimensional.comprimento.r2_polegadas` | 39 | 0.7618 | 0.6597 | 0.7618 | +0.0000 |
| Area (mm2/cm2/m2) | `dimensional.area.r1` | 14 | 0.7619 | 0.6978 | 0.7619 | +0.0000 |
| Volume (mm3/cm3/m3) | `dimensional.volume.r1` | 7 | 0.6429 | 0.6429 | 0.6429 | +0.0000 |
| Diametro (simbolo Ø) | `dimensional.diametro.r1_simbolo` | 2 | - | - | - | **sem dados** |
| Diametro nominal (DN) | `dimensional.diametro.r2_dn` | 24 | 0.9417 | 0.9792 | 0.9792 | +0.0375 |
| Bitola AWG/MCM *(amostra pequena)* | `dimensional.bitola_awg.r1` | 4 | 0.7083 | 0.7083 | 0.7083 | +0.0000 |
| Material base (categorico) | `material.material_base.r1` | 430 | 0.8102 | 0.7975 | 0.8190 | +0.0088 |
| Classe CA do aco (25/50/60) *(amostra pequena)* | `material.resistencia_estrutural_aco.r1_ca_aco` | 1 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| Isolacao eletrica (hepr/lszh/xlpe...) | `material.isolacao_eletrica.r1` | 60 | 0.8613 | 0.8444 | 0.8993 | +0.0380 |
| Cor base (categorico) | `cor.cor_base.r1` | 116 | 0.7377 | 0.6543 | 0.7218 | -0.0159 |
| Cor composta (A/B) | `cor.cor_base.r2_composta` | 0 | - | - | - | **sem dados** |
| Grau de protecao IP | `normativo.ip.r1` | 0 | - | - | - | **sem dados** |
| Certificado CA | `normativo.ca.r1` | 0 | - | - | - | **sem dados** |
| Norma regulamentadora NR | `normativo.nr.r1` | 0 | - | - | - | **sem dados** |
| Norma NBR | `normativo.nbr.r1` | 132 | 0.6826 | 0.6649 | 0.6737 | -0.0089 |
| Norma ISO | `normativo.iso.r1` | 2 | - | - | - | **sem dados** |
| Quantidade por embalagem (caixa/pct/kit com N) *(amostra pequena)* | `embalagem.quantidade_embalagem.r1` | 2 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| Quantidade por embalagem (N unidades/pecas) *(amostra pequena)* | `embalagem.quantidade_embalagem.r2` | 5 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| Classe (A-D) *(amostra pequena)* | `modelo_classificacao.classe.r1` | 4 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| Concentracao quimica (%) | `quimico.concentracao.r1` | 7 | 0.6905 | 0.6905 | 0.6905 | +0.0000 |
| Diametro em polegadas *(= comprimento_polegadas (regex identica))* | `dimensional.diametro.r3_polegadas` | 39 | 0.7618 | 0.6597 | 0.7618 | +0.0000 |

## Comprimento em polegadas (`dimensional.comprimento.r2_polegadas`)

Regra: `(?<!\w)\*?(\d+(?:[\.,]\d+)?|(?:\d+\s+)?\d+\s*[/\u2044]\s*\d+|¾|½|¼|⅛|⅜|⅝|⅞)\*?(?:\s?)(\"|pol\b|pol\.|polegada(?:s)?)(?!\w)`

- Itens do catalogo com valor: **665** de 5813
- Consultas com valor extraido: **39**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7618 | - |
| Reranking ingenuo | 0.6597 | -0.1021 |
| **Gateado por topico (adotado)** | **0.7618** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 6 | 0.8056 | 0.6071 | 0.8056 |
| Fortes | 33 | 0.7538 | 0.6692 | 0.7538 |

Intrusos: **512**, de topico diferente: **448** (88%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 23 | nao | 0.7627 | 0.7627 | +0.0000 |
| T94 | diametro nominal, fita aco, galvanizado diametro, fita, eletroduto flexivel, nominal | 6 | **sim** | 0.8056 | 0.8056 | +0.0000 |
| T50 | perfil aco, espelho, laminado, dobradica, mm anel, perfil | 4 | nao | 0.5833 | 0.5833 | +0.0000 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 2 | nao | 0.5000 | 0.5000 | +0.0000 |
| T3 | angelim, regiao, regiao bruta, bruta, 25, 75 | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T119 | quente fria, mm cor, conector, cor marrom, marrom agua, marrom | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T25 | metal, cromado, sifao, valvula, americana, lavatorio | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Area (mm2/cm2/m2) (`dimensional.area.r1`)

Regra: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(mm2|mm²|cm2|cm²|m2|m²)(?!\w)`

- Itens do catalogo com valor: **213** de 5813
- Consultas com valor extraido: **14**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7619 | - |
| Reranking ingenuo | 0.6978 | -0.0641 |
| **Gateado por topico (adotado)** | **0.7619** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 14 | 0.7619 | 0.6978 | 0.7619 |

Intrusos: **63**, de topico diferente: **36** (57%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T121 | unipolar, blindado, cobertura, kv, isolacao, cabo cobre | 5 | nao | 1.0000 | 1.0000 | +0.0000 |
| T24 | polido, granito, cm, regiao, marmore, andorinha | 4 | nao | 0.5000 | 0.5000 | +0.0000 |
| T13 | aluminio, rosca 12, bucha, 12 eletroduto, eletroduto, bucha reducao | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| outliers | outliers (sem tópico coerente) | 2 | nao | 0.3333 | 0.3333 | +0.0000 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm, tubo concreto | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Volume (mm3/cm3/m3) (`dimensional.volume.r1`)

Regra: `(?<!\w)\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(mm3|mm³|cm3|cm³|m3|m³)(?!\w)`

- Itens do catalogo com valor: **103** de 5813
- Consultas com valor extraido: **7**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.6429 | - |
| Reranking ingenuo | 0.6429 | +0.0000 |
| **Gateado por topico (adotado)** | **0.6429** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 2 | 0.5000 | 0.5000 | 0.5000 |
| Fortes | 5 | 0.7000 | 0.7000 | 0.7000 |

Intrusos: **7**, de topico diferente: **5** (71%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T69 | moldado, comp, contribuintes, guia, concreto premoldado, mm malha | 3 | nao | 0.5000 | 0.5000 | +0.0000 |
| T113 | bomba, usinado, resistencia, servico, classe, concreto | 2 | **sim** | 0.5000 | 0.5000 | +0.0000 |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T9 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua, soldavel | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Diametro (simbolo Ø) (`dimensional.diametro.r1_simbolo`)

Regra: `(?:ø)\s?\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(mm|cm|m)?`

- Itens do catalogo com valor: **0** de 5813
- Consultas com valor extraido: **2** -- nenhum item do catalogo contem esse atributo (reranking seria sempre um no-op).


## Diametro nominal (DN) (`dimensional.diametro.r2_dn`)

Regra: `(?<!\w)dn(?:\/di)?\s?\*?(\d+(?:[\.,]\d+)?)\*?(?:\s?)(mm)?(?!\w)`

- Itens do catalogo com valor: **396** de 5813
- Consultas com valor extraido: **24**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.9417 | - |
| Reranking ingenuo | 0.9792 | +0.0375 |
| **Gateado por topico (adotado)** | **0.9792** | **+0.0375** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 2 | 0.5500 | 0.7500 | 0.7500 |
| Fortes | 22 | 0.9773 | 1.0000 | 1.0000 |

Intrusos: **330**, de topico diferente: **290** (88%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 11 | nao | 1.0000 | 1.0000 | +0.0000 |
| T32 | tubo pvc, corrugado, 5688, nbr 5688, luva correr, rede coletora | 5 | nao | 0.9000 | 1.0000 | +0.1000 |
| T27 | pex, tubo pex, conexao, conexao anel, plastica, metalica | 2 | **sim** | 0.5500 | 0.7500 | +0.2000 |
| T89 | ponta, mm junta, expansao, junta, 900, ponta bolsa | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T119 | quente fria, mm cor, conector, cor marrom, marrom agua, marrom | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T112 | predial nbr, 5648, nbr 5648, tubo pvc, nervurado, graus soldavel | 2 | nao | 1.0000 | 1.0000 | +0.0000 |

## Bitola AWG/MCM (`dimensional.bitola_awg.r1`)

Regra: `(?<!\w)(\d+(?:\/\d+)?)(?:\s?)(awg|mcm)(?!\w)`

- Itens do catalogo com valor: **5** de 5813
- Consultas com valor extraido: **4** *(amostra pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7083 | - |
| Reranking ingenuo | 0.7083 | +0.0000 |
| **Gateado por topico (adotado)** | **0.7083** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 4 | 0.7083 | 0.7083 | 0.7083 |

Intrusos: **0**, de topico diferente: **0**

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T48 | mpa nbr, mpa, estrutural, bloco, canaleta, nbr | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T85 | cat, categoria, 5e, pares, par, patch | 2 | nao | 0.4167 | 0.4167 | +0.0000 |

## Material base (categorico) (`material.material_base.r1`)

Regra: `(?<!\w)(pedra|pvc|nylon|pl[aá]stico|vidro|gesso|m[aá]rmore|granito|ep[oó]xi|a[çc]o(?:\s?inox)?|alum[ií]nio|cobre|lat[aã]o|ferro|metal|concreto|madeira|borracha|resina|cer[aâ]mica|porcelanato|reciclado|argila)(?!\w)`

- Itens do catalogo com valor: **3444** de 5813
- Consultas com valor extraido: **430**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.8102 | - |
| Reranking ingenuo | 0.7975 | -0.0127 |
| **Gateado por topico (adotado)** | **0.8190** | **+0.0088** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 34 | 0.3946 | 0.3267 | 0.4031 |
| Fortes | 396 | 0.8459 | 0.8379 | 0.8547 |

Intrusos: **13571**, de topico diferente: **11780** (87%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 115 | nao | 0.7894 | 0.7894 | +0.0000 |
| T22 | janela, brilhante, bandeira, aluminio, vidro, janela correr | 25 | nao | 0.7923 | 0.7923 | +0.0000 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm, tubo concreto | 23 | nao | 0.7640 | 0.8478 | +0.0839 |
| T90 | resistencia dan, dan, extensao resistencia, armado secao, extensao, poste concreto | 22 | nao | 0.9545 | 0.9545 | +0.0000 |
| T81 | resistencia dan, dan, extensao resistencia, armado secao, extensao, poste concreto | 21 | nao | 0.9444 | 0.9444 | +0.0000 |
| T75 | forma, madeira, mm sinapi, 11, concreto, mm chapa | 20 | nao | 0.6056 | 0.6052 | -0.0005 |
| T55 | circular, dan, resistencia dan, extensao resistencia, armado secao, poste concreto | 15 | nao | 1.0000 | 1.0000 | +0.0000 |
| T69 | moldado, comp, contribuintes, guia, concreto premoldado, mm malha | 14 | nao | 1.0000 | 1.0000 | +0.0000 |
| T100 | fogo, bandeira, mm sinapi, mecanica, 15 mm, aco galvanizado | 12 | nao | 1.0000 | 1.0000 | +0.0000 |
| T9 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua, soldavel | 11 | nao | 1.0000 | 1.0000 | +0.0000 |
| T32 | tubo pvc, corrugado, 5688, nbr 5688, luva correr, rede coletora | 10 | nao | 0.8577 | 0.9500 | +0.0923 |
| T61 | capa, marco, folha, dobradicas, pronta, alizares | 10 | **sim** | 0.3263 | 0.3109 | -0.0155 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 8 | nao | 0.7906 | 0.7906 | +0.0000 |
| T107 | forro, forro pvc, regua, cm espessura, borda, mineral | 8 | nao | 0.8958 | 0.8958 | +0.0000 |
| T3 | angelim, regiao, regiao bruta, bruta, 25, 75 | 8 | nao | 0.9375 | 0.7656 | -0.1719 |

## Classe CA do aco (25/50/60) (`material.resistencia_estrutural_aco.r1_ca_aco`)

Regra: `(?<!\w)ca\s?[\.-]?\s?(25|50|60)(?!\w)`

- Itens do catalogo com valor: **28** de 5813
- Consultas com valor extraido: **1** *(amostra pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 1.0000 | - |
| Reranking ingenuo | 1.0000 | +0.0000 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 1 | 1.0000 | 1.0000 | 1.0000 |

Intrusos: **4**, de topico diferente: **4** (100%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T18 | conexao crimpagem, crimpagem, plastico, conexao, tubo pex, pex | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Isolacao eletrica (hepr/lszh/xlpe...) (`material.isolacao_eletrica.r1`)

Regra: `(?<!\w)(hepr|lszh|xlpe|epr|bwf-b|pvc[/-]?[a-z0-9]?)(?!\w)`

- Itens do catalogo com valor: **982** de 5813
- Consultas com valor extraido: **60**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.8613 | - |
| Reranking ingenuo | 0.8444 | -0.0170 |
| **Gateado por topico (adotado)** | **0.8993** | **+0.0380** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 7 | 0.5372 | 0.3916 | 0.6087 |
| Fortes | 53 | 0.9041 | 0.9041 | 0.9377 |

Intrusos: **2531**, de topico diferente: **2312** (91%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 13 | nao | 0.8615 | 0.8615 | +0.0000 |
| T32 | tubo pvc, corrugado, 5688, nbr 5688, luva correr, rede coletora | 10 | nao | 0.8577 | 0.9500 | +0.0923 |
| T9 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua, soldavel | 9 | nao | 1.0000 | 1.0000 | +0.0000 |
| T121 | unipolar, blindado, cobertura, kv, isolacao, cabo cobre | 5 | nao | 1.0000 | 1.0000 | +0.0000 |
| T44 | grelha, branca, pvc mm, ralo, redonda, quadrada | 5 | nao | 0.8000 | 0.8000 | +0.0000 |
| T5 | je, mm rede, rede coletora, coletora esgoto, coletora, rede | 4 | **sim** | 0.6750 | 0.8000 | +0.1250 |
| T85 | cat, categoria, 5e, pares, par, patch | 3 | nao | 1.0000 | 1.0000 | +0.0000 |
| T112 | predial nbr, 5648, nbr 5648, tubo pvc, nervurado, graus soldavel | 3 | nao | 1.0000 | 1.0000 | +0.0000 |
| T57 | naval, tubo pvc, compensado, compensado naval, 220, 160 | 3 | nao | 0.7143 | 1.0000 | +0.2857 |
| T15 | ppr, quente predial, graus soldavel, quente, predial joelho, ff | 2 | **sim** | 0.0303 | 0.0303 | +0.0000 |
| T34 | prediais, pluviais prediais, esgoto aguas, pvc serie, serie, mm esgoto | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 1 | **sim** | 1.0000 | 1.0000 | +0.0000 |

## Cor base (categorico) (`cor.cor_base.r1`)

Regra: `(?<!\w)(branco|branca|preto|preta|azul|amarelo|amarela|vermelho|vermelha|verde|cinza|grafite|marrom|bege|laranja|rosa|roxo|roxa|violeta|lilas|dourado|dourada|prata|prateado|prateada|cromado|cromada|transparente|incolor|natural)(?!\w)`

- Itens do catalogo com valor: **469** de 5813
- Consultas com valor extraido: **116**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7377 | - |
| Reranking ingenuo | 0.6543 | -0.0834 |
| **Gateado por topico (adotado)** | **0.7218** | **-0.0159** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 19 | 0.4558 | 0.4631 | 0.4600 |
| Fortes | 97 | 0.7929 | 0.6917 | 0.7731 |

Intrusos: **1913**, de topico diferente: **1543** (81%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 37 | nao | 0.7623 | 0.7623 | +0.0000 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 15 | nao | 0.6474 | 0.6005 | -0.0469 |
| T70 | torneira, cromada, bico, arejador, cozinha, 12 34 | 13 | **sim** | 0.4110 | 0.4238 | +0.0128 |
| T123 | lavatorio, mesa lavatorio, mesa, cromada, cromada mesa, torneira | 6 | nao | 0.6875 | 0.6500 | -0.0375 |
| T75 | forma, madeira, mm sinapi, 11, concreto, mm chapa | 6 | nao | 0.7566 | 0.7566 | +0.0000 |
| T67 | usinado, servico, resistencia, latao cromado, classe, nbr | 4 | nao | 1.0000 | 1.0000 | +0.0000 |
| T9 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua, soldavel | 4 | nao | 1.0000 | 1.0000 | +0.0000 |
| T61 | capa, marco, folha, dobradicas, pronta, alizares | 3 | **sim** | 0.4197 | 0.3908 | -0.0288 |
| T22 | janela, brilhante, bandeira, aluminio, vidro, janela correr | 3 | nao | 1.0000 | 1.0000 | +0.0000 |
| T44 | grelha, branca, pvc mm, ralo, redonda, quadrada | 3 | nao | 1.0000 | 1.0000 | +0.0000 |
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 3 | **sim** | 0.6863 | 0.6863 | +0.0000 |
| T25 | metal, cromado, sifao, valvula, americana, lavatorio | 3 | nao | 0.8333 | 0.8333 | +0.0000 |
| T111 | roscavel flanges, vedacao mm, flanges anel, anel vedacao, flanges, mm caixa | 2 | nao | 0.5000 | 0.5000 | +0.0000 |
| T50 | perfil aco, espelho, laminado, dobradica, mm anel, perfil | 2 | nao | 0.6667 | 0.6667 | +0.0000 |
| T42 | litros, litros tampa, tampa caixa, asfaltica, caixa dagua, dagua | 2 | nao | 1.0000 | 1.0000 | +0.0000 |

## Cor composta (A/B) (`cor.cor_base.r2_composta`)

Regra: `(?<!\w)(branco|branca|preto|preta|azul|amarelo|amarela|vermelho|vermelha|verde|cinza|grafite|marrom|bege|laranja|rosa|roxo|roxa|violeta|lilas|dourado|dourada|prata|prateado|prateada|cromado|cromada|transparente|incolor|natural)\s*(?:\/|e|com)\s*(branco|branca|preto|preta|azul|amarelo|amarela|vermelho|vermelha|verde|cinza|grafite|marrom|bege|laranja|rosa|roxo|roxa|violeta|lilas|dourado|dourada|prata|prateado|prateada|cromado|cromada|transparente|incolor|natural)(?!\w)`

- Itens do catalogo com valor: **0** de 5813
- Consultas com valor extraido: **0** -- nenhuma consulta contem esse atributo.


## Grau de protecao IP (`normativo.ip.r1`)

Regra: `(?<!\w)ip\s?(\d{2})(?!\w)`

- Itens do catalogo com valor: **1** de 5813
- Consultas com valor extraido: **0** -- nenhuma consulta contem esse atributo.


## Certificado CA (`normativo.ca.r1`)

Regra: `(?<!\w)ca\s?\.?\s?(\d{3,6})(?!\w)`

- Itens do catalogo com valor: **0** de 5813
- Consultas com valor extraido: **0** -- nenhuma consulta contem esse atributo.


## Norma regulamentadora NR (`normativo.nr.r1`)

Regra: `(?<!\w)nr\s?-?\s?(\d{1,2})(?!\w)`

- Itens do catalogo com valor: **0** de 5813
- Consultas com valor extraido: **0** -- nenhuma consulta contem esse atributo.


## Norma NBR (`normativo.nbr.r1`)

Regra: `(?<!\w)nbr\s?-?\s?(\d{3,6})(?!\w)`

- Itens do catalogo com valor: **464** de 5813
- Consultas com valor extraido: **132**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.6826 | - |
| Reranking ingenuo | 0.6649 | -0.0177 |
| **Gateado por topico (adotado)** | **0.6737** | **-0.0089** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 83 | 0.5848 | 0.5611 | 0.5603 |
| Fortes | 49 | 0.8482 | 0.8406 | 0.8657 |

Intrusos: **785**, de topico diferente: **226** (29%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T21 | agua esgoto, densidade pead, polietileno alta, alta densidade, densidade, pn | 45 | **sim** | 0.6870 | 0.6465 | -0.0405 |
| outliers | outliers (sem tópico coerente) | 16 | nao | 0.8042 | 0.8042 | +0.0000 |
| T125 | termoplastica, manta, mm nbr, lisa, pead, nbr | 14 | **sim** | 0.5000 | 0.5000 | +0.0000 |
| T83 | faces, termoplastica, bolsa bolsa, manta, mm nbr, bolsa | 14 | nao | 1.0000 | 1.0000 | +0.0000 |
| T61 | capa, marco, folha, dobradicas, pronta, alizares | 10 | **sim** | 0.3263 | 0.3147 | -0.0117 |
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 8 | **sim** | 0.7326 | 0.7366 | +0.0040 |
| T41 | 500, media, capa, folha, tensao nominal, tripolar | 5 | **sim** | 0.2602 | 0.2692 | +0.0090 |
| T57 | naval, tubo pvc, compensado, compensado naval, 220, 160 | 3 | nao | 0.7143 | 1.0000 | +0.2857 |
| T69 | moldado, comp, contribuintes, guia, concreto premoldado, mm malha | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T88 | poste, poste concreto, kg, circular, bolsa, bolsa bolsa | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T44 | grelha, branca, pvc mm, ralo, redonda, quadrada | 2 | nao | 0.5000 | 0.5000 | +0.0000 |
| T112 | predial nbr, 5648, nbr 5648, tubo pvc, nervurado, graus soldavel | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T32 | tubo pvc, corrugado, 5688, nbr 5688, luva correr, rede coletora | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 2 | nao | 0.1929 | 0.1929 | +0.0000 |
| T5 | je, mm rede, rede coletora, coletora esgoto, coletora, rede | 1 | **sim** | 0.2000 | 0.0256 | -0.1744 |

## Norma ISO (`normativo.iso.r1`)

Regra: `(?<!\w)iso\s?-?\s?(\d{3,6})(?!\w)`

- Itens do catalogo com valor: **0** de 5813
- Consultas com valor extraido: **2** -- nenhum item do catalogo contem esse atributo (reranking seria sempre um no-op).


## Quantidade por embalagem (caixa/pct/kit com N) (`embalagem.quantidade_embalagem.r1`)

Regra: `(?<!\w)(?:cx|caixa|pct|pacote|kit|fardo|rolo|saco)\s*(?:c\/|com)?\s*(\d+)(?!\w)`

- Itens do catalogo com valor: **5** de 5813
- Consultas com valor extraido: **2** *(amostra pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 1.0000 | - |
| Reranking ingenuo | 1.0000 | +0.0000 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 2 | 1.0000 | 1.0000 | 1.0000 |

Intrusos: **0**, de topico diferente: **0**

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| T111 | roscavel flanges, vedacao mm, flanges anel, anel vedacao, flanges, mm caixa | 2 | nao | 1.0000 | 1.0000 | +0.0000 |

## Quantidade por embalagem (N unidades/pecas) (`embalagem.quantidade_embalagem.r2`)

Regra: `(?<!\w)(\d+)\s*(?:un|und|unid|unidade(?:s)?|pe[çc]a(?:s)?)(?!\w)`

- Itens do catalogo com valor: **6** de 5813
- Consultas com valor extraido: **5** *(amostra pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 1.0000 | - |
| Reranking ingenuo | 1.0000 | +0.0000 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 5 | 1.0000 | 1.0000 | 1.0000 |

Intrusos: **0**, de topico diferente: **0**

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 4 | nao | 1.0000 | 1.0000 | +0.0000 |
| T13 | aluminio, rosca 12, bucha, 12 eletroduto, eletroduto, bucha reducao | 1 | nao | 1.0000 | 1.0000 | +0.0000 |

## Classe (A-D) (`modelo_classificacao.classe.r1`)

Regra: `(?<!\w)classe\s?([a-d])(?!\w)`

- Itens do catalogo com valor: **39** de 5813
- Consultas com valor extraido: **4** *(amostra pequena, interpretar com cautela)*

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 1.0000 | - |
| Reranking ingenuo | 1.0000 | +0.0000 |
| **Gateado por topico (adotado)** | **1.0000** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 4 | 1.0000 | 1.0000 | 1.0000 |

Intrusos: **28**, de topico diferente: **28** (100%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T89 | ponta, mm junta, expansao, junta, 900, ponta bolsa | 2 | nao | 1.0000 | 1.0000 | +0.0000 |

## Concentracao quimica (%) (`quimico.concentracao.r1`)

Regra: `(?<!\w)(\d+(?:[\.,]\d+)?)(?:\s?)(%)(?!\w)`

- Itens do catalogo com valor: **16** de 5813
- Consultas com valor extraido: **7**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.6905 | - |
| Reranking ingenuo | 0.6905 | +0.0000 |
| **Gateado por topico (adotado)** | **0.6905** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 0 | 0.0000 | 0.0000 | 0.0000 |
| Fortes | 7 | 0.6905 | 0.6905 | 0.6905 |

Intrusos: **8**, de topico diferente: **8** (100%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 4 | nao | 0.7917 | 0.7917 | +0.0000 |
| T85 | cat, categoria, 5e, pares, par, patch | 2 | nao | 0.4167 | 0.4167 | +0.0000 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm, tubo concreto | 1 | nao | 0.8333 | 0.8333 | +0.0000 |

## Diametro em polegadas (`dimensional.diametro.r3_polegadas`)

Regra: `(?<!\w)\*?(\d+(?:[\.,]\d+)?|(?:\d+\s+)?\d+\s*[/\u2044]\s*\d+|¾|½|¼|⅛|⅜|⅝|⅞)\*?(?:\s?)(\"|pol\b|pol\.|polegada(?:s)?)(?!\w)`

*(mesma regex de `comprimento_polegadas (regex identica)` -- resultado identico, nao recomputado)*

- Itens do catalogo com valor: **665** de 5813
- Consultas com valor extraido: **39**

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7618 | - |
| Reranking ingenuo | 0.6597 | -0.1021 |
| **Gateado por topico (adotado)** | **0.7618** | **+0.0000** |

| Segmento | N | Baseline | Ingenuo | Gateado |
|---|---|---|---|---|
| Fracos (MAP<0.6) | 6 | 0.8056 | 0.6071 | 0.8056 |
| Fortes | 33 | 0.7538 | 0.6692 | 0.7538 |

Intrusos: **512**, de topico diferente: **448** (88%)

### MAP por topico (top 15 por N)

| Topico | Palavras-chave | N | Fraco? | MAP baseline | MAP gateado | Delta |
|---|---|---|---|---|---|---|
| outliers | outliers (sem tópico coerente) | 23 | nao | 0.7627 | 0.7627 | +0.0000 |
| T94 | diametro nominal, fita aco, galvanizado diametro, fita, eletroduto flexivel, nominal | 6 | **sim** | 0.8056 | 0.8056 | +0.0000 |
| T50 | perfil aco, espelho, laminado, dobradica, mm anel, perfil | 4 | nao | 0.5833 | 0.5833 | +0.0000 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi | 2 | nao | 0.5000 | 0.5000 | +0.0000 |
| T3 | angelim, regiao, regiao bruta, bruta, 25, 75 | 2 | nao | 1.0000 | 1.0000 | +0.0000 |
| T119 | quente fria, mm cor, conector, cor marrom, marrom agua, marrom | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
| T25 | metal, cromado, sifao, valvula, americana, lavatorio | 1 | nao | 1.0000 | 1.0000 | +0.0000 |
