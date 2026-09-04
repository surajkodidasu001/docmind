"""API-key based multi-tenancy.

Scope decision (made explicitly, since this needed a decision and none was
given): simple API-key -> tenant-id mapping via a FastAPI dependency, not
JWT/SSO — that's the right default for a self-hosted internal tool, and it's
what's actually implementable and testable without you standing up an
identity provider. Swap for JWT/OAuth against your IdP later; the dependency
interface (`get_tenant_id`) stays the same for callers.

Each tenant's Qdrant collection is namespaced (`{base_collection}__{tenant}`)
so one tenant's documents are never retrievable by another's queries.
"""
from __future__ import annotations

from typing import Dict, Optional

from fastapi import Header, HTTPException

from app.config import settings


def _parse_tenant_keys() -> Dict[str, str]:
    mapping = {}
    for pair in settings.tenant_api_keys.split(","):
        pair = pair.strip()
        if not pair:
            continue
        key, _, tenant = pair.partition(":")
        if key and tenant:
            mapping[key] = tenant
    return mapping


def get_tenant_id(x_api_key: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency. Returns 'default' tenant when multi-tenancy is
    disabled (single-tenant mode, the MVP default), otherwise requires a
    valid X-API-Key header mapped to a tenant."""
    if not settings.multi_tenancy_enabled:
        return "default"

    keys = _parse_tenant_keys()
    if not x_api_key or x_api_key not in keys:
        raise HTTPException(401, "Missing or invalid X-API-Key header")
    return keys[x_api_key]


def collection_name_for_tenant(tenant_id: str) -> str:
    if tenant_id == "default":
        return settings.qdrant_collection
    return f"{settings.qdrant_collection}__{tenant_id}"
