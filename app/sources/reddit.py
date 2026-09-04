import re
from datetime import datetime, timedelta
from pathlib import Path

import praw

from app.config import load_config, require
from app.normalization import to_iso_utc
from app.paths import ProjectPaths
from app.sentiment.tone_analysis import analyze_tone

_reddit_client = None


def get_reddit_client() -> praw.Reddit:
    """
    Lazily create a PRAW client from environment configuration.
    This prevents import-time failures when Reddit source is disabled.
    """
    global _reddit_client
    if _reddit_client is not None:
        return _reddit_client

    cfg = load_config()
    _reddit_client = praw.Reddit(
        client_id=require(cfg.reddit_client_id, "REDDIT_CLIENT_ID"),
        client_secret=require(cfg.reddit_client_secret, "REDDIT_CLIENT_SECRET"),
        user_agent=require(cfg.reddit_user_agent, "REDDIT_USER_AGENT"),
    )
    return _reddit_client

def clean_reddit_posts(posts):
    unwanted_keywords = [
        'promo', 'offer', 'discount', 'click here', 'subscribe', 'sale',
        'buy now', 'limited time', 'free shipping', 'order now', 'deal',
        'link', 'referral','code', 'promotion', 'save'
    ]
    unwanted_phrases = [
        'job opening', 'hiring', 'ad', 'sponsored', 'promotion', 
        'looking for', 'we are hiring', 'apply now', 'position available', 'receive up'
    ]
    
    cleaned_posts = []
    for post in posts:
        title = post['title'].lower()
        text = post.get('text', '').lower()
        combined_text = f"{title} {text}"
        
        # Skip very short posts
        if len(combined_text.split()) < 5:
            continue
        
        # Remove ads and spam
        if any(word in combined_text for word in unwanted_keywords):
            continue
            
        # Remove posts with too many links
        if len(re.findall(r'http[s]?://', combined_text)) > 2:
            continue
        
        # Remove bot posts
        subreddit = post.get('subreddit', '').lower()
        if any(bot in subreddit for bot in ['bot', 'auto', 'moderator']):
            continue
        
        # Remove posts with excessive special characters
        if len(re.findall(r'[!@#$%^&*()_+=\[\]{};:"|<>?]', combined_text)) > 15:
            continue
        
        # Remove posts with excessive emojis
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            "]+", flags=re.UNICODE)
        if len(emoji_pattern.findall(combined_text)) > 3:
            continue
        
        # Remove hiring/announcement phrases
        if any(phrase in combined_text for phrase in unwanted_phrases):
            continue
        
        # Remove repeated-character spam
        if re.search(r'(.)\1{4,}', combined_text):
            continue
        
        # Accept post
        cleaned_posts.append(post)
    
    return cleaned_posts

def fetch_reddit_posts(query, days):
    subreddit = get_reddit_client().subreddit("all")
    fromDate = datetime.now() - timedelta(days=min(180, days))
    posts = []
    
    params = {
        "limit": 100,
        "sort": "new",
        "time_filter": "all"
    }
    
    for submission in subreddit.search(query, **params):
        post_date = datetime.fromtimestamp(submission.created_utc)
        if post_date > fromDate:
            posts.append({
                "title": submission.title,
                "text": submission.selftext,
                "score": submission.score,
                "created": post_date,
                "url": submission.url,
                "subreddit": submission.subreddit.display_name,
                "num_comments": submission.num_comments
            })
        elif post_date <= fromDate:
            # Posts are time-ordered; stop when out of range.
            break
    
    return clean_reddit_posts(posts)

def analyze_tweets(query, days, callback=None, root: Path | None = None):
    posts = fetch_reddit_posts(query, days)
    results = []
    
    for post in posts:
        try:
            title = post['title'].replace('\n', ' ').replace('\r', ' ').replace(';', '')
            text = post['text'].replace('\n', ' ').replace('\r', ' ').replace(';', '')
            url = post['url']
            created = post.get('created')
            if not created:
                print(f"Missing created date for '{title}'.")
                continue
            created_iso = to_iso_utc(created)
            if not created_iso:
                print(f"Invalid created date: {created}")
                continue

            sentiment = analyze_tone(title)

            result = {
                'date': created_iso,
                'news': title,
                'description': text,
                'url': url,
                'score': sentiment,
                'type': 'twit'
            }
            
            results.append(result)

            if callback:
                callback(result)
            else:
                print(result)

        except Exception as e:
            print(f"Post analysis error: {e}")
    
    import json
    from datetime import datetime
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    paths = ProjectPaths(root=(root or Path.cwd()))
    paths.ensure_dirs()
    filename = paths.data_processed_dir / f"reddit_data_{current_date}.json"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Reddit data saved to: {filename}")
    
    return results

if __name__ == "__main__":
    analyze_tweets("Tesla", 90)