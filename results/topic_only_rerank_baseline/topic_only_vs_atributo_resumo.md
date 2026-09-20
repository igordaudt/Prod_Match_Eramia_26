# Reranking so-por-topico (ignorando toda regex de atributo) -- Resultados

Pergunta: e se, em vez de extrair e comparar o valor especifico de cada atributo (kg, mm, cv/hp, mpa...), a gente simplesmente promovesse qualquer item do MESMO topico BERTopic da consulta, sem checar valor nenhum? Isola o efeito do 'gate por topico' (repetido em todos os testes anteriores) do efeito do 'match de atributo especifico' (o que mudava a cada regex).

## Resultado geral (todas as 852 consultas do benchmark)

- MAP baseline (hibrido publicado): **0.7932**
- MAP reranking so-por-topico (sem nenhuma regex de atributo): **0.8109** (delta +0.0177)

## Comparacao consulta a consulta: 'atributo + topico' (ja testado) vs. 'so topico' (esta analise)

Resumo: em **7** dos 28 atributos, o match especifico do atributo (combinado com o gate) superou o reranking so-por-topico; em **11**, o reranking so-por-topico foi igual ou melhor; **10** empates exatos.

| Atributo | N | MAP baseline | MAP atributo+topico | MAP so-topico | Delta atributo+topico | Delta so-topico | Vencedor |
|---|---|---|---|---|---|---|---|
| Diametro nominal (DN) | 24 | 0.9417 | 0.9792 | 0.9417 | +0.0375 | +0.0000 | **atributo** |
| Dimensional (mm/cm/m/pol, 6 regras) | 548 | 0.7906 | 0.8342 | 0.8074 | +0.0437 | +0.0168 | **atributo** |
| Peso (kg/g/mg/t) | 46 | 0.7623 | 0.8003 | 0.7793 | +0.0379 | +0.0170 | **atributo** |
| Potencia mecanica (cv/hp) | 22 | 0.6162 | 0.6383 | 0.6218 | +0.0221 | +0.0057 | **atributo** |
| Capacidade (litros) | 27 | 0.8657 | 0.8657 | 0.8537 | +0.0000 | -0.0120 | **atributo** |
| Corrente eletrica | 52 | 0.8136 | 0.8161 | 0.8136 | +0.0025 | -0.0000 | **atributo** |
| Area (mm2/cm2/m2) | 14 | 0.7619 | 0.7619 | 0.7619 | +0.0000 | -0.0000 | **atributo** |
| Vias condutoras | 9 | 0.7315 | 1.0000 | 1.0000 | +0.2685 | +0.2685 | empate |
| Categoria de rede (CAT5...) | 8 | 0.8438 | 1.0000 | 1.0000 | +0.1562 | +0.1562 | empate |
| Volume (mm3/cm3/m3) | 7 | 0.6429 | 0.6429 | 0.6429 | +0.0000 | +0.0000 | empate |
| Classe CA do aco | 1 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 | empate |
| Classe (A-D) | 4 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 | empate |
| Embalagem (caixa/pct/kit com N) | 2 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 | empate |
| Embalagem (N unidades/pecas) | 5 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 | empate |
| Frequencia (hz) | 1 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 | empate |
| Bivolt | 1 | 1.0000 | 1.0000 | 1.0000 | +0.0000 | +0.0000 | empate |
| Fases/polos | 3 | 0.8333 | 0.8333 | 0.8333 | +0.0000 | +0.0000 | empate |
| Potencia eletrica (w/kw/kva) | 29 | 0.8046 | 0.8046 | 0.8046 | +0.0000 | +0.0000 | **só-tópico** |
| Comprimento/diametro em polegadas | 39 | 0.7618 | 0.7618 | 0.7661 | +0.0000 | +0.0043 | **só-tópico** |
| Tensao (v/kv) | 17 | 0.9779 | 0.9779 | 0.9853 | +0.0000 | +0.0074 | **só-tópico** |
| Material base | 430 | 0.8102 | 0.8190 | 0.8273 | +0.0088 | +0.0172 | **só-tópico** |
| Isolacao eletrica | 60 | 0.8613 | 0.8993 | 0.9094 | +0.0380 | +0.0481 | **só-tópico** |
| Cor base | 116 | 0.7377 | 0.7218 | 0.7343 | -0.0159 | -0.0034 | **só-tópico** |
| Norma NBR | 132 | 0.6826 | 0.6737 | 0.6928 | -0.0089 | +0.0102 | **só-tópico** |
| Pressao hidraulica | 17 | 0.6877 | 0.6820 | 0.7927 | -0.0056 | +0.1050 | **só-tópico** |
| Resistencia estrutural (mpa) | 15 | 0.6711 | 0.6647 | 0.7817 | -0.0064 | +0.1107 | **só-tópico** |
| Concentracao quimica (%) | 7 | 0.6905 | 0.6905 | 0.8571 | +0.0000 | +0.1667 | **só-tópico** |
| Bitola AWG/MCM | 4 | 0.7083 | 0.7083 | 1.0000 | +0.0000 | +0.2917 | **só-tópico** |
