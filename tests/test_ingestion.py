from pathlib import Path

from app.ingestion.loader import load_document, RawSegment
from app.ingestion.chunker import chunk_segments


def test_load_txt(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("This is a simple test document about hybrid retrieval systems.")
    segments = load_document(str(p))
    assert len(segments) == 1
    assert "hybrid retrieval" in segments[0].text


def test_load_csv(tmp_path):
    p = tmp_path / "sample.csv"
    p.write_text("name,role\nSuraj,Engineer\nAda,Scientist\n")
    segments = load_document(str(p))
    assert len(segments) == 2
    assert "Suraj" in segments[0].text


def test_load_json(tmp_path):
    p = tmp_path / "sample.json"
    p.write_text('{"key": "value"}')
    segments = load_document(str(p))
    assert "key" in segments[0].text


def test_unsupported_extension(tmp_path):
    p = tmp_path / "sample.xyz"
    p.write_text("data")
    try:
        load_document(str(p))
        assert False, "should have raised"
    except ValueError:
        pass


def test_chunker_overlap():
    segs = [RawSegment(text=" ".join(f"word{i}" for i in range(200)), source="f.txt", location="document")]
    chunks = chunk_segments(segs, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    assert all(c.source == "f.txt" for c in chunks)
    # verify overlap: last N words of chunk[0] should appear in chunk[1]
    first_tail = chunks[0].text.split()[-5:]
    second_words = chunks[1].text.split()
    assert any(w in second_words for w in first_tail)
