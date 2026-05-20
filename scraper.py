import json
import os
import requests
from datetime import datetime, timedelta

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
CACHE_FILE = "cache.json"
MAX_NOTIFY = 10
FEED_URL = "https://www.net-frx.com/feeds/posts/default?alt=json&max-results=150"
CHECK_DAYS = 7  # 直近何日分を監視（およびキャッシュ保持）するか

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

def load_and_clean_cache():
    """キャッシュを読み込み、同時に古いデータを自動掃除する"""
    if not os.path.exists(CACHE_FILE):
        return {}
    
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except:
        return {}

    # 古いキャッシュデータを削除する基準時間
    now = datetime.utcnow()
    cutoff = now - timedelta(days=CHECK_DAYS)
    
    cleaned_cache = {}
    for title, info in cache.items():
        # 過去の古いキャッシュ構造（URL文字列だけだった場合）への互換性ケア
        if isinstance(info, str):
            # 日付情報がないため一旦残し、新しい形式として扱えるようダミー日付を入れておく
            cleaned_cache[title] = {
                "thumb": info,
                "published": now.isoformat()
            }
            continue
            
        published_str = info.get("published", "")
        try:
            published = datetime.strptime(published_str[:19], "%Y-%m-%dT%H:%M:%S")
            # CHECK_DAYS (7日) 以内のものだけを新しいキャッシュに残す
            if published >= cutoff:
                cleaned_cache[title] = info
        except:
            # 日付形式のエラーなどの場合は念のため残す
            cleaned_cache[title] = info
            
    return cleaned_cache

def save_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_discord(items_to_send):
    embeds = []
    for item in items_to_send:
        embeds.append({
            "title": item["title"],
            "url": item["link"],
            "image": {"url": item["thumb"]},
            "color": 0xE50914
        })
    
    payload = {
        "content": f"🎬 Netflix新着 {len(items_to_send)}件",
        "embeds": embeds
    }
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    print(f"Discord: {r.status_code}")

def main():
    print("フェッチ開始...")
    items = scrape_titles()
    print(f"取得件数: {len(items)}")

    # キャッシュ読み込み＆古いキャッシュの削除
    cache = load_and_clean_cache()
    
    # 新着アイテムの判定
    new_items = [item for item in items if item["title"] not in cache]
    print(f"新着判定件数: {len(new_items)}")

    if new_items:
        # 今回送信する分だけを抽出（先頭から最大MAX_NOTIFY件）
        items_to_send = new_items[:MAX_NOTIFY]
        
        send_discord(items_to_send)
        
        # 送信したアイテムをキャッシュに追加
        for item in items_to_send:
            cache[item["title"]] = {
                "thumb": item["thumb"],
                "published": item["published"]
            }
        
        # キャッシュの保存（古いデータの削除結果もここでファイルに反映される）
        save_cache(cache)
        print(f"{len(items_to_send)}件送信し、キャッシュを更新しました。")
        
        if len(new_items) > MAX_NOTIFY:
            print(f"※ 残りの {len(new_items) - MAX_NOTIFY} 件は次回の実行時に送信されます。")
    else:
        # 新着がなくても、古いキャッシュが削除された可能性があるのでキャッシュを保存し直す
        save_cache(cache)
        print("新着なし（キャッシュ維持/掃除のみ実行）")

if __name__ == "__main__":
    main()
