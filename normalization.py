import regex as re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, List, Dict, Any, Tuple

__version__ = "1.0.0"

NormalizerStep = Callable[[str], str]

VULGAR_FRACTION_MAP = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅐": "1/7",
    "⅑": "1/9",
    "⅒": "1/10",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

try:
    import nltk
    from nltk.corpus import stopwords
except ImportError:  # pragma: no cover - depende do ambiente
    nltk = None
    stopwords = None

def _strip_accents(text: str) -> str:
    # Remove acentos mantendo letras
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def _normalize_case(text: str) -> str:
    # casefold é melhor que lower pra alguns casos
    return text.casefold()

def _normalize_symbols(text: str) -> str:
    # unifica separadores comuns
    text = text.replace("×", "x").replace("X", "x")
    text = text.replace("–", "-").replace("—", "-")
    return text

def _normalize_fractions(text: str) -> str:
    for symbol, fraction in VULGAR_FRACTION_MAP.items():
        text = text.replace(symbol, fraction)
    text = text.replace("⁄", "/")
    return re.sub(r"(?<=\d)\s*/\s*(?=\d)", "/", text)

def _normalize_decimal_comma(text: str) -> str:
    # troca vírgula decimal por ponto apenas quando entre dígitos (6,5 -> 6.5)
    return re.sub(r"(?<=\d),(?=\d)", ".", text)

def _normalize_technical_spacing(text: str) -> str:
    """
    Normaliza tokens técnicos:
    17 X 27 -> 17x27
    10 mm -> 10mm
    220 V -> 220v
    6.5 kva -> 6.5kva (após casefold)
    """
    t = text
    t = re.sub(r"(?i)(\d)\s*x\s*(\d)", r"\1x\2", t)
    t = re.sub(r"(?i)(\d)\s*(mm|cm|m|v|w|kw|kva|hp)\b", r"\1\2", t)
    t = re.sub(r"(?i)\b(dn)\s*(\d)", r"\1\2", t)  # dn 50 -> dn50
    return t

def _remove_noise_punct(text: str) -> str:
    # mantém letras, números e alguns símbolos úteis; troca resto por espaço
    return re.sub(r"[^\w\s\./\"-]+", " ", text)

@lru_cache(maxsize=1)
def _get_stopwords() -> set[str]:
    if nltk is None or stopwords is None:
        return set()
    try:
        words = stopwords.words("portuguese")
    except LookupError:
        nltk.download("stopwords", quiet=True)
        try:
            words = stopwords.words("portuguese")
        except LookupError:
            return set()
    stop_words = set(words)
    stop_words.discard("para")
    return stop_words

def _remove_stopwords(text: str) -> str:
    stop_words = _get_stopwords()
    if not stop_words:
        return text
    tokens = text.split()
    return " ".join(token for token in tokens if token not in stop_words)

def _sample_removed_stopwords(before: str, after: str) -> List[str]:
    before_tokens = before.split()
    after_tokens = after.split()
    after_counts: Dict[str, int] = {}
    removed: List[str] = []
    for token in after_tokens:
        after_counts[token] = after_counts.get(token, 0) + 1
    for token in before_tokens:
        remaining = after_counts.get(token, 0)
        if remaining:
            after_counts[token] = remaining - 1
        else:
            removed.append(token)
    return removed

@dataclass
class TextNormalizer:
    """
    Normalizador configurável por pipeline de etapas.
    Você pode adicionar/remover/reordenar steps sem quebrar o restante do sistema.
    """
    steps: List[Tuple[str, NormalizerStep]] = field(default_factory=list)
    debug: bool = False

    def __post_init__(self):
        if not self.steps:
            # pipeline padrão (editável no futuro)
            self.steps = [
                ("strip_accents", _strip_accents),
                ("normalize_case", _normalize_case),
                ("normalize_symbols", _normalize_symbols),
                ("normalize_fractions", _normalize_fractions),
                ("normalize_decimal_comma", _normalize_decimal_comma),
                ("remove_noise_punct", _remove_noise_punct),
                ("normalize_technical_spacing", _normalize_technical_spacing),
                ("remove_stopwords", _remove_stopwords),
                ("normalize_whitespace", _normalize_whitespace),
            ]

    def normalize(self, text: str) -> str:
        out = text or ""
        for name, step in self.steps:
            before = out
            out = step(out)
            if self.debug and out != before:
                print(f"[normalize] step={name} changed: '{before}' -> '{out}'")
        return out

    def normalize_with_report(self, text: str) -> Dict[str, Any]:
        """
        Retorna um relatório das transformações — útil pra PDCA e tuning.
        """
        out = text or ""
        changes = []
        for name, step in self.steps:
            before = out
            out = step(out)
            if out != before:
                changes.append({"step": name, "before": before, "after": out})
        return {"raw": text, "normalized": out, "changes": changes}

if __name__ == "__main__":
    normalizer = TextNormalizer(debug=True)
    examples = [
        "Parafuso 6,5 mm × 50 mm",
        "Cabo de força 220 V",
        "Motor 1.5 HP",
        "DN 50",
        "Aço inoxidável – resistente à corrosão",
        "Conjunto de parafusos para a montagem do painel",
        "Bomba de agua para o sistema de irrigacao",
        "Registro esfera PVC rosca externa ¾",
        "Registro esfera PVC rosca externa 3 / 4",
        "Joelho PVC soldavel 1/2",
        "Joelho PVC soldavel ½",
    ]
    for ex in examples:
        report = normalizer.normalize_with_report(ex)
        stopword_change = next(
            (change for change in report["changes"] if change["step"] == "remove_stopwords"),
            None,
        )
        print(f"Original: '{ex}'")
        print(f"Normalized: '{report['normalized']}'")
        if stopword_change:
            removed = _sample_removed_stopwords(
                stopword_change["before"],
                stopword_change["after"],
            )
            if removed:
                print(f"Stopwords removidas: {removed}")
        print("-" * 40)
