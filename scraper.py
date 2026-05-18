import json
import os
import requests
from datetime import datetime, timedelta

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
CACHE_FILE = "cache.json"
MAX_NOTIFY = 20
FEED_URL = "https://www.net-frx.com/feeds/posts/default?alt=json&max-results=150"
CHECK_DAYS = 7  # 直近何日分を監視するか

def scrape_titles():
    response = requests.get(FEED_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    entries = data.get("feed", {}).get("entry", [])
    now = datetime.utcnow()
    cutoff = now - timedelta(days=CHECK_DAYS)
    
    items = []
    for entry in entries:
        # 公開日チェック
        published_str = entry.get("published", {}).get("$t", "")
        try:
            published = datetime.strptime(published_str[:19], "%Y-%m-%dT%H:%M:%S")
        except:
            continue
        
        if published < cutoff:
            continue
        
        # タイトル
        title = entry.get("title", {}).get("$t", "")
        
        # サムネイル（content内の最初のsrc=）
        content = entry.get("content", {}).get("$t", "")
        thumb = ""
        if 'src="' in content:
            thumb = content.split('src="')[1].split('"')[0]
        
        # 記事URL
        link = ""
        for l in entry.get("link", []):
            if l.get("rel") == "alternate":
                link = l.get("href", "")
                break
        
        if title and thumb:
            items.append({
                "title": title,
                "thumb": thumb,
                "link": link,
                "published": published_str
            })
    
    return items

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_discord(new_items):
    for i in range(0, len(new_items), MAX_NOTIFY):
        chunk = new_items[i:i+MAX_NOTIFY]
        embeds = []
        for item in chunk:
            embeds.append({
                "title": item["title"],
                "url": item["link"],
                "image": {"url": item["thumb"]},
                "color": 0xE50914
            })
        payload = {
            "content": f"🎬 Netflix新着 {len(new_items)}件（{i+1}〜{i+len(chunk)}件目）",
            "embeds": embeds
        }
        r = requests.post(DISCORD_WEBHOOK, json=payload)
        print(f"Discord: {r.status_code}")

def main():
    print("フェッチ開始...")
    items = scrape_titles()
    print(f"取得件数: {len(items)}")

    cache = load_cache()
    new_items = [item for item in items if item["title"] not in cache]

    print(f"新着件数: {len(new_items)}")

    if new_items:
        send_discord(new_items)
        for item in items:
            cache[item["title"]] = item["thumb"]
        save_cache(cache)
        print("キャッシュ更新完了")
    else:
        print("新着なし")

if __name__ == "__main__":
    main()
