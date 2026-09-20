# Auditoria dos tokens 'cv'/'hp' (potencia) -- Resultados

Escopo: as 852 consultas reais do benchmark, tokenizadas com a mesma regex de `scripts/retrieval_adaptive_fusion_v5.py` (`TOKEN_RE`), procurando os tokens isolados `cv` (cavalo-vapor) e `hp` (horsepower) -- mesma metodologia de `scripts/audit_kg_regex.py`.

## Positivos (token 'cv'/'hp' disparado)
- Total de consultas com token `cv` ou `hp`: **21** de 852 (2.5%)
- **Verdadeiro positivo a nivel de token** (sempre precedido de numero, ex. "326 CV"): **21/21**
- **Falso positivo a nivel de token** (solto, sem numero antes): **0/21**

- **Util para o objetivo da tecnica** (dispara num topico com MAP < 0.6): **11/21** (52.4%)
- **"Falso positivo de utilidade"** (match real, mas topico ja com MAP >= 0.6): **10/21** (47.6%)

## Distribuicao por topico

| Topico | Palavras-chave | MAP do topico | N hits | Topico fraco (precisa ajuda)? |
|---|---|---|---|---|
| T7 | motor, cv, capacidade, motor diesel, diesel, potencia | 0.8924 | 4 | nao |
| T10 | hp, peso, hp peso, potencia, liquida, maximo | 0.7218 | 6 | nao |
| T73 | distancia, kg, carroceria, eixos, cv inclui, peso bruto | 0.5431 | 6 | **SIM** |
| T101 | kg, cabine, cv inclui, peso bruto, total, chassi | 0.4453 | 5 | **SIM** |

## Falsos negativos

1. **Colado ao numero, sem espaco** (ex. `20cv`, `160hp`): **1** caso(s).
   - Q6462 (T42): "ESCAVADEIRA DRAGA DE ARRASTE, CAP. 3/4 JC 140HP (INCL MANUTENCAO/OPERACAO)"
2. **Menciona 'potencia' mas usa outra unidade** (kw, w, etc.): **15** caso(s).
   - Q2790 (T7): "GRUPO GERADOR ESTACIONARIO SILENCIADO, POTENCIA 50 KVA, MOTOR DIESEL"
   - Q2793 (T7): "GRUPO GERADOR ESTACIONARIO, SILENCIADO, POTENCIA 180 KVA, MOTOR DIESEL"
   - Q2804 (T7): "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 28,80 M, CAPACIDADE MAXIMA 30 T, POTENCIA 97 KW, TRACAO 4 X 4"
   - Q2805 (T7): "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 40 M, CAPACIDADE MAXIMA 60 T, POTENCIA 260 KW, TRACAO 6 X 6"
   - Q2806 (T7): "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 50 M, CAPACIDADE MAXIMA 100 T, POTENCIA 350 KW, TRACAO 10 X 6"
   - Q5474 (T10): "USINA DE ASFALTO, GRAVIMETRICA, CAPACIDADE DE 150 T/H, POTENCIA DE 400 KW"
   - Q6063 (T7): "GRUPO GERADOR ESTACIONARIO SILENCIADO, POTENCIA 50 KVA, MOTOR DIESEL"
   - Q6064 (T7): "GRUPO GERADOR ESTACIONARIO, SILENCIADO, POTENCIA 180 KVA, MOTOR DIESEL"
   - Q6065 (T7): "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 28,80 M, CAPACIDADE MAXIMA 30 T, POTENCIA 97 KW, TRACAO 4 X 4"
   - Q6066 (T7): "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 40 M, CAPACIDADE MAXIMA 60 T, POTENCIA 260 KW, TRACAO 6 X 6"
   - Q6067 (T7): "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 50 M, CAPACIDADE MAXIMA 100 T, POTENCIA 350 KW, TRACAO 10 X 6"
   - Q6197 (T10): "USINA DE ASFALTO, GRAVIMETRICA, CAPACIDADE DE 150 T/H, POTENCIA DE 400 KW"
   - Q16756 (T-1): "Luminária de led para iluminação publica, potencia 98w a 137w, temperatura de cor 5000k involucro em aluminio ou aço inox"
   - Q35688 (T10): "USINA DE ASFALTO, GRAVIMETRICA, CAPACIDADE DE 150 T/H, POTENCIA DE 400 KW"
   - Q35694 (T10): "USINA MISTURADORA DE SOLOS, DOSADORES TRIPLOS, CALHA VIBRATORIA CAPACIDADE DE 200 A 500 T/H, POTENCIA DE 75 KW"
3. **Unidades de potencia/eletricas vizinhas** (`kw`, `w`, `hz`, `rpm`): **15** caso(s).
   - Q2804 (T7), unidades=['kw']: "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 28,80 M, CAPACIDADE MAXIMA 30 T, POTENCIA 97 KW, TRACAO 4 X 4"
   - Q2805 (T7), unidades=['kw']: "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 40 M, CAPACIDADE MAXIMA 60 T, POTENCIA 260 KW, TRACAO 6 X 6"
   - Q2806 (T7), unidades=['kw']: "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 50 M, CAPACIDADE MAXIMA 100 T, POTENCIA 350 KW, TRACAO 10 X 6"
   - Q3246 (T-1), unidades=['w']: "LUMINARIA DE LED PARA ILUMINACAO PUBLICA, DE 98 W ATE 137 W, INVOLUCRO EM ALUMINIO OU ACO INOX"
   - Q5474 (T10), unidades=['kw']: "USINA DE ASFALTO, GRAVIMETRICA, CAPACIDADE DE 150 T/H, POTENCIA DE 400 KW"
   - Q6065 (T7), unidades=['kw']: "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 28,80 M, CAPACIDADE MAXIMA 30 T, POTENCIA 97 KW, TRACAO 4 X 4"
   - Q6066 (T7), unidades=['kw']: "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 40 M, CAPACIDADE MAXIMA 60 T, POTENCIA 260 KW, TRACAO 6 X 6"
   - Q6067 (T7), unidades=['kw']: "GUINDASTE HIDRAULICO AUTOPROPELIDO, COM LANCA TELESCOPICA 50 M, CAPACIDADE MAXIMA 100 T, POTENCIA 350 KW, TRACAO 10 X 6"
   - Q6197 (T10), unidades=['kw']: "USINA DE ASFALTO, GRAVIMETRICA, CAPACIDADE DE 150 T/H, POTENCIA DE 400 KW"
   - Q6588 (T-1), unidades=['w']: "LUMINARIA DE LED PARA ILUMINACAO PUBLICA, DE 98 W ATE 137 W, INVOLUCRO EM ALUMINIO OU ACO INOX (COLETADO CAIXA)"
   - Q7062 (T-1), unidades=['w']: "[cópia] LUMINARIA DE LED PARA ILUMINACAO PUBLICA, DE 98 W ATE 137 W, INVOLUCRO EM ALUMINIO OU ACO INOX (COLETADO CAIXA)"
   - Q7074 (T-1), unidades=['w']: "[cópia] LUMINARIA DE LED PARA ILUMINACAO PUBLICA, DE 98 W ATE 137 W, INVOLUCRO EM ALUMINIO OU ACO INOX (COLETADO CAIXA)"
   - Q35688 (T10), unidades=['kw']: "USINA DE ASFALTO, GRAVIMETRICA, CAPACIDADE DE 150 T/H, POTENCIA DE 400 KW"
   - Q35694 (T10), unidades=['kw']: "USINA MISTURADORA DE SOLOS, DOSADORES TRIPLOS, CALHA VIBRATORIA CAPACIDADE DE 200 A 500 T/H, POTENCIA DE 75 KW"
   - Q42356 (T29), unidades=['hz']: "DETECTOR DE TENSÃO DE 90 A 1.000 VAC (48 A 62 HZ)"

## Conclusao
- Os tokens `cv`/`hp`, isoladamente, tem **0 falsos positivos de tokenizacao** em 21 ocorrencias.
- **11 das 21** ocorrencias caem em topicos que de fato precisam de ajuda (MAP baixo).
- Falsos negativos por concatenacao sem espaco e por uso de unidade alternativa (kw) seguem o mesmo padrao observado para `kg`.
