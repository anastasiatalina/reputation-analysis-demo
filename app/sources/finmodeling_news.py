import json
from datetime import datetime, timedelta
from urllib.request import urlopen

import certifi
from bs4 import BeautifulSoup

from app.config import load_config, require
from app.normalization import to_iso_utc
from app.sentiment.tone_analysis import analyze_tone

def _get_fmp_api_key() -> str:
    cfg = load_config()
    return require(cfg.fmp_api_key, "FMP_API_KEY")

# Fetch JSON from API.
def get_jsonparsed_data(url):
    try:
        response = urlopen(url, cafile=certifi.where())
        data = response.read().decode("utf-8")
        return json.loads(data)
    except Exception as e:
        print(f"Data fetch error: {e}")
        return None

def clean_html(html_text):
    if html_text:
        soup = BeautifulSoup(html_text, 'html.parser')
        return soup.get_text(separator=" ").replace("\n", " ")
    return ""

# Fetch company news with pagination.
def fetch_with_retry(ticker, days, retries=3):
    api_key = _get_fmp_api_key()
    base_url = "https://financialmodelingprep.com/api/v3/stock_news"
    to_date = datetime.now().strftime('%Y-%m-%d')
    from_date = (datetime.now() - timedelta(days)).strftime('%Y-%m-%d')
    page = 0
    all_data = []

    for _ in range(retries):
        try:
            while True:
                safe_url = f"{base_url}?apikey=***&tickers={ticker}&page={page}&from={from_date}&to={to_date}"
                print(f"Fetching URL: {safe_url}")
                url = f"{base_url}?tickers={ticker}&page={page}&from={from_date}&to={to_date}&apikey={api_key}"
                data = get_jsonparsed_data(url)
                
                if not data or len(data) == 0:
                    break

                all_data.extend(data)
                page += 1
            break
        except Exception as e:
            print(f"Request error: {e}")
            continue

    return all_data

# Analyze and normalize news payloads.
def analyze_finmodeling_news(ticker, days, callback=None):
    news_data = fetch_with_retry(ticker, days)
    
    if not news_data:
        print("No news found.")
        return
    
    for article in news_data:
        try:
            title = article.get('title', 'No title available').replace('\n', ' ').replace('\r', ' ').replace(';', '')
            text = article.get('text', 'No content available').replace('\n', ' ').replace('\r', ' ').replace(';', '')
            url = article.get('url', 'No URL available')
            published_at = article.get('publishedDate')

            if not published_at:
                print(f"Missing published date for '{title}'.")
                continue

            formatted_date = to_iso_utc(published_at)
            if not formatted_date:
                print(f"Invalid published date: {published_at}")
                continue

            clean_text = clean_html(text)
            sentiment = analyze_tone(clean_text if clean_text else title)

            result = {
                'date': formatted_date,
                'news': title,
                'description': clean_text,
                'url': url,
                'score': sentiment,
                'type': 'news_fm'
            }
            
            if callback:
                callback(result)
            else:
                print(result)

        except Exception as e:
            print(f"News processing error: {e}")

# Entry point for direct execution.
if __name__ == "__main__":
    analyze_finmodeling_news("TSLA", 1)