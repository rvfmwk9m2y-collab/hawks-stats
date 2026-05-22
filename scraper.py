"""
Hawks 2026 Stats Scraper
Fetches data from AFL Tables every week and saves to data.json
Run automatically via GitHub Actions every Monday, or manually anytime.
"""

import json
import re
import time
from datetime import date
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser

HEADERS = {"User-Agent": "Mozilla/5.0 (Hawks Stats App; contact via GitHub)"}

# ── Hawthorn 2026 match pages (update round number and URL each week) ──
# AFL Tables URL format: /afl/stats/games/2026/HOMETEAMAWAY_DATE.html
MATCH_PAGES = [
    ("R1",  "https://afltables.com/afl/stats/games/2026/102120260307.html"),  # GWS
    ("R2",  "https://afltables.com/afl/stats/games/2026/051020260313.html"),  # Essendon
    ("R3",  "https://afltables.com/afl/stats/games/2026/101620260319.html"),  # Sydney
    ("R5",  "https://afltables.com/afl/stats/games/2026/091020260406.html"),  # Geelong
    ("R6",  "https://afltables.com/afl/stats/games/2026/071020260411.html"),  # W.Bulldogs
    ("R7",  "https://afltables.com/afl/stats/games/2026/101320260418.html"),  # Port Adelaide
    ("R8",  "https://afltables.com/afl/stats/games/2026/102020260425.html"),  # Gold Coast
    ("R9",  "https://afltables.com/afl/stats/games/2026/041020260430.html"),  # Collingwood
    ("R10", "https://afltables.com/afl/stats/games/2026/081020260507.html"),  # Fremantle
    ("R11", "https://afltables.com/afl/stats/games/2026/101120260516.html"),  # Melbourne
    # ── ADD NEW ROUNDS HERE EACH WEEK ──
    # ("R12", "https://afltables.com/afl/stats/games/2026/XXXXX.html"),
]

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
}

# Static player info (jumper, position, age, height, draft) — update if players change
PLAYER_INFO = {
    "Karl Amon":           {"jn":10,"pos":"DF","age":30,"ht":181,"draftLbl":"68"},
    "Tom Barrass":         {"jn":37,"pos":"DF","age":30,"ht":196,"draftLbl":"43"},
    "Josh Battle":         {"jn":24,"pos":"DF","age":27,"ht":193,"draftLbl":"39"},
    "Sam Butler":          {"jn":30,"pos":"MF","age":23,"ht":184,"draftLbl":"23"},
    "Mabior Chol":         {"jn":18,"pos":"FW","age":29,"ht":200,"draftLbl":"30"},
    "Massimo D'Ambrosio":  {"jn":16,"pos":"MF","age":22,"ht":178,"draftLbl":"3"},
    "Jack Dalton":         {"jn":34,"pos":"MF","age":19,"ht":177,"draftLbl":"34"},
    "Calsher Dear":        {"jn":13,"pos":"FW","age":20,"ht":195,"draftLbl":"56"},
    "Jack Ginnivan":       {"jn":33,"pos":"FW","age":23,"ht":183,"draftLbl":"13"},
    "Jack Gunston":        {"jn":19,"pos":"FW","age":34,"ht":193,"draftLbl":"29"},
    "Blake Hardwick":      {"jn":15,"pos":"DF","age":29,"ht":181,"draftLbl":"44"},
    "Henry Hustwaite":     {"jn":44,"pos":"MF","age":21,"ht":195,"draftLbl":"37"},
    "Jarman Impey":        {"jn":4, "pos":"DF","age":30,"ht":178,"draftLbl":"21"},
    "Mitch Lewis":         {"jn":2, "pos":"FW","age":27,"ht":198,"draftLbl":"76"},
    "Connor Macdonald":    {"jn":9, "pos":"FW","age":23,"ht":184,"draftLbl":"26"},
    "Cam Mackenzie":       {"jn":28,"pos":"MF","age":22,"ht":188,"draftLbl":"7"},
    "Finn Maginness":      {"jn":20,"pos":"FW","age":25,"ht":187,"draftLbl":"29"},
    "Lloyd Meek":          {"jn":17,"pos":"RU","age":28,"ht":203,"draftLbl":"69"},
    "Dylan Moore":         {"jn":8, "pos":"FW","age":26,"ht":176,"draftLbl":"67"},
    "Harry Morrison":      {"jn":1, "pos":"MF","age":27,"ht":180,"draftLbl":"74"},
    "Conor Nash":          {"jn":11,"pos":"MF","age":27,"ht":197,"draftLbl":"Cat B"},
    "Jai Newcombe":        {"jn":3, "pos":"MF","age":24,"ht":186,"draftLbl":"2"},
    "Ned Reeves":          {"jn":7, "pos":"RU","age":27,"ht":208,"draftLbl":"SSP"},
    "Jack Scrimshaw":      {"jn":14,"pos":"DF","age":27,"ht":193,"draftLbl":"7"},
    "James Sicily":        {"jn":6, "pos":"DF","age":31,"ht":186,"draftLbl":"56"},
    "Josh Ward":           {"jn":25,"pos":"MF","age":22,"ht":181,"draftLbl":"7"},
    "Nick Watson":         {"jn":5, "pos":"FW","age":21,"ht":170,"draftLbl":"5"},
    "Josh Weddle":         {"jn":23,"pos":"DF","age":22,"ht":191,"draftLbl":"18"},
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

        # Columns: KI MK HB DI GL BH HO TK ...
        try:
            ki = safe_int(cells[2])
            di = safe_int(cells[5])
            gl = safe_int(cells[6])
            tk = safe_int(cells[9])
        except IndexError:
            continue

        results[name] = {"gl": gl, "tk": tk, "di": di, "ki": ki, "gp": 1}

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
    """Scrape all match pages and accumulate season totals."""
    totals = {}  # name -> {gl, tk, di, ki, gp}

    for round_label, url in MATCH_PAGES:
        print(f"  Fetching {round_label}: {url}")
        html = fetch(url)
        if not html:
            print(f"  ⚠ Failed to fetch {round_label}")
            continue

        stats = parse_match_stats(html)
        print(f"    Found {len(stats)} Hawthorn players")

        for name, s in stats.items():
            if name not in totals:
                totals[name] = {"gl": 0, "tk": 0, "di": 0, "ki": 0, "gp": 0}
            totals[name]["gl"] += s["gl"]
            totals[name]["tk"] += s["tk"]
            totals[name]["di"] += s["di"]
            totals[name]["ki"] += s["ki"]
            totals[name]["gp"] += 1

        time.sleep(1)  # be polite to AFL Tables

    return totals


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


def build_data(match_totals, profiles, round_num):
    """Combine all scraped data into the final JSON structure."""
    players = []

    # Determine record from match pages count
    # (In practice you'd parse the ladder page; here we use a placeholder)
    total_games = max((v["gp"] for v in match_totals.values()), default=0)

    for name, info in PLAYER_INFO.items():
        # Match totals (may not exist if player didn't play)
        mt = match_totals.get(name, {"gl": 0, "tk": 0, "di": 0, "ki": 0, "gp": 0})
        # Try alternate name formats
        if mt["gp"] == 0:
            for k in match_totals:
                if name.split()[-1] in k and name.split()[0][0] == k.split()[0][0]:
                    mt = match_totals[k]
                    break

        # 2025 profile
        prof = profiles.get(name, {"gp25": 0, "di25": 0, "gl25": 0, "tk25": 0})

        players.append({
            **info,
            "name": name,
            "gp": mt["gp"],
            "gl": mt["gl"],
            "tk": mt["tk"],
            "di": mt["di"],
            "ki": mt["ki"],
            **prof,
        })

    # Sort by goals descending for default display
    players.sort(key=lambda p: p["gl"], reverse=True)

    return {
        "updated": str(date.today()),
        "round": round_num,
        "record": "See ladder",  # update manually or parse from AFL Tables
        "position": "TBC",
        "players": players,
    }


def main():
    print("🦅 Hawks Stats Scraper starting…\n")

    latest_round = len(MATCH_PAGES)
    print(f"📋 Scraping {latest_round} match pages for goals & tackles…")
    match_totals = scrape_match_pages()

    print(f"\n👤 Scraping {len(PLAYER_PROFILES)} player profiles for 2025 data…")
    profiles = scrape_2025_profiles()

    print("\n🔨 Building data.json…")
    data = build_data(match_totals, profiles, latest_round)

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n✅ Done! data.json updated for Round {latest_round}")
    print(f"   {len(data['players'])} players · Updated {data['updated']}")


if __name__ == "__main__":
    main()
