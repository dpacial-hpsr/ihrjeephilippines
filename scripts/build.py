#!/usr/bin/env python3
"""Validate the dashboard data and compile site/data.json.

Standard library only. Run from the repository root:
    python scripts/build.py
Exits with status 1 and a list of problems if any data file is invalid,
so a bad edit never reaches the published page.
"""
import csv
import datetime as dt
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")

STATUSES = ["Not yet reported", "Not started", "On track", "At risk", "Delayed", "Completed", "Dropped"]
ACTIVE = {"Not started", "On track", "At risk", "Delayed"}
COVERAGE = ["Full", "Partial", "Not reflected"]
SEVERITY = ["High", "Medium", "Low"]
DOMAIN_ORDER = ["Prevent", "Detect", "Respond", "IHR-related hazards, PoE and border health"]
TIER_ORDER = {"Critical": 0, "Advance": 1, "Sustain": 2}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

errors = []


def err(file, row, msg):
    errors.append(f"{file} row {row}: {msg}")


def read(name, required):
    path = os.path.join(DATA, name)
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        header = rows[0].keys() if rows else []
    missing = [c for c in required if c not in header]
    if missing:
        errors.append(f"{name}: missing column(s) {', '.join(missing)}")
    return [{k: (v or "").strip() for k, v in r.items() if k} for r in rows]


def parse_date(file, row, value, field):
    if not value:
        return None
    if not DATE_RE.match(value):
        err(file, row, f"{field} '{value}' must be YYYY-MM-DD")
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        err(file, row, f"{field} '{value}' is not a real date")
        return None


def split(v):
    return [x.strip() for x in v.split(";") if x.strip()]


def main():
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    tz = dt.timezone(dt.timedelta(hours=cfg.get("timezone_offset_hours", 8)))
    now = dt.datetime.now(tz)
    today = now.date()
    stale_days = int(cfg.get("stale_after_days", 45))

    ind = read("indicators.csv", ["indicator", "area", "technical_area", "domain", "name", "jee_2024", "target_2029"])
    act = read("naphs_actions.csv", ["action_id", "naphs_indicator", "jee_indicator", "also_supports", "strategic_action",
                                     "lead_authority", "status", "progress_pct", "target_date", "last_updated"])
    recs = read("jee_recommendations.csv", ["rec_id", "area", "indicators", "recommendation", "naphs_coverage", "naphs_action_ids"])
    over = read("overarching.csv", ["rec_id", "recommendation", "naphs_coverage", "naphs_action_ids"])
    checks = read("naphs_alignment_checks.csv", ["check_id", "indicator", "issue_type", "finding", "severity", "suggested_fix"])
    hist = read("score_history.csv", ["indicator", "assessment_date", "assessment_type", "score"])
    if errors:
        return fail()

    # ---- indicators
    codes = {}
    for i, r in enumerate(ind, 2):
        c = r["indicator"]
        if c in codes:
            err("indicators.csv", i, f"duplicate indicator {c}")
        for f in ("jee_2024", "target_2029"):
            if not r[f].isdigit() or not 1 <= int(r[f]) <= 5:
                err("indicators.csv", i, f"{f} must be a whole number 1-5 (got '{r[f]}')")
        if r["domain"] not in DOMAIN_ORDER:
            err("indicators.csv", i, f"domain '{r['domain']}' not one of {DOMAIN_ORDER}")
        codes[c] = r

    # ---- score history
    latest = {}
    for i, r in enumerate(hist, 2):
        if r["indicator"] not in codes:
            err("score_history.csv", i, f"unknown indicator {r['indicator']}")
            continue
        d = parse_date("score_history.csv", i, r["assessment_date"], "assessment_date")
        if not r["score"].isdigit() or not 1 <= int(r["score"]) <= 5:
            err("score_history.csv", i, "score must be 1-5")
            continue
        if d and (r["indicator"] not in latest or d >= latest[r["indicator"]]["d"]):
            latest[r["indicator"]] = {"d": d, "score": int(r["score"]), "type": r["assessment_type"]}

    # ---- actions
    ids = {}
    for i, r in enumerate(act, 2):
        a = r["action_id"]
        if not a:
            err("naphs_actions.csv", i, "action_id is blank")
        if a in ids:
            err("naphs_actions.csv", i, f"duplicate action_id {a}")
        if r["jee_indicator"] not in codes:
            err("naphs_actions.csv", i, f"jee_indicator '{r['jee_indicator']}' is not in indicators.csv")
        for s in split(r["also_supports"]):
            if s not in codes:
                err("naphs_actions.csv", i, f"also_supports '{s}' is not in indicators.csv")
        if r["status"] not in STATUSES:
            err("naphs_actions.csv", i, f"status '{r['status']}' must be one of: {', '.join(STATUSES)}")
        if r["progress_pct"]:
            try:
                p = float(r["progress_pct"])
                if not 0 <= p <= 100:
                    raise ValueError
            except ValueError:
                err("naphs_actions.csv", i, "progress_pct must be blank or 0-100")
        r["_target"] = parse_date("naphs_actions.csv", i, r["target_date"], "target_date")
        r["_updated"] = parse_date("naphs_actions.csv", i, r["last_updated"], "last_updated")
        if r.get("evidence_url") and not r["evidence_url"].startswith(("http://", "https://")):
            err("naphs_actions.csv", i, "evidence_url must start with http:// or https://")
        if r["status"] != "Not yet reported" and not r["_updated"]:
            err("naphs_actions.csv", i, "last_updated is required once a status is reported")
        ids[a] = r

    for fname, rows in (("jee_recommendations.csv", recs), ("overarching.csv", over)):
        for i, r in enumerate(rows, 2):
            if r["naphs_coverage"] not in COVERAGE:
                err(fname, i, f"naphs_coverage must be one of {COVERAGE}")
            for a in split(r["naphs_action_ids"]):
                if a not in ids:
                    err(fname, i, f"naphs_action_ids references unknown action {a}")
            for c in split(r.get("indicators", "")):
                if c not in codes:
                    err(fname, i, f"unknown indicator {c}")
    for i, r in enumerate(checks, 2):
        if r["severity"] not in SEVERITY:
            err("naphs_alignment_checks.csv", i, f"severity must be one of {SEVERITY}")
        if r["indicator"] and r["indicator"] not in codes and r["indicator"] not in {a["naphs_indicator"] for a in act}:
            err("naphs_alignment_checks.csv", i, f"unknown indicator {r['indicator']}")
    if errors:
        return fail()

    # ---- derived action fields
    out_actions = []
    for a in act:
        flags = []
        if not a["lead_authority"]:
            flags.append("No lead")
        if a["_target"] and a["_target"] < today and a["status"] not in ("Completed", "Dropped"):
            flags.append("Overdue")
        if a["status"] in ACTIVE and a["_updated"] and (today - a["_updated"]).days > stale_days:
            flags.append("Stale")
        out_actions.append({
            "id": a["action_id"], "naphs_indicator": a["naphs_indicator"], "indicator": a["jee_indicator"],
            "also": split(a["also_supports"]), "text": a["strategic_action"], "lead": a["lead_authority"],
            "status": a["status"], "progress": float(a["progress_pct"]) if a["progress_pct"] else None,
            "target_date": a["target_date"], "last_updated": a["last_updated"],
            "focal": a.get("focal_person", ""), "evidence": a.get("evidence_url", ""),
            "remarks": a.get("remarks", ""), "flags": flags,
            "eb": bool(re.search(r"\bDOH-EB\b|\bEB\b", a["lead_authority"])),
        })
    by_ind = defaultdict(list)
    sup_ind = defaultdict(list)
    for a in out_actions:
        by_ind[a["indicator"]].append(a)
        for s in a["also"]:
            sup_ind[s].append(a)

    recs_by_ind = defaultdict(list)
    for r in recs:
        for c in split(r["indicators"]):
            recs_by_ind[c].append(r["rec_id"])
    checks_by_ind = defaultdict(list)
    for r in checks:
        if r["indicator"]:
            checks_by_ind[r["indicator"]].append(r["check_id"])
    rec_cov = {r["rec_id"]: r["naphs_coverage"] for r in recs}

    # ---- indicators
    out_ind = []
    for c, r in codes.items():
        base = int(r["jee_2024"])
        lt = latest.get(c, {"score": base, "d": None, "type": "JEE (external)"})
        score, target = lt["score"], int(r["target_2029"])
        tier = "Critical" if score <= 2 else ("Advance" if score == 3 else "Sustain")
        prim, sup = by_ind.get(c, []), sup_ind.get(c, [])
        st = Counter(a["status"] for a in prim)
        cov = Counter(rec_cov[x] for x in recs_by_ind.get(c, []))
        flags = []
        if r.get("in_naphs_table") == "no":
            flags.append("No NAPHS indicator row")
        if score < target and len(prim) <= 1:
            flags.append("One or no strategic action")
        if any(not a["lead"] for a in prim):
            flags.append("Action without lead")
        if cov.get("Not reflected"):
            flags.append(f"{cov['Not reflected']} JEE action(s) not in NAPHS")
        if prim and st.get("Not yet reported", 0) == len(prim):
            flags.append("No status reported")
        if any("Overdue" in a["flags"] for a in prim):
            flags.append("Overdue action")
        if any("Stale" in a["flags"] for a in prim):
            flags.append("Stale update")
        out_ind.append({
            "code": c, "area": r["area"], "technical_area": r["technical_area"], "domain": r["domain"],
            "name": r["name"], "jee_2024": base, "latest": score,
            "latest_date": lt["d"].isoformat() if lt["d"] else "", "latest_type": lt["type"],
            "target": target, "target_basis": r.get("target_basis", ""), "gap": max(target - score, 0),
            "tier": tier, "in_naphs_table": r.get("in_naphs_table", "yes") == "yes",
            "actions": [a["id"] for a in prim], "supporting": [a["id"] for a in sup if a not in prim],
            "status_counts": dict(st), "completed": st.get("Completed", 0),
            "reported": len(prim) - st.get("Not yet reported", 0),
            "recs": recs_by_ind.get(c, []), "coverage": dict(cov), "checks": checks_by_ind.get(c, []),
            "eb": any(a["eb"] for a in prim), "flags": flags,
        })
    out_ind.sort(key=lambda x: (TIER_ORDER[x["tier"]], -x["gap"], -x["coverage"].get("Not reflected", 0),
                                -len(x["flags"]), x["code"]))
    for n, x in enumerate(out_ind, 1):
        x["priority"] = n

    # ---- summaries
    scores = [x["latest"] for x in out_ind]
    status_total = Counter(a["status"] for a in out_actions)
    cov_total = Counter(r["naphs_coverage"] for r in recs)
    lead_count = Counter()
    for a in out_actions:
        for l in split(a["lead"]) or ["(no lead assigned)"]:
            lead_count[re.sub(r"\s*\(NIP\)$", "", l)] += 1
    nj = dt.date.fromisoformat(cfg["next_jee"]["date"])
    summary = {
        "indicators": len(out_ind),
        "limited": sum(1 for s in scores if s <= 2),
        "developed": sum(1 for s in scores if s == 3),
        "demonstrated_plus": sum(1 for s in scores if s >= 4),
        "mean_score": round(sum(scores) / len(scores), 2),
        "mean_2024": round(sum(x["jee_2024"] for x in out_ind) / len(out_ind), 2),
        "at_target": sum(1 for x in out_ind if x["latest"] >= x["target"]),
        "points_to_target": sum(x["gap"] for x in out_ind),
        "actions": len(out_actions), "actions_reported": len(out_actions) - status_total.get("Not yet reported", 0),
        "actions_completed": status_total.get("Completed", 0),
        "actions_overdue": sum(1 for a in out_actions if "Overdue" in a["flags"]),
        "actions_stale": sum(1 for a in out_actions if "Stale" in a["flags"]),
        "actions_no_lead": sum(1 for a in out_actions if not a["lead"]),
        "status": {s: status_total.get(s, 0) for s in STATUSES},
        "recs": len(recs), "coverage": {c: cov_total.get(c, 0) for c in COVERAGE},
        "days_to_jee": (nj - today).days,
        "checks_high": sum(1 for r in checks if r["severity"] == "High"),
    }
    areas = []
    seen = []
    for x in sorted(out_ind, key=lambda x: (DOMAIN_ORDER.index(x["domain"]), list(codes).index(x["code"]))):
        if x["area"] not in seen:
            seen.append(x["area"])
    for a in seen:
        xs = [x for x in out_ind if x["area"] == a]
        rs = [r for r in recs if r["area"] == a]
        areas.append({
            "area": a, "technical_area": xs[0]["technical_area"], "domain": xs[0]["domain"],
            "indicators": sorted([x["code"] for x in xs], key=lambda c: list(codes).index(c)),
            "mean": round(sum(x["latest"] for x in xs) / len(xs), 2),
            "coverage": {c: sum(1 for r in rs if r["naphs_coverage"] == c) for c in COVERAGE},
            "status": {s: sum(1 for a2 in out_actions if codes[a2["indicator"]]["area"] == a and a2["status"] == s) for s in STATUSES},
        })

    payload = {
        "config": cfg,
        "built_at": now.isoformat(timespec="minutes"),
        "data_as_of": max([a["last_updated"] for a in out_actions if a["last_updated"]] or [""]),
        "commit": os.environ.get("GITHUB_SHA", "")[:7],
        "statuses": STATUSES, "coverage_levels": COVERAGE, "domains": DOMAIN_ORDER,
        "summary": summary, "areas": areas, "indicators": out_ind, "actions": out_actions,
        "recommendations": recs, "overarching": over, "checks": checks,
        "leads": [{"lead": k, "n": v} for k, v in lead_count.most_common()],
    }
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    with open(os.path.join(SITE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    for name in os.listdir(DATA):
        if name.endswith(".csv"):
            shutil.copy(os.path.join(DATA, name), os.path.join(SITE, "data", name))

    msg = (f"Built {len(out_ind)} indicators, {len(out_actions)} actions, {len(recs)} JEE priority actions. "
           f"Limited capacity: {summary['limited']}; reported actions: {summary['actions_reported']}/{summary['actions']}; "
           f"overdue: {summary['actions_overdue']}; stale: {summary['actions_stale']}.")
    print(msg)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### JEE dashboard build\n\n{msg}\n")
    return 0


def fail():
    print("Data validation failed:\n  - " + "\n  - ".join(errors), file=sys.stderr)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### JEE dashboard build failed\n\nFix these rows, then commit again:\n\n" +
                    "\n".join(f"- {e}" for e in errors) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
