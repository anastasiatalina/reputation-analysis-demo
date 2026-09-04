import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from app.config import load_config
from app.normalization import to_iso_utc
from app.paths import ProjectPaths
from app.sentiment.tone_analysis import analyze_tone

def _get_newsapi_keys():
    cfg = load_config()
    if cfg.newsapi_keys:
        return cfg.newsapi_keys
    raise RuntimeError("Missing configuration: NEWSAPI_KEYS")

def get_from(days):
    from_days = datetime.now() - timedelta(days)
    return from_days.strftime('%Y-%m-%d')

def fetch_news(query, days, retries=6):
    api_keys = _get_newsapi_keys()
    all_articles = []
    end_date = datetime.now()
    current_key_index = 0
    
    for day in range(min(30, days)):
        date = end_date - timedelta(days=day)
        from_date = date.strftime('%Y-%m-%d')
        to_date = (date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        for _ in range(retries):
            try:
                url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_keys[current_key_index]}&from={from_date}&to={to_date}&pageSize=100&language=en"
                print(f"Fetching URL: {url}")
                
                response = requests.get(url, timeout=1)
                
                if response.status_code == 429:
                    current_key_index = (current_key_index + 1) % len(api_keys)
                    continue
                    
                response.raise_for_status()
                articles = response.json().get("articles", [])
                all_articles.extend(articles)
                break
                
            except requests.exceptions.RequestException as e:
                print(f"Request error: {e}")
                time.sleep(2)
                continue
    
    return all_articles

def analyze_news(query, days, callback=None, root: Path | None = None):
    news_data = fetch_news(query, days)
    results = []
    
    if not news_data:
        print("No news found.")
        return
    
    for article in news_data:
        try:
            title = article.get('title', 'No title available')
            description = article.get('description', '')
            if description:
                description = description.replace('\n', ' ').replace('\r', ' ').replace(';', '')
            else:
                description = ''
                
            url = article.get('url', 'No URL available')
            published_at = article.get('publishedAt')
            
            if not published_at:
                print(f"Missing published date for '{title}'.")
                continue

            published_iso = to_iso_utc(published_at)
            if not published_iso:
                print(f"Invalid published date: {published_at}")
                continue
            
            sentiment = analyze_tone(description if description else title)

            result = {
                'date': published_iso,
                'news': title,
                'description': description,
                'url': url,
                'score': sentiment,
                'type': 'news'
            }
            
            results.append(result)
            
            if callback:
                callback(result)
            else:
                print(result)
        
        except Exception as e:
            print(f"News processing error: {e}")
            print(f"Problematic article: {article}")
    
    import pandas as pd
    from datetime import datetime
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    df = pd.DataFrame(results)
    
    df = df.drop_duplicates()
    
    paths = ProjectPaths(root=(root or Path.cwd()))
    paths.ensure_dirs()
    filename = paths.data_processed_dir / f"news_data_{current_date}.csv"
    df.to_csv(filename, index=False, encoding="utf-8")
    print(f"Data saved to: {filename}")
    print(f"Total rows after cleanup: {len(df)}")

if __name__ == "__main__":
    analyze_news("Tesla", 30)