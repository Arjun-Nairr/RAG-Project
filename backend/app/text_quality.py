import re

# Cheap heuristic for whether extracted PDF text looks like real language
# rather than OCR/encoding garbage (e.g. a scanned image or handwriting with
# no clean text layer). This is a safety-net signal, not a language model -
# it will occasionally be wrong in both directions (symbol-heavy legitimate
# text scoring low, short garbled snippets scoring high by luck), and the
# exact ok/low boundary for partially-garbled real text is inherently fuzzy.

_WORD_RE = re.compile(r"[A-Za-z]+")
_JUNK_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f�]")
_VOWELS = set("aeiouAEIOU")

# ~80 of the most common English words. Real prose is dense with these;
# random letter clusters (OCR/encoding garbage) essentially never produce
# exact matches - a much stronger real-vs-garbage signal than checking
# whether a token merely *contains* a vowel (most random tokens do, by chance:
# for a 4-letter random string there's roughly a 65% chance of at least one
# vowel showing up anyway).
_COMMON_WORDS = {
    "the", "and", "of", "to", "in", "a", "is", "that", "for", "on", "with", "as",
    "was", "by", "this", "from", "at", "an", "be", "are", "or", "it", "which",
    "not", "have", "has", "but", "can", "we", "you", "their", "its", "also",
    "been", "were", "if", "they", "he", "she", "his", "her", "one", "two",
    "other", "than", "these", "those", "such", "may", "when", "where", "how",
    "what", "who", "all", "each", "more", "most", "some", "into", "over",
    "then", "so", "no", "only", "between", "during", "using", "used", "based",
    "results", "however", "because", "both", "after", "before", "while", "our",
    "new",
}

# real English rarely runs more than ~3 consonants in a row; garbage
# frequently does (this is a soft signal, not a hard rule - real exceptions
# like "months" exist)
_MAX_PLAUSIBLE_CONSONANT_RUN = 3


def _max_consonant_run(word: str) -> int:
    run = best = 0
    for ch in word:
        if ch in _VOWELS:
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best


def score_text(text: str) -> float:
    """0-1 plausibility score. Higher = more likely to be real, readable text."""
    text = text.strip()
    if not text:
        return 0.0

    total = len(text)
    junk_frac = len(_JUNK_RE.findall(text)) / total
    alpha_frac = sum(1 for c in text if c.isalpha() or c.isspace()) / total

    words = _WORD_RE.findall(text)
    if words:
        common_frac = sum(1 for w in words if w.lower() in _COMMON_WORDS) / len(words)
        plausible_shape = sum(
            1 for w in words if _max_consonant_run(w) <= _MAX_PLAUSIBLE_CONSONANT_RUN
        ) / len(words)
    else:
        common_frac = 0.0
        plausible_shape = 0.0

    # common_frac is the strongest signal - real prose of any reasonable
    # length is dense with these words, garbage essentially never matches -
    # so it dominates the score. Requiring ~20% density for full credit keeps
    # partially-garbled text (diluted common-word density) from scoring as
    # if it were clean.
    common_norm = min(common_frac / 0.20, 1.0)
    score = common_norm * 0.6 + plausible_shape * 0.15 + alpha_frac * 0.15 + (1 - junk_frac) * 0.10
    return max(0.0, min(1.0, score))


# Deliberately conservative: this only fires when there's essentially nothing
# usable, since blocking the pipeline is a strong action and false positives
# here are much worse than false positives on the soft warning below. The
# primary hard-fail gate is chunk_count == 0 (nothing extracted at all) -
# the score floor is just a backstop for near-total gibberish.
HARD_FAIL_THRESHOLD = 0.15
SOFT_WARN_THRESHOLD = 0.55


def classify(score: float, chunk_count: int) -> str:
    if chunk_count == 0 or score < HARD_FAIL_THRESHOLD:
        return "unreadable"
    if score < SOFT_WARN_THRESHOLD:
        return "low"
    return "ok"
