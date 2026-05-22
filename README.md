# 🦅 Hawks Stats 2026 — Setup Guide

A live Hawthorn Hawks stats app for iPhone and iPad that auto-updates every Monday.

---

## What you get
- Beautiful mobile app showing 2026 player stats
- Year-on-year improvement vs 2025 with trend scores
- Auto-refreshes every Monday morning from AFL Tables
- Works on iPhone, iPad, and desktop
- Add to home screen — looks and feels like a real app

---

## Setup (one-time, ~15 minutes)

### Step 1 — Create a free GitHub account
Go to **github.com** → click Sign Up → use any email address.

### Step 2 — Create a new repository
1. Click the **+** button (top right) → **New repository**
2. Name it `hawks-stats` (or anything you like)
3. Make sure **Public** is selected (required for free hosting)
4. Click **Create repository**

### Step 3 — Upload the files
1. In your new repository, click **uploading an existing file**
2. Drag and drop ALL of these files:
   - `index.html`
   - `scraper.py`
   - `manifest.json`
   - `data.json` ← the latest stats file
3. Also create the folder structure for the workflow:
   - In the repository, click **Create new file**
   - Type `.github/workflows/weekly-update.yml` as the filename
   - Paste the contents of `weekly-update.yml`
4. Click **Commit changes**

### Step 4 — Enable GitHub Pages
1. Go to your repository → **Settings** tab
2. Click **Pages** in the left sidebar
3. Under "Source", select **Deploy from a branch**
4. Set Branch to `main` and folder to `/ (root)`
5. Click **Save**
6. After ~2 minutes, your site will be live at:
   **`https://YOUR-USERNAME.github.io/hawks-stats/`**

### Step 5 — Add to home screen (iPhone/iPad)
1. Open Safari on your iPhone or iPad
2. Go to your GitHub Pages URL
3. Tap the **Share** button (the box with an arrow)
4. Scroll down and tap **Add to Home Screen**
5. Name it "Hawks Stats" and tap **Add**

It will appear on the home screen with a brown icon — share the same URL with Billy and Maddie and they can do the same on their iPads! 🏉

---

## Keeping it up to date

### Auto-update (recommended)
The GitHub Actions workflow runs every Monday morning and automatically updates `data.json`. You don't need to do anything — just open the app and the latest stats are there.

**Enable Actions:**
1. Go to your repository → **Actions** tab
2. If prompted, click **I understand my workflows, go ahead and enable them**

### Manual update (add new rounds)
Each week, you need to add the new round's match page URL to `scraper.py`.

Find the URL from AFL Tables:
1. Go to **afltables.com**
2. Navigate to the Hawthorn vs [opponent] match stats page
3. Copy the URL (looks like `/afl/stats/games/2026/XXXXXXXXXX.html`)

Then in `scraper.py`, find the `MATCH_PAGES` list and add:
```python
("R12", "https://afltables.com/afl/stats/games/2026/XXXXXXXXXX.html"),
```

Commit the change and the workflow will pick it up next Monday.

### Run the scraper manually
If you want to update immediately without waiting for Monday:
1. Go to your repository → **Actions** tab
2. Click **Update Hawks Stats** in the left list
3. Click **Run workflow** → **Run workflow**

---

## Troubleshooting

**The app shows old data**
The app loads `data.json` automatically. If it fails (e.g. on first load before data.json exists), it falls back to embedded data from when the app was built. Run the scraper to generate a fresh `data.json`.

**The scraper failed**
Check the Actions tab for error details. AFL Tables occasionally blocks scrapers — if this happens, wait an hour and try the manual trigger again.

**I want to update player info** (e.g. someone changed jumper number)
Edit the `PLAYER_INFO` dictionary in `scraper.py` and commit the change.

---

## File structure
```
hawks-stats/
├── index.html          ← The app (open this in a browser)
├── data.json           ← Latest stats (auto-updated by scraper)
├── scraper.py          ← Fetches fresh data from AFL Tables
├── manifest.json       ← Makes it installable on iPhone/iPad
├── README.md           ← This file
└── .github/
    └── workflows/
        └── weekly-update.yml  ← Auto-runs scraper every Monday
```

---

Built with ❤️ for Billy, Maddie and the Hawks faithful. Go Hawks! 🦅
