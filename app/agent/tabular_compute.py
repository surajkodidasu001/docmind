"""Detects and answers computation-style questions against ingested CSVs.

Keyword-triggered, single-column aggregation only (sum/average/count/min/max)
— see app/retrieval/tabular_store.py docstring for why that scope was chosen
over full text-to-SQL. This runs entirely with pandas, no LLM call needed for
the computation itself (the LLM is only used, if at all, to phrase the final
sentence — see `phrase_answer` below, which is optional and falls back to a
template if no API key is configured).
"""
from __future__ import annotations

import re
from typing import Optional, Dict, Any

from app.retrieval.tabular_store import list_tables, get_dataframe

_AGG_KEYWORDS = {
    "sum": ["sum of", "total"],
    "mean": ["average", "avg", "mean"],
    "count": ["how many", "count of", "number of"],
    "max": ["maximum", "highest", "largest", "max"],
    "min": ["minimum", "lowest", "smallest", "min"],
}


def detect_computation_request(query: str) -> Optional[Dict[str, Any]]:
    """Returns {'operation': ..., 'column': ..., 'table': ...} if the query
    looks like a tabular aggregation request the pandas path can handle,
    else None (falls through to normal retrieval)."""
    tables = list_tables()
    if not tables:
        return None

    q = query.lower()
    operation = None
    for op, phrases in _AGG_KEYWORDS.items():
        if any(p in q for p in phrases):
            operation = op
            break
    if operation is None:
        return None

    # find which table + column the query is talking about, by simple
    # substring match against known column names (case-insensitive)
    best_match = None
    for table_name, columns in tables.items():
        for col in columns:
            if col.lower() in q:
                best_match = {"table": table_name, "column": col, "operation": operation}
                break
        if best_match:
            break

    return best_match


def run_computation(request: Dict[str, Any]) -> Dict[str, Any]:
    df = get_dataframe(request["table"])
    if df is None:
        return {"error": f"table {request['table']} not found"}

    col = request["column"]
    op = request["operation"]

    if op == "count":
        value = int(df[col].count())
    else:
        numeric = df[col].astype(str).str.replace(r"[^\d.\-]", "", regex=True)
        numeric = numeric.replace("", None).astype(float)
        if op == "sum":
            value = float(numeric.sum())
        elif op == "mean":
            value = float(numeric.mean())
        elif op == "max":
            value = float(numeric.max())
        elif op == "min":
            value = float(numeric.min())
        else:
            return {"error": f"unsupported operation {op}"}

    return {
        "table": request["table"],
        "column": col,
        "operation": op,
        "value": value,
        "row_count": len(df),
    }


def phrase_answer(computation: Dict[str, Any]) -> str:
    """Template phrasing — deterministic, no LLM call needed. Kept separate
    so a caller could swap in an LLM-phrased version without touching the
    computation logic."""
    if "error" in computation:
        return f"I couldn't compute that: {computation['error']}"

    op_phrase = {
        "sum": "total", "mean": "average", "count": "count",
        "max": "maximum", "min": "minimum",
    }[computation["operation"]]

    value = computation["value"]
    value_str = f"{value:,.2f}" if isinstance(value, float) and not value.is_integer() else f"{int(value):,}"

    return (
        f"The {op_phrase} of **{computation['column']}** in `{computation['table']}` "
        f"is **{value_str}** (computed across {computation['row_count']} rows)."
    )
