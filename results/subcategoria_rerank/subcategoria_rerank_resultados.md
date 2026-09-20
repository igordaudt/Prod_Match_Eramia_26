# Gate por subcategoria (SINAPI) vs. gate por topico (BERTopic) -- Resultados

Testa a subcategoria manual do SINAPI (`class_match/results/regex_subcategories/sinapi-295-regex-subcategories.csv`, coluna `subcategoria_id`) como gate de reranking, em comparacao com o gate por topico BERTopic (flat, ja usado a sessao inteira) e uma versao combinada dos dois. Mesma convencao anterior: topico/subcategoria da consulta = os do proprio item relevante (ORACULO -- ver ressalva sobre inferencia em `results/hierarchical_topic_rerank/`, que vale igualmente aqui).

## Resultado geral (852 consultas)

| Politica | MAP | Delta vs. baseline |
|---|---|---|
| Baseline | 0.7932 | - |
| Flat topico (BERTopic, oraculo) | 0.8109 | +0.0177 |
| **Flat subcategoria (SINAPI, oraculo)** | **0.8016** | **+0.0084** |
| **Combinado (topico + subcategoria)** | **0.8143** | **+0.0211** |

## Top 20 subcategorias por N de consultas

| Subcategoria | N | MAP baseline | MAP flat-sub | MAP flat-topico | MAP combinado |
|---|---|---|---|---|---|
| Canos e Conexões Hidráulicas | 76 | 0.8578 | 0.8691 | 0.9075 | 0.9075 |
| Sanitário | 70 | 0.7517 | 0.7517 | 0.7517 | 0.7517 |
| Poste de Concreto | 61 | 0.9504 | 0.9504 | 0.9563 | 0.9563 |
| Acessórios de Portas e Janelas | 42 | 0.7930 | 0.7930 | 0.7930 | 0.7930 |
| Barreiras de Proteção | 32 | 0.7812 | 0.7812 | 0.7812 | 0.7812 |
| Construção Civil | 26 | 0.9615 | 1.0000 | 0.9615 | 1.0000 |
| Para Raios e SPDA | 25 | 0.9933 | 0.9933 | 0.9933 | 0.9933 |
| Poste Metálico | 23 | 0.5987 | 0.6098 | 0.5987 | 0.6098 |
| Acessórios e Consumíveis para Ferramentas | 22 | 0.6439 | 0.6515 | 0.7727 | 0.7727 |
| Artefatos de Concreto | 22 | 0.7608 | 0.7620 | 0.8485 | 0.8485 |
| Chapas e Painéis | 21 | 0.6244 | 0.6244 | 0.6244 | 0.6244 |
| Blocos Cerâmicos | 20 | 0.5079 | 0.5802 | 0.5985 | 0.5814 |
| Tintas | 20 | 0.7162 | 0.7162 | 0.6746 | 0.6763 |
| Cabos e Fios Elétricos | 19 | 0.8289 | 0.8289 | 0.9561 | 0.9561 |
| Cimentos | 19 | 0.8596 | 0.8596 | 0.8596 | 0.8596 |
| Torneiras | 18 | 0.4704 | 0.4704 | 0.4728 | 0.4728 |
| Transportes | 17 | 0.7018 | 0.7018 | 0.7018 | 0.7018 |
| Telhas Cerâmicas | 17 | 0.5196 | 0.5196 | 0.5196 | 0.5196 |
| Portas e esquadrias | 17 | 0.3861 | 0.3861 | 0.3819 | 0.3819 |
| Ferramentas Manuais | 17 | 0.9559 | 1.0000 | 0.9706 | 1.0000 |
