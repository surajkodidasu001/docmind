"""Cross-source contradiction detection.

For the MVP this uses a cheap negation/numeric-mismatch heuristic rather
than a full NLI model: for each pair of retrieved chunks, flag disagreement
if they share substantial topical overlap (many common content words) but
contain differing numbers, or one contains a negation ("not", "no", "never")
near a shared keyword that the other doesn't. This catches the common case
(two sources give different figures for the same thing) without needing an
extra model dependency. Swap in a real NLI model (e.g. a cross-encoder
trained on MNLI) for production-grade detection.
"""
from __future__ import annotations

import re
from itertools import combinations
from typing import List, Dict, Any

_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
_NEGATIONS = {"not", "no", "never", "cannot", "can't", "isn't", "doesn't", "won't"}


def _content_words(text: str) -> set:
    return {w.lower().strip(".,!?") for w in text.split() if len(w) > 4}


def find_contradictions(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    contradictions = []
    for a, b in combinations(range(len(chunks)), 2):
        text_a, text_b = chunks[a]["text"], chunks[b]["text"]
        words_a, words_b = _content_words(text_a), _content_words(text_b)
        overlap = words_a & words_b

        # only worth comparing if they're actually discussing the same thing
        if len(overlap) < 3:
            continue

        nums_a, nums_b = set(_NUMBER_RE.findall(text_a)), set(_NUMBER_RE.findall(text_b))
        numeric_conflict = bool(nums_a) and bool(nums_b) and nums_a.isdisjoint(nums_b)

        neg_a = any(n in text_a.lower().split() for n in _NEGATIONS)
        neg_b = any(n in text_b.lower().split() for n in _NEGATIONS)
        negation_conflict = neg_a != neg_b and len(overlap) >= 4

        if numeric_conflict or negation_conflict:
            contradictions.append({
                "chunk_a": {"source": chunks[a]["source"], "location": chunks[a]["location"]},
                "chunk_b": {"source": chunks[b]["source"], "location": chunks[b]["location"]},
                "shared_topic_words": sorted(overlap)[:6],
                "reason": "differing figures for the same topic" if numeric_conflict else "one source negates what the other states",
            })
    return contradictions
