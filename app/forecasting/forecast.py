from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

from app.paths import ProjectPaths

def prepare_weighted_weekly_data(file1, file2, root: Path | None = None):
    # Load data.
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)
    
    # Parse dates.
    df1['date'] = pd.to_datetime(df1['date'])
    df2['date'] = pd.to_datetime(df2['date'])
    
    # Combine inputs.
    df = pd.concat([df1, df2], ignore_index=True)

    # Clean data.
    df = df.dropna(subset=['score'])
    df = df[df['score'].between(-1, 1)]

    # Add week column (week start).
    df['week'] = df['date'].dt.to_period('W').apply(lambda r: r.start_time)

    # Group by weight.
    high_weight_types = ['analytical note', '10K']
    low_weight_types = df[~df['type'].isin(high_weight_types)]['type'].unique()

    # Group high-weight types.
    high_weight_group = (
        df[df['type'].isin(high_weight_types)]
        .groupby('week')['score']
        .mean()
        .reset_index()
    )
    high_weight_group['group'] = 'high_weight'

    # Group low-weight types.
    low_weight_group = (
        df[~df['type'].isin(high_weight_types)]
        .groupby('week')['score']
        .mean()
        .reset_index()
    )
    low_weight_group['group'] = 'low_weight'

    # Merge groups.
    combined_data = pd.concat([high_weight_group, low_weight_group], ignore_index=True)
    combined_data = combined_data.sort_values(by='week').reset_index(drop=True)

    # Store min/max values.
    original_min = combined_data['score'].min()
    original_max = combined_data['score'].max()

    # Normalize scores.
    combined_data['score'] = (combined_data['score'] - original_min) / (original_max - original_min)

    # Persist min/max as attributes.
    combined_data.attrs['original_min'] = original_min
    combined_data.attrs['original_max'] = original_max

    # Print preview.
    print("First 10 rows of normalized weekly data:")
    print(combined_data.head(10))

    # Save output into the processed data directory.
    paths = ProjectPaths(root=(root or Path.cwd()))
    paths.ensure_dirs()
    output_path = paths.data_processed_dir / "weighted_weekly_data.csv"
    combined_data.to_csv(output_path, index=False)
    print(f"Grouped data saved to '{output_path}'.")

    return combined_data

def train_arima_with_weekly_forecast(
    combined_data,
    forecast_periods=12,
    root: Path | None = None,
):
    """
    Train ARIMA and forecast the next N weeks.
    """
    # Train ARIMA on the full series.
    model = ARIMA(combined_data['score'], order=(6, 1, 6))
    results = model.fit()

    # Forecast from the last available week.
    last_date = combined_data['week'].max()
    future_dates = pd.date_range(start=last_date, periods=forecast_periods + 1, freq='W')[1:]
    forecast_future = results.forecast(steps=forecast_periods)

    # Denormalize forecasts.
    score_min = combined_data.attrs['original_min']
    score_max = combined_data.attrs['original_max']
    forecast_future_denormalized = forecast_future * (score_max - score_min) + score_min

    # Plot.
    plt.figure(figsize=(15, 6))

    # Denormalized historical series.
    plt.plot(combined_data['week'], 
             combined_data['score'] * (score_max - score_min) + score_min, 
             label='Historical Data (Denormalized)', color='green')

    # Denormalized forecast.
    plt.plot(future_dates, forecast_future_denormalized, label='Forecast (Denormalized)', linestyle='--', color='orange')

    # X axis formatting.
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    plt.xticks(rotation=45)

    # Plot styling.
    plt.legend()
    plt.title('ARIMA Forecast: Historical and Future (Denormalized)')
    plt.xlabel('Date')
    plt.ylabel('Score')
    plt.grid()
    paths = ProjectPaths(root=(root or Path.cwd()))
    paths.ensure_dirs()
    plot_path = paths.forecast_plot_png()
    plt.savefig(plot_path)
    print(f"Forecast plot saved to '{plot_path}'.")
    plt.show()

    # Return forecast dataframe.
    forecast_df = pd.DataFrame({
        'date': future_dates, 
        'forecast_normalized': forecast_future, 
        'forecast_denormalized': forecast_future_denormalized
    })
    return results, forecast_df

def main() -> None:
    file1 = "NO_1.csv"
    file2 = "Apple_2025-01-11_2years.csv"

    combined_data = prepare_weighted_weekly_data(file1, file2)
    if combined_data is None:
        print("No data produced for forecasting.")
        return

    _, forecast_df = train_arima_with_weekly_forecast(combined_data, forecast_periods=12)
    print("Forecast for the next 12 weeks:")
    print(forecast_df)


if __name__ == "__main__":
    main()