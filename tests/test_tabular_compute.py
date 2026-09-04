import pandas as pd

from app.retrieval.tabular_store import store_dataframe, clear, list_tables
from app.agent.tabular_compute import detect_computation_request, run_computation, phrase_answer


def setup_function():
    clear()
    df = pd.DataFrame({
        "product": ["A", "B", "C"],
        "revenue": [1000, 2500, 750],
        "units": [50, 80, 30],
    })
    store_dataframe("sales.csv", df)


def test_detects_sum_request():
    req = detect_computation_request("what is the total revenue?")
    assert req == {"table": "sales.csv", "column": "revenue", "operation": "sum"}


def test_detects_average_request():
    req = detect_computation_request("what's the average units?")
    assert req["operation"] == "mean"
    assert req["column"] == "units"


def test_no_detection_for_unrelated_query():
    assert detect_computation_request("what is the refund policy?") is None


def test_no_detection_when_no_tables_ingested():
    clear()
    assert detect_computation_request("what is the total revenue?") is None


def test_run_computation_sum():
    req = {"table": "sales.csv", "column": "revenue", "operation": "sum"}
    result = run_computation(req)
    assert result["value"] == 4250.0
    assert result["row_count"] == 3


def test_run_computation_count():
    req = {"table": "sales.csv", "column": "product", "operation": "count"}
    result = run_computation(req)
    assert result["value"] == 3


def test_phrase_answer_formats_integer_cleanly():
    result = {"table": "sales.csv", "column": "revenue", "operation": "sum", "value": 4250.0, "row_count": 3}
    text = phrase_answer(result)
    assert "4,250" in text
    assert "sales.csv" in text


def test_phrase_answer_handles_error():
    assert "couldn't compute" in phrase_answer({"error": "table not found"})
