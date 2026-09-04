import numpy as np

from app.observability.cache import SemanticCache


def test_cache_hit_on_near_duplicate_vector():
    cache = SemanticCache(max_entries=10, threshold=0.9)
    vec = np.array([1.0, 0.0, 0.0])
    cache.store("What is the refund policy?", vec, {"answer": "30 days", "confidence": 0.9})

    near_duplicate = np.array([0.99, 0.01, 0.0])
    hit = cache.lookup(near_duplicate)
    assert hit is not None
    assert hit.response["answer"] == "30 days"
    assert hit.hits == 1


def test_cache_miss_on_dissimilar_vector():
    cache = SemanticCache(max_entries=10, threshold=0.9)
    cache.store("refund policy", np.array([1.0, 0.0, 0.0]), {"answer": "30 days", "confidence": 0.9})
    unrelated = np.array([0.0, 1.0, 0.0])
    assert cache.lookup(unrelated) is None


def test_cache_eviction_at_capacity():
    cache = SemanticCache(max_entries=2, threshold=0.99)
    cache.store("q1", np.array([1.0, 0.0]), {"answer": "a1", "confidence": 1.0})
    cache.store("q2", np.array([0.0, 1.0]), {"answer": "a2", "confidence": 1.0})
    cache.store("q3", np.array([-1.0, 0.0]), {"answer": "a3", "confidence": 1.0})
    assert cache.stats()["entries"] == 2
    # oldest entry (q1) should have been evicted
    assert cache.lookup(np.array([1.0, 0.0])) is None
