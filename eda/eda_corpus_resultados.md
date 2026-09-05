# EDA — Base Combinada (Todos os Dados: Real + Sintético)

Gerado a partir de `combined_items_all.tsv` (7,252 itens únicos) e `combined_queries_all.tsv` (996 consultas: 948 reais + 48 sintéticas).

Corpus de itens por origem: 2,401 só no real, 1,442 só no sintético, 3,409 presentes nos dois (deduplicados por descrição).

### Corpus de itens combinado (7,252, deduplicado)
- Documentos: 7,252
- Total de tokens: 144,125
- Caracteres — média: 88.2 / mediana: 79
- Tokens — média: 19.9 / mediana: 19
- % docs com <= 30 caracteres: 3.3%

### Consultas reais (query_text, 948)
- Documentos: 948
- Total de tokens: 19,881
- Caracteres — média: 96.0 / mediana: 89
- Tokens — média: 21.0 / mediana: 18
- % docs com <= 30 caracteres: 6.6%

### Itens-alvo das consultas reais (target_text, 948)
- Documentos: 948
- Total de tokens: 22,126
- Caracteres — média: 102.2 / mediana: 101
- Tokens — média: 23.3 / mediana: 22
- % docs com <= 30 caracteres: 1.4%

### Consultas sintéticas (query_text, 48)
- Documentos: 48
- Total de tokens: 393
- Caracteres — média: 45.2 / mediana: 46
- Tokens — média: 8.2 / mediana: 8
- % docs com <= 30 caracteres: 10.4%

### Vocabulário
- Vocabulário único — corpus de itens combinado: 4,947
- Vocabulário único — consultas reais: 1,943
- Vocabulário único — consultas sintéticas: 61
- Sobreposição (itens ∩ consultas reais): 1,512 (28.1% do vocabulário combinado)

### Similaridade lexical (Jaccard) query_text × target_text — comparação direta na base combinada
- Real (n=948): Jaccard médio **0.652**, mediano 0.765
- Sintético (n=48): Jaccard médio **0.403**, mediano 0.380
- Diferença (real − sintético): +0.249
- Real: Jaccard = 0 em 2 (0.2%); Jaccard >= 0,8 em 350 (36.9%)
- Sintético: Jaccard = 0 em 0 (0.0%); Jaccard >= 0,8 em 2 (4.2%)
