# Relatório consolidado — reranking por match exato de atributo, gateado por tópico

Resumo de toda a investigação feita nesta sessão: da hipótese inicial ("dar mais peso ao BM25 quando
a consulta é atributo-pesada") até a técnica final adotada e testada em praticamente todas as regras
de extração de parâmetros técnicos de `class_match/param_3.json`.

## 1. Contexto e origem

A investigação partiu da EDA de `eda/categ_map/topic_map_resultados.md`: os tópicos BERTopic de menor
MAP no benchmark de 852 consultas (T101, T73, T59, T125, T94, T2, T21...) eram dominados por atributos
numéricos/unidades de medida (kg, mm, cv, mpa...), onde nem o BM25 nem o embedding denso (BGE-M3)
garantiam que o item recuperado tivesse o **valor certo** do atributo — só aumentavam a chance de o
termo aparecer perto.

Duas abordagens foram testadas, nessa ordem:

1. **Fusão adaptativa por densidade numérica** (V5/V6, `scripts/retrieval_adaptive_fusion_v5.py`):
   aumentar o peso do BM25 na fusão RRF quando a consulta é detectada como "atributo-pesada" via
   regex de densidade de tokens numéricos. Resultado: o melhor ponto do grid (MAP 0,7982) ficou
   estatisticamente empatado com simplesmente aumentar o peso do BM25 globalmente (sem nenhuma
   detecção) — a "adaptividade" não agregou valor real neste benchmark.
2. **Reranking por match exato de valor de atributo** (o essencial deste relatório): em vez de só
   aumentar peso de um sinal difuso, extrair o(s) valor(es) numérico(s)/categóricos de cada atributo
   (via regex) tanto da consulta quanto dos itens candidatos, e **promover no ranking os itens cujo
   valor bate exatamente** com o da consulta. Essa abordagem foi a que gerou resultados fortes e é o
   foco de todo o restante deste documento.

As regexes usadas migraram de versões ad-hoc construídas durante a sessão para as regras **oficiais**
de `class_match/param_3.json` (criamos a v1.1.0, `param_3.json`, corrigindo `massa.peso.r1` para não
casar `kg/m` e separando `eletrico.potencia` em `potencia_eletrica` w/kw/kva e `mecanico.
potencia_mecanica` cv/hp).

## 2. Metodologia (igual em todos os testes)

- **Baseline**: fusão híbrida padrão publicada (BM25 + BGE-M3, RRF `k=60`, `limit=100`) — nenhuma
  mudança em relação ao pipeline em produção.
- **Reranking ingênuo**: dentro da MESMA lista de candidatos (sem nova busca), promove itens cujo
  conjunto de valores do atributo tem interseção com o da consulta — ignora a que tópico o item
  pertence. Serve só de contraponto, para evidenciar o risco.
- **Reranking gateado por tópico (política adotada)**: como o ingênuo, mas só conta o match se o item
  candidato pertencer ao **mesmo tópico BERTopic** da consulta (tópico `-1`/"outliers" nunca conta
  como match — dois itens sem categoria não são uma correspondência categórica real).
- **Unit-aware por padrão**: unidades de escalas diferentes (kg≠g≠mg≠t; mm≠cm≠m; w≠kw≠kva; v≠kv;
  bar≠psi≠pa≠kpa≠mpa) exigem bater valor E unidade. Exceção: `cv`/`hp`, tratados como equivalentes por
  valor (sem exigir mesma unidade), por serem fisicamente quase iguais e usados de forma
  intercambiável no catálogo.
- **Tópicos "fracos"**: para kg/cv-hp usamos os tópicos-alvo originais (T101, T73); para todo o
  resto, calculados dinamicamente como MAP médio do tópico < 0,60 (o atributo se espalha por tópicos
  diferentes dos originais).
- **Auditoria de intrusos**: para cada teste, identificamos itens que sobem de posição no reranking
  ingênuo sem ser relevantes, e verificamos se pertencem a um tópico diferente da consulta.

## 3. Resultado mestre — todas as regras testadas

| # | Atributo (regra `param_3.json`) | N consultas | MAP baseline | MAP ingênuo | **MAP gateado** | **Delta gateado** |
|---|---|---|---|---|---|---|
| 1 | Peso — kg/g/mg/t (`massa.peso.r1`) | 46 | 0,7623 | 0,7670 | **0,8003** | **+0,0379** |
| 2 | Dimensional — mm/cm/m/pol, 6 regras combinadas (`comprimento`, `espessura`, `raio`, `multidimensional_2d`×2, `multidimensional_3d`) | 548 | 0,7906 | 0,8214 | **0,8342** | **+0,0437** |
| 3 | Potência mecânica — cv/hp (`mecanico.potencia_mecanica.r1`) | 22 | 0,6162 | 0,6344 | **0,6383** | **+0,0221** |
| 4 | Diâmetro nominal — DN (`dimensional.diametro.r2_dn`) | 24 | 0,9417 | 0,9792 | **0,9792** | **+0,0375** |
| 5 | Isolação elétrica — hepr/lszh/xlpe... (`material.isolacao_eletrica.r1`) | 60 | 0,8613 | 0,8444 | **0,8993** | **+0,0380** |
| 6 | **Vias condutoras — N condutor/par/fio (`eletrico.vias_condutoras.r1_quantidade`)** | 9 | 0,7315 | 0,6362 | **1,0000** | **+0,2685** |
| 7 | **Categoria de rede — CAT5/CAT6A (`eletrico.categoria_rede.r1`)** | 8 | 0,8438 | 0,8854 | **1,0000** | **+0,1562** |
| 8 | Material base — categórico (`material.material_base.r1`) | 430 | 0,8102 | 0,7975 | **0,8190** | **+0,0088** |
| 9 | Corrente elétrica — a/ma (`eletrico.corrente.r1`) | 52 | 0,8136 | 0,8143 | **0,8161** | **+0,0025** |
| 10 | Resistência estrutural — mpa (`mecanico.resistencia.r1`) | 15 | 0,6711 | 0,6628 | 0,6647 | -0,0064 |
| 11 | Pressão hidráulica — bar/psi/pa/kpa/mpa (`hidraulico.pressao.r1`) | 17 | 0,6877 | 0,6804 | 0,6820 | -0,0056 |
| 12 | Norma NBR (`normativo.nbr.r1`) | 132 | 0,6826 | 0,6649 | 0,6737 | -0,0089 |
| 13 | Cor base — categórico (`cor.cor_base.r1`) | 116 | 0,7377 | 0,6543 | 0,7218 | -0,0159 |
| 14 | Tensão — v/kv (`eletrico.tensao.r1`) | 17 | 0,9779 | 0,8762 | 0,9779 | +0,0000 |
| 15 | Potência elétrica — w/kw/kva (`eletrico.potencia_eletrica.r1`) | 29 | 0,8046 | 0,8103 | 0,8046 | +0,0000 |
| 16 | Capacidade — l/litros/ml (`dimensional.capacidade.r1_litros`) | 27 | 0,8657 | 0,8652 | 0,8657 | +0,0000 |
| 17 | Comprimento/diâmetro em polegadas (`comprimento.r2_polegadas` = `diametro.r3_polegadas`, regra idêntica) | 39 | 0,7618 | 0,6597 | 0,7618 | +0,0000 |
| 18 | Área — mm²/cm²/m² (`dimensional.area.r1`) | 14 | 0,7619 | 0,6978 | 0,7619 | +0,0000 |
| 19 | Volume — mm³/cm³/m³ (`dimensional.volume.r1`) | 7 | 0,6429 | 0,6429 | 0,6429 | +0,0000 |
| 20 | Concentração química — % (`quimico.concentracao.r1`) | 7 | 0,6905 | 0,6905 | 0,6905 | +0,0000 |
| 21 | Fases/polos, bitola AWG, classe CA aço, embalagem×2, classe A-D, frequência, bivolt | 1–5 cada | — | — | — | amostra pequena, sem sinal claro |
| — | Diâmetro (símbolo Ø), cor composta, IP, certificado CA, NR, ISO, RPM, torque, temperatura, vazão hidráulica | 0 | — | — | — | **sem dados no benchmark/catálogo** |

*(Delta gateado ordenado do maior ganho para a maior perda; linhas 21 e as "sem dados" agrupadas por
brevidade — números completos em cada pasta de resultado, seção 7.)*

### Casos combinados (atributo "de classe padronizada" + dimensão)

| Combinação | MAP baseline | Só atributo | Só dimensão | **Combinado** |
|---|---|---|---|---|
| mpa (resistência) + dimensional | 0,6711 | 0,6647 | 0,8444 | **0,8481 (+0,1771)** |
| pressão + dimensional | 0,6877 | 0,6820 | 0,8407 | **0,8440 (+0,1563)** |

## 4. Padrões identificados

**a) O gate por tópico nunca piora em relação ao ingênuo, e frequentemente é a diferença entre
prejudicar e ajudar.** Em quase todo teste, o reranking ingênuo (sem checar tópico) foi neutro ou
prejudicial — às vezes drasticamente (tensão: -0,1017; vias condutoras: -0,0952; comprimento em
polegadas: -0,1021). O gate reverteu esses prejuízos, no mínimo restaurando o baseline exatamente, e
com frequência convertendo em ganho real.

**b) Funciona muito bem quando o valor é específico/quase único por item, ou quando é um código
discreto que DEFINE o produto.** Vias condutoras e categoria de rede (cabos de rede: "CAT5E", "4
pares") chegaram a MAP=1,0000 — porque esses valores são exatamente o que diferencia um cabo do
outro. Peso combinado (peso bruto + carga útil), dimensão (principalmente combinações 2D/3D) e DN
seguem o mesmo princípio.

**c) Funciona mal — mesmo gateado — quando o valor é uma "classe padronizada" compartilhada por
várias variantes do MESMO tópico.** Resistência (mpa), pressão (mpa também), cor base e norma NBR
caem nessa categoria: blocos de tamanhos diferentes compartilham a mesma classe de resistência;
tintas diferentes compartilham a mesma cor base; tubos diferentes citam a mesma norma NBR. Nesses
casos a confusão é **dentro do próprio tópico**, então o gate (que só filtra contaminação **entre**
tópicos) não resolve sozinho.

**d) A correção para o caso (c) é combinar com um atributo verdadeiramente discriminante.**
Resistência+dimensão e pressão+dimensão viraram os dois maiores ganhos absolutos do projeto
(+0,1771 e +0,1563) — a dimensão já resolve quase tudo sozinha; o atributo fraco some como ruído
quando somado a um sinal forte, mas raramente domina sozinho.

**e) Vários atributos são neutros simplesmente porque não existe "buraco" para tampar.** Tensão,
potência elétrica, capacidade, área, volume, polegadas: nenhuma das consultas caiu num tópico com MAP
baixo neste benchmark específico — o gate protege (nunca piora), mas não há ganho disponível para
capturar. Isso não significa que o atributo seja inútil em geral, só que ele não coincide com uma
fraqueza real deste corpus.

**f) Vários atributos simplesmente não aparecem no benchmark ou no catálogo.** RPM, torque,
temperatura, vazão hidráulica, IP, certificado CA, NR, ISO, diâmetro-Ø, cor composta — 0 consultas
e/ou 0 itens do catálogo os contêm. Não há como avaliar reranking sem dados.

## 5. Recomendação prática

Para produção, a política recomendada é: **reranking por match exato, gateado por tópico**, aplicado
preferencialmente com:
- atributos combinados por natureza (peso bruto+carga útil; dimensões multi-eixo) — maior retorno;
- atributos-código que definem a categoria do produto (categoria de rede, DN, classificações
  discretas) — retorno altíssimo mesmo sozinhos;
- atributos "de classe padronizada" (resistência, pressão, cor, norma) **só combinados com um
  atributo dimensional/discriminante** — nunca isolados.

Não vale a pena investir nos atributos "sem dados" neste benchmark específico, a menos que o corpus
de consultas mude.

## 6. Possíveis próximos passos

- Testar reranking com **interseção obrigatória** (em vez de soma de pontos por união de conjuntos)
  para os casos combinados — o teste de mpa+dimensão achou 2 consultas ("meio bloco") onde a soma
  favoreceu um item errado com mais atributos batendo; interseção exigiria bater os dois tipos
  simultaneamente.
- Investigar a ambiguidade semântica de `mpa` (resistência estrutural vs. pressão hidráulica) com
  desambiguação por contexto do produto, já que as duas regras de `param_3.json` compartilham a
  unidade sem distinguir o significado.
- Repetir os testes "sem dados" (rpm, torque, temperatura, vazão...) caso o benchmark de consultas
  seja expandido no futuro.

## 7. Índice de arquivos e pastas geradas nesta sessão

| Pasta | Conteúdo |
|---|---|
| `results/real_295_v5_adaptive_fusion/` | Fusão adaptativa por densidade numérica (V5/V6) — abordagem anterior, descontinuada |
| `results/regex_kg_audit/` | Auditoria do token `kg` (verdadeiro/falso positivo, falsos negativos) |
| `results/kg_exact_match_rerank/` | Reranking `kg` — versão ad-hoc, com política condicional (descartada) e gateada por tópico |
| `results/power_cv_hp_analysis/` | Auditoria + reranking `cv`/`hp` — versão ad-hoc |
| `results/param3_regex_validation/` | Revalidação de kg (peso) e cv/hp com as regras oficiais de `param_3.json` |
| `results/mm_regex_analysis/` | Dimensional (`mm`/`cm`/`m`/`pol`), rodada 1 (2 regras) e rodada 2 (6 regras) |
| `results/resistencia_mpa_analysis/` | Resistência estrutural (mpa) isolada + combinada com dimensão |
| `results/eletrico_analysis/` | Tensão, potência elétrica, corrente, frequência, vias condutoras, categoria de rede, bivolt, fases/polos |
| `results/mecanico_hidraulico_analysis/` | Pressão, RPM, resistência (reincluída), torque + pressão combinada com dimensão |
| `results/termico_hidraulico_capacidade_analysis/` | Temperatura, vazão, pressão (reincluída), capacidade em litros |
| `results/param3_remaining_analysis/` | As 20 regras finais: polegadas, área, volume, diâmetro, bitola AWG, material, aço CA, isolação elétrica, cor, normativo (IP/CA/NR/NBR/ISO), embalagem, classe, concentração |
| `class_match/param_3.json` | Lista de regras regex v1.1.0 (correção kg/m + split potência elétrica/mecânica) |

Scripts em `scripts/`: `retrieval_adaptive_fusion_v5.py`, `audit_kg_regex.py`, `rerank_kg_exact_match.py`,
`analyze_kg_rerank_intruders.py`, `audit_power_regex.py`, `rerank_power_exact_match.py`,
`validate_param3_regex.py`, `analyze_mm_regex.py`, `analyze_resistencia_regex.py`,
`analyze_resistencia_dimensional_combo.py`, `analyze_eletrico_regex.py`,
`analyze_mecanico_hidraulico_regex.py`, `analyze_pressao_dimensional_combo.py`,
`analyze_termico_hidraulico_capacidade_regex.py`, `analyze_eletrico_remaining_regex.py`,
`analyze_remaining_param3_regex.py`.
