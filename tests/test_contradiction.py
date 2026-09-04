from app.generation.contradiction import find_contradictions


def test_detects_numeric_contradiction():
    chunks = [
        {"source": "a.pdf", "location": "page 1",
         "text": "Quarterly revenue growth reached 12 percent according to internal reporting."},
        {"source": "b.pdf", "location": "page 3",
         "text": "Quarterly revenue growth reached 45 percent according to internal reporting."},
    ]
    result = find_contradictions(chunks)
    assert len(result) == 1
    assert result[0]["reason"] == "differing figures for the same topic"


def test_no_contradiction_for_unrelated_chunks():
    chunks = [
        {"source": "a.pdf", "location": "page 1", "text": "Quarterly revenue growth reached 12 percent."},
        {"source": "b.pdf", "location": "page 2", "text": "The cafeteria menu changes every Tuesday."},
    ]
    assert find_contradictions(chunks) == []


def test_no_false_positive_on_identical_chunks():
    chunks = [
        {"source": "a.pdf", "location": "page 1", "text": "Quarterly revenue growth reached 12 percent overall."},
        {"source": "b.pdf", "location": "page 4", "text": "Quarterly revenue growth reached 12 percent overall."},
    ]
    assert find_contradictions(chunks) == []
