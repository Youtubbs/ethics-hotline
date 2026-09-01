"""Category suggestion from Comprehend key phrases.

Runs on the redacted text only, never the original submission. The only
AWS call is DetectKeyPhrases; the matching itself is local.

CATEGORY_KEYWORDS is plain data. Tune the word lists without touching
any logic below it.
"""

from __future__ import annotations

from ethics_hotline.aws.comprehend import ComprehendClient

# Editable data, not logic. Keys must stay within the Category literal.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "safety": (
        "safety",
        "hazard",
        "unsafe",
        "injury",
        "injured",
        "accident",
        "osha",
        "spill",
        "fire",
        "ppe",
        "equipment",
        "exposure",
    ),
    "harassment": (
        "harassment",
        "harassed",
        "discrimination",
        "discriminated",
        "hostile",
        "retaliation",
        "retaliated",
        "bullying",
        "threatened",
        "slur",
        "inappropriate",
        "abusive",
    ),
    "financial": (
        "fraud",
        "embezzlement",
        "embezzled",
        "bribe",
        "bribery",
        "kickback",
        "expense",
        "invoice",
        "accounting",
        "misappropriation",
        "falsified",
        "theft",
    ),
}

# Ties break in this order, so the same input always yields the same
# category rather than depending on dict iteration.
TIE_BREAK_ORDER: tuple[str, ...] = ("safety", "harassment", "financial")

DEFAULT_CATEGORY = "other"


def _count_keyword_hits(phrases: list[str]) -> dict[str, int]:
    """Count how many key phrases contain a keyword from each category."""
    hits = {category: 0 for category in CATEGORY_KEYWORDS}
    lowered = [phrase.lower() for phrase in phrases]

    for category, keywords in CATEGORY_KEYWORDS.items():
        for phrase in lowered:
            if any(keyword in phrase for keyword in keywords):
                hits[category] += 1

    return hits


def suggest_category(text: str, comprehend: ComprehendClient) -> str:
    """Suggest a category for already-redacted report text.

    A category qualifies on one or more keyword hits, and the category
    with the most hits wins, ties broken by TIE_BREAK_ORDER. With no hits
    anywhere, this returns the default rather than guessing.
    """
    phrases = comprehend.detect_key_phrases(text)
    hits = _count_keyword_hits(phrases)

    best_count = max(hits.values(), default=0)
    if best_count == 0:
        return DEFAULT_CATEGORY

    for category in TIE_BREAK_ORDER:
        if hits.get(category) == best_count:
            return category

    return DEFAULT_CATEGORY
