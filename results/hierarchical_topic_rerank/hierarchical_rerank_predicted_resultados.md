# H1 com topico INFERIDO (nao-oraculo) -- Resultados

Teste correto de H1 (ver nota no final de `hierarchical_rerank_resultados.md`): em vez de usar o topico do item relevante como 'topico da consulta' (o oraculo usado em TODOS os testes anteriores), o topico da consulta e **inferido** via `topic_model.transform()` (BERTopic retreinado, mesma config de `eda_bertopic.py`) sobre o texto da propria consulta -- um processo que pode errar para um topico vizinho ou para outliers (-1), exatamente o cenario que H1 precisa para ter chance de fazer diferenca.

**Correcao de bug aplicada nesta versao**: a primeira rodada usava distancia infinita para pares envolvendo o topico -1, o que enterrava um item outlier no fim absoluto da lista (pior que QUALQUER topico real, mesmo o mais distante da arvore) sempre que a consulta era classificada (erradamente) num topico real -- um artefato da implementacao, nao do metodo. Corrigido para usar a distancia maxima FINITA da arvore como valor neutro (empatado com o par de topicos reais mais distantes, nao pior que isso) -- replica o que o gate flat ja fazia (outlier recebe a mesma nota neutra de qualquer nao-match, sem penalidade extra).

## Acuracia da classificacao de topico da consulta

- Acertou o topico exato do item relevante: **650/852** (76.3%)
- Errou: **201** (23.6%)
  - Dos erros, **91** tem distancia hierarquica finita entre previsto e oraculo (media **1.5043**, min 0.0001, max 2.2869)
  - **110** erros envolvem -1 de um dos lados (sem distancia hierarquica definida)

## Resultado principal (topico da consulta PREVISTO, nao oraculo)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7932 | - |
| Flat topico (topico previsto) | 0.7414 | -0.0519 |
| **Hierarquico continuo (topico previsto)** | **0.6965** | **-0.0967** |
| **Hierarquico em niveis (topico previsto)** | **0.7413** | **-0.0519** |

Delta hierarquico (continuo) vs. flat, usando topico previsto: **-0.0449**. Delta hierarquico (niveis) vs. flat: **-0.0001**.

## Segmentado por acerto/erro da classificacao

| Segmento | N | Baseline | Flat (previsto) | Hier. continuo (previsto) | Hier. niveis (previsto) |
|---|---|---|---|---|---|
| Geral | 852 | 0.7932 | 0.7414 | 0.6965 | 0.7413 |
| Predicao ACERTOU o topico | 650 | 0.7944 | 0.7987 | 0.7987 | 0.7987 |
| Predicao ERROU o topico | 202 | 0.7896 | 0.5569 | 0.3676 | 0.5567 |

A linha 'Predicao ERROU' e onde H1 realmente pode se manifestar: se a hierarquia ajuda, o MAP hierarquico deve superar o flat especificamente NESSE subgrupo (onde o topico previsto nao e o exato, mas pode ser proximo do certo).

