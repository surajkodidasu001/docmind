from app.generation.citation import verify_citations, build_context_block


def test_build_context_block_numbers_chunks():
    chunks = [
        {"source": "a.pdf", "location": "page 1", "text": "Alpha content"},
        {"source": "b.pdf", "location": "page 2", "text": "Beta content"},
    ]
    block = build_context_block(chunks)
    assert "[1]" in block and "[2]" in block
    assert "Alpha content" in block


def test_verify_citations_flags_unsupported_claim():
    chunks = [{"source": "a.pdf", "location": "page 1", "text": "The sky is blue during clear daytime weather."}]
    # Claim [1] is well supported by the chunk
    supported_answer = "The sky is blue during clear daytime weather. [1]"
    result = verify_citations(supported_answer, chunks)
    assert result["total_cited_claims"] == 1
    assert result["supported_claims"] == 1

    # Claim cites chunk 1 but is about something totally unrelated
    unsupported_answer = "Quantum computers use superconducting qubits for computation. [1]"
    result2 = verify_citations(unsupported_answer, chunks)
    assert result2["flagged"], "should flag an unsupported claim"
