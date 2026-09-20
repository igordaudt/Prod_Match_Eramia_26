# Reranking por distancia hierarquica de topico -- Resultados

Usa a arvore de `Topic Modeling/EDA_hierarchy/eda_hierarchy_merges.csv` (BERTopic.hierarchical_topics(), ward linkage sobre c-TF-IDF dos 128 topicos-folha -- mesma config/corpus do `item_topics.csv` usado a sessao inteira). SO reranking por topico, sem regex de atributo nenhuma.

**Achado estrutural antes de rodar**: o topico -1 (outliers, 219 consultas no benchmark) NAO participa da arvore hierarquica -- confirmado em `EDA_hierarchy_resultados.md` ('-1 nao participa dessa fusao'). Ou seja, nao existe distancia hierarquica definida entre -1 e qualquer outro topico. **H2 (hierarquia resolveria outliers) e estruturalmente improvavel com este dado** -- testado mesmo assim abaixo, isolando a fatia de consultas com topico -1.

## Duas variantes de pontuacao testadas

- **Continua**: ordena os candidatos por distancia hierarquica ascendente ao topico da consulta (distancia 0 = mesmo topico; quanto mais perto na arvore, melhor).
- **Em niveis**: 3 niveis -- mesmo topico > topico a distancia <= 0.35 (o mesmo threshold que `EDA_hierarchy.py` usa para definir 'topicos redundantes') > resto.

## Resultado principal (todas as 852 consultas)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7932 | - |
| Flat topico (so mesmo/diferente, ja testado antes) | 0.8109 | +0.0177 |
| **Hierarquico continuo** | **0.8107** | **+0.0175** |
| **Hierarquico em niveis (threshold 0.35)** | **0.8109** | **+0.0177** |

## H1 -- topico hierarquicamente proximo ajuda?

Comparando hierarquico vs. flat nas 852 consultas: delta continuo vs. flat = -0.0002; delta niveis vs. flat = +0.0000.


## H2 -- hierarquia resolve outliers (-1)?

| Segmento | N | Baseline | Flat topico | Hier. continuo | Hier. niveis |
|---|---|---|---|---|---|
| So outliers (-1) | 219 | 0.8317 | 0.8317 | 0.8317 | 0.8317 |
| Sem outliers | 633 | 0.7799 | 0.8037 | 0.8035 | 0.8037 |
