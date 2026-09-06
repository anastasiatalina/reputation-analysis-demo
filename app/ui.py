import time
from pathlib import Path

import flet as ft
import pandas as pd
import plotly.graph_objects as go
from flet.plotly_chart import PlotlyChart

from app.logging_utils import get_logger
from app.paths import ProjectPaths
from app.pipeline import analyze as pipeline_analyze

def _placeholder_figure(message: str) -> go.Figure:
    """
    An empty-but-valid Plotly figure showing a centered message, used before any
    data has been loaded. A PlotlyChart control with no figure at all renders a
    raw Flet error ('Image must have either "src" or "src_base64" specified.'),
    so every chart control must always hold a real figure, even an empty one.
    """
    fig = go.Figure()
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[{
            "text": message,
            "xref": "paper",
            "yref": "paper",
            "x": 0.5,
            "y": 0.5,
            "showarrow": False,
            "font": {"size": 16, "color": "#94a3b8"},
        }],
        height=450,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    return fig

def main(page: ft.Page):
    logger = get_logger(__name__)
    page.window.width = 1000
    page.window.height = 1000
    page.assets_dir = str(Path(__file__).resolve().parent.parent / "assets")
    page.title = "Reputation Analysis"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 20

    def on_analyze_click(e):
        company_name = ticker_selector.value
        period = period_selector.value

        if not company_name or not period:
            logger.warning("Company or period is not selected.")
            return

        ticker = COMPANY_TICKERS.get(company_name)
        days = PERIOD_DAYS.get(period)

        if not ticker or not days:
            logger.warning("Invalid company or period selection.")
            return

        load_data(company_name, ticker, days)
        fill_events(company_name, days)
        fill_prediction()

    def _project_paths() -> ProjectPaths:
        root = Path(__file__).resolve().parent.parent
        paths = ProjectPaths(root=root)
        paths.ensure_dirs()
        return paths

    def _find_latest_file(*globs: str) -> str | None:
        """
        Find latest matching file across root and data/processed.
        Returns string path or None.
        """
        paths = _project_paths()
        candidates: list[Path] = []
        for g in globs:
            candidates.extend(paths.root.glob(g))
            candidates.extend(paths.data_processed_dir.glob(g))
        if not candidates:
            return None
        candidates = [p for p in candidates if p.exists()]
        if not candidates:
            return None
        return str(max(candidates, key=lambda p: p.stat().st_mtime))

    def load_data(company_name, ticker, days):
        analyze_error = None
        try:
            analyze_button.disabled = True
            analyze_button.text = "Loading data..."
            analyze_button.icon = ft.ProgressRing(width=16, height=16)
            page.update()

            try:
                pipeline_analyze(
                    company_name=company_name,
                    ticker=ticker,
                    days=days,
                    root=Path(__file__).resolve().parent.parent,
                )
            except Exception as e:
                logger.exception("Analyze failed: %s", e)
                analyze_error = str(e)

            # Always try to render whatever data already exists (fresh or
            # leftover from a previous run) even if the live fetch above
            # failed - a missing API key shouldn't blank the whole screen.
            try:
                fill_reputation_graph(company_name, days)
                fill_stock_chart(company_name, days)
            except Exception as e:
                logger.exception("Rendering charts failed: %s", e)
                if not analyze_error:
                    analyze_error = str(e)

            tabs.selected_index = 1

            if analyze_error:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Analyze failed: {analyze_error}"),
                    bgcolor=ft.Colors.RED_400,
                )
                page.snack_bar.open = True

            page.update()
        finally:
            analyze_button.disabled = False
            analyze_button.text = "Analyze reputation"
            analyze_button.icon = None
            page.update()

    def fill_reputation_graph(company_name, days):
        filename = _find_latest_file(
            f"combined_output_*_{company_name}_{days}days.csv",
        )
        if not filename:
            logger.warning("Combined events file not found. Run Analyze first.")
            reputation_graph.figure = _placeholder_figure(
                f"No reputation data yet for {company_name} ({days} days)."
            )
            return
        df = pd.read_csv(filename)
        df['date'] = pd.to_datetime(df['date'])
        
        weekly_data = df.groupby(pd.Grouper(key='date', freq='W'))['score'].mean().reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weekly_data['date'],
            y=weekly_data['score'],
            mode='lines+markers',
            name='Reputation score'
        ))
        
        fig.update_layout(
            title=f'Reputation analysis {company_name}',
            xaxis_title='Date',
            yaxis_title='Score',
            hovermode='x unified',
            height=450
        )
        
        reputation_graph.figure = fig

    def fill_stock_chart(company_name, days):
        filename = _find_latest_file(
            f"stock_data_*_{company_name}_{days}days.csv",
            f"stock_data*_{company_name}_{days}days.csv",
        )
        if not filename:
            logger.warning("Stock prices file not found. Run Analyze first.")
            stock_chart.figure = _placeholder_figure(
                f"No stock price data yet for {company_name} ({days} days)."
            )
            return
        df = pd.read_csv(filename)
        df['date'] = pd.to_datetime(df['date'])
        
        weekly_data = df.groupby(pd.Grouper(key='date', freq='W'))['close'].mean().reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weekly_data['date'],
            y=weekly_data['close'],
            mode='lines+markers',
            name='Close'
        ))
        
        fig.update_layout(
            title=f'Stock price change {company_name}',
            xaxis_title='Date',
            yaxis_title='Price',
            hovermode='x unified',
            height=450
        )
        
        stock_chart.figure = fig

    def fill_events(company_name, days):
        filename = _find_latest_file(
            f"combined_output_*_{company_name}_{days}days.csv",
        )
        if not filename:
            logger.warning("Combined events file not found. Run Analyze first.")
            return
        try:
            df = pd.read_csv(filename)
            required_columns = ['date', 'news', 'description', 'score', 'type']
            if not all(col in df.columns for col in required_columns):
                logger.warning(
                    "Missing required columns in events file. Found: %s",
                    df.columns.tolist(),
                )
                return
            table = ft.DataTable(
                width=1000,
                column_spacing=0,
                vertical_lines=ft.BorderSide(1, "red"),
                columns=[
                    ft.DataColumn(ft.Text("Date")),
                    ft.DataColumn(ft.Text("News")),
                    ft.DataColumn(ft.Text("URL")),
                    ft.DataColumn(ft.Text("Score")),
                ],
                rows=[
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(row['date'][:19], max_lines=2, width=85)),
                        ft.DataCell(ft.Text(row['news'], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, width=250)),
                        ft.DataCell(ft.Text(
                            disabled=False,
                            spans=[
                                ft.TextSpan(
                                    row['url'],
                                    ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
                                    url=row['url']          
                                ),
                            ],
                            max_lines=2, 
                            overflow=ft.TextOverflow.ELLIPSIS, 
                            width=250)),
                        ft.DataCell(ft.Text(row['score'], max_lines=1, no_wrap=True, width=100)),
                    ])
                    for index, row in df.iterrows()
                ],
            )            

            events_table.rows = table.rows
            page.update()
        except Exception as e:
            logger.exception("Events loading failed: %s", e)

    def fill_prediction():
        filename = _find_latest_file("assets/forecast_plot_12_weeks.png", "forecast_plot_12_weeks.png")
        if not filename:
            logger.warning("Forecast plot not found.")
            return
        image = ft.Image(src=filename, width=1200, height=675)
        forecast_graph.content = image
        page.update()

    def on_forecast_click(e):
        forecast_button.disabled = True
        forecast_button.text = "Processing..."
        forecast_button.icon = ft.ProgressRing(width=16, height=16)
        page.update()

        time.sleep(2)

        fill_prediction()
        forecast_button.disabled = False
        forecast_button.text = "Reputation forecast for next 3 months"
        forecast_button.icon = None

        tabs.selected_index = 3
        page.update()

    def on_back_to_analysis(e):
        tabs.selected_index = 1
        page.update()

    # Company display names mapped to tickers.
    COMPANY_TICKERS = {
        "Apple": "AAPL",
        "Tesla": "TSLA",
        "Intel": "INTC",
        "NVIDIA": "NVDA",
        "AMD": "AMD",
        "Microsoft": "MSFT",
        "Amazon": "AMZN",
    }

    # Period label mapped to day count.
    PERIOD_DAYS = {
        "3 months": 90,
        "6 months": 180,
        "1 year": 365
    }

    # Input controls.
    ticker_selector = ft.Dropdown(
        label="Choose company",
        options=[ft.dropdown.Option(company) for company in COMPANY_TICKERS.keys()],
    )
    
    period_selector = ft.Dropdown(
        label="Choose period",
        options=[ft.dropdown.Option(period) for period in PERIOD_DAYS.keys()]
    )

    analyze_button = ft.ElevatedButton(text="Analyze reputation", on_click=on_analyze_click)
    forecast_button = ft.ElevatedButton(text="Reputation forecast for next 3 months", on_click=on_forecast_click)

    main_tab = ft.Column(
        [
            ft.Container(padding=ft.padding.only(top=20)),
            ticker_selector,
            period_selector,
            ft.Row([analyze_button, forecast_button], spacing=20)
        ],
        spacing=20
    )

    # Chart components.
    reputation_graph = PlotlyChart(
        figure=_placeholder_figure("Choose a company and period, then click Analyze."),
        expand=True,
    )
    stock_chart = PlotlyChart(
        figure=_placeholder_figure("Choose a company and period, then click Analyze."),
        expand=True,
    )

    correlation_analysis = ft.Text("Reputation and Stock Price Correlation")

    analysis_tab = ft.Column([
        ft.Container(padding=ft.padding.only(top=20)),
        ft.Column([
            reputation_graph,
            stock_chart
        ], spacing=20),
        correlation_analysis,
    ], spacing=20)

    # Events view
    events_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Date")),
            ft.DataColumn(ft.Text("News")),
            ft.DataColumn(ft.Text("URL")),
            ft.DataColumn(ft.Text("Score")),
        ],
        rows=[]
    )
    back_to_analysis_button = ft.ElevatedButton(text="Back to analysis", on_click=on_back_to_analysis)

    events_tab = ft.Column([
        events_table,
        ft.Row([back_to_analysis_button], spacing=20)
    ], spacing=20)

    # Forecast view
    forecast_graph = ft.Container(content=ft.Image(src="forecast_plot_12_weeks.png", fit=ft.ImageFit.FILL, width=1000, height=400),
                                  border=ft.border.all(color="purple", width=2))
    return_to_reputation_button = ft.ElevatedButton(text="Back to analysis", on_click=on_back_to_analysis)

    forecast_tab = ft.Column([
        ft.Container(padding=ft.padding.only(top=20)),
        forecast_graph,
        ft.Row([return_to_reputation_button], spacing=20)
    ], spacing=20)

    # Tabs.
    tabs = ft.Tabs(
        selected_index=0,
        tabs=[
            ft.Tab(text="Home", content=main_tab),
            ft.Tab(text="Reputation analysis", content=analysis_tab),
            ft.Tab(text="Events", content=events_tab),
            ft.Tab(text="Forecast", content=forecast_tab),
        ],
    )

    # Render.
    page.add(tabs)


ft.app(target=main)
