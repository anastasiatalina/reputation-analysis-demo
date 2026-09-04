from datetime import datetime, timedelta

import pandas as pd
import requests

from app.config import load_config, require

def fetch_stock_data(company_name, ticker, days):
    cfg = load_config()
    api_key = require(cfg.fmp_api_key, "FMP_API_KEY")
    # Compute the request date range.
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Format dates for the API.
    from_date = start_date.strftime('%Y-%m-%d')
    to_date = end_date.strftime('%Y-%m-%d')

    BASE_URL = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?from={from_date}&to={to_date}&apikey={api_key}"

    print(f"Fetching stock data from {from_date} to {to_date}")

    response = requests.get(BASE_URL)
    if response.status_code == 200:
        data = response.json()
        if 'historical' in data:
            df = pd.DataFrame(data['historical'])

            # Parse date column.
            df['date'] = pd.to_datetime(df['date'])

            # Sort by date.
            df = df.sort_values(by='date')

            return df
        else:
            print("No historical data.")
            return pd.DataFrame()
    else:
        print(f"Error: {response.status_code}")
        return pd.DataFrame()
