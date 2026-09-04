import time
from datetime import datetime, timedelta

import requests

from app.config import load_config, require
from app.normalization import to_iso_utc
from app.sentiment.tone_analysis import analyze_tone

API_URL = "https://api.benzinga.com/api/v1/analyst/insights"

def fetch_analytical_notes(query, retries=3, page_size=10):
    cfg = load_config()
    api_token = require(cfg.benzinga_token, "BENZINGA_TOKEN")
    BASE_URL = "https://api.benzinga.com/api/v1/analyst/insights"
    all_insights = []
    page = 1
    
    while True:
        querystring = {
            "token": api_token,
            "symbols": query,
            "page": page,
            "pageSize": page_size
        }
        
        safe_url = f"{BASE_URL}?token=***&symbols={query}&page={page}&pageSize={page_size}"
        print(f"Fetching URL: {safe_url}")
        
        for _ in range(retries):
            try:
                response = requests.get(BASE_URL, params=querystring, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                if isinstance(data, list):
                    return all_insights
                
                insights = data.get("analyst-insights", [])
                
                if not insights:
                    return
                    
                all_insights.extend(insights)
                page += 1
                break
                
            except requests.exceptions.RequestException as e:
                print(f"Request error on page {page}: {e}")
                if _ == retries - 1:
                    return all_insights
                time.sleep(2)
    
    return all_insights

def analyze_analytical_notes(query, days, callback=None):
    notes_data = fetch_analytical_notes(query)

    if not notes_data:
        return

    fromDate = datetime.now() - timedelta(days)

    for note in notes_data:
        try:
            date_str = note.get('date', 'No date available')
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

            if date < fromDate:
                continue

            news = note.get('analyst_insights', 'No news available').replace('\n', ' ').replace('\r', ' ').replace(';', '')
            description = note.get('rating', 'No description available').replace('\n', ' ').replace('\r', ' ').replace(';', '')
            url = note.get('url', 'No URL available')

            combined_text = f"{news} {description}"
            sentiment = analyze_tone(combined_text)

            date_iso = to_iso_utc(date)
            if not date_iso:
                print(f"Invalid note date: {date_str}")
                continue

            result = {
                'date': date_iso,
                'news': news,
                'description': description,
                'url': url,
                'score': sentiment,
                'type': 'analytical note'
            }

            if callback:
                callback(result)
            else:
                print(result)

        except Exception as e:
            print(f"Analytical note processing error: {e}")
            print(f"Problematic record: {note}")

if __name__ == "__main__":
    analyze_analytical_notes("TSLA", 360)