# Divisão por Mediana de Jaccard — Metade Inferior vs. Superior (900 consultas combinadas)

Mediana de Jaccard (base combinada, 900 consultas): **0.7543**

## MAP por método, por metade

| Metade | N (real+sint) | Jaccard (faixa) | Jaccard médio | BM25 | E5 puro | E5 hybrid | BGE-M3 hybrid | Vantagem semântica (BGE-M3 hyb. − BM25) |
|---|---|---|---|---|---|---|---|---|
| Inferior (Jaccard < 0.754) | 450 (404+46) | 0.000–0.750 | 0.447 | 0.7165 | 0.6689 | 0.7236 | 0.7396 | +0.0230 |
| Superior (Jaccard >= 0.754) | 450 (448+2) | 0.759–1.000 | 0.825 | 0.8516 | 0.7403 | 0.7945 | 0.8382 | -0.0134 |

## Teste da hipótese

Vantagem semântica (MAP BGE-M3 hybrid − MAP BM25): **+0.0230** na metade inferior vs. **-0.0134** na metade superior.

**Hipótese CONFIRMADA**: a vantagem semântica é maior na metade de Jaccard inferior do que na superior, consistente com 'busca semântica se destaca em baixo Jaccard, lexical melhora em alto Jaccard'.
- BM25: MAP inferior=0.7165, MAP superior=0.8516 (Δ=+0.1350)
- E5 puro: MAP inferior=0.6689, MAP superior=0.7403 (Δ=+0.0714)
- E5 hybrid: MAP inferior=0.7236, MAP superior=0.7945 (Δ=+0.0709)
- BGE-M3 hybrid: MAP inferior=0.7396, MAP superior=0.8382 (Δ=+0.0986)
