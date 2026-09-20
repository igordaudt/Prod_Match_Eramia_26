# Combinar 'gate por topico' + 'match de atributo' -- potencializa o resultado?

Formula testada: `score = (mesmo_topico, match_count)`, ordenacao lexicografica -- primeiro agrupa por mesmo topico (igual ao so-topico), depois desempata pelo NUMERO de valores do atributo que baterem (preserva a granularidade que o attr+topico usava, ex. caminhao que bate peso bruto E carga util fica acima do que so bate um dos dois).

**Correcao importante**: ao contrario do que a primeira versao desta analise afirmava, isso NAO e garantidamente >= so-topico em todo caso. Reordenar por match_count dentro do bloco de mesmo topico so ajuda quando o atributo realmente discrimina ali dentro; quando o atributo e ruidoso (mpa, capacidade -- ver tabela), o desempate pode empurrar um item errado (que bateu por coincidencia) acima do item certo (que a fusao hibrida ja tinha rankeado bem, mas que nao teve o valor extraido) -- e o combinado fica ABAIXO do so-topico nesses casos (mpa: 0,7732 < 0,7817; capacidade: 0,8537 < attr+topico 0,8657). Na maioria dos atributos, porem, o combinado empata ou supera os dois isolados.

## Resultado global (852 consultas, uniao de todos os atributos por consulta)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7932 | - |
| So-topico (sem regex) | 0.8109 | +0.0177 |
| **Combinado (topico + atributo)** | **0.8308** | **+0.0376** |

## Por atributo: baseline vs. so-topico vs. atributo+topico vs. combinado

| Atributo | N | Baseline | So-topico | Atributo+topico | **Combinado** | Vencedor |
|---|---|---|---|---|---|---|
| Peso (kg/g/mg/t) | 46 | 0.7623 | 0.7793 | 0.8003 | **0.8118** | combinado |
| Potencia mecanica (cv/hp) | 22 | 0.6162 | 0.6218 | 0.6383 | **0.6439** | combinado |
| Dimensional (mm/cm/m/pol, 6 regras) | 548 | 0.7906 | 0.8074 | 0.8342 | **0.8367** | combinado |
| Comprimento/diametro em polegadas | 76 | 0.7222 | 0.7244 | 0.7331 | **0.7353** | combinado |
| Diametro nominal (DN) | 24 | 0.9417 | 0.9417 | 0.9792 | **0.9792** | empate (combinado nao perde) |
| Isolacao eletrica | 60 | 0.8613 | 0.9094 | 0.8993 | **0.9094** | empate (combinado nao perde) |
| Vias condutoras | 9 | 0.7315 | 1.0000 | 1.0000 | **1.0000** | empate (combinado nao perde) |
| Categoria de rede (CAT5...) | 8 | 0.8438 | 1.0000 | 1.0000 | **1.0000** | empate (combinado nao perde) |
| Corrente eletrica | 52 | 0.8136 | 0.8136 | 0.8161 | **0.8161** | empate (combinado nao perde) |
| Tensao (v/kv) | 17 | 0.9779 | 0.9853 | 0.9779 | **0.9853** | empate (combinado nao perde) |
| Potencia eletrica (w/kw/kva) | 29 | 0.8046 | 0.8046 | 0.8046 | **0.8046** | empate (combinado nao perde) |
| Area (mm2/cm2/m2) | 14 | 0.7619 | 0.7619 | 0.7619 | **0.7619** | empate (combinado nao perde) |
| Volume (mm3/cm3/m3) | 7 | 0.6429 | 0.6429 | 0.6429 | **0.6429** | empate (combinado nao perde) |
| Concentracao quimica (%) | 7 | 0.6905 | 0.8571 | 0.6905 | **0.8571** | empate (combinado nao perde) |
| Material base | 430 | 0.8102 | 0.8273 | 0.8190 | **0.8248** | so-topico |
| Pressao hidraulica | 17 | 0.6877 | 0.7927 | 0.6820 | **0.7852** | so-topico |
| Resistencia estrutural (mpa) | 15 | 0.6711 | 0.7817 | 0.6647 | **0.7732** | so-topico |
| Capacidade (litros) | 27 | 0.8657 | 0.8537 | 0.8657 | **0.8537** | atributo+topico |
| Cor base | 116 | 0.7377 | 0.7343 | 0.7218 | **0.7196** | so-topico |
| Norma NBR | 132 | 0.6826 | 0.6928 | 0.6737 | **0.6777** | so-topico |
