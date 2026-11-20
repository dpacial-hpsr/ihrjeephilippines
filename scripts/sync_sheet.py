#!/usr/bin/env python3
"""Optional: pull the action tracker from a Google Sheet.

Used only when the repository variable ACTIONS_SHEET_CSV_URL is set
(Settings > Secrets and variables > Actions > Variables). The URL is the
"Publish to the web > CSV" link of the tracker tab, and the tab must keep the
same column headers as data/naphs_actions.csv.

The download replaces data/naphs_actions.csv only if the header matches and
every existing action_id is still present, so a broken sheet cannot wipe the
tracker. build.py then validates the content.
"""
import csv
import io
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "data", "naphs_actions.csv")


def main():
    url = os.environ.get("ACTIONS_SHEET_CSV_URL", "").strip()
    if not url:
        print("ACTIONS_SHEET_CSV_URL not set; keeping data/naphs_actions.csv as committed.")
        return 0
    with urllib.request.urlopen(url, timeout=60) as r:
        text = r.read().decode("utf-8-sig")
    new = list(csv.reader(io.StringIO(text)))
    with open(TARGET, newline="", encoding="utf-8") as f:
        old = list(csv.reader(f))
    if not new or new[0] != old[0]:
        print("Sheet header does not match data/naphs_actions.csv; sync skipped.", file=sys.stderr)
        print(f"  expected: {old[0]}\n  received: {new[0] if new else '(empty)'}", file=sys.stderr)
        return 1
    old_ids = {r[0] for r in old[1:] if r}
    new_ids = {r[0] for r in new[1:] if r}
    missing = sorted(old_ids - new_ids)
    if missing:
        print(f"Sheet is missing {len(missing)} action_id(s), e.g. {missing[:5]}; sync skipped.", file=sys.stderr)
        return 1
    with open(TARGET, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows([r for r in new if any(c.strip() for c in r)])
    print(f"Synced {len(new) - 1} rows from the Google Sheet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
