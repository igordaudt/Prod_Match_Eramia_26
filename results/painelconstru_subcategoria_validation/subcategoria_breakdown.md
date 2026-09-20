# PainelConstru (300 consultas) -- segmentacao por subcategoria

Agrega `painelconstru_subcategoria_rerank_300_per_query.csv` por `subcategory_id`. 87 subcategorias distintas nas 300 consultas amostradas (media ~3.4 consultas/subcategoria -- bem fragmentado). Tabelas abaixo usam so subcategorias com N>=3 consultas (N=35) para reduzir ruido de amostra pequena; o CSV completo (`subcategoria_breakdown.csv`) tem todas as 87, incluindo N=1/2.

## Top 10 -- gate MAIS ajuda (maior delta, N>=3)

| Subcategoria | N | MAP baseline | MAP flat-sub | Delta | Exemplos |
|---|---|---|---|---|---|
| Sanitário (21) | 6 | 0.6892 | 0.9167 | +0.2274 | TUBO DE POLIETILENO DE ALTA DENSIDADE, PEAD, PE-80, DE= 630 MM X 57,3 MM PAREDE (SDR 11 - PN 12,5 ) PARA REDE DE AGUA OU ESGOTO ( NBR 15561) | TE, PVC, 90 GRAUS, BBB, JE, DN 200 MM, PARA REDE COLETORA ESGOTO (NBR 10569) | SELIM COMPACTO EM PVC, SEM TRAVA,  DN 200 X 100 MM, PARA REDE COLETORA ESGOTO (NBR 10569) |
| Refletores (143) | 5 | 0.3425 | 0.5667 | +0.2242 | Refletor de LED 200W, voltagem de 220 v, fluxo luminoso de no mínimo 14.000 lumens, eficiência luminosa de no mínimo 70l/w, vida útil de no mínimo 25.000 horas. | LUMINÁRIA PÚBLICA LED | LUMINÁRIA PÚBLICA LED |
| Ferragens para Fixar e Montar (107) | 5 | 0.8118 | 0.9667 | +0.1549 | ARMACAO VERTICAL COM HASTE E CONTRA-PINO, EM CHAPA DE ACO GALVANIZADO 3/16", COM 3 ESTRIBOS E 3 ISOLADORES | GRAMPO DE ACO POLIDO 1 " X 9 | ABRAÇADEIRA DE NYLON 6.6 (PA66) 350 X 7,6MM PRETA |
| Tubos e conexões industriais (398) | 10 | 0.6991 | 0.7935 | +0.0944 | Tee reduzido 2x1' galvanizado | TE DE FERRO GALVANIZADO, DE 2" | TE DE FERRO GALVANIZADO, DE 1 1/2" |
| Aços para Construção (159) | 3 | 0.7296 | 0.8164 | +0.0867 | ACO CA-25, 32,0 MM, BARRA DE TRANSFERENCIA | Aço CA-50 12,5mm | ACO CA-60, 6,0 MM OU 7,0 MM, DOBRADO E CORTADO |
| Madeiras para Construção (152) | 3 | 0.8781 | 0.9583 | +0.0803 | MADEIRA EUCALIPTO (10cmX20cmX5,4m) | VIGA APARELHADA  *6 X 12* CM, EM MACARANDUBA, ANGELIM OU EQUIVALENTE DA REGIAO | Caibro 5x10x5,5 |
| Acessórios e Conexões Elétricas (188) | 6 | 0.4298 | 0.4823 | +0.0525 | TERMINAL ELÉTRICO - PRÉ-ISOLADO PINO TUBULAR SIMPLES (ILHÓS) VERMELHA 1,00MM² | Fita isolante 18mm x 20m | PRENSA CABO BSP 1" |
| Registros e Bases (214) | 4 | 0.7086 | 0.7427 | +0.0341 | REGISTRO ESFERA PVC COM ROSCA INTERNA ½ | Registro DN20mm PVC | REGISTRO GAVETA BRUTO EM LATAO FORJADO, BITOLA 2 1/2 " (REF 1509) |
| Cabos e Fios Elétricos (189) | 29 | 0.3485 | 0.3631 | +0.0146 | Condutor 10mm vermelho | CABO FLEXÍVEL AUTO 450V/750V 10MM PRETO | CABO FLEXÍVEL PP BIPOLAR 2 X 2,5MM², DE FIO DE COBRE ELETROLÍTICO, COM CAPACIDADE DE ATÉ 750V, COM A ESPESSURA MÍNIMA DE ISOLAÇÃO DE 0,8MM E ESPESSURA MÍNIMA DA COBERTURA DE 1,0MM, COM CARACTERÍSTICAS ESPECIAIS PARA NÃO PROPAGAÇÃO E AUTO EXTINÇÃO DO FOGO, |
| Canos e Conexões Hidráulicas (207) | 35 | 0.9106 | 0.9244 | +0.0138 | CAP PVC, ROSCAVEL, 3",  AGUA FRIA PREDIAL | ADAPTADOR PVC PARA SIFAO, ROSCAVEL, 40 MM X 1 1/4" | LUVA DE REDUCAO DE FERRO GALVANIZADO, COM ROSCA BSP, DE 1 1/2" X 1/2" |

## Top 10 -- gate MAIS atrapalha (menor delta, N>=3)

| Subcategoria | N | MAP baseline | MAP flat-sub | Delta | Exemplos |
|---|---|---|---|---|---|
| Disjuntores e Fusíveis (190) | 6 | 0.7040 | 0.6580 | -0.0460 | DISJUNTOR 3 X 40 A | DISJUNTOR TERMOMAGNETICO PARA TRILHO DIN (IEC), MONOPOLAR, 6 - 32 A | Disjuntor monopolar tipo DIN 3KA 1P 20A, curva C. |
| EPI: Equipamentos Proteção Individual (255) | 6 | 1.0000 | 0.9583 | -0.0417 | FILTRO MECÂNICO PARA POEIRAS, FUMOS E NÉVOAS TÓXICAS NÃO OLEO- SAS, CLASSE P2. QUANTITATIVOS SERÃO INFORMADOS APÓS A EMISSÃO DA NOTA DE EMPENHO EM FORMULÁRIO PRÓPRIO, SE ELETRÔNICO, EX- TENSÃO PDF. O MATERIAL DEVERÁ TER COMO MARCA DE REFERÊNCIA DE QUALIDADE IGUAL OU SUPERIOR A 3M (REF. Filtro 3M, 5N11, SÉRIE 6000). | PATCH CORD, CATEGORIA 5 E, EXTENSAO DE 2,50 M | FERRAMENTAS - FAMILIA OPERADOR ESCAVADEIRA - MENSALISTA (ENCARGOS COMPLEMENTARES - COLETADO CAIXA) |
| Tubos e Eletrodutos (203) | 14 | 0.9456 | 0.9423 | -0.0034 | NIPLE SEXTAVADO EM ACO CARBONO, COM ROSCA BSP, PRESSAO 3.000 LBS, DN 2 1/2" | ELETRODUTO FLEXIVEL, EM ACO GALVANIZADO, REVESTIDO EXTERNAMENTE COM PVC PRETO, DIAMETRO EXTERNO DE 75 MM (2 1/2"), TIPO SEALTUBO | CONDULETE DE ALUMINIO TIPO T, PARA ELETRODUTO ROSCAVEL DE 2", COM TAMPA CEGA |
| Construção Civil (314) | 12 | 0.9861 | 0.9861 | +0.0000 | AJUDANTE DE OPERACAO EM GERAL | MUDA DE ARBUSTO FLORIFERO, CLUSIA/GARDENIA/MOREIA BRANCA/ AZALEIA OU EQUIVALENTE DA REGIAO, H= *50 A 70* CM | AUXILIAR DE ENCANADOR OU BOMBEIRO HIDRAULICO |
| Poste de Concreto (361) | 12 | 0.8949 | 0.8949 | +0.0000 | Poste de Concreto- B e BT 18,00m tipo B 600DaN | POSTE DE CONCRETO ARMADO DE SECAO CIRCULAR, EXTENSAO DE 14,00 M, RESISTENCIA DE 2500 DAN, TIPO C-29 | Poste de Concreto- B e BT 14,00m tipo B 600DaN |
| Ferramentas Elétricas/Bateria (123) | 5 | 0.8667 | 0.8667 | +0.0000 | POLIDORA DE PISO (POLITRIZ) ELETRICA, MOTOR MONOFASICO DE 4 HP, PESO DE 100 KG, DIAMETRO DO TRABALHO DE 450 MM | COMPRESSOR DE AR REBOCAVEL, VAZAO 89 PCM, PRESSAO EFETIVA DE TRABALHO *102* PSI, MOTOR DIESEL, POTENCIA *20* CV | COMPRESSOR DE AR REBOCAVEL VAZAO 748 PCM, PRESSAO EFETIVA DE TRABALHO 102 PSI, MOTOR DIESEL, POTENCIA 210 CV |
| Proteções Elétricas (38) | 5 | 0.8667 | 0.8667 | +0.0000 | FUSIVEL NH 20 A TAMANHO 000, CAPACIDADE DE INTERRUPCAO DE 120 KA, TENSAO NOMIMNAL DE 500 V | FUSIVEL DIAZED 20 A TAMANHO DII, CAPACIDADE DE INTERRUPCAO DE 50 KA EM VCA E 8 KA EM VCC, TENSAO NOMINAL DE 500 V | FUSIVEL NH 100 A TAMANHO 00, CAPACIDADE DE INTERRUPCAO DE 120 KA, TENSAO NOMINAL DE 500 V |
| Cimentos (169) | 4 | 1.0000 | 1.0000 | +0.0000 | Cimento Votoran 50kg | CIMENTO PORTLAND ESTRUTURAL BRANCO CPB-32 | REJUNTE BRANCO, CIMENTICIO |
| Artefatos de Concreto (317) | 4 | 1.0000 | 1.0000 | +0.0000 | MOURAO DE CONCRETO; MODELO: PONTA VIRADA PARA CERCAS; | ANEL EM CONCRETO ARMADO, LISO,  PARA FOSSAS SEPTICAS E SUMIDOUROS, COM FUNDO, DIAMETRO INTERNO DE 1,20 M E ALTURA DE 0,50 M | CAIXA DE CONCRETO ARMADO PRE-MOLDADO, SEM FUNDO, QUADRADA, DIMENSOES DE 0,30 X 0,30 X 0,30 M |
| Parafusos e acessórios (467) | 4 | 0.8958 | 0.8958 | +0.0000 | PARAFUSO ROSCA SOBERBA ZINCADO CABECA CHATA FENDA SIMPLES 5,5 X 50 MM (2") | PORCA OLHAL M 16,  EM ACO GALVANIZADO, DIAMETRO = 16 MM | PINO DE ACO COM ARRUELA CONICA, DIAMETRO ARRUELA = *23* MM E COMP HASTE = *27* MM (ACAO INDIRETA) |

## Top 10 -- maior MAP absoluto (com gate, N>=3)

| Subcategoria | N | MAP baseline | MAP flat-sub | Delta |
|---|---|---|---|---|
| Cimentos (169) | 4 | 1.0000 | 1.0000 | +0.0000 |
| Artefatos de Concreto (317) | 4 | 1.0000 | 1.0000 | +0.0000 |
| Acessórios de Portas e Janelas (236) | 4 | 1.0000 | 1.0000 | +0.0000 |
| Dutos e conexões PEAD (454) | 4 | 1.0000 | 1.0000 | +0.0000 |
| Barras, Tubos e Chapas Metalon (163) | 3 | 1.0000 | 1.0000 | +0.0000 |
| Telhas Cerâmicas (183) | 3 | 1.0000 | 1.0000 | +0.0000 |
| Acessórios e Consumíveis para Ferramentas (119) | 3 | 1.0000 | 1.0000 | +0.0000 |
| Para Raios e SPDA (14) | 3 | 1.0000 | 1.0000 | +0.0000 |
| Construção Civil (314) | 12 | 0.9861 | 0.9861 | +0.0000 |
| Ferragens para Fixar e Montar (107) | 5 | 0.8118 | 0.9667 | +0.1549 |

## Top 10 -- menor MAP absoluto (com gate, N>=3)

| Subcategoria | N | MAP baseline | MAP flat-sub | Delta |
|---|---|---|---|---|
| Cabos e Fios Elétricos (189) | 29 | 0.3485 | 0.3631 | +0.0146 |
| Acessórios e Conexões Elétricas (188) | 6 | 0.4298 | 0.4823 | +0.0525 |
| Refletores (143) | 5 | 0.3425 | 0.5667 | +0.2242 |
| Disjuntores e Fusíveis (190) | 6 | 0.7040 | 0.6580 | -0.0460 |
| Perfis e chapas em aço carbono (439) | 3 | 0.6667 | 0.6667 | +0.0000 |
| Ferramentas   para Pintura (127) | 3 | 0.6728 | 0.6758 | +0.0030 |
| Lâmpadas (138) | 3 | 0.6774 | 0.6806 | +0.0031 |
| Chapas e Painéis (147) | 3 | 0.7398 | 0.7404 | +0.0006 |
| Registros e Bases (214) | 4 | 0.7086 | 0.7427 | +0.0341 |
| Ar Condicionado (66) | 5 | 0.7711 | 0.7713 | +0.0002 |
