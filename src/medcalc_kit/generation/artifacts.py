"""Classify each generation as a generation artifact or a well-formed answer.

Categories are exclusive and checked in this order:
    empty -> truncated -> degenerate -> format_invalid -> well_formed
A competence is best measured on well-formed answers only; the others are reported as artifact rates
(compressed or small models often produce empty, cut-off or looping text). Thresholds are arguments.

    >>> classify_generation("", 0, 512, format_valid=False)
    'empty'
    >>> classify_generation("I think " * 200, 512, 512, format_valid=False)
    'truncated'
    >>> classify_generation('{"result": 12}', 8, 512, format_valid=True)
    'well_formed'
"""
from __future__ import annotations

from collections import Counter

DEGENERATE_NGRAM = 4
DEGENERATE_REPEAT_SHARE = 0.5    # share of repeated n-grams above which the text is degenerate
DEGENERATE_LINE_REPEATS = 3      # the same non-trivial line appearing at least this many times
MIN_WORDS_FOR_NGRAM_CHECK = 40   # short answers are never judged degenerate on n-gram statistics

CATEGORIES = ("empty", "truncated", "degenerate", "format_invalid", "well_formed")


def repeated_ngram_share(text: str, n: int = DEGENERATE_NGRAM) -> float:
    """Share of word n-grams that are repeats of an earlier n-gram (0 = no repetition).

    >>> repeated_ngram_share("a b c d e f"), repeated_ngram_share("a b a b a b a b", n=2)
    (0.0, 0.7142857142857143)
    """
    words = text.split()
    grams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    if not grams:
        return 0.0
    counts = Counter(grams)
    return sum(c - 1 for c in counts.values()) / len(grams)


def max_line_repeats(text: str) -> int:
    """How many times the most repeated line (of at least 8 characters) occurs.

    >>> max_line_repeats("Step 1: compute\\nStep 1: compute\\nStep 1: compute\\ndone")
    3
    """
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 8]
    return max(Counter(lines).values(), default=0)


def is_degenerate(text: str, ngram: int = DEGENERATE_NGRAM, repeat_share: float = DEGENERATE_REPEAT_SHARE,
                  line_repeats: int = DEGENERATE_LINE_REPEATS, min_words: int = MIN_WORDS_FOR_NGRAM_CHECK) -> bool:
    """True if the text loops: a line repeated `line_repeats` times, or (for texts of at least `min_words` words)
    more than `repeat_share` of its word `ngram`s are repeats.

    >>> is_degenerate("the value is " * 30), is_degenerate("The anion gap is 140 - (104 + 24) = 12.")
    (True, False)
    """
    if max_line_repeats(text) >= line_repeats:
        return True
    if len(text.split()) >= min_words:
        return repeated_ngram_share(text, ngram) > repeat_share
    return False


def classify_generation(text: str, n_new_tokens: int, max_new_tokens: int, format_valid: bool,
                        **degenerate_options) -> str:
    """Category of a generation, in this order: empty, truncated (the token budget is used up), degenerate (see
    is_degenerate), format_invalid (the probe found no answer in the expected format), well_formed.
    degenerate_options: ngram, repeat_share, line_repeats, min_words (see is_degenerate).

    >>> classify_generation("The result is 12.", 6, 512, format_valid=False)
    'format_invalid'
    """
    if not text or not text.strip():
        return "empty"
    if n_new_tokens >= max_new_tokens:
        return "truncated"
    if is_degenerate(text, **degenerate_options):
        return "degenerate"
    if not format_valid:
        return "format_invalid"
    return "well_formed"
