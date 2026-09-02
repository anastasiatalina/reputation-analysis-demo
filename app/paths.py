from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """
    Centralize output directories and filename conventions (to-be).
    """

    root: Path

    @property
    def data_raw_dir(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def data_processed_dir(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def assets_dir(self) -> Path:
        # Keep compatibility with existing UI assets folder.
        return self.root / "assets"

    def ensure_dirs(self) -> None:
        for d in [self.data_raw_dir, self.data_processed_dir, self.reports_dir, self.assets_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def run_date_str(run_dt: datetime | None = None) -> str:
        return (run_dt or datetime.now()).strftime("%Y-%m-%d")

    def combined_events_csv(self, company_name: str, days: int, run_dt: datetime | None = None) -> Path:
        run_date = self.run_date_str(run_dt)
        return self.data_processed_dir / f"combined_output_{run_date}_{company_name}_{days}days.csv"

    def stock_prices_csv(self, company_name: str, days: int, run_dt: datetime | None = None) -> Path:
        run_date = self.run_date_str(run_dt)
        return self.data_processed_dir / f"stock_data_{run_date}_{company_name}_{days}days.csv"

    def forecast_plot_png(self) -> Path:
        # UI expects this name today; keep it.
        return self.assets_dir / "forecast_plot_12_weeks.png"

