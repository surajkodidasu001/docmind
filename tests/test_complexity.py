from app.agent.complexity import classify_complexity, model_for_complexity
from app.config import settings


def test_short_lookup_is_simple():
    assert classify_complexity("What is the refund policy?") == "simple"


def test_comparison_question_is_complex():
    assert classify_complexity("Compare the refund policy versus the warranty policy") == "complex"


def test_why_question_is_complex():
    assert classify_complexity("Why did revenue decline in Q3?") == "complex"


def test_long_query_is_complex():
    long_query = " ".join(["word"] * (settings.simple_query_max_words + 5))
    assert classify_complexity(long_query) == "complex"


def test_model_routing_matches_complexity():
    assert model_for_complexity("simple") == settings.llm_model_small
    assert model_for_complexity("complex") == settings.llm_model
