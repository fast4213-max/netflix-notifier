import json
import os
import requests
from playwright.sync_api import sync_playwright

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
CACHE_FILE = "cache.json"
MAX_NOTIFY = 20
TARGET_URL = "https://www.net-frx.com/p/netflix-new-arrivals.html?m=1"

def scrape_titles():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        # 「もっと見る」ボタンの直前まで取得
        # サムネイルとタイトルを持つ要素を探す（実際のセレクタは要確認）
        items = page.evaluate("""() => {
            const results = [];
            // サムネイル画像とタイトルのセレクタ（要調整）
            document.querySelectorAll('.post-body img, .card img').forEach(img => {
                const title = img.alt || img.title || '';
                const thumb = img.src || img.dataset.src || '';
                if (title && thumb && !thumb.includes('progress')) {
                    results.push({ title, thumb });
                }
            });
            return results;
        }""")
        
        browser.close()
        return items

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_discord(new_items):
    # 20件ずつに分割
    for i in range(0, len(new_items), MAX_NOTIFY):
        chunk = new_items[i:i+MAX_NOTIFY]
        embeds = []
        for item in chunk:
            embeds.append({
                "title": item["title"],
                "image": {"url": item["thumb"]},
                "color": 0xE50914  # Netflixレッド
            })
        payload = {
            "content": f"🎬 Netflix新着 {len(new_items)}件（{i+1}〜{i+len(chunk)}件目）",
            "embeds": embeds
        }
        r = requests.post(DISCORD_WEBHOOK, json=payload)
        print(f"Discord: {r.status_code}")

def main():
    print("スクレイピング開始...")
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
