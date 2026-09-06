from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.paths import ProjectPaths


@dataclass(frozen=True)
class MockOutput:
    combined_events_csv: Path
    stock_prices_csv: Path
    forecast_input_csv: Path
    tenk_csv: Path
    forecast_plot_png: Path


def _seed_from(company_name: str, days: int, seed: int | None) -> int:
    if seed is not None:
        return seed
    return abs(hash(f"{company_name}:{days}")) % (2**32)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_event_rows(
    company_name: str,
    days: int,
    rng: np.random.Generator,
    events_per_day: int = 3,
) -> list[dict]:
    types = ["news", "twit", "analytical note", "news_fm"]
    now = datetime.now(tz=timezone.utc)
    rows: list[dict] = []
    for day_offset in range(days):
        day = now - timedelta(days=day_offset)
        for idx in range(events_per_day):
            created_at = day - timedelta(hours=int(rng.integers(0, 20)))
            score = float(np.clip(rng.normal(loc=0.05, scale=0.45), -1, 1))
            event_type = types[int(rng.integers(0, len(types)))]
            rows.append(
                {
                    "date": _iso_utc(created_at),
                    "news": f"{company_name} mock event {day_offset + 1}-{idx + 1}",
                    "description": f"Mock description for {company_name} event {idx + 1}.",
                    "url": f"https://example.com/{company_name.lower()}/{day_offset}/{idx}",
                    "score": score,
                    "type": event_type,
                }
            )
    return rows


def _make_stock_rows(days: int, rng: np.random.Generator) -> pd.DataFrame:
    now = datetime.now(tz=timezone.utc).date()
    dates = [now - timedelta(days=i) for i in range(days)]
    dates.reverse()
    prices = [float(100 + rng.normal(0, 1))]
    for _ in range(1, len(dates)):
        prices.append(float(prices[-1] + rng.normal(0.1, 1.5)))
    prices = np.maximum(prices, 1.0)
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": np.array(prices) - rng.normal(0.2, 0.5, size=len(prices)),
            "high": np.array(prices) + rng.normal(0.5, 0.6, size=len(prices)),
            "low": np.array(prices) - rng.normal(0.6, 0.6, size=len(prices)),
            "close": prices,
            "volume": rng.integers(1_000_000, 5_000_000, size=len(prices)),
        }
    )
    return df


def _make_forecast_inputs(
    root: Path,
    rng: np.random.Generator,
    company_name: str = "Apple",
    years: int = 2,
) -> tuple[Path, Path]:
    paths = ProjectPaths(root=root)
    paths.ensure_dirs()
    raw_dir = paths.data_raw_dir
    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=365 * years)
    weeks = pd.date_range(start=start, end=now, freq="W")

    events = []
    types = ["news", "twit", "analytical note", "news_fm"]
    for week in weeks:
        for _ in range(int(rng.integers(2, 5))):
            events.append(
                {
                    "date": _iso_utc(week.to_pydatetime()),
                    "news": f"{company_name} historical event",
                    "description": "Mock historical event used for forecasting.",
                    "url": "https://example.com/history",
                    "score": float(np.clip(rng.normal(0.02, 0.35), -1, 1)),
                    "type": types[int(rng.integers(0, len(types)))],
                }
            )

    forecast_input = raw_dir / f"{company_name}_{now.strftime('%Y-%m-%d')}_2years.csv"
    pd.DataFrame(events).to_csv(forecast_input, index=False, encoding="utf-8")

    tenk_dates = pd.date_range(start=start, end=now, freq="180D")
    tenk_rows = []
    for date in tenk_dates:
        tenk_rows.append(
            {
                "date": _iso_utc(date.to_pydatetime()),
                "news": "10-K report summary",
                "description": "Mock 10-K narrative event.",
                "url": "https://example.com/10k",
                "score": float(np.clip(rng.normal(0.1, 0.25), -1, 1)),
                "type": "10K",
            }
        )
    tenk_csv = raw_dir / "NO_1.csv"
    pd.DataFrame(tenk_rows).to_csv(tenk_csv, index=False, encoding="utf-8")

    return forecast_input, tenk_csv


def _make_forecast_plot(root: Path) -> Path:
    paths = ProjectPaths(root=root)
    paths.ensure_dirs()
    plot_path = paths.forecast_plot_png()
    x = np.arange(12)
    y = np.sin(x / 3) * 0.2 + 0.5
    plt.figure(figsize=(8, 4))
    plt.plot(x, y, marker="o")
    plt.title("Mock forecast")
    plt.xlabel("Week")
    plt.ylabel("Score")
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    return plot_path


def generate_mocks(
    company_name: str,
    ticker: str,
    days: int,
    root: Path,
    seed: int | None = None,
    include_forecast_inputs: bool = True,
    include_forecast_plot: bool = True,
    force: bool = False,
) -> MockOutput:
    paths = ProjectPaths(root=root)
    paths.ensure_dirs()
    rng = np.random.default_rng(_seed_from(company_name, days, seed))

    combined_path = paths.combined_events_csv(company_name, days)
    if combined_path.exists() and not force:
        print(f"Skipping existing combined events: {combined_path}")
    else:
        events = _make_event_rows(company_name, days, rng)
        events_df = pd.DataFrame(events)
        events_df["date"] = pd.to_datetime(events_df["date"], errors="coerce", utc=True)
        events_df = events_df.sort_values(by="date", ascending=False)
        events_df.to_csv(combined_path, index=False, encoding="utf-8")

    stock_path = paths.stock_prices_csv(company_name, days)
    if stock_path.exists() and not force:
        print(f"Skipping existing stock prices: {stock_path}")
    else:
        stock_df = _make_stock_rows(days, rng)
        stock_df.to_csv(stock_path, index=False, encoding="utf-8")

    forecast_input = paths.data_raw_dir / f"{company_name}_{datetime.now().strftime('%Y-%m-%d')}_2years.csv"
    tenk_csv = paths.data_raw_dir / "NO_1.csv"
    if include_forecast_inputs:
        if forecast_input.exists() and tenk_csv.exists() and not force:
            print(f"Skipping existing forecast inputs: {forecast_input}, {tenk_csv}")
        else:
            forecast_input, tenk_csv = _make_forecast_inputs(root, rng, company_name=company_name)

    plot_path = paths.forecast_plot_png()
    if include_forecast_plot:
        if plot_path.exists() and not force:
            print(f"Skipping existing forecast plot: {plot_path}")
        else:
            plot_path = _make_forecast_plot(root)

    return MockOutput(
        combined_events_csv=combined_path,
        stock_prices_csv=stock_path,
        forecast_input_csv=forecast_input,
        tenk_csv=tenk_csv,
        forecast_plot_png=plot_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate mock data for demo runs.")
    parser.add_argument("--company", default="Apple", help="Company name (default: Apple)")
    parser.add_argument("--ticker", default="AAPL", help="Ticker symbol (default: AAPL)")
    parser.add_argument("--days", type=int, default=90, help="Lookback period in days (default: 90)")
    parser.add_argument("--root", default=".", help="Project root directory (default: current directory)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (default: derived)")
    parser.add_argument(
        "--no-forecast-inputs",
        action="store_true",
        help="Skip generating data/raw/NO_1.csv and *2years.csv inputs.",
    )
    parser.add_argument(
        "--no-forecast-plot",
        action="store_true",
        help="Skip generating assets/forecast_plot_12_weeks.png.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate files even if they already exist.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    root = Path(args.root).resolve()
    output = generate_mocks(
        company_name=args.company,
        ticker=args.ticker,
        days=args.days,
        root=root,
        seed=args.seed,
        include_forecast_inputs=not args.no_forecast_inputs,
        include_forecast_plot=not args.no_forecast_plot,
        force=args.force,
    )

    print("Mock data generated.")
    print(f"Combined events: {output.combined_events_csv}")
    print(f"Stock prices:   {output.stock_prices_csv}")
    if not args.no_forecast_inputs:
        print(f"Forecast input: {output.forecast_input_csv}")
        print(f"10-K input:     {output.tenk_csv}")
    if not args.no_forecast_plot:
        print(f"Forecast plot:  {output.forecast_plot_png}")


if __name__ == "__main__":
    main()
