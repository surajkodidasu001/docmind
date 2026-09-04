"""Vision-based fallback for scanned/image-only PDF pages.

pypdf's text extraction returns empty (or near-empty) strings for pages
that are actually scanned images rather than real text layers. This module
detects that case, rasterizes the page to an image with PyMuPDF, and sends
it to Claude's vision API to get a text description/transcription back —
so scanned pages don't silently disappear from the index.

Detection threshold: a page with fewer than `min_chars_per_page` extracted
characters is treated as image-only. This is a real, testable heuristic
(exercised in tests/test_vision_pdf.py against a synthetically generated
blank-text PDF) — the vision API call itself is mocked in tests since it
needs a real API key and costs money per call.
"""
from __future__ import annotations

import base64
from typing import List

MIN_CHARS_PER_PAGE = 20


def page_needs_vision_fallback(extracted_text: str, min_chars: int = MIN_CHARS_PER_PAGE) -> bool:
    """True if pypdf's text extraction came back effectively empty, implying
    the page is a scanned image rather than a real text layer."""
    return len((extracted_text or "").strip()) < min_chars


def rasterize_page(pdf_path: str, page_number: int, dpi: int = 150) -> bytes:
    """Renders one PDF page (0-indexed) to PNG bytes for a vision API call."""
    import pymupdf

    doc = pymupdf.open(pdf_path)
    try:
        page = doc[page_number]
        zoom = dpi / 72
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pix.tobytes("png")
    finally:
        doc.close()


def transcribe_page_image(image_bytes: bytes, model: str | None = None) -> str:
    """Sends a rasterized page image to Claude's vision API and returns the
    transcribed/described text. Requires ANTHROPIC_API_KEY."""
    from app.generation.llm import _get_client
    from app.config import settings

    client = _get_client()
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    resp = client.messages.create(
        model=model or settings.llm_model,
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": (
                    "Transcribe all readable text from this scanned document page "
                    "exactly as written. If there are tables or charts, describe "
                    "their structure and key values in plain text. Output only the "
                    "transcription/description, no commentary."
                )},
            ],
        }],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def extract_pdf_with_vision_fallback(pdf_path: str) -> List[str]:
    """Full pipeline: extract text normally per page, and for any page that
    looks image-only, rasterize + transcribe it via vision instead. Returns
    one text string per page (in page order)."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    page_texts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if page_needs_vision_fallback(text):
            image_bytes = rasterize_page(pdf_path, i)
            text = transcribe_page_image(image_bytes)
        page_texts.append(text)
    return page_texts
