"""Chunking with overlap, preserving citation provenance (source + location)."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import List

from app.config import settings
from app.ingestion.loader import RawSegment


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    location: str
    chunk_index: int
    doc_hash: str = field(default="")


def _split_text(text: str, size: int, overlap: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        if piece:
            chunks.append(" ".join(piece))
        if start + size >= len(words):
            break
    return chunks


def chunk_segments(segments: List[RawSegment], chunk_size: int | None = None,
                    overlap: int | None = None) -> List[Chunk]:
    chunk_size = chunk_size or settings.chunk_size // 5  # word-approx, not char
    overlap = overlap or settings.chunk_overlap // 5

    chunks: List[Chunk] = []
    idx = 0
    for seg in segments:
        doc_hash = hashlib.sha1(f"{seg.source}:{seg.location}".encode()).hexdigest()[:8]
        pieces = _split_text(seg.text, size=max(chunk_size, 40), overlap=overlap)
        for piece in pieces:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=piece,
                source=seg.source,
                location=seg.location,
                chunk_index=idx,
                doc_hash=doc_hash,
            ))
            idx += 1
    return chunks
