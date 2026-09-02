import argparse
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app", description="Reputation analysis toolkit (to-be).")
    sub = p.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Run ingestion + merge + stock download.")
    analyze.add_argument("--company", required=True, help="Company name (e.g. Apple)")
    analyze.add_argument("--ticker", required=True, help="Ticker symbol (e.g. AAPL)")
    analyze.add_argument("--days", required=True, type=int, help="Lookback period in days (e.g. 90)")
    analyze.add_argument("--root", default=".", help="Project root directory (default: current directory)")

    forecast = sub.add_parser("forecast", help="Run weekly aggregation + ARIMA forecast.")
    forecast.add_argument(
        "--file1",
        default="data/raw/NO_1.csv",
        help="10-K derived events CSV (default: data/raw/NO_1.csv)",
    )
    forecast.add_argument(
        "--file2",
        default="data/raw/Apple_2025-01-11_2years.csv",
        help="Historical events CSV (default: data/raw/Apple_2025-01-11_2years.csv)",
    )
    forecast.add_argument("--weeks", default=12, type=int, help="Forecast horizon in weeks (default: 12)")
    forecast.add_argument("--root", default=".", help="Project root directory (default: current directory)")

    return p


def main() -> None:
    args = _build_parser().parse_args()

    if args.command == "analyze":
        from app.pipeline import analyze

        root = Path(args.root).resolve()
        result = analyze(company_name=args.company, ticker=args.ticker, days=args.days, root=root)
        print("Analyze completed.")
        print(f"Combined events: {result.combined_events_csv}")
        print(f"Stock prices:   {result.stock_prices_csv}")
        return

    if args.command == "forecast":
        from app.forecasting.forecast import (
            prepare_weighted_weekly_data,
            train_arima_with_weekly_forecast,
        )

        root = Path(args.root).resolve()
        file1 = str((root / args.file1).resolve())
        file2 = str((root / args.file2).resolve())
        combined = prepare_weighted_weekly_data(file1, file2, root=root)
        if combined is None:
            raise SystemExit("No data produced for forecasting.")
        _, forecast_df = train_arima_with_weekly_forecast(
            combined,
            forecast_periods=args.weeks,
            root=root,
        )
        print("Forecast completed.")
        print(forecast_df.head(20).to_string(index=False))
        return


if __name__ == "__main__":
    main()

