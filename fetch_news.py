"""
Hawks News Fetcher
Uses Reddit JSON API for articles (no auth, no CORS issues)
and YouTube Atom + podcast RSS for media content.
Runs daily via GitHub Actions.
"""

import json
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote
from html.parser import HTMLParser

CUTOFF_DAYS = 14

# Reddit works perfectly from GitHub Actions — no auth, no CORS issues
REDDIT_HEADERS = {
    'User-Agent': 'HawksStatsApp/1.0 (family fan app; Hawthorn news aggregator)'
}

# Browser-style headers for podcast/RSS feeds that block bots
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
}

HAWK_KEYWORDS = [
    'hawthorn', 'hawks', 'sam mitchell', 'jack gunston', 'jai newcombe',
    'james sicily', 'mitch lewis', 'nick watson', 'blake hardwick',
]


# ── Helpers ─────────────────────────────────────────────────────────────────

def strip_html(text, limit=280):
    if not text: return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&[a-zA-Z#0-9]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit] + ('…' if len(text) > limit else '')

def mentions_hawthorn(text):
    t = text.lower()
    return any(kw in t for kw in HAWK_KEYWORDS)

def fmt_date(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ'), dt.strftime('%-d %b %Y')

def cutoff():
    return datetime.now(timezone.utc) - timedelta(days=CUTOFF_DAYS)


# ── Reddit sources ────────────────────────────────────────────────────────────

def fetch_reddit(subreddit, search_query=None, limit=30):
    """Fetch posts from a subreddit or subreddit search."""
    if search_query:
        url = f'https://www.reddit.com/r/{subreddit}/search.json?q={quote(search_query)}&sort=new&restrict_sr=1&limit={limit}'
    else:
        url = f'https://www.reddit.com/r/{subreddit}/new.json?limit={limit}'
    
    print(f"  [Reddit r/{subreddit}] {url[:80]}")
    try:
        req = Request(url, headers=REDDIT_HEADERS)
        with urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        posts = data.get('data', {}).get('children', [])
        cut = cutoff()
        items = []
        for post in posts:
            p = post.get('data', {})
            pub = datetime.fromtimestamp(p.get('created_utc', 0), tz=timezone.utc)
            if pub < cut: continue
            title = p.get('title', '').strip()
            link  = p.get('url', '').strip()
            if not title or not link: continue
            # Skip self-posts with no external link
            if link.startswith('https://www.reddit.com'): continue
            # Filter for Hawthorn if coming from broad subreddit
            if subreddit == 'AFL' and not mentions_hawthorn(title + ' ' + p.get('selftext','')):
                continue
            thumb = p.get('thumbnail', '')
            date_str, date_disp = fmt_date(pub)
            items.append({
                'type':        'article',
                'source':      f"r/{p.get('subreddit', subreddit)}",
                'title':       title,
                'url':         link,
                'description': strip_html(p.get('selftext', '') or p.get('url', '')),
                'date':        date_str,
                'dateDisplay': date_disp,
                'image':       thumb if thumb.startswith('http') else None,
                'audio':       None,
            })
        print(f"    ✓ {len(items)} items")
        return items
    except Exception as e:
        print(f"    ⚠ Failed: {e}")
        return []


# ── YouTube Atom feed ─────────────────────────────────────────────────────────

def fetch_youtube_channel(channel_id, source_name):
    """Fetch latest videos from a YouTube channel via Atom feed."""
    url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
    print(f"  [YouTube {source_name}]")
    try:
        req = Request(url, headers=REDDIT_HEADERS)
        with urlopen(req, timeout=15) as r:
            xml = r.read().decode('utf-8')
        cut = cutoff()
        items = []
        entries = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
        for entry in entries:
            title_m = re.search(r'<title>(.*?)</title>', entry)
            link_m  = re.search(r'<link rel="alternate" href="([^"]+)"', entry)
            date_m  = re.search(r'<published>(.*?)</published>', entry)
            thumb_m = re.search(r'<media:thumbnail url="([^"]+)"', entry)
            if not (title_m and link_m): continue
            title = strip_html(title_m.group(1))
            link  = link_m.group(1)
            thumb = thumb_m.group(1) if thumb_m else None
            if date_m:
                try:
                    pub = datetime.fromisoformat(date_m.group(1).replace('Z','+00:00'))
                    if pub < cut: continue
                    date_str, date_disp = fmt_date(pub)
                except Exception:
                    date_str = date_disp = 'Recent'
            else:
                date_str = date_disp = 'Recent'
            items.append({
                'type':        'video',
                'source':      source_name,
                'title':       title,
                'url':         link,
                'description': '',
                'date':        date_str,
                'dateDisplay': date_disp,
                'image':       thumb,
                'audio':       None,
            })
        print(f"    ✓ {len(items)} videos")
        return items
    except Exception as e:
        print(f"    ⚠ Failed: {e}")
        return []


# ── Podcast RSS feeds ─────────────────────────────────────────────────────────

def fetch_podcast(url, source_name, filter_hawthorn=False):
    """Fetch podcast episodes — tries browser headers to bypass blocks."""
    print(f"  [Podcast {source_name}]")
    try:
        req = Request(url, headers=BROWSER_HEADERS)
        with urlopen(req, timeout=20) as r:
            xml = r.read().decode('utf-8', errors='replace')
        cut = cutoff()
        items = []
        # Split into items
        episodes = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
        for ep in episodes:
            title_m = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', ep, re.DOTALL)
            enc_m   = re.search(r'<enclosure[^>]+url="([^"]+)"', ep)
            date_m  = re.search(r'<pubDate>(.*?)</pubDate>', ep)
            desc_m  = re.search(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', ep, re.DOTALL)
            if not (title_m and enc_m): continue
            title = strip_html(title_m.group(1).strip())
            audio = enc_m.group(1).strip()
            desc  = strip_html(desc_m.group(1) if desc_m else '')
            if filter_hawthorn and not mentions_hawthorn(title + ' ' + desc): continue
            date_str = date_disp = 'Recent'
            if date_m:
                try:
                    from email.utils import parsedate_to_datetime
                    pub = parsedate_to_datetime(date_m.group(1).strip())
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=timezone.utc)
                    if pub < cut: continue
                    date_str, date_disp = fmt_date(pub)
                except Exception:
                    pass
            items.append({
                'type':        'podcast',
                'source':      source_name,
                'title':       title,
                'url':         audio,
                'description': desc,
                'date':        date_str,
                'dateDisplay': date_disp,
                'image':       None,
                'audio':       audio,
            })
        print(f"    ✓ {len(items)} episodes")
        return items
    except Exception as e:
        print(f"    ⚠ Failed: {e}")
        return []


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print('📰 Hawks News Fetcher starting…\n')
    all_items = []
    seen_urls = set()

    def add(items):
        for item in items:
            key = item.get('audio') or item.get('url', '')
            if key and key not in seen_urls:
                seen_urls.add(key)
                all_items.append(item)

    # ── Articles via Reddit (proven to work from GitHub Actions) ──
    add(fetch_reddit('hawkiesafl'))                           # dedicated Hawks sub
    time.sleep(1)
    add(fetch_reddit('AFL', search_query='hawthorn'))         # AFL sub, Hawthorn filter
    time.sleep(1)

    # ── Official Hawthorn YouTube ──
    add(fetch_youtube_channel('UCweshjuhmLYGxHuH2xIPXpg', 'Hawthorn FC'))
    time.sleep(1)

    # ── Podcasts (browser headers — best effort) ──
    add(fetch_podcast(
        'https://feeds.acast.com/public/shows/hawk-talk-podcast-1',
        'Hawk Talk Podcast'
    ))
    time.sleep(1)
    add(fetch_podcast(
        'https://anchor.fm/s/b2d1916c/podcast/rss',
        'Talking Hawks'
    ))
    time.sleep(1)
    add(fetch_podcast(
        'https://www.omnycontent.com/d/playlist/8ae80818-a88e-475b-9776-ad05005c36ff/'
        '8c30cfe4-8785-4fb1-8b38-ad570072390d/'
        '487a8045-ed6a-43af-816d-ad5700723925/podcast.rss',
        'AFL Daily', filter_hawthorn=True
    ))

    # Sort newest first, cap at 60
    all_items.sort(key=lambda x: x.get('date') or '2000-01-01', reverse=True)
    all_items = all_items[:60]

    news = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'items':   all_items,
    }

    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(news, f, indent=2, ensure_ascii=False)

    art = sum(1 for i in all_items if i['type'] == 'article')
    pod = sum(1 for i in all_items if i['type'] == 'podcast')
    vid = sum(1 for i in all_items if i['type'] == 'video')
    print(f'\n✅ {len(all_items)} items → news.json')
    print(f'   Articles: {art}  Podcasts: {pod}  Videos: {vid}')


if __name__ == '__main__':
    main()
