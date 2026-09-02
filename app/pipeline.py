from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from app.paths import ProjectPaths
from app.logging_utils import get_logger


@dataclass(frozen=True)
class AnalyzeResult:
    combined_events_csv: Path
    stock_prices_csv: Path
    run_date: str


def project_root_from_file(file_path: str) -> Path:
    return Path(file_path).resolve().parent


def analyze(company_name: str, ticker: str, days: int, root: Optional[Path] = None) -> AnalyzeResult:
    """
    Orchestrate ingestion + merge + stock download using legacy modules,
    but write outputs using to-be paths and naming.
    """
    root = root or Path.cwd()
    paths = ProjectPaths(root=root)
    paths.ensure_dirs()
    logger = get_logger(__name__)

    # Import legacy modules locally to keep side effects minimal.
    from app.sources.news import analyze_news
    from app.sources.reddit import analyze_tweets
    from app.sources.analytical_notes import analyze_analytical_notes
    from app.sources.finmodeling_news import analyze_finmodeling_news
    from app.sources.stockprice import fetch_stock_data

    run_dt = datetime.now()
    combined_path = paths.combined_events_csv(company_name, days, run_dt=run_dt)
    stock_path = paths.stock_prices_csv(company_name, days, run_dt=run_dt)

    rows = []
    logger.info("Collecting events for company=%s ticker=%s days=%s", company_name, ticker, days)
    analyze_news(company_name, days, callback=rows.append, root=root)
    analyze_tweets(company_name, days, callback=rows.append, root=root)
    analyze_analytical_notes(ticker, days, callback=rows.append)
    analyze_finmodeling_news(ticker, days, callback=rows.append)
    logger.info("Collected %s raw events", len(rows))

    df = pd.DataFrame(rows)
    if "date" not in df.columns:
        df["date"] = pd.NaT
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)

    # Basic cleaning: drop removed/empty entries and duplicate events.
    df["news"] = df.get("news", pd.Series(dtype=str)).fillna("")
    df["description"] = df.get("description", pd.Series(dtype=str)).fillna("")
    df = df[~((df["news"].str.strip() == "[Removed]") | (df["description"].str.strip() == "[Removed]"))]
    if all(c in df.columns for c in ["news", "description", "url"]):
        df = df.drop_duplicates(subset=["news", "description", "url"])
    df = df.sort_values(by="date", ascending=False)

    df.to_csv(combined_path, index=False, encoding="utf-8-sig")
    logger.info("Wrote merged events CSV: %s", combined_path)

    stock_df = fetch_stock_data(company_name, ticker, days)
    if stock_df is not None and not stock_df.empty:
        stock_df.to_csv(stock_path, index=False, encoding="utf-8")
        logger.info("Wrote stock prices CSV: %s", stock_path)
    else:
        logger.warning("Stock prices dataframe is empty; skipping CSV write")

    return AnalyzeResult(
        combined_events_csv=combined_path,
        stock_prices_csv=stock_path,
        run_date=paths.run_date_str(run_dt),
    )

