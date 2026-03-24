#!/usr/bin/env python3
"""
ado_boards_audit.py  –  Audit ADO Boards / Backlogs / WITs and export to Excel.
"""

import os, sys, argparse, base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import quote

import requests, pandas as pd
from tqdm import tqdm

# ───── CONFIG ─────
ORG            = "1id"
BASE_URL       = f"https://dev.azure.com/{ORG}"
API_VER_CORE   = "7.1"
API_VER_WORK   = "7.1"
API_VER_WIT    = "7.1"
OUT_DIR        = Path.cwd()

# ───── CLI ─────
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Audit ADO Boards configuration")
    ap.add_argument("-p", "--project", action="append",
                    help="Project name (repeat for multiple). Default = all.")
    return ap.parse_args()

# ───── HELPERS ─────
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
    s.headers.update({
        "Authorization": f"Basic {tok}",
        "Content-Type" : "application/json; charset=utf-8"
    })
    return s

def paged(s: requests.Session, url: str) -> List[Dict[str, Any]]:
    items=[]
    while url:
        r=s.get(url); r.raise_for_status()
        items.extend(r.json().get("value", []))
        tok=r.headers.get("x-ms-continuationtoken")
        url=f"{url}&continuationToken={tok}" if tok else None
    return items

def safe_json(s: requests.Session, url: str) -> Dict[str, Any] | None:
    r=s.get(url)
    if r.status_code in (404,403,500):
        print(f"⚠️  {r.status_code} on {url}")
        return None
    r.raise_for_status()
    return r.json()

# ───── MAIN ─────
def main() -> None:
    args  = parse_args()
    sess  = make_sess(get_pat())

    proc_url = f"{BASE_URL}/_apis/process/processes?api-version=7.1"
    proc_json = safe_json(sess, proc_url) or {"value": []}
    process_map = {p["id"]: p["name"] for p in proc_json.get("value", [])}

    projects = paged(sess, f"{BASE_URL}/_apis/projects?api-version={API_VER_CORE}")
    if args.project:
        sel={n.lower() for n in args.project}
        projects=[p for p in projects if p["name"].lower() in sel]
        if not projects: sys.exit("No matching projects found.")

    print(f"\n🔍 Scanning {len(projects)} project(s) in org '{ORG}'\n")

    projects_rows, teams_rows, settings_rows = [], [], []
    backlog_rows, board_rows, wit_rows      = [], [], []

    for proj in tqdm(projects, desc="Projects", unit="proj"):
        pname = proj["name"]; pesc = quote(pname)

        # --- process template via project properties (new & legacy keys) ---
        prop_url = (
            f"{BASE_URL}/_apis/projects/{proj['id']}/properties"
            f"?api-version=7.1-preview.1"
        )
        prop_json = safe_json(sess, prop_url)

        proc_id = ""
        proc_name = "Unknown"

        if prop_json and prop_json["value"]:
            prop_map = {item["name"]: item["value"] for item in prop_json["value"]}

            # 1️⃣ Preferred GUID field (works with /process/processes)
            proc_id = prop_map.get("System.ProcessTemplateType", "")

            # 2️⃣ Fallback GUIDs (legacy) if ① absent
            if not proc_id:
                proc_id = prop_map.get("System.CurrentProcessTemplateId") \
                    or prop_map.get("System.OriginalProcessTemplateId", "")

            # 3️⃣ Map GUID → name using the catalogue (process_map)
            proc_name = process_map.get(proc_id)

            # 4️⃣ Final fallback: use the literal property "System.Process Template"
            if not proc_name:
                proc_name = prop_map.get("System.Process Template", "Unknown")

        projects_rows.append({
            "Project Name": pname,
            "Project ID"  : proj["id"],
            "Process ID"  : proc_id,        # ← NEW COLUMN
            "Process Name": proc_name,       # shows Scrum / Agile / … or Unknown
            "Project State": proj["state"],
            "Project Vis": proj["visibility"]
        })

        # WIT states
        wurl=f"{BASE_URL}/{pesc}/_apis/wit/workitemtypes?api-version={API_VER_WIT}"
        if (wj:=safe_json(sess,wurl)):
            for t in wj.get("value", []):
                for order, st in enumerate(t.get("states", []), 1):
                    wit_rows.append({
                        "Project": pname, "WIT": t["name"],
                        "State"  : st["name"], "Category": st.get("category",""),
                        "Order"  : order
                    })

        # Teams
        for team in paged(sess,
            f"{BASE_URL}/_apis/projects/{proj['id']}/teams?api-version={API_VER_CORE}"):
            tname=team["name"]; tesc=quote(tname)
            teams_rows.append({"Project":pname,"Team":tname,"Team ID":team["id"]})

            # Team settings
            sets=f"{BASE_URL}/{pesc}/{tesc}/_apis/work/teamsettings?api-version={API_VER_WORK}"
            if (ts:=safe_json(sess,sets)):
                settings_rows.append({
                    "Project":pname,"Team":tname,
                    "Backlog Iteration": ts.get("backlogIteration",{}).get("path",""),
                    "Working Days"    : ", ".join(ts.get("workingDays",[])),
                    "Bugs Behavior"   : ts.get("bugsBehavior","")
                })

            # Boards → Columns
            boards=f"{BASE_URL}/{pesc}/{tesc}/_apis/work/boards?api-version={API_VER_WORK}"
            if (bj:=safe_json(sess,boards)):
                for b in bj.get("value", []):
                    bid,bname=b["id"],b["name"]
                    cols=f"{BASE_URL}/{pesc}/{tesc}/_apis/work/boards/{bid}/columns?api-version={API_VER_WORK}"
                    if (cj:=safe_json(sess,cols)):
                        for col in cj.get("value", []):
                            state_map = col.get("stateMappings", {})
                            state     = ", ".join(set(state_map.values())) or "-"
                            board_rows.append({
                                "Project":pname,"Team":tname,"Board":bname,
                                "Column":col["name"],"WIP":col.get("itemLimit",0),
                                "Split":col.get("isSplit",False),"State":state
                            })

            # Backlog levels (requirement + portfolio)
            bc_url = f"{BASE_URL}/{pesc}/{tesc}/_apis/work/backlogconfiguration?api-version=7.1"
            
            bc = safe_json(sess, bc_url)

            if bc:
                all_lvls = bc.get("backlogLevels", []) + bc.get("portfolioBacklogs", [])
                for lvl in all_lvls:
                    backlog_rows.append({
                        "Project" : pname,
                        "Team"    : tname,
                        "Backlog" : lvl["name"],
                        "Type"    : lvl.get("type", ""),
                        "Rank"    : lvl.get("rank", ""),
                        "Hidden": lvl.get("isHidden"),
                        "WITs"    : "; ".join(w["name"] for w in lvl.get("workItemTypes", []))
                    })
    
    # ── Export
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    tag = "_".join(n.replace(" ","") for n in args.project) if args.project else "ALL"
    out = OUT_DIR / f"ado_boards_audit_{tag}_{ts}.xlsx"

    with pd.ExcelWriter(out, engine="openpyxl") as x:
        pd.DataFrame(projects_rows ).to_excel(x,"Projects",      index=False)
        pd.DataFrame(teams_rows    ).to_excel(x,"Teams",         index=False)
        pd.DataFrame(settings_rows ).to_excel(x,"TeamSettings",  index=False)
        pd.DataFrame(backlog_rows  ).to_excel(x,"BacklogLevels", index=False)
        pd.DataFrame(board_rows    ).to_excel(x,"BoardColumns",  index=False)
        pd.DataFrame(wit_rows      ).to_excel(x,"WIT_States",    index=False)

    print(f"\n✅  Audit complete — {out} written.")

if __name__ == "__main__":
    main()
