# V5 -- Fusao hibrida adaptativa por densidade numerica da query -- Resultados

## Hipotese
Os topicos BERTopic de menor MAP (T101, T73, T59, T125, T94, T2, T21, ...) sao dominados por atributos numericos/unidades de medida (kg, cm, mm, mpa, pn, ...), onde o BM25 (match exato de token) tende a superar o embedding denso (BGE-M3), que 'borra' esses atributos em favor de similaridade semantica geral. O V4 (`retrieval_weighted_rrf_v4.py`) ja mostrou que um boost estatico global do peso esparso na fusao RRF melhora o MAP (0,7932 -> 0,7981 em `esparso_3x`). Este experimento testa uma fusao **adaptativa**: o boost so e aplicado quando a query e detectada, via regex de densidade numerica, como 'atributo-pesada'.

## Metodo
- Deteccao: `densidade_numerica(query) = (tokens com digito ou unidade conhecida) / (total de tokens)`.
- Se `densidade_numerica >= threshold`: `w_esparso = boost` (senao `w_esparso = 1.0`); `w_denso = 1.0` sempre.
- Fusao: RRF ponderado, `k=60`, mesma formula do V4.
- Grid: threshold em [0.0, 0.1, 0.15, 0.2, 0.3, 0.4], boost em [1.5, 2.0, 3.0, 4.0, 5.0] (30 configs) + baseline.

## Resultado principal
- Baseline (RRF 1.0/1.0): **MAP = 0.7932**
- Melhor config adaptativa: **adaptativo_thr0.20_boost4.0x** -> **MAP = 0.7982** (delta +0.0050, 67.1% das consultas classificadas atributo-pesadas)
- Recall@10: baseline 0.9767 -> melhor config 0.9773

Ver `adaptive_fusion_grid.md` para o grid completo (comparar com `results/real_295_v4_rrf_weights/rrf_weights_resultados.md` para o boost estatico global).

### A "seletividade" adaptativa realmente ajuda, ou e so o boost bem calibrado?

O grid inclui `threshold=0.0`, que marca 100% das consultas como "atributo-pesadas" -- ou seja, equivale exatamente ao boost estatico global do V4 (mesma formula, so que testado aqui ate 5x em vez de parar em 3x). Comparando os top configs:

| Config | threshold | boost | % marcadas | MAP geral | MAP 12 piores topicos |
|---|---|---|---|---|---|
| adaptativo_thr0.20_boost4.0x | 0.20 | 4.0x | 67,1% | **0,7982** | 0,5707 |
| adaptativo_thr0.00_boost3.0x (= boost global, como no V4) | 0,00 | 3.0x | 100% | 0,7981 | 0,5700 |
| adaptativo_thr0.00_boost4.0x (boost global) | 0,00 | 4.0x | 100% | 0,7980 | 0,5723 |
| adaptativo_thr0.20_boost5.0x | 0,20 | 5.0x | 67,1% | 0,7979 | 0,5708 |
| adaptativo_thr0.00_boost5.0x (boost global) | 0,00 | 5.0x | 100% | 0,7976 | **0,5726** |

As diferencas entre esses 5 configs (0,7976-0,7982 no geral; 0,5700-0,5726 nos piores topicos) sao da ordem de 1-3 consultas de AP em 852 -- ruido, nao um efeito real. **Conclusao honesta: uma vez que o boost estatico global tambem e testado numa faixa mais ampla (ate 5x, nao so ate 3x como no V4 original), ele iguala ou supera a versao "adaptativa por regex" tanto no MAP geral quanto no MAP dos topicos-alvo.** A deteccao via densidade numerica nao esta adicionando valor discriminativo neste conjunto -- o ganho vem quase todo do boost em si, nao de aplica-lo seletivamente. Isso tambem explica por que o pico do boost fica em ~3x-4x e nao mais alto: acima disso (5x) o MAP comeca a cair tanto no cenario global quanto no adaptativo, entao 3x/4x nao foi um limite arbitrario do grid original -- e proximo do real otimo.

## Efeito nos 12 topicos de menor MAP (eda/categ_map/topic_map_resultados.md)
- MAP medio (baseline) nesses 162 consultas: **0.5549**
- MAP medio (melhor config adaptativa): **0.5707** (delta +0.0158)
- MAP medio (melhor boost global puro, thr=0.00_boost5.0x): **0,5726** (delta +0,0177) -- **melhor que a versao adaptativa**

Ver `map_by_worst_topic.md` para o detalhamento por topico.

## Arquivos gerados
- `adaptive_fusion_grid.csv` / `.md`: MAP e Recall@10 para cada combinacao threshold x boost.
- `per_query_ap.csv`: AP por consulta em cada config, com densidade numerica e topico BERTopic.
- `map_by_worst_topic.csv` / `.md`: MAP baseline vs melhor config, restrito aos 12 piores topicos.
