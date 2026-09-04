"""Lightweight RAGAS-style evaluation harness.

Computes three metrics per question, reusing pipeline components that are
already unit-tested rather than pulling in the full `ragas` package (which
adds a heavy LLM-judge dependency chain):

  - faithfulness: the same claim-level citation verification used at
    inference time (app.generation.citation.verify_citations) — measures
    whether the answer's claims are actually supported by retrieved chunks.
  - answer_relevance: cosine similarity between the generated answer and
    the human-written reference answer's embeddings.
  - context_precision: fraction of retrieved chunks that were actually
    cited at least once in the generated answer (signal for retrieval
    quality / noise in top_k).

Requires ANTHROPIC_API_KEY set and documents already ingested (run
`python eval/run_eval.py --ingest` to auto-ingest data/sample_docs first).
Requires network access to download the embedding model on first run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.ingestion.loader import load_document
from app.ingestion.chunker import chunk_segments
from app.retrieval.vector_store import get_store
from app.retrieval.embeddings import embed_texts
from app.agent.graph import run_agent
from app.generation.citation import verify_citations


def ingest_sample_docs():
    store = get_store()
    sample_dir = Path(__file__).resolve().parents[1] / "data" / "sample_docs"
    for path in sample_dir.glob("*"):
        segments = load_document(str(path))
        for s in segments:
            s.source = path.name
        chunks = chunk_segments(segments)
        store.upsert_chunks(chunks)
        print(f"ingested {path.name}: {len(chunks)} chunks")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def _cited_indices(answer: str) -> set:
    return {int(n) for group in re.findall(r"\[(\d+(?:,\s*\d+)*)\]", answer) for n in group.split(",")}


def evaluate_case(case: dict) -> dict:
    result = run_agent(case["question"])
    answer = result["answer"]

    # faithfulness: reuse the same claim-level verifier used at inference time
    faithfulness = result["confidence"]

    # answer relevance: does the generated answer semantically match the
    # human reference answer?
    vecs = embed_texts([answer, case["reference_answer"]])
    relevance = _cosine(vecs[0], vecs[1])

    # context precision: fraction of retrieved sources actually cited
    num_sources = len(result["sources"])
    num_cited = len(_cited_indices(answer))
    precision = min(num_cited / num_sources, 1.0) if num_sources else 0.0

    return {
        "id": case["id"],
        "question": case["question"],
        "faithfulness": round(faithfulness, 3),
        "answer_relevance": round(relevance, 3),
        "context_precision": round(precision, 3),
        "answer": answer,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest", action="store_true", help="ingest data/sample_docs before evaluating")
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "dataset.json"))
    args = parser.parse_args()

    if args.ingest:
        ingest_sample_docs()

    dataset = json.loads(Path(args.dataset).read_text())
    results = [evaluate_case(c) for c in dataset["cases"]]

    print("\n=== Eval results ===")
    for r in results:
        print(f"[{r['id']}] faithfulness={r['faithfulness']} relevance={r['answer_relevance']} "
              f"precision={r['context_precision']}")

    avg = lambda k: round(sum(r[k] for r in results) / len(results), 3)
    print("\n=== Averages ===")
    print(f"faithfulness:      {avg('faithfulness')}")
    print(f"answer_relevance:  {avg('answer_relevance')}")
    print(f"context_precision: {avg('context_precision')}")

    out_path = Path(__file__).parent / "last_run_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
