from app.retrieval.hybrid import _rrf_fuse
from app.retrieval.bm25_index import BM25Index


def test_rrf_fuse_prioritizes_agreement():
    dense = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.8}]
    sparse = [{"id": "b", "score": 5.0}, {"id": "c", "score": 4.0}]
    fused = _rrf_fuse([dense, sparse])
    # "b" appears in both lists so should rank first
    assert fused[0]["id"] == "b"


def test_bm25_returns_relevant_chunk():
    # 3+ docs needed: with N=2 and a term in exactly 1 doc, BM25's IDF term
    # (log((N-n+0.5)/(n+0.5))) degenerates to exactly zero.
    chunks = [
        {"id": "1", "text": "hybrid retrieval combines dense and sparse search"},
        {"id": "2", "text": "the weather today is sunny and warm"},
        {"id": "3", "text": "cooking pasta requires boiling water and salt"},
    ]
    idx = BM25Index(chunks)
    results = idx.search("dense sparse retrieval", top_k=3)
    assert results
    assert results[0]["id"] == "1"


def test_bm25_empty_index():
    idx = BM25Index([])
    assert idx.search("anything", top_k=5) == []
