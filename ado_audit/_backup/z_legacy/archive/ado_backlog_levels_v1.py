#!/usr/bin/env python3
"""
ado_backlog_levels.py
Create an Excel file listing backlog levels for each team.

Usage (cmd.exe)
---------------
:: one-shot PAT for this window
set ADO_PAT=your-pat-here

:: all projects
python ado_backlog_levels.py

:: specific project(s)
python ado_backlog_levels.py -p "Starling" -p "DBO"
"""

import os, sys, argparse, base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import requests, pandas as pd
from tqdm import tqdm

ORG            = "1id"
BASE_URL       = f"https://dev.azure.com/{ORG}"
API_VER_CORE   = "7.1"
API_VER_WORK   = "7.1-preview.1"   # backlogconfiguration is still preview
OUT_DIR        = Path.cwd()

# ── CLI ------------------------------------------------------------------ #
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Export backlog levels for ADO teams")
    ap.add_argument("-p", "--project", action="append",
                    help="Project name (repeat for multiple). Default = all.")
    return ap.parse_args()

# ── Helpers -------------------------------------------------------------- #
def get_pat() -> str:
    tok = os.getenv("ADO_PAT")
    if tok:
        return tok.strip()
    fp = Path(__file__).with_name("ado_pat.txt")
    if fp.exists():
        return fp.read_text().strip()
    sys.exit("❌  PAT not found (set ADO_PAT or add ado_pat.txt)")

def make_sess(pat: str) -> requests.Session:
    tok = base64.b64encode(f":{pat}".encode()).decode()
    s   = requests.Session()
    s.headers.update({"Authorization": f"Basic {tok}",
                      "Content-Type" : "application/json; charset=utf-8"})
    return s

def paged(s: requests.Session, url: str) -> List[Dict[str, Any]]:
    items = []
    while url:
        r = s.get(url); r.raise_for_status()
        items.extend(r.json().get("value", []))
        tok = r.headers.get("x-ms-continuationtoken")
        url = f"{url}&continuationToken={tok}" if tok else None
    return items

def safe_json(s: requests.Session, url: str) -> Dict[str, Any] | None:
    r = s.get(url)
    if r.status_code in (404, 403, 500):
        print(f"⚠️  {r.status_code} on {url}")
        return None
    r.raise_for_status() ; return r.json()

# ── Main ----------------------------------------------------------------- #
def main() -> None:
    args  = parse_args()
    sess  = make_sess(get_pat())

    # projects list
    projects = paged(sess, f"{BASE_URL}/_apis/projects?api-version={API_VER_CORE}")
    if args.project:
        wanted = {n.lower() for n in args.project}
        projects = [p for p in projects if p["name"].lower() in wanted]
        if not projects: sys.exit("No matching projects found.")

    print(f"\n🔍 Scanning {len(projects)} project(s) in org '{ORG}'\n")

    backlog_rows: list[dict] = []

    for proj in tqdm(projects, desc="Projects", unit="proj"):
        pid   = proj["id"]
        pname = proj["name"]

        # teams in this project
        teams_url = f"{BASE_URL}/_apis/projects/{pid}/teams?api-version={API_VER_CORE}"
        for team in paged(sess, teams_url):
            tid   = team["id"]
            tname = team["name"]

            bc_url = (
                f"{BASE_URL}/{pid}/{tid}"
                f"/_apis/work/backlogconfiguration?api-version={API_VER_WORK}"
            )
            print(f"\n✅  bc_url built — {bc_url}")

            if (bc := safe_json(sess, bc_url)):
                lvls = bc.get("backlogLevels", []) + bc.get("portfolioBacklogs", [])
                for lvl in lvls:
                    backlog_rows.append({
                        "Project" : pname,
                        "Team"    : tname,
                        "Backlog" : lvl["name"],
                        "Type"    : lvl.get("type", ""),
                        "Rank"    : lvl.get("rank", ""),
                        "WITs"    : "; ".join(w["name"] for w in lvl.get("workItemTypes", []))
                    })

    # Excel output
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    tag  = "_".join(n.replace(" ","") for n in args.project) if args.project else "ALL"
    out  = OUT_DIR / f"ado_backlog_levels_{tag}_{ts}.xlsx"

    pd.DataFrame(backlog_rows).to_excel(out, index=False, engine="openpyxl")
    print(f"\n✅  Backlog levels exported → {out}")

if __name__ == "__main__":
    main()
