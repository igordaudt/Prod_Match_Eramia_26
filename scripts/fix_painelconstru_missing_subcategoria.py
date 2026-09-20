"""Corrige metadado FALTANDO (subcategory_id=None) no ground truth
PainelConstru para 12 itens identificados via diagnostico manual das
subcategorias que mais regrediram com o gate (Cimentos, Madeiras para
Construcao, Acos para Construcao, Ferramentas para Pintura -- ver
resultados/painelconstru_subcategoria_validation/).

Confirmado antes de aplicar (analyze_ground_truth scan): esses 12 itens
tem subcategory_id=None em TODAS as ocorrencias no arquivo inteiro (nunca
aparecem com um valor valido em nenhuma consulta ou no bucket "no_prod"),
e a descricao de cada um bate inequivocamente com a subcategoria da
consulta a qual foram anotados como relevantes. Por isso a correcao e
"preencher o dado faltando", nao "sobrescrever uma classificacao existente".

NAO mexe nos outros 4 casos de mismatch encontrados (itens com subcategoria
DIFERENTE, nao nula, de outra categoria valida -- ex: "bucha de reducao"
catalogada em Hidraulica mas relevante para consulta de Eletrodutos):
esses sao ambiguidade legitima de categorizacao cruzada, nao erro de dado,
e nao devem ser sobrescritos sem confirmacao humana.

Aplica a correcao em TODAS as ocorrencias do item no arquivo (o mesmo
item_id pode aparecer nas relevant_items de varias consultas diferentes).

Uso:
    python scripts/fix_painelconstru_missing_subcategoria.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BENCHMARK_JSON = PROJECT_ROOT.parent / "class_match" / "ground_truth" / "benchmark_grouped_v4.json"

CORRECTIONS = {
    # item_id: (subcategory_id corrigida, nome da subcategoria, descricao p/ conferencia)
    148567: (169, "Cimentos", "Cimento Votoran Cpiv 50kg"),
    148180: (152, "Madeiras para Construção", "10 X 20 X 5.40-EUCALIPTO BRUTO"),
    148228: (152, "Madeiras para Construção", "MADEIRA EUCALIPTO (10cmX20cmX5,4m)"),
    148236: (152, "Madeiras para Construção", "CAIBRO EUCALIPTO BRUTO 10X20X5,40 MTS"),
    149053: (159, "Aços para Construção", "VERG CA50 12,5MM RT 12M 1T NV"),
    149057: (159, "Aços para Construção", "PCVERG CA50 12,50 MM (1/2\") BARRA 12M"),
    149087: (159, "Aços para Construção", "ACO CA 50 12.5MM 12M - 1/2"),
    149094: (159, "Aços para Construção", "101819 - CA50 12,50 MM RETO 12,0 M FX 2000 KG"),
    149100: (159, "Aços para Construção", "101819 - CA50 12,50 MM RETO 12,0 M FX 2000 KG"),
    149105: (159, "Aços para Construção", "CORTE E DOBRA CD CA50 12.50 MM"),
    148515: (127, "Ferramentas para Pintura", "PINCEL CERDA BRANCA DTOOLS G 303X 3''"),
    148589: (127, "Ferramentas para Pintura", "Atlas Pincel Pluma Tek At315 2\""),
}


def main() -> None:
    print(f"Lendo {BENCHMARK_JSON} ...")
    with BENCHMARK_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"{len(data)} entradas carregadas.")

    changed_occurrences = 0
    changed_items = {iid: 0 for iid in CORRECTIONS}
    unexpected = []

    for entry in data:
        for item in entry.get("relevant_items") or []:
            iid = item.get("item_id")
            if iid in CORRECTIONS:
                target_sub, target_name, expected_desc = CORRECTIONS[iid]
                if item.get("subcategory_id") is not None:
                    unexpected.append((iid, item.get("subcategory_id"), entry.get("product_id")))
                    continue
                item["subcategory_id"] = target_sub
                changed_occurrences += 1
                changed_items[iid] += 1

    print(f"\nOcorrencias corrigidas: {changed_occurrences}")
    for iid, count in changed_items.items():
        sub, name, desc = CORRECTIONS[iid]
        status = "OK" if count > 0 else "NAO ENCONTRADO (verificar)"
        print(f"  item {iid} -> subcategory_id={sub} ({name})  [{count} ocorrencia(s)]  {status}  desc={desc[:60]}")

    if unexpected:
        print("\nAVISO: itens que ja tinham subcategory_id != None (NAO sobrescritos):")
        for iid, existing, pid in unexpected:
            print(f"  item {iid} ja tinha subcategory_id={existing} (na consulta product_id={pid})")

    print(f"\nGravando de volta em {BENCHMARK_JSON} ...")
    with BENCHMARK_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print("Concluido.")


if __name__ == "__main__":
    main()
