# Gate por topico + match de atributo, com TOPICO INFERIDO (nao-oraculo) -- Resultados

Repete `combined_vs_isolados_resumo.md` (mesmas ~20 regras de `class_match/param_3.json`, mesma formula combinada `(mesmo_topico, match_count)`), mas usando o topico da consulta **inferido** via `topic_model.transform()` (BERTopic retreinado) em vez do topico do item relevante (o oraculo usado em toda a sessao ate aqui). O topico dos ITENS do catalogo continua sendo o real (`eda/item_topics.csv`) -- so a consulta precisa de inferencia, porque e texto novo.

## Resultado global (852 consultas, uniao de todos os atributos por consulta)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7932 | - |
| So-topico previsto (sem regex) | 0.7414 | -0.0519 |
| **Combinado (topico previsto + atributo)** | **0.7565** | **-0.0368** |

Para comparacao (cenario oraculo, `combined_vs_isolados_resumo.md`): baseline 0,7932 -> so-topico 0,8109 (+0,0177) -> combinado 0,8308 (+0,0376). E (cenario topico previsto SEM atributo, `hierarchical_rerank_predicted_resultados.md`): baseline 0,7932 -> flat previsto 0,7414 (-0,0518).

## Por atributo: baseline vs. so-topico vs. atributo+topico vs. combinado (topico PREVISTO)

| Atributo | N | Baseline | So-topico (previsto) | Atributo+topico (previsto) | **Combinado (previsto)** | Vencedor |
|---|---|---|---|---|---|---|
| Potencia eletrica (w/kw/kva) | 29 | 0.8046 | 0.8046 | 0.8046 | **0.8046** | empate (combinado nao perde) |
| Area (mm2/cm2/m2) | 14 | 0.7619 | 0.7619 | 0.7619 | **0.7619** | empate (combinado nao perde) |
| Volume (mm3/cm3/m3) | 7 | 0.6429 | 0.6429 | 0.6429 | **0.6429** | empate (combinado nao perde) |
| Concentracao quimica (%) | 7 | 0.6905 | 0.6905 | 0.6905 | **0.6905** | empate (combinado nao perde) |
| Potencia mecanica (cv/hp) | 22 | 0.6162 | 0.6137 | 0.6383 | **0.6358** | atributo+topico |
| Isolacao eletrica | 60 | 0.8613 | 0.7902 | 0.7944 | **0.7902** | atributo+topico |
| Capacidade (litros) | 27 | 0.8657 | 0.8611 | 0.8657 | **0.8611** | atributo+topico |
| Material base | 430 | 0.8102 | 0.7641 | 0.7730 | **0.7606** | atributo+topico |
| Norma NBR | 132 | 0.6826 | 0.6728 | 0.6738 | **0.6577** | atributo+topico |
| Pressao hidraulica | 17 | 0.6877 | 0.6950 | 0.6690 | **0.6763** | so-topico |
| Resistencia estrutural (mpa) | 15 | 0.6711 | 0.6711 | 0.6498 | **0.6498** | so-topico |
| Comprimento/diametro em polegadas | 76 | 0.7222 | 0.6898 | 0.7310 | **0.6985** | atributo+topico |
| Peso (kg/g/mg/t) | 46 | 0.7623 | 0.7253 | 0.7821 | **0.7469** | atributo+topico |
| Dimensional (mm/cm/m/pol, 6 regras) | 548 | 0.7906 | 0.7453 | 0.8052 | **0.7685** | atributo+topico |
| Cor base | 116 | 0.7377 | 0.6557 | 0.6989 | **0.6563** | atributo+topico |
| Tensao (v/kv) | 17 | 0.9779 | 0.9265 | 0.9779 | **0.9265** | atributo+topico |
| Vias condutoras | 9 | 0.7315 | 0.5012 | 0.5648 | **0.5012** | atributo+topico |
| Corrente eletrica | 52 | 0.8136 | 0.7498 | 0.8161 | **0.7522** | atributo+topico |
| Diametro nominal (DN) | 24 | 0.9417 | 0.8514 | 0.9583 | **0.8889** | atributo+topico |
| Categoria de rede (CAT5...) | 8 | 0.8438 | 0.5847 | 0.7042 | **0.5847** | atributo+topico |
