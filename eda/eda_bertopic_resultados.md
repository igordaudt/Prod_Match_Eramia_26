# EDA — BERTopic sobre o Corpus de Itens Combinado (7,252 itens, real + sintético)

Configuracao: embeddings `paraphrase-multilingual-MiniLM-L12-v2`, UMAP {'n_neighbors': 15, 'n_components': 5, 'metric': 'cosine', 'min_dist': 0.0, 'random_state': 42}, HDBSCAN(min_cluster_size=20), CountVectorizer(custom+bigramas, min_df=3). Reaproveitada de `Topic Modeling/tarefa2c_preprocessing.py` (melhor config identificada).

- Topicos encontrados: **128**
- Outliers (topico -1): 1694 (23.4%)
- Tempo de treinamento: 36.7s

## Top 20 tópicos por tamanho

| # | Tópico | Docs | Palavras-chave (top-7) |
|---|---|---|---|
| 1 | T0 | 180 | mensalista, auxiliar, horista, engenheiro, civil, mecanico, pedreiro |
| 2 | T1 | 144 | parafuso, zincado, cabeca, soberba, rosca soberba, comprimento mm, comprimento |
| 3 | T2 | 144 | bloco, furos, cm, vedacao, mpa, estrutural, 20 |
| 4 | T3 | 116 | angelim, regiao, regiao bruta, bruta, 25, 75, viga |
| 5 | T4 | 110 | diametro externo, externo mm, flexivel, eletroduto flexivel, preto, 34 ligacao, externo |
| 6 | T5 | 103 | je, mm rede, rede coletora, coletora esgoto, coletora, rede, 10569 |
| 7 | T6 | 97 | amarracao, abracadeira, zamac, cromado, dobradica, poco, acabamento natural |
| 8 | T7 | 96 | motor, cv, capacidade, motor diesel, diesel, potencia, capacidade nominal |
| 9 | T8 | 94 | inox, maquina, kit, mm fechadura, fechadura, carenagem, apoio |
| 10 | T9 | 94 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua, soldavel, livre |
| 11 | T10 | 90 | hp, peso, hp peso, potencia, liquida, maximo, m3 |
| 12 | T11 | 87 | cpvc, cpvc soldavel, agua quente, quente, mm agua, soldavel mm, quente predial |
| 13 | T12 | 79 | tinta, premium, acrilica, tinta esmalte, esmalte, sinapi, argamassa |
| 14 | T13 | 76 | aluminio, rosca 12, bucha, 12 eletroduto, eletroduto, bucha reducao, rosca |
| 15 | T14 | 73 | cabo, mm cabo, cobre flexivel, secao nominal, nominal mm, nominal, cabo cobre |
| 16 | T15 | 70 | ppr, quente predial, graus soldavel, quente, predial joelho, ff, agua quente |
| 17 | T16 | 66 | lampada, bivolt, luva eletroduto, lampada vapor, base e27, base, e27 |
| 18 | T17 | 65 | eucalipto, tratamento, regiao, preto, cm mm, painel, placas |
| 19 | T18 | 64 | conexao crimpagem, crimpagem, plastico, conexao, tubo pex, pex, rosca femea |
| 20 | T19 | 64 | antichama, cobre flexivel, classe isolacao, mm2 cabo, isolacao, nominal mm2, secao nominal |

## Distribuição temática das consultas (852 reais + 48 sintéticas)

- Real: consultas cujo item-alvo cai em outlier de tópico: 25.8%
- Sintético: consultas cujo item-alvo cai em outlier de tópico: 6.2%

| Tópico | Palavras-chave | Consultas reais | % real | Consultas sintéticas | % sintético |
|---|---|---|---|---|---|
| T-1 | outliers (-1) | 220 | 25.8% | 3 | 6.2% |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte | 58 | 6.8% | 0 | 0.0% |
| T21 | agua esgoto, densidade pead, polietileno alta, alta densidade, densidade | 48 | 5.6% | 0 | 0.0% |
| T2 | bloco, furos, cm, vedacao, mpa | 28 | 3.3% | 0 | 0.0% |
| T22 | janela, brilhante, bandeira, aluminio, vidro | 25 | 2.9% | 0 | 0.0% |
| T7 | motor, cv, capacidade, motor diesel, diesel | 24 | 2.8% | 0 | 0.0% |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm | 23 | 2.7% | 0 | 0.0% |
| T90 | resistencia dan, dan, extensao resistencia, armado secao, extensao | 22 | 2.6% | 0 | 0.0% |
| T81 | resistencia dan, dan, extensao resistencia, armado secao, extensao | 21 | 2.5% | 0 | 0.0% |
| T75 | forma, madeira, mm sinapi, 11, concreto | 20 | 2.3% | 0 | 0.0% |
| T20 | costura, leve dn, tubo aco, ii, maxima | 0 | 0.0% | 18 | 37.5% |
| T69 | moldado, comp, contribuintes, guia, concreto premoldado | 17 | 2.0% | 0 | 0.0% |
| T55 | circular, dan, resistencia dan, extensao resistencia, armado secao | 15 | 1.8% | 0 | 0.0% |
| T83 | faces, termoplastica, bolsa bolsa, manta, mm nbr | 14 | 1.6% | 0 | 0.0% |
| T111 | roscavel flanges, vedacao mm, flanges anel, anel vedacao, flanges | 14 | 1.6% | 0 | 0.0% |

## MAP médio por tópico e método — dados combinados (tópicos com >= 5 consultas)

Ordenado pela maior vantagem do BM25 sobre o BGE-M3 hybrid (delta = MAP(bm25) − MAP(bge_m3_hybrid)).

| Tópico | Palavras-chave | n_consultas | bm25 | e5 | e5_hybrid | bge_m3_hybrid | delta_bm25_menos_bge |
|---|---|---|---|---|---|---|---|
| T119 | quente fria, mm cor, conector, cor marrom, marrom agua | 5 | 1.000 | 0.753 | 0.883 | 0.833 | 0.167 |
| T75 | forma, madeira, mm sinapi, 11, concreto | 20 | 0.749 | 0.537 | 0.652 | 0.606 | 0.143 |
| T101 | kg, cabine, cv inclui, peso bruto, total | 11 | 0.538 | 0.408 | 0.408 | 0.428 | 0.110 |
| T23 | mm anel, tampa concreto, elastica, arame, malha cm | 23 | 0.844 | 0.813 | 0.867 | 0.764 | 0.080 |
| T94 | diametro nominal, fita aco, galvanizado diametro, fita, eletroduto flexivel | 12 | 0.639 | 0.195 | 0.615 | 0.576 | 0.062 |
| T73 | distancia, kg, carroceria, eixos, cv inclui | 6 | 0.764 | 0.256 | 0.449 | 0.704 | 0.060 |
| T2 | bloco, furos, cm, vedacao, mpa | 28 | 0.665 | 0.382 | 0.524 | 0.613 | 0.052 |
| T90 | resistencia dan, dan, extensao resistencia, armado secao, extensao | 22 | 1.000 | 0.856 | 1.000 | 0.955 | 0.045 |
| T12 | tinta, premium, acrilica, tinta esmalte, esmalte | 58 | 0.823 | 0.750 | 0.785 | 0.778 | 0.045 |
| T32 | tubo pvc, corrugado, 5688, nbr 5688, luva correr | 13 | 0.851 | 0.649 | 0.839 | 0.810 | 0.041 |
| T41 | 500, media, capa, folha, tensao nominal | 5 | 0.296 | 0.244 | 0.257 | 0.260 | 0.036 |
| T14 | cabo, mm cabo, cobre flexivel, secao nominal, nominal mm | 7 | 0.929 | 0.905 | 0.929 | 0.893 | 0.036 |
| T50 | perfil aco, espelho, laminado, dobradica, mm anel | 5 | 0.700 | 0.500 | 0.567 | 0.667 | 0.033 |
| T81 | resistencia dan, dan, extensao resistencia, armado secao, extensao | 21 | 0.976 | 0.909 | 1.000 | 0.944 | 0.032 |
| T61 | capa, marco, folha, dobradicas, pronta | 10 | 0.349 | 0.219 | 0.288 | 0.326 | 0.023 |
| T21 | agua esgoto, densidade pead, polietileno alta, alta densidade, densidade | 48 | 0.682 | 0.351 | 0.488 | 0.675 | 0.007 |
| T22 | janela, brilhante, bandeira, aluminio, vidro | 25 | 0.793 | 0.631 | 0.733 | 0.792 | 0.001 |
| T125 | termoplastica, manta, mm nbr, lisa, pead | 14 | 0.500 | 0.123 | 0.214 | 0.500 | 0.000 |
| T9 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua | 13 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| T17 | eucalipto, tratamento, regiao, preto, cm mm | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| T7 | motor, cv, capacidade, motor diesel, diesel | 24 | 0.896 | 0.882 | 0.896 | 0.896 | 0.000 |
| T121 | unipolar, blindado, cobertura, kv, isolacao | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| T100 | fogo, bandeira, mm sinapi, mecanica, 15 mm | 12 | 1.000 | 0.917 | 1.000 | 1.000 | 0.000 |
| T67 | usinado, servico, resistencia, latao cromado, classe | 5 | 1.000 | 0.900 | 1.000 | 1.000 | 0.000 |
| T55 | circular, dan, resistencia dan, extensao resistencia, armado secao | 15 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| T11 | cpvc, cpvc soldavel, agua quente, quente, mm agua | 5 | 1.000 | 0.733 | 1.000 | 1.000 | 0.000 |
| T69 | moldado, comp, contribuintes, guia, concreto premoldado | 17 | 0.912 | 0.912 | 0.912 | 0.912 | 0.000 |
| T44 | grelha, branca, pvc mm, ralo, redonda | 5 | 0.800 | 0.767 | 0.800 | 0.800 | 0.000 |
| T83 | faces, termoplastica, bolsa bolsa, manta, mm nbr | 14 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| T24 | polido, granito, cm, regiao, marmore | 8 | 0.625 | 0.562 | 0.604 | 0.625 | 0.000 |
| T42 | litros, litros tampa, tampa caixa, asfaltica, caixa dagua | 13 | 0.967 | 0.866 | 0.929 | 0.968 | -0.001 |
| T3 | angelim, regiao, regiao bruta, bruta, 25 | 11 | 0.870 | 0.834 | 0.847 | 0.871 | -0.001 |
| T10 | hp, peso, hp peso, potencia, liquida | 11 | 0.736 | 0.676 | 0.736 | 0.739 | -0.002 |
| T111 | roscavel flanges, vedacao mm, flanges anel, anel vedacao, flanges | 14 | 0.827 | 0.787 | 0.824 | 0.829 | -0.003 |
| T59 | mm amianto, amianto, ondulada, fibrocimento, telha | 10 | 0.437 | 0.433 | 0.500 | 0.450 | -0.013 |
| T123 | lavatorio, mesa lavatorio, mesa, cromada, cromada mesa | 7 | 0.706 | 0.695 | 0.714 | 0.732 | -0.026 |
| T-1 | outliers (-1) | 232 | 0.796 | 0.785 | 0.808 | 0.828 | -0.032 |
| T70 | torneira, cromada, bico, arejador, cozinha | 13 | 0.359 | 0.379 | 0.355 | 0.411 | -0.052 |
| T122 | fibra vidro, litros tampa, fibra, reforcado, reservatorio | 5 | 0.900 | 1.000 | 0.900 | 1.000 | -0.100 |
| T15 | ppr, quente predial, graus soldavel, quente, predial joelho | 5 | 0.510 | 0.408 | 0.609 | 0.612 | -0.102 |
| T85 | cat, categoria, 5e, pares, par | 7 | 0.549 | 0.821 | 0.592 | 0.655 | -0.106 |
| T107 | forro, forro pvc, regua, cm espessura, borda | 8 | 0.708 | 0.812 | 0.771 | 0.896 | -0.188 |
| T20 | costura, leve dn, tubo aco, ii, maxima | 18 | 0.364 | 0.364 | 0.460 | 0.581 | -0.217 |
| T112 | predial nbr, 5648, nbr 5648, tubo pvc, nervurado | 9 | 0.553 | 0.694 | 0.730 | 0.815 | -0.262 |
