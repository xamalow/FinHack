"""Leak filter: does a piece of text contain a figure from paid content?

contains_paid_figures(text) -> bool is called on every outgoing message
(Sales agent replies, discover summaries, catalog metadata).

The sensitive set is every number found in sellable or excluded content,
minus the numbers that are public anyway (numbers in free content, years,
small integers 0 to 10). Numbers are compared on their value, so 31.4,
31,4, 31.40 and 31.4% all match, as do 17,340, 17 340 and 17.340.
"""
import re
import threading
import unicodedata
from decimal import Decimal, InvalidOperation

SPACES = "    "
# A number cannot start right after a letter or digit (skips "x402", hex
# addresses and hashes). It may be followed by a unit ("235.6GWh", "31.4%").
NUMBER = re.compile(
    rf"(?<![\w.,])(?:\d{{1,3}}(?:[{SPACES}]\d{{3}})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)"
)

_lock = threading.Lock()
_index = None


def _canon(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return format(value.normalize(), "f")


def _interpretations(token):
    """Every value a written number can mean, as canonical strings."""
    if any(c in token for c in SPACES):
        out = _interpretations(re.sub(f"[{SPACES}]", "", token))
        for part in re.split(f"[{SPACES}]", token):
            out |= _interpretations(part)
        return out
    seps = [c for c in token if c in ".,"]
    if not seps:
        values = {_canon(token)}
    elif len(set(seps)) == 2:
        # 1.234,5 or 1,234.5: the last separator is the decimal point
        last = max(token.rfind("."), token.rfind(","))
        values = {_canon(re.sub("[.,]", "", token[:last]) + "." + token[last + 1:])}
    else:
        groups = re.split("[.,]", token)
        if len(groups) == 2:
            values = {_canon(f"{groups[0]}.{groups[1]}")}
            if len(groups[1]) == 3:  # 17,340 is ambiguous: 17340 or 17.34
                values.add(_canon(groups[0] + groups[1]))
        elif all(len(g) == 3 for g in groups[1:]):
            values = {_canon("".join(groups))}
        else:
            values = set().union(*(_interpretations(g) for g in groups))
    return {v for v in values if v is not None}


def _is_trivial(canon):
    value = Decimal(canon)
    if value != value.to_integral_value():
        return False
    return 0 <= value <= 10 or 1900 <= value <= 2100


ARABIC_SEPARATORS = str.maketrans({"\u066b": ".", "\u066c": ","})


def _normalize(text):
    """Undo the usual tricks to slip a figure past the filter: compatibility forms (NFKC), invisible
    format characters inside a number ("31\u200b.4") and Arabic decimal or thousands separators."""
    text = unicodedata.normalize("NFKC", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    return text.translate(ARABIC_SEPARATORS)


def extract_numbers(text):
    """[(token after normalization, set of canonical values)] for every number in text."""
    return [(m.group(0), _interpretations(m.group(0))) for m in NUMBER.finditer(_normalize(text))]


def build_index(paid_texts, public_texts=()):
    paid = set()
    for text in paid_texts:
        for _, values in extract_numbers(text):
            paid |= values
    public = set()
    for text in public_texts:
        for _, values in extract_numbers(text):
            public |= values
    return frozenset(v for v in paid - public if not _is_trivial(v))


def _load_index():
    from ingestion.store import get_texts_by_status
    rows = get_texts_by_status()
    return build_index(
        [text for status, text in rows if status != "free"],
        [text for status, text in rows if status == "free"],
    )


def _current_index():
    global _index
    with _lock:
        if _index is None:
            _index = _load_index()
        return _index


def invalidate():
    global _index
    with _lock:
        _index = None


def find_paid_figures(text, index=None):
    """Numbers in text that match a paid figure, as written in text."""
    index = _current_index() if index is None else index
    return [token for token, values in extract_numbers(text) if values & index]


def contains_paid_figures(text, index=None):
    return bool(find_paid_figures(text, index))
