"""Citation-grounded answer generation + claim-level verification.

Generation prompt forces the model to tag each claim with [n] referencing
the numbered context chunks. Verification re-checks that cited chunks
actually support the claim (lexical-overlap heuristic for the MVP; swap in
an NLI/entailment model for production-grade verification).
"""
from __future__ import annotations

import re
from typing import List, Dict, Any

from app.generation.llm import call_llm

SYSTEM_PROMPT = """You are a citation-grounded document assistant.
Answer ONLY using the numbered context chunks provided. Every factual claim
must end with a citation marker containing a real chunk number from the
numbered context above, such as [1] or [2,3]. Always substitute the actual
number of the chunk you are referencing. If the context does not contain
the answer, say so explicitly instead of guessing. Do not fabricate
citations."""


def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] (source: {c['source']}, {c['location']})\n{c['text']}")
    return "\n\n".join(lines)


def generate_answer(query: str, chunks: List[Dict[str, Any]], model: str | None = None,
                     history: str = "") -> Dict[str, Any]:
    context = build_context_block(chunks)
    history_block = f"Conversation so far:\n{history}\n\n" if history else ""
    user_prompt = (
        f"{history_block}Context chunks:\n\n{context}\n\n"
        f"Question: {query}\n\nAnswer with inline citations [n]."
    )
    result = call_llm(SYSTEM_PROMPT, user_prompt, max_tokens=800, model=model)
    result["chunks"] = chunks
    return result


_CITATION_RE = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")


def verify_citations(answer_text: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Claim-level check: for each sentence with a citation, confirm lexical
    overlap between the sentence and the cited chunk(s). Flags unsupported
    claims instead of only scoring the whole answer.
    """
    # Negative lookahead avoids splitting "...weather. [1]" into two pieces,
    # which would separate a trailing citation marker from its sentence.
    sentences = re.split(r"(?<=[.!?])\s+(?!\[)", answer_text.strip())
    flagged = []
    supported = 0
    total_cited = 0

    for sent in sentences:
        matches = _CITATION_RE.findall(sent)
        if not matches:
            continue
        cited_indices = [int(n) for group in matches for n in group.split(",")]
        total_cited += 1
        sent_words = set(w.lower().strip(".,!?") for w in sent.split() if len(w) > 3)

        best_overlap = 0.0
        for idx in cited_indices:
            if 1 <= idx <= len(chunks):
                chunk_words = set(w.lower().strip(".,!?") for w in chunks[idx - 1]["text"].split() if len(w) > 3)
                if sent_words:
                    overlap = len(sent_words & chunk_words) / max(len(sent_words), 1)
                    best_overlap = max(best_overlap, overlap)

        if best_overlap >= 0.15:
            supported += 1
        else:
            flagged.append({"sentence": sent, "cited": cited_indices, "overlap": round(best_overlap, 2)})

    confidence = supported / total_cited if total_cited else 0.0
    uncited_claims = sum(
        1 for s in sentences
        if len(s.split()) > 4 and not _CITATION_RE.search(s)
    )

    return {
        "confidence": round(confidence, 2),
        "supported_claims": supported,
        "total_cited_claims": total_cited,
        "uncited_sentences": uncited_claims,
        "flagged": flagged,
    }
