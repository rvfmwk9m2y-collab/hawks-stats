"""
Hawks 2026 Stats Scraper
Fetches data from AFL Tables every week and saves to data.json
Run automatically via GitHub Actions every Monday, or manually anytime.
"""

import json
import re
import time
from datetime import date, datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser

HEADERS = {"User-Agent": "Mozilla/5.0 (Hawks Stats App; contact via GitHub)"}
SQUIGGLE_HEADERS = {"User-Agent": "HawksStatsApp/1.0 (family fan app; contact via GitHub)"}
SQUIGGLE_URL = "https://api.squiggle.com.au/"

# ── ONLY FALLBACK VALUES — everything is fetched automatically ────────────
FALLBACK_RECORD    = "7W–3L–1D"
FALLBACK_POSITION  = "3rd"
FALLBACK_NEXT_GAME = {
    "round": 13, "opponent": "Western Bulldogs",
    "venue": "MCG", "home": True,
    "kickoff": "2026-06-05T09:40:00Z"
}
# ─────────────────────────────────────────────────────────────────────────

# ── Hawthorn FC official YouTube channel ──
HAWKS_CHANNEL_ID   = "UCweshjuhmLYGxHuH2xIPXpg"
HAWKS_YT_RSS       = f"https://www.youtube.com/feeds/videos.xml?channel_id={HAWKS_CHANNEL_ID}"

# ── Fallback match pages (used only if AFL Tables auto-discovery fails) ──
# No need to update this manually — discover_match_pages() handles it automatically.
FALLBACK_MATCH_PAGES = [
    ("OR", "https://afltables.com/afl/stats/games/2026/102120260307.html"),
    ("R1", "https://afltables.com/afl/stats/games/2026/051020260313.html"),
    ("R2", "https://afltables.com/afl/stats/games/2026/101620260319.html"),
    ("R4", "https://afltables.com/afl/stats/games/2026/091020260406.html"),
    ("R5", "https://afltables.com/afl/stats/games/2026/071020260411.html"),
    ("R6", "https://afltables.com/afl/stats/games/2026/101320260418.html"),
    ("R7", "https://afltables.com/afl/stats/games/2026/102020260425.html"),
    ("R8", "https://afltables.com/afl/stats/games/2026/041020260430.html"),
    ("R9", "https://afltables.com/afl/stats/games/2026/081020260507.html"),
    ("R10","https://afltables.com/afl/stats/games/2026/101120260516.html"),
]

def discover_match_pages():
    """
    Auto-discover Hawthorn's 2026 match pages from AFL Tables all-games page.
    Returns list of (round_label, url) tuples, or empty list on failure.
    """
    url = "https://afltables.com/afl/teams/hawthorn/allgames.html"
    print(f"  Fetching Hawthorn all-games page…")
    html = fetch(url)
    if not html:
        print("  ⚠ Could not reach AFL Tables all-games page — using fallback")
        return []

    # Find the 2026 section (year anchor) and stop before 2025
    idx = html.find('>2026<')
    if idx == -1:
        idx = html.find('name="2026"')
    if idx == -1:
        print("  ⚠ 2026 section not found — using fallback")
        return []

    section = html[idx:]
    end = section.find('>2025<')
    if end > 0:
        section = section[:end]

    # Extract rows containing 2026 game links
    results = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', section, re.DOTALL)
    for row in rows:
        link_m = re.search(r'href="(/afl/stats/games/2026/[^"]+\.html)"', row)
        if not link_m:
            continue
        # Round label from first <td>
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if cells:
            raw = re.sub(r'<[^>]+>', '', cells[0]).strip()
            if raw.upper() in ('OR', '0'):
                label = 'OR'
            elif raw.isdigit():
                label = f'R{raw}'
            else:
                label = raw or f'R{len(results)+1}'
        else:
            label = f'R{len(results)+1}'
        results.append((label, f"https://afltables.com{link_m.group(1)}"))

    if results:
        print(f"  ✓ Discovered {len(results)} Hawthorn 2026 match pages")
    else:
        print("  ⚠ No match pages found — using fallback")
    return results

# Player profile pages for 2025 comparison data
PLAYER_PROFILES = {
    "Karl Amon":           "https://afltables.com/afl/stats/players/K/Karl_Amon.html",
    "Tom Barrass":         "https://afltables.com/afl/stats/players/T/Tom_Barrass.html",
    "Josh Battle":         "https://afltables.com/afl/stats/players/J/Josh_Battle.html",
    "Sam Butler":          "https://afltables.com/afl/stats/players/S/Sam_Butler1.html",
    "Mabior Chol":         "https://afltables.com/afl/stats/players/M/Mabior_Chol.html",
    "Massimo D'Ambrosio":  "https://afltables.com/afl/stats/players/M/Massimo_DAmbrosio.html",
    "Jack Dalton":         "https://afltables.com/afl/stats/players/J/Jack_Dalton1.html",
    "Calsher Dear":        "https://afltables.com/afl/stats/players/C/Calsher_Dear.html",
    "Jack Ginnivan":       "https://afltables.com/afl/stats/players/J/Jack_Ginnivan.html",
    "Jack Gunston":        "https://afltables.com/afl/stats/players/J/Jack_Gunston.html",
    "Blake Hardwick":      "https://afltables.com/afl/stats/players/B/Blake_Hardwick.html",
    "Henry Hustwaite":     "https://afltables.com/afl/stats/players/H/Henry_Hustwaite.html",
    "Jarman Impey":        "https://afltables.com/afl/stats/players/J/Jarman_Impey.html",
    "Mitch Lewis":         "https://afltables.com/afl/stats/players/M/Mitch_Lewis.html",
    "Connor Macdonald":    "https://afltables.com/afl/stats/players/C/Connor_Macdonald.html",
    "Cam Mackenzie":       "https://afltables.com/afl/stats/players/C/Cam_Mackenzie.html",
    "Finn Maginness":      "https://afltables.com/afl/stats/players/F/Finn_Maginness.html",
    "Lloyd Meek":          "https://afltables.com/afl/stats/players/L/Lloyd_Meek.html",
    "Dylan Moore":         "https://afltables.com/afl/stats/players/D/Dylan_Moore.html",
    "Harry Morrison":      "https://afltables.com/afl/stats/players/H/Harry_Morrison.html",
    "Conor Nash":          "https://afltables.com/afl/stats/players/C/Conor_Nash.html",
    "Jai Newcombe":        "https://afltables.com/afl/stats/players/J/Jai_Newcombe.html",
    "Ned Reeves":          "https://afltables.com/afl/stats/players/N/Ned_Reeves.html",
    "Jack Scrimshaw":      "https://afltables.com/afl/stats/players/J/Jack_Scrimshaw.html",
    "James Sicily":        "https://afltables.com/afl/stats/players/J/James_Sicily.html",
    "Josh Ward":           "https://afltables.com/afl/stats/players/J/Josh_Ward.html",
    "Nick Watson":         "https://afltables.com/afl/stats/players/N/Nick_Watson.html",
    "Josh Weddle":         "https://afltables.com/afl/stats/players/J/Josh_Weddle.html",
    "Will Day":            "https://afltables.com/afl/stats/players/W/Will_Day.html",
    "Flynn Perez":         "https://afltables.com/afl/stats/players/F/Flynn_Perez.html",
    "Bodie Ryan":          "https://afltables.com/afl/stats/players/B/Bodie_Ryan.html",
    "Will McCabe":         "https://afltables.com/afl/stats/players/W/Will_McCabe.html",
    "Cameron Nairn":       "https://afltables.com/afl/stats/players/C/Cameron_Nairn.html",
}

# Static player info — update if players change
PLAYER_INFO = {
    "Karl Amon":           {"jn":10,"pos":"DF","age":30,"ht":181,"draftLbl":"68",   "draft":68,   "pu":"https://www.hawthornfc.com.au/players/801/karl-amon"},
    "Tom Barrass":         {"jn":37,"pos":"DF","age":30,"ht":196,"draftLbl":"43",   "draft":43,   "pu":"https://www.hawthornfc.com.au/players/790/tom-barrass"},
    "Josh Battle":         {"jn":24,"pos":"DF","age":27,"ht":193,"draftLbl":"39",   "draft":39,   "pu":"https://www.hawthornfc.com.au/players/1412/josh-battle"},
    "Sam Butler":          {"jn":30,"pos":"MF","age":23,"ht":184,"draftLbl":"23",   "draft":23,   "pu":"https://www.hawthornfc.com.au/teams/afl"},
    "Mabior Chol":         {"jn":18,"pos":"FW","age":29,"ht":200,"draftLbl":"30",   "draft":30,   "pu":"https://www.hawthornfc.com.au/players/1125/mabior-chol"},
    "Massimo D'Ambrosio":  {"jn":16,"pos":"MF","age":22,"ht":178,"draftLbl":"3",    "draft":3,    "pu":"https://www.hawthornfc.com.au/players/4349/massimo-d-ambrosio"},
    "Jack Dalton":         {"jn":34,"pos":"MF","age":19,"ht":177,"draftLbl":"34",   "draft":34,   "pu":"https://www.hawthornfc.com.au/players/12018/jack-dalton"},
    "Calsher Dear":        {"jn":13,"pos":"FW","age":20,"ht":195,"draftLbl":"56",   "draft":56,   "pu":"https://www.hawthornfc.com.au/players/9423/calsher-dear"},
    "Jack Ginnivan":       {"jn":33,"pos":"FW","age":23,"ht":183,"draftLbl":"13",   "draft":13,   "pu":"https://www.hawthornfc.com.au/players/2237/jack-ginnivan"},
    "Jack Gunston":        {"jn":19,"pos":"FW","age":34,"ht":193,"draftLbl":"29",   "draft":29,   "pu":"https://www.hawthornfc.com.au/players/500/jack-gunston"},
    "Blake Hardwick":      {"jn":15,"pos":"DF","age":29,"ht":181,"draftLbl":"44",   "draft":44,   "pu":"https://www.hawthornfc.com.au/players/924/blake-hardwick"},
    "Henry Hustwaite":     {"jn":44,"pos":"MF","age":21,"ht":195,"draftLbl":"37",   "draft":37,   "pu":"https://www.hawthornfc.com.au/players/5410/henry-hustwaite"},
    "Jarman Impey":        {"jn":4, "pos":"DF","age":30,"ht":178,"draftLbl":"21",   "draft":21,   "pu":"https://www.hawthornfc.com.au/players/702/jarman-impey"},
    "Mitch Lewis":         {"jn":2, "pos":"FW","age":27,"ht":198,"draftLbl":"76",   "draft":76,   "pu":"https://www.hawthornfc.com.au/players/1333/mitch-lewis"},
    "Connor Macdonald":    {"jn":9, "pos":"FW","age":23,"ht":184,"draftLbl":"26",   "draft":26,   "pu":"https://www.hawthornfc.com.au/players/2723/connor-macdonald"},
    "Cam Mackenzie":       {"jn":28,"pos":"MF","age":22,"ht":188,"draftLbl":"7",    "draft":7,    "pu":"https://www.hawthornfc.com.au/players/5630/cam-mackenzie"},
    "Finn Maginness":      {"jn":20,"pos":"FW","age":25,"ht":187,"draftLbl":"29",   "draft":29,   "pu":"https://www.hawthornfc.com.au/players/2812/finn-maginness"},
    "Lloyd Meek":          {"jn":17,"pos":"RU","age":28,"ht":203,"draftLbl":"69",   "draft":69,   "pu":"https://www.hawthornfc.com.au/players/1560/lloyd-meek"},
    "Dylan Moore":         {"jn":8, "pos":"FW","age":26,"ht":176,"draftLbl":"67",   "draft":67,   "pu":"https://www.hawthornfc.com.au/players/1595/dylan-moore"},
    "Harry Morrison":      {"jn":1, "pos":"MF","age":27,"ht":180,"draftLbl":"74",   "draft":74,   "pu":"https://www.hawthornfc.com.au/players/1341/harry-morrison"},
    "Conor Nash":          {"jn":11,"pos":"MF","age":27,"ht":197,"draftLbl":"Cat B","draft":9999, "pu":"https://www.hawthornfc.com.au/players/1302/conor-nash"},
    "Jai Newcombe":        {"jn":3, "pos":"MF","age":24,"ht":186,"draftLbl":"2",    "draft":2,    "pu":"https://www.hawthornfc.com.au/players/4711/jai-newcombe"},
    "Ned Reeves":          {"jn":7, "pos":"RU","age":27,"ht":208,"draftLbl":"SSP",  "draft":9998, "pu":"https://www.hawthornfc.com.au/players/1822/ned-reeves"},
    "Jack Scrimshaw":      {"jn":14,"pos":"DF","age":27,"ht":193,"draftLbl":"7",    "draft":7,    "pu":"https://www.hawthornfc.com.au/players/1336/jack-scrimshaw"},
    "James Sicily":        {"jn":6, "pos":"DF","age":31,"ht":186,"draftLbl":"56",   "draft":56,   "pu":"https://www.hawthornfc.com.au/players/514/james-sicily"},
    "Josh Ward":           {"jn":25,"pos":"MF","age":22,"ht":181,"draftLbl":"7",    "draft":7,    "pu":"https://www.hawthornfc.com.au/players/5252/josh-ward"},
    "Nick Watson":         {"jn":5, "pos":"FW","age":21,"ht":170,"draftLbl":"5",    "draft":5,    "pu":"https://www.hawthornfc.com.au/players/5592/nick-watson"},
    "Josh Weddle":         {"jn":23,"pos":"DF","age":22,"ht":191,"draftLbl":"18",   "draft":18,   "pu":"https://www.hawthornfc.com.au/players/6669/josh-weddle"},
    "Will Day":            {"jn":12,"pos":"MF","age":24,"ht":191,"draftLbl":"13",   "draft":13,   "pu":"https://www.hawthornfc.com.au/players/3726/will-day"},
    "Flynn Perez":         {"jn":39,"pos":"DF","age":24,"ht":187,"draftLbl":"SSP",  "draft":9997, "pu":"https://www.hawthornfc.com.au/players/2209/flynn-perez"},
    "Bodie Ryan":          {"jn":26,"pos":"DF","age":21,"ht":187,"draftLbl":"46",   "draft":46,   "pu":"https://www.hawthornfc.com.au/players/9721/bodie-ryan"},
    "Will McCabe":         {"jn":27,"pos":"DF","age":20,"ht":197,"draftLbl":"19",   "draft":19,   "pu":"https://www.hawthornfc.com.au/players/9672/will-mccabe"},
    "Cameron Nairn":       {"jn":22,"pos":"MF","age":18,"ht":185,"draftLbl":"20",   "draft":20,   "pu":"https://www.hawthornfc.com.au/players/10897/cameron-nairn"},
}


def fetch(url):
    """Fetch HTML from a URL with retries."""
    for attempt in range(3):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except URLError as e:
            print(f"  Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2 ** attempt)
    return ""


def parse_match_stats(html, team="Hawthorn"):
    """
    Parse an AFL Tables match page and return {player_name: {gl, tk, di, ki, gp:1}}
    for all players from the specified team.
    """
    results = {}
    # Find the Hawthorn stats table
    # Each team section starts with "Hawthorn Match Statistics"
    marker = f"{team} Match Statistics"
    idx = html.find(marker)
    if idx == -1:
        return results

    # Extract the table after the marker
    table_start = html.find("<table", idx)
    table_end = html.find("</table>", table_start) + 8
    if table_start == -1:
        return results

    table_html = html[table_start:table_end]

    # Parse rows
    rows = re.findall(r"<tr>(.*?)</tr>", table_html, re.DOTALL)
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if len(cells) < 10:
            continue
        # Check if first cell is a jumper number
        if not cells[0].isdigit():
            continue
        # Second cell should have player name in an anchor
        name_match = re.search(r">([A-Z][a-z]+,\s*[A-Z][a-z]+)<", row)
        if not name_match:
            continue
        raw_name = name_match.group(1)
        # Convert "Last, First" to "First Last"
        parts = raw_name.split(",")
        if len(parts) == 2:
            name = f"{parts[1].strip()} {parts[0].strip()}"
        else:
            name = raw_name

        def safe_int(v):
            try:
                return int(v)
            except (ValueError, IndexError):
                return 0

        # AFL Tables match page columns (0-indexed after jumper# and name):
        # 0=KI 1=MK 2=HB 3=DI 4=GL 5=BH 6=HO 7=TK 8=RB 9=IF 10=CL 11=CG
        # 12=FF 13=FA 14=BR 15=CP 16=UP 17=CM 18=MI 19=1% 20=BO 21=GA 22=%P
        try:
            ki = safe_int(cells[2])
            di = safe_int(cells[5])
            gl = safe_int(cells[6])
            ho = safe_int(cells[8])
            tk = safe_int(cells[9])
            cl = safe_int(cells[12])
            ff = safe_int(cells[14])
            fa = safe_int(cells[15])
            cm = safe_int(cells[19])
            op = safe_int(cells[21])   # one percenters
            ga = safe_int(cells[23])   # goal assists
        except IndexError:
            continue

        results[name] = {"gl": gl, "tk": tk, "di": di, "ki": ki,
                         "ho": ho, "cl": cl, "ff": ff, "fa": fa,
                         "cm": cm, "op": op, "ga": ga, "gp": 1}

    return results


def parse_gby_totals(html):
    """
    Parse AFL Tables GBG page (static HTML) for disposals and kicks season totals.
    Returns {player_name: {di, ki, gp}}
    """
    results = {}
    # The GBG page shows tables for DI and KI with player rows + Tot column
    # Each table row: | Player | R1 | R2 | ... | Tot |
    # Find rows with player links and a Tot value
    pattern = re.compile(
        r'<a href="[^"]+players/[^"]+">([^<]+)</a>'  # player name
        r'.*?</td>'  # rest of first cell
        r'((?:\s*<td[^>]*>[^<]*</td>){10,})',  # 10+ data cells
        re.DOTALL
    )
    # Simpler: just find rows where last cell (Tot) is a number > 0
    rows = re.findall(
        r'href="[^"]+players/[A-Z]/([^"]+)\.html">([^<]+)</a>(.*?)</tr>',
        html, re.DOTALL
    )
    for _, player, cells_html in rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', cells_html, re.DOTALL)
        values = []
        for td in tds:
            clean = re.sub(r'<[^>]+>', '', td).strip()
            values.append(clean)
        if not values:
            continue
        # Last value should be the total
        try:
            total = int(values[-1])
        except (ValueError, IndexError):
            continue
        # Count non-empty cells (excluding total) for games played
        game_vals = [v for v in values[:-1] if v and v != '-']
        gp = len(game_vals)
        results[player] = {"total": total, "gp": gp}
    return results


def parse_profile_2025(html):
    """
    Parse a player profile page and return 2025 season stats.
    Returns {gp25, di25, gl25, tk25} or None
    """
    # Find 2025 row in the career table
    idx = html.find(">2025<")
    if idx == -1:
        return None

    # Find the table row containing this
    row_start = html.rfind("<tr>", 0, idx)
    row_end = html.find("</tr>", idx) + 5
    if row_start == -1:
        return None

    row = html[row_start:row_end]
    cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
    cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]

    def si(v):
        try:
            return int(v)
        except (ValueError, IndexError):
            return 0

    # Columns: Year Team # GM W-D-L KI MK HB DI GL BH HO TK ...
    if len(cells) < 13:
        return None

    try:
        gm_text = re.sub(r"<[^>]+>", "", cells[3]).strip()
        gm = int(re.sub(r"[^\d]", "", gm_text)) if gm_text else 0
        ki = si(cells[5])
        di = si(cells[8])
        gl = si(cells[9])
        tk = si(cells[12])
        return {"gp25": gm, "di25": di, "gl25": gl, "tk25": tk}
    except (IndexError, ValueError):
        return None


def scrape_match_pages():
    """
    Auto-discover and scrape all Hawthorn 2026 match pages.
    Returns (totals, rounds) — season totals and per-round breakdowns.
    """
    match_pages = discover_match_pages() or FALLBACK_MATCH_PAGES
    totals = {}
    rounds = {}

    for round_label, url in match_pages:
        print(f"  Fetching {round_label}: {url}")
        html = fetch(url)
        if not html:
            print(f"  ⚠ Failed to fetch {round_label}")
            continue

        stats = parse_match_stats(html)
        print(f"    Found {len(stats)} Hawthorn players")

        for name, s in stats.items():
            if name not in totals:
                totals[name] = {"gl":0,"tk":0,"di":0,"ki":0,
                                "ho":0,"cl":0,"ff":0,"fa":0,
                                "cm":0,"op":0,"ga":0,"gp":0}
                rounds[name] = []
            totals[name]["gl"] += s["gl"]
            totals[name]["tk"] += s["tk"]
            totals[name]["di"] += s["di"]
            totals[name]["ki"] += s["ki"]
            totals[name]["ho"] += s["ho"]
            totals[name]["cl"] += s["cl"]
            totals[name]["ff"] += s["ff"]
            totals[name]["fa"] += s["fa"]
            totals[name]["cm"] += s["cm"]
            totals[name]["op"] += s["op"]
            totals[name]["ga"] += s["ga"]
            totals[name]["gp"] += 1
            # Store per-round snapshot (key stats only, keeps data.json compact)
            rounds[name].append({
                "r":  round_label,
                "di": s["di"], "gl": s["gl"], "tk": s["tk"],
                "ho": s["ho"], "cl": s["cl"], "cm": s["cm"],
                "op": s["op"], "ga": s["ga"],
            })

        time.sleep(1)  # be polite to AFL Tables

    return totals, rounds


def scrape_2025_profiles():
    """Scrape each player's profile page for 2025 season stats."""
    profiles = {}

    for name, url in PLAYER_PROFILES.items():
        print(f"  Profile: {name}")
        html = fetch(url)
        if not html:
            print(f"  ⚠ Failed to fetch profile for {name}")
            profiles[name] = {"gp25": 0, "di25": 0, "gl25": 0, "tk25": 0}
            continue

        data = parse_profile_2025(html)
        if data:
            profiles[name] = data
            print(f"    2025: {data['gp25']} games, {data['di25']} disp, {data['gl25']} goals, {data['tk25']} tackles")
        else:
            profiles[name] = {"gp25": 0, "di25": 0, "gl25": 0, "tk25": 0}
            print(f"    No 2025 data found")

        time.sleep(0.5)

    return profiles


def fetch_youtube_videos():
    """
    Fetch the Hawthorn FC YouTube RSS feed (no API key needed).
    Returns: (videos, fallback_id)
      videos    = [{'id': str, 'title': str}]  — up to 15 most recent
      fallback_id = most recent video id (used when no player-specific match)
    """
    import xml.etree.ElementTree as ET

    print("  Fetching Hawthorn FC YouTube RSS feed…")
    xml_text = fetch(HAWKS_YT_RSS)
    if not xml_text:
        print("  ⚠ Could not reach YouTube RSS — skipping video matching")
        return [], None

    try:
        root = ET.fromstring(xml_text)
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'yt':   'http://www.youtube.com/xml/schemas/2015',
        }
        videos = []
        for entry in root.findall('atom:entry', ns):
            vid_el   = entry.find('yt:videoId',  ns)
            title_el = entry.find('atom:title',  ns)
            if vid_el is not None and title_el is not None:
                videos.append({'id': vid_el.text, 'title': title_el.text or ''})

        fallback = videos[0]['id'] if videos else None
        print(f"  ✓ Found {len(videos)} recent Hawks videos")
        return videos, fallback

    except ET.ParseError as e:
        print(f"  ⚠ XML parse error: {e}")
        return [], None


def match_videos_to_players(videos, player_names):
    """
    Scan video titles for player names and return best-match video ID per player.
    Scoring: full name in title = 2 pts, last name only = 1 pt.
    Returns: {player_name: video_id | None}
    """
    results = {}
    for name in player_names:
        last  = name.split()[-1].lower()
        best_vid, best_score = None, 0
        for v in videos:
            t = v['title'].lower()
            score = 2 if name.lower() in t else (1 if last in t else 0)
            if score > best_score:
                best_score, best_vid = score, v['id']
        results[name] = best_vid
    return results


def fetch_squiggle_standings():
    """
    Fetch current AFL ladder from Squiggle API.
    Returns: (record_str, position_str) or (None, None) on failure.
    """
    try:
        req = Request(
            f"{SQUIGGLE_URL}?q=standings;year=2026",
            headers=SQUIGGLE_HEADERS
        )
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        for team in data.get('standings', []):
            if 'hawthorn' in (team.get('name') or '').lower():
                rank  = int(team.get('rank', 0))
                wins  = int(team.get('wins', 0))
                losses = int(team.get('losses', 0))
                draws = int(team.get('draws', 0))
                record = f"{wins}W\u2013{losses}L" + (f"\u2013{draws}D" if draws else "")
                # Ordinal suffix
                suf = 'th'
                if rank % 100 not in (11, 12, 13):
                    suf = {1:'st', 2:'nd', 3:'rd'}.get(rank % 10, 'th')
                position = f"{rank}{suf}"
                print(f"  ✓ Standings: {record} · {position}")
                return record, position
        print("  ⚠ Hawthorn not found in standings response")
    except Exception as e:
        print(f"  ⚠ Squiggle standings failed: {e}")
    return None, None


def fetch_squiggle_next_game():
    """
    Fetch next upcoming (or live) Hawthorn game from Squiggle API.
    Returns: nextGame dict or None on failure.
    """
    try:
        req = Request(
            f"{SQUIGGLE_URL}?q=games;year=2026;team=10;complete=!100",
            headers=SQUIGGLE_HEADERS
        )
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        games = data.get('games', [])
        if not games:
            print("  ⚠ No upcoming Hawthorn games found in Squiggle")
            return None
        # Sort by localtime, take first
        games.sort(key=lambda g: g.get('localtime') or '')
        g = games[0]
        is_home  = 'hawthorn' in (g.get('hteam') or '').lower()
        opponent = g.get('ateam') if is_home else g.get('hteam')
        venue    = g.get('venue', '')
        rnd      = int(g.get('round', 0))
        localtime = g.get('localtime', '')
        tz_str   = g.get('tz', 'Australia/Melbourne')
        # Convert localtime → UTC
        kickoff_utc = None
        if localtime:
            try:
                from zoneinfo import ZoneInfo
                dt = datetime.strptime(localtime, '%Y-%m-%d %H:%M:%S')
                dt = dt.replace(tzinfo=ZoneInfo(tz_str))
                kickoff_utc = dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception:
                # Fallback: assume AEST (UTC+10) — correct for May–August
                dt = datetime.strptime(localtime, '%Y-%m-%d %H:%M:%S')
                kickoff_utc = (dt - timedelta(hours=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
        print(f"  ✓ Next game: Round {rnd} vs {opponent} at {venue} ({localtime})")
        return {'round': rnd, 'opponent': opponent, 'venue': venue,
                'home': is_home, 'kickoff': kickoff_utc}
    except Exception as e:
        print(f"  ⚠ Squiggle next game failed: {e}")
    return None


def build_data(match_totals, round_data, profiles, record, position, next_game, video_map=None, fallback_vid=None):
    """Combine all scraped data into the final JSON structure."""

    # Load existing data.json as fallback for 2025 stats and other preserved fields
    existing_players = {}
    try:
        with open("data.json") as f:
            existing = json.load(f)
        existing_players = {p["name"]: p for p in existing.get("players", [])}
        print(f"  Loaded existing data.json ({len(existing_players)} players) as fallback")
    except Exception:
        print("  No existing data.json found — starting fresh")

    players = []

    for name, info in PLAYER_INFO.items():
        # Match totals for this season
        mt = match_totals.get(name, {"gl":0,"tk":0,"di":0,"ki":0,
                                     "ho":0,"cl":0,"ff":0,"fa":0,
                                     "cm":0,"op":0,"ga":0,"gp":0})
        # Try alternate name formats if no match
        if mt["gp"] == 0:
            for k in match_totals:
                if name.split()[-1] in k and name.split()[0][0] == k.split()[0][0]:
                    mt = match_totals[k]
                    break

        # 2025 profile — use scraped data, fall back to existing data.json
        prof = profiles.get(name, {})
        existing_p = existing_players.get(name, {})
        if not prof or prof.get("gp25", 0) == 0:
            prof = {
                "gp25": existing_p.get("gp25", 0),
                "di25": existing_p.get("di25", 0),
                "gl25": existing_p.get("gl25", 0),
                "tk25": existing_p.get("tk25", 0),
            }

        # Current season stats — if AFL Tables was unreachable (gp=0 but
        # we have existing data), preserve the existing values
        if mt["gp"] == 0 and existing_p.get("gp", 0) > 0:
            print(f"    ↩ Using existing stats for {name} (AFL Tables unreachable)")
            mt = {k: existing_p.get(k, 0)
                  for k in ["gl","tk","di","ki","ho","cl","ff","fa","cm","op","ga","gp"]}

        # Per-round breakdown — prefer freshly scraped, fall back to existing
        rounds_for_player = round_data.get(name) or existing_p.get("rounds", [])

        players.append({
            **info,
            "name": name,
            "gp": mt["gp"],
            "gl": mt["gl"],
            "tk": mt["tk"],
            "di": mt["di"],
            "ki": mt["ki"],
            "ho": mt.get("ho", 0),
            "cl": mt.get("cl", 0),
            "ga": mt.get("ga", 0),
            "ff": mt.get("ff", 0),
            "fa": mt.get("fa", 0),
            "cm": mt.get("cm", 0),
            "op": mt.get("op", 0),
            "vid": (video_map or {}).get(name),
            "rounds": rounds_for_player,
            **prof,
        })

    players.sort(key=lambda p: p["gl"], reverse=True)

    # Derive current round from next game (next round - 1)
    current_round = max(1, next_game.get('round', 1) - 1)

    return {
        "updated":     str(date.today()),
        "round":       current_round,
        "record":      record,
        "position":    position,
        "fallbackVid": fallback_vid,
        "nextGame":    next_game,
        "players":     players,
    }


def main():
    print("🦅 Hawks Stats Scraper starting…\n")

    print(f"📋 Auto-discovering and scraping Hawthorn match pages…")
    match_totals, round_data = scrape_match_pages()

    print(f"\n👤 Scraping {len(PLAYER_PROFILES)} player profiles for 2025 data…")
    profiles = scrape_2025_profiles()

    print(f"\n🎬 Fetching Hawthorn FC YouTube highlights…")
    videos, fallback_vid = fetch_youtube_videos()
    video_map = match_videos_to_players(videos, list(PLAYER_INFO.keys()))
    matched = sum(1 for v in video_map.values() if v)
    print(f"  Matched {matched}/{len(video_map)} players to recent videos")

    print(f"\n📊 Fetching live standings & fixture from Squiggle…")
    record, position = fetch_squiggle_standings()
    next_game = fetch_squiggle_next_game()
    if not record:
        record, position = FALLBACK_RECORD, FALLBACK_POSITION
        print(f"  Using fallback: {record} · {position}")
    if not next_game:
        next_game = FALLBACK_NEXT_GAME
        print(f"  Using fallback: Round {next_game['round']} vs {next_game['opponent']}")

    print("\n🔨 Building data.json…")
    data = build_data(match_totals, round_data, profiles, record, position, next_game, video_map, fallback_vid)

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n✅ Done! Round {data['round']} · {record} · {position}")
    print(f"   Next: Round {next_game['round']} vs {next_game['opponent']} · {next_game['venue']}")
    print(f"   {len(data['players'])} players · Updated {data['updated']}")


if __name__ == "__main__":
    main()
