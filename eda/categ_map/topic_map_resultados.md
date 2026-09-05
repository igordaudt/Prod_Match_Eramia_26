# MAP por Subcategoria (Tópicos BERTopic) — Melhores e Piores

Tópicos definidos por BERTopic sobre o corpus combinado (7.252 itens, mesma config de `scripts/eda_bertopic.py`). MAP médio das 900 consultas combinadas (852 reais + 48 sintéticas), média dos 4 métodos comuns (BM25, E5 puro, E5 hybrid, BGE-M3 hybrid). Ranking considera apenas tópicos com >= 5 consultas (46 de 78 tópicos qualificam).


## Top 12 tópicos com MAIOR MAP

| Tópico | Palavras-chave | N consultas | MAP médio |
|---|---|---|---|
| T9 | adaptador pvc, adaptador, pvc soldavel, agua adaptador, caixa agua, soldavel | 13 | 1.0000 |
| T17 | eucalipto, tratamento, regiao, preto, cm mm, painel | 5 | 1.0000 |
| T121 | unipolar, blindado, cobertura, kv, isolacao, cabo cobre | 5 | 1.0000 |
| T55 | circular, dan, resistencia dan, extensao resistencia, armado secao, poste concreto | 15 | 1.0000 |
| T83 | faces, termoplastica, bolsa bolsa, manta, mm nbr, bolsa | 14 | 1.0000 |
| T100 | fogo, bandeira, mm sinapi, mecanica, 15 mm, aco galvanizado | 12 | 0.9792 |
| T67 | usinado, servico, resistencia, latao cromado, classe, nbr | 5 | 0.9750 |
| T81 | resistencia dan, dan, extensao resistencia, armado secao, extensao, poste concreto | 21 | 0.9573 |
| T90 | resistencia dan, dan, extensao resistencia, armado secao, extensao, poste concreto | 22 | 0.9527 |
| T122 | fibra vidro, litros tampa, fibra, reforcado, reservatorio, litros | 5 | 0.9500 |
| T11 | cpvc, cpvc soldavel, agua quente, quente, mm agua, soldavel mm | 5 | 0.9333 |
| T42 | litros, litros tampa, tampa caixa, asfaltica, caixa dagua, dagua | 13 | 0.9325 |

## Top 12 tópicos com MENOR MAP

| Tópico | Palavras-chave | N consultas | MAP médio |
|---|---|---|---|
| T41 | 500, media, capa, folha, tensao nominal, tripolar | 5 | 0.2644 |
| T61 | capa, marco, folha, dobradicas, pronta, alizares | 10 | 0.2956 |
| T125 | termoplastica, manta, mm nbr, lisa, pead, nbr | 14 | 0.3343 |
| T70 | torneira, cromada, bico, arejador, cozinha, 12 34 | 13 | 0.3761 |
| T20 | costura, leve dn, tubo aco, ii, maxima, kgm | 18 | 0.4421 |
| T101 | kg, cabine, cv inclui, peso bruto, total, chassi | 11 | 0.4453 |
| T59 | mm amianto, amianto, ondulada, fibrocimento, telha, telha fibrocimento | 10 | 0.4550 |
| T94 | diametro nominal, fita aco, galvanizado diametro, fita, eletroduto flexivel, nominal | 12 | 0.5062 |
| T15 | ppr, quente predial, graus soldavel, quente, predial joelho, ff | 5 | 0.5349 |
| T73 | distancia, kg, carroceria, eixos, cv inclui, peso bruto | 6 | 0.5431 |
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 28 | 0.5459 |
| T21 | agua esgoto, densidade pead, polietileno alta, alta densidade, densidade, pn | 48 | 0.5491 |

*Nota: tópico -1 ('outliers') agrupa itens que o BERTopic não conseguiu associar a nenhum cluster coerente — 223 consultas, MAP médio 0.8053.*
