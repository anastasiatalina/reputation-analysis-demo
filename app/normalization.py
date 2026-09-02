from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


def to_datetime_utc(value: Any) -> Optional[datetime]:
    """
    Best-effort conversion to timezone-aware UTC datetime.
    Returns None if parsing fails.
    """
    if value is None:
        return None
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return None
        # pandas can return Timestamp; convert to python datetime
        dt = ts.to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def to_iso_utc(value: Any) -> Optional[str]:
    dt = to_datetime_utc(value)
    if not dt:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

