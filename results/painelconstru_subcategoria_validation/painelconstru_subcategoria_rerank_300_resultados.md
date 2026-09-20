# Validacao PainelConstru (300 consultas) -- gate por subcategoria

Estende `painelconstru_subcategoria_rerank_resultados.md` (100 consultas) com mais 200 consultas novas do mesmo benchmark (`class_match/ground_truth/benchmark_grouped_v4.json`), sem sobreposicao (mesma seed=42, sequencia de amostragem continuada). Corpus estendido: 12315 itens (12000 do corpus original + 315 itens novos necessarios para cobrir os itens relevantes das 200 consultas adicionais). Os embeddings BGE-M3 dos itens originais foram reaproveitados do cache; so os itens novos foram embedados nesta rodada.

## Resultado

| Lote | N | MAP baseline | MAP flat-subcategoria | Delta |
|---|---|---|---|---|
| Original 100 (recalculado) | 100 | 0.7969 | 0.8209 | +0.0241 |
| Novas 200 | 200 | 0.7962 | 0.8080 | +0.0118 |
| Combinado (300) | 300 | 0.7964 | 0.8123 | +0.0159 |

Para referencia: SINAPI (852 consultas, oraculo) = baseline 0.7932, flat subcategoria 0.8016 (+0.0084). PainelConstru 100 consultas (rodada anterior, corpus menor/reprodutivel de forma independente) = baseline 0.7991, flat subcategoria 0.8080 (+0.0089).

