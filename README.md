# JEE Readiness Dashboard

A self-updating GitHub Pages dashboard that shows the gaps the Philippines needs to close before the third Joint External Evaluation (JEE) of IHR (2005) core capacities, envisioned for 2029. It maps every 2024 JEE indicator and priority action to the strategic actions in the Strategic National Action Plan for Health Security (NAPHS) 2026–2030 and tracks implementation.

> **Visibility.** A GitHub Pages site is public to anyone with the address unless the repository belongs to a GitHub Enterprise Cloud organization with private Pages turned on. The seed data is drawn from the *Updated Draft* Strategic NAPHS 2026–2030. Obtain clearance to publish draft NAPHS content before you enable Pages.

## What the dashboard shows

| Section | Question it answers |
|---|---|
| Headline figures | How many indicators sit at limited capacity, how far we are from target, and how many days remain |
| Score map | Where each of the 56 indicators stands, by technical area |
| Priority gap register | Which indicators to work on first, and why (tier, gap, NAPHS coverage, flags) |
| JEE vs NAPHS coverage | Which JEE priority actions the NAPHS carries fully, partly, or not at all |
| Implementation tracker | Status of all 206 NAPHS strategic actions; overdue, stale, and unowned actions; load per lead authority |
| NAPHS draft checks | Drafting fixes that would tighten the line from a JEE indicator to an owned action |

Select any tile or row to open the indicator detail: scores, flags, JEE priority actions with coverage rating, NAPHS actions with status, and drafting checks.

## Repository layout

```
config.json                       Title, credit line, next JEE date, stale window, sources
data/
  indicators.csv                  56 JEE indicators, 2024 scores, 2029 targets
  naphs_actions.csv               206 NAPHS strategic actions: the tracker you update
  jee_recommendations.csv         91 JEE 2024 priority actions (paraphrased) and NAPHS coverage
  overarching.csv                 The 5 overarching JEE recommendations and coverage
  naphs_alignment_checks.csv      Drafting checks on the NAPHS
  score_history.csv               JEE and internal self-assessment scores over time
scripts/
  build.py                        Validates the data and compiles site/data.json
  sync_sheet.py                   Optional pull of the tracker from a Google Sheet
site/index.html                   The dashboard (no external libraries)
.github/workflows/dashboard.yml   Build, validate, and publish
```

## Set up (one time, about 10 minutes)

1. Create a new repository on GitHub (e.g., `jee-readiness`).
2. Upload the contents of this folder, keeping the folder structure, including the hidden `.github` folder. Through the web interface: **Add file → Upload files**, then drag the folder contents in. If the `.github` folder does not upload, create `.github/workflows/dashboard.yml` with **Add file → Create new file** and paste the file contents.
3. Go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Go to **Actions → Build and publish JEE dashboard → Run workflow**.
5. When the run finishes, the page address appears in the run summary and under **Settings → Pages** (usually `https://<account>.github.io/<repository>/`).

## Keeping it current

The page rebuilds on every commit to `data/`, `site/`, `scripts/`, or `config.json`, and every **Friday at 15:17 Philippine Standard Time**. The scheduled run refreshes the countdown and the overdue and stale flags even when no one edits the data.

### Option A: edit on GitHub (default)

Open `data/naphs_actions.csv`, select the pencil icon, edit the row, and commit. GitHub shows CSV files as a searchable table, which helps you find an action by its ID.

### Option B: link a Google Sheet

1. Import `data/naphs_actions.csv` into a Google Sheet. Keep the header row and the `action_id` column exactly as they are.
2. Share it with the focal persons who will update it.
3. **File → Share → Publish to the web**, select the tracker tab and **Comma-separated values (.csv)**, then copy the link. A published link can be opened by anyone who has it.
4. In the repository, go to **Settings → Secrets and variables → Actions → Variables** and add `ACTIONS_SHEET_CSV_URL` with that link.

Each run then pulls the sheet, validates it, commits any change to `data/naphs_actions.csv`, and republishes. The sync stops without changing anything if the headers differ or an `action_id` has gone missing.

### If a build fails

The build stops, the published page stays as it was, and the run summary under **Actions** lists each problem by file and row (for example, a misspelled status or a date not in `YYYY-MM-DD` form). Fix the row and commit again.

## Data dictionary

### `naphs_actions.csv` (the tracker)

| Column | Fill in | Rules |
|---|---|---|
| `action_id` | Do not change | Unique; referenced by other files |
| `naphs_indicator` | Do not change | Indicator row in the NAPHS draft (includes NAPHS-only rows P7.3 and R4.5) |
| `jee_indicator` | Do not change | JEE indicator the action counts toward |
| `also_supports` | Optional | Other JEE indicators it supports, separated by `;` |
| `strategic_action`, `lead_authority` | Update when the NAPHS text changes | Blank lead is flagged |
| `status` | Yes | `Not yet reported`, `Not started`, `On track`, `At risk`, `Delayed`, `Completed`, or `Dropped` |
| `progress_pct` | Optional | 0–100 |
| `target_date` | Yes, once agreed | `YYYY-MM-DD`; past dates without completion show as overdue |
| `last_updated` | Yes, whenever status changes | `YYYY-MM-DD`; required for any status other than `Not yet reported` |
| `focal_person`, `evidence_url`, `remarks` | Optional | `evidence_url` must start with `http` |

An active action (`Not started`, `On track`, `At risk`, `Delayed`) not updated within `stale_after_days` (default 45, in `config.json`) is flagged as stale.

### `indicators.csv`

`target_2029` is the score the indicator should reach by the third JEE. Defaults: next level for scores 1–3; hold the current level for 4 and 5; D2.2 is set to 5 because the NAPHS says so. Replace these with the targets the NAPHS Steering Committee approves, and update `target_basis` to say so.

### `score_history.csv`

Add one row per indicator for each internal assessment against the JEE tool (`assessment_type`, e.g., `Self-assessment (JEE tool)`). The most recent row becomes the "latest" score. Keep e-SPAR results out of this file unless converted to the JEE indicator set, because the two tools use different indicators.

### `jee_recommendations.csv` and `overarching.csv`

`naphs_coverage` is `Full`, `Partial`, or `Not reflected`; `naphs_action_ids` lists the NAPHS actions that carry the recommendation. The seed ratings are a preliminary desk assessment for the subcommittees to confirm.

## Preview locally

```
python scripts/build.py
python -m http.server -d site 8000
```

Then open `http://localhost:8000`. Opening `site/index.html` directly from disk does not work, because browsers block it from loading `data.json`.

## Sources

- WHO (2025). *Joint external evaluation of the International Health Regulations (2005) core capacities of the Philippines: mission report, 25–29 November 2024.* https://www.who.int/publications/i/item/9789240116795
- WHO (2022). *Joint external evaluation tool: International Health Regulations (2005), third edition.* https://www.who.int/publications/i/item/9789240051980
- Department of Health. *Strategic National Action Plan for Health Security 2026–2030*, Updated Draft (8 May–10 November 2026).
