# Regex de atributo + gate por subcategoria (SINAPI) -- Resultados

Mesma formula ja validada para atributo+topico (`results/topic_only_rerank_baseline/combined_vs_isolados_resumo.md`), agora usando a subcategoria SINAPI como gate no lugar do topico BERTopic: `score = (mesma_subcategoria, match_count_se_mesma_subcategoria)`. Sem topico nesta rodada (a pedido do usuario). Subcategoria da consulta = a do proprio item relevante (ORACULO, mesma convencao da sessao -- ver ressalva de inferencia em `results/hierarchical_topic_rerank/`).

## Resultado global (852 consultas, uniao de todos os atributos)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7932 | - |
| **Atributo + subcategoria** | **0.8249** | **+0.0316** |

Para referencia (ja calculado em `subcategoria_rerank_resultados.md`, sem atributo): flat subcategoria = 0.8016 (+0.0084); flat topico = 0.8109 (+0.0177); combinado topico+subcategoria = 0.8143 (+0.0211).


## Por atributo

| Atributo | N | Baseline | **Atributo + subcategoria** | Delta |
|---|---|---|---|---|
| Dimensional (mm/cm/m/pol, 6 regras) | 548 | 0.7906 | **0.8351** | +0.0446 |
| Categoria de rede (CAT5...) | 8 | 0.8438 | **0.8854** | +0.0417 |
| Peso (kg/g/mg/t) | 46 | 0.7623 | **0.8003** | +0.0379 |
| Diametro nominal (DN) | 24 | 0.9417 | **0.9792** | +0.0375 |
| Potencia mecanica (cv/hp) | 22 | 0.6162 | **0.6355** | +0.0194 |
| Potencia eletrica (w/kw/kva) | 29 | 0.8046 | **0.8103** | +0.0057 |
| Isolacao eletrica | 60 | 0.8613 | **0.8667** | +0.0053 |
| Corrente eletrica | 52 | 0.8136 | **0.8154** | +0.0017 |
| Material base | 430 | 0.8102 | **0.8107** | +0.0005 |
| Capacidade (litros) | 27 | 0.8657 | **0.8657** | +0.0000 |
| Volume (mm3/cm3/m3) | 7 | 0.6429 | **0.6429** | +0.0000 |
| Concentracao quimica (%) | 7 | 0.6905 | **0.6905** | +0.0000 |
| Comprimento/diametro em polegadas | 76 | 0.7222 | **0.7201** | -0.0021 |
| Cor base | 116 | 0.7377 | **0.7355** | -0.0022 |
| Norma NBR | 132 | 0.6826 | **0.6695** | -0.0131 |
| Pressao hidraulica | 17 | 0.6877 | **0.6714** | -0.0163 |
| Resistencia estrutural (mpa) | 15 | 0.6711 | **0.6525** | -0.0185 |
| Area (mm2/cm2/m2) | 14 | 0.7619 | **0.7202** | -0.0417 |
| Tensao (v/kv) | 17 | 0.9779 | **0.8995** | -0.0784 |
| Vias condutoras | 9 | 0.7315 | **0.6389** | -0.0926 |
