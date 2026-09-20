# V5 -- MAP por topico (12 piores da eda), baseline vs melhor fusao adaptativa

Melhor config do grid: `adaptativo_thr0.20_boost4.0x` (threshold=0.2, boost=4.0).

| Topico | Palavras-chave | N consultas | MAP baseline | MAP adaptativo | Delta |
|---|---|---|---|---|---|
| T41 | 500, media, capa, folha, tensao nominal, tripolar | 5 | 0.2602 | 0.2837 | +0.0235 |
| T61 | capa, marco, folha, dobradicas, pronta, alizares | 10 | 0.3263 | 0.3280 | +0.0017 |
| T125 | termoplastica, manta, mm nbr, lisa, pead, nbr | 14 | 0.5000 | 0.5000 | +0.0000 |
| T70 | torneira, cromada, bico, arejador, cozinha, 12 34 | 13 | 0.4110 | 0.3763 | -0.0347 |
| T20 | costura, leve dn, tubo aco, ii, maxima, kgm | 0 | - | - | - |
| T101 | kg, cabine, cv inclui, peso bruto, total, chassi | 11 | 0.4280 | 0.5288 | +0.1008 |
| T59 | mm amianto, amianto, ondulada, fibrocimento, telha, telha fibrocimento | 10 | 0.4500 | 0.4400 | -0.0100 |
| T94 | diametro nominal, fita aco, galvanizado diametro, fita, eletroduto flexivel, nominal | 12 | 0.5764 | 0.5764 | +0.0000 |
| T15 | ppr, quente predial, graus soldavel, quente, predial joelho, ff | 5 | 0.6121 | 0.5121 | -0.1000 |
| T73 | distancia, kg, carroceria, eixos, cv inclui, peso bruto | 6 | 0.7037 | 0.7278 | +0.0241 |
| T2 | bloco, furos, cm, vedacao, mpa, estrutural | 28 | 0.6128 | 0.6802 | +0.0674 |
| T21 | agua esgoto, densidade pead, polietileno alta, alta densidade, densidade, pn | 48 | 0.6753 | 0.6823 | +0.0069 |
