"""
Hawks News Fetcher
Pulls news articles, podcasts and videos mentioning Hawthorn Hawks
from RSS/Atom feeds and saves to news.json.
Runs daily via GitHub Actions at 7am AEST.
"""

import feedparser
import requests
import json
import re
import time
from datetime import datetime, timezone, timedelta

HEADERS = {'User-Agent': 'HawksStatsApp/1.0 (news aggregator; contact via GitHub)'}

HAWK_KEYWORDS = [
    'hawthorn', 'hawks', 'sam mitchell', 'jack gunston', 'jai newcombe',
    'james sicily', 'mitch lewis', 'nick watson', 'blake hardwick',
    'conor nash', 'dylan moore', 'lloyd meek', 'ned reeves',
]

CUTOFF_DAYS = 7

FEEDS = [
    # ── News Articles ──────────────────────────────────────────────────────
    {'url': 'https://www.afl.com.au/rss',
     'source': 'AFL.com.au',      'type': 'article', 'filter': True},
    {'url': 'https://www.zerohanger.com/feed',
     'source': 'Zero Hanger',     'type': 'article', 'filter': True},
    {'url': 'https://www.theage.com.au/rss/sport/afl.xml',
     'source': 'The Age',         'type': 'article', 'filter': True},
    {'url': 'https://www.theroar.com.au/feed',
     'source': 'The Roar',        'type': 'article', 'filter': True},

    # ── Official Hawthorn FC YouTube ──────────────────────────────────────
    {'url': 'https://www.youtube.com/feeds/videos.xml?channel_id=UCweshjuhmLYGxHuH2xIPXpg',
     'source': 'Hawthorn FC',     'type': 'video',   'filter': False},

    # ── Hawthorn-specific podcasts (no keyword filter needed) ─────────────
    {'url': 'https://feeds.acast.com/public/shows/hawk-talk-podcast-1',
     'source': 'Hawk Talk',       'type': 'podcast', 'filter': False},
    {'url': 'https://anchor.fm/s/b2d1916c/podcast/rss',
     'source': 'Talking Hawks',   'type': 'podcast', 'filter': False},

    # ── AFL-wide podcasts (filter for Hawthorn mentions) ──────────────────
    {'url': 'https://www.omnycontent.com/d/playlist/8ae80818-a88e-475b-9776-ad05005c36ff/8c30cfe4-8785-4fb1-8b38-ad570072390d/487a8045-ed6a-43af-816d-ad5700723925/podcast.rss',
     'source': 'AFL Daily',       'type': 'podcast', 'filter': True},
    {'url': 'https://feeds.captivate.fm/zero-hanger-afl-podcast/',
     'source': 'ZH Podcast',      'type': 'podcast', 'filter': True},
    {'url': 'https://omny.fm/shows/real-footy/playlists/podcast.rss',
     'source': 'Real Footy',      'type': 'podcast', 'filter': True},
]


# ── Helpers ─────────────────────────────────────────────────────────────────

def strip_html(text, limit=280):
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&amp;',  '&', text)
    text = re.sub(r'&lt;',   '<', text)
    text = re.sub(r'&gt;',   '>', text)
    text = re.sub(r'&[a-zA-Z#0-9]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit] + ('…' if len(text) > limit else '')


def mentions_hawthorn(entry):
    text = ' '.join([
        str(getattr(entry, 'title',       '') or ''),
        str(getattr(entry, 'summary',     '') or ''),
        str(getattr(entry, 'description', '') or ''),
        str(getattr(entry, 'tags',        '') or ''),
    ]).lower()
    return any(kw in text for kw in HAWK_KEYWORDS)


def get_entry_date(entry):
    for attr in ('published_parsed', 'updated_parsed'):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def get_audio_url(entry):
    for enc in getattr(entry, 'enclosures', []):
        if enc.get('type', '').startswith('audio'):
            return enc.get('href') or enc.get('url')
    return None


def get_image_url(entry):
    # media:thumbnail (YouTube, most podcast feeds)
    for t in getattr(entry, 'media_thumbnail', []):
        if t.get('url'):
            return t['url']
    # media:content image
    for mc in getattr(entry, 'media_content', []):
        if (mc.get('medium') == 'image' or
                mc.get('type', '').startswith('image')):
            return mc.get('url')
    # image enclosure
    for enc in getattr(entry, 'enclosures', []):
        if enc.get('type', '').startswith('image'):
            return enc.get('href') or enc.get('url')
    return None


# ── Feed fetcher ─────────────────────────────────────────────────────────────

def fetch_feed(cfg):
    print(f"  [{cfg['source']}] {cfg['url'][:70]}")
    try:
        resp = requests.get(cfg['url'], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"    ⚠ Fetch failed: {e}")
        return []

    if not parsed.entries:
        print(f"    ⚠ No entries found")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=CUTOFF_DAYS)
    items = []

    for entry in parsed.entries:
        pub = get_entry_date(entry)
        if pub and pub < cutoff:
            continue
        if cfg['filter'] and not mentions_hawthorn(entry):
            continue

        title = str(getattr(entry, 'title', '') or '').strip()
        url   = str(getattr(entry, 'link',  '') or '').strip()
        desc  = strip_html(
            getattr(entry, 'summary', '') or
            getattr(entry, 'description', '') or ''
        )
        audio = get_audio_url(entry)
        image = get_image_url(entry)
        date_str     = pub.strftime('%Y-%m-%dT%H:%M:%SZ') if pub else None
        date_display = pub.strftime('%-d %b %Y')          if pub else 'Recent'

        if not title or not url:
            continue

        items.append({
            'type':        cfg['type'],
            'source':      cfg['source'],
            'title':       title,
            'url':         url,
            'description': desc,
            'date':        date_str,
            'dateDisplay': date_display,
            'image':       image,
            'audio':       audio,
        })

    print(f"    ✓ {len(items)} Hawthorn items")
    return items


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print('📰 Hawks News Fetcher starting…\n')

    all_items = []
    seen_urls = set()

    for cfg in FEEDS:
        for item in fetch_feed(cfg):
            if item['url'] not in seen_urls:
                seen_urls.add(item['url'])
                all_items.append(item)
        time.sleep(1)  # be polite to servers

    # Sort newest-first
    all_items.sort(
        key=lambda x: x['date'] or '2000-01-01T00:00:00Z',
        reverse=True,
    )
    all_items = all_items[:60]  # cap at 60 items

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
