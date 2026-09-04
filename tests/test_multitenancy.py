"""Verifies tenant isolation: with multi-tenancy enabled, each API key maps
to its own tenant, and each tenant gets its own Qdrant collection + cache —
one tenant's documents/answers are never visible to another's.
"""
import uuid
import numpy as np
from fastapi.testclient import TestClient
from qdrant_client.http import models as qm

from app.main import app
from app import config
from app.api import auth
from app.retrieval.vector_store import VectorStore, get_store, _stores
from app.observability.cache import get_cache, _caches


def test_get_tenant_id_defaults_to_default_when_disabled(monkeypatch):
    monkeypatch.setattr(config.settings, "multi_tenancy_enabled", False)
    assert auth.get_tenant_id(x_api_key=None) == "default"


def test_get_tenant_id_requires_valid_key_when_enabled(monkeypatch):
    monkeypatch.setattr(config.settings, "multi_tenancy_enabled", True)
    monkeypatch.setattr(config.settings, "tenant_api_keys", "abc123:acme,def456:globex")

    assert auth.get_tenant_id(x_api_key="abc123") == "acme"
    assert auth.get_tenant_id(x_api_key="def456") == "globex"


def test_get_tenant_id_rejects_unknown_key(monkeypatch):
    monkeypatch.setattr(config.settings, "multi_tenancy_enabled", True)
    monkeypatch.setattr(config.settings, "tenant_api_keys", "abc123:acme")

    from fastapi import HTTPException
    import pytest
    with pytest.raises(HTTPException) as exc_info:
        auth.get_tenant_id(x_api_key="wrong-key")
    assert exc_info.value.status_code == 401


def test_vector_stores_are_isolated_per_tenant():
    _stores.clear()
    store_a = get_store("acme")
    store_b = get_store("globex")
    assert store_a.collection != store_b.collection

    points = [qm.PointStruct(id=str(uuid.uuid4()), vector=np.random.rand(384).tolist(),
                              payload={"text": "acme secret doc", "source": "s.pdf", "location": "p1"})]
    store_a.client.upsert(collection_name=store_a.collection, points=points)

    assert len(store_a.all_chunks()) == 1
    assert len(store_b.all_chunks()) == 0  # globex sees nothing from acme


def test_caches_are_isolated_per_tenant():
    _caches.clear()
    cache_a = get_cache("acme")
    cache_b = get_cache("globex")
    vec = np.array([1.0, 0.0, 0.0])
    cache_a.store("what is the price?", vec, {"answer": "acme's answer", "confidence": 0.9})

    assert cache_a.lookup(vec) is not None
    assert cache_b.lookup(vec) is None  # globex's cache never sees acme's cached answer
