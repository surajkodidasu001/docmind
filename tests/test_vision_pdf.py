"""Tests the scanned-PDF detection and rasterization pipeline against a
genuinely generated image-only PDF (built in a fixture, no text layer,
0 chars extractable by pypdf — this reproduces the real bug being solved).
The paid vision API call itself is mocked; everything up to that call is
real and verified.
"""
from unittest.mock import patch
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw
import pytest

from app.ingestion.vision_pdf import (
    page_needs_vision_fallback,
    rasterize_page,
    extract_pdf_with_vision_fallback,
)


@pytest.fixture
def scanned_pdf(tmp_path) -> str:
    """Builds a real PDF containing only a rendered image of text — no text
    layer — the same shape as a genuine scanned document."""
    img_path = tmp_path / "scanned_page.png"
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 80), "This is scanned text as an image, not a text layer.", fill="black")
    img.save(img_path)

    pdf_path = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=200)
    page.insert_image(pymupdf.Rect(0, 0, 600, 200), filename=str(img_path))
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


@pytest.fixture
def text_pdf(tmp_path) -> str:
    """A normal PDF with a real text layer, for the negative case."""
    pdf_path = tmp_path / "text.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=200)
    page.insert_text((20, 80), "This is real, extractable PDF text content for testing.")
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_scanned_page_has_zero_extractable_text(scanned_pdf):
    from pypdf import PdfReader
    reader = PdfReader(scanned_pdf)
    text = reader.pages[0].extract_text() or ""
    assert len(text.strip()) == 0


def test_page_needs_vision_fallback_flags_empty_text():
    assert page_needs_vision_fallback("") is True
    assert page_needs_vision_fallback("   ") is True
    assert page_needs_vision_fallback("short") is True  # under 20 chars


def test_page_needs_vision_fallback_skips_real_text():
    long_text = "This is a perfectly normal page of extracted PDF text content."
    assert page_needs_vision_fallback(long_text) is False


def test_rasterize_page_produces_valid_png(scanned_pdf):
    image_bytes = rasterize_page(scanned_pdf, 0, dpi=150)
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG magic bytes
    assert len(image_bytes) > 1000


def test_extract_pdf_with_vision_fallback_triggers_on_scanned_page(scanned_pdf):
    with patch("app.ingestion.vision_pdf.transcribe_page_image",
               return_value="This is scanned text as an image, not a text layer.") as mock_transcribe:
        pages = extract_pdf_with_vision_fallback(scanned_pdf)

    mock_transcribe.assert_called_once()
    assert len(pages) == 1
    assert "scanned text" in pages[0]


def test_extract_pdf_with_vision_fallback_skips_real_text_pages(text_pdf):
    with patch("app.ingestion.vision_pdf.transcribe_page_image") as mock_transcribe:
        pages = extract_pdf_with_vision_fallback(text_pdf)

    mock_transcribe.assert_not_called()  # real text layer, no vision call needed
    assert "real, extractable" in pages[0]
