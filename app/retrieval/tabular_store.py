"""Raw tabular data store, kept separate from the chunked-text index.

CSVs get chunked into text like every other format for retrieval purposes
(so a semantic question like "what does the pricing sheet say about
discounts" still works), but that loses row/column structure needed for
actual computation ("what's the average of column X"). This store keeps
the original DataFrame per ingested CSV so a compute-capable query can
operate on real structured data instead of text approximations of it.

Scope decision (since this needs to be picked, not left ambiguous): the
compute node supports single-column aggregations — sum, mean/average,
count, min, max — triggered by keyword detection, not full free-form SQL.
That covers the common "how many / what's the total / what's the average"
class of question without executing arbitrary generated code.
"""
from __future__ import annotations

from typing import Dict, Optional
import pandas as pd

_tables: Dict[str, pd.DataFrame] = {}


def store_dataframe(filename: str, df: pd.DataFrame):
    _tables[filename] = df


def get_dataframe(filename: str) -> Optional[pd.DataFrame]:
    return _tables.get(filename)


def list_tables() -> Dict[str, list]:
    return {name: list(df.columns) for name, df in _tables.items()}


def delete_table(filename: str) -> bool:
    return _tables.pop(filename, None) is not None


def clear():
    _tables.clear()
