#!/usr/bin/env python3
import os
import sys
import base64
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict

# ─── Config & Auth ───
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"

# **Adjust this to change the “stale” threshold**:
DAYS_THRESHOLD = 90

# PAT retrieval: env ADO_PAT or ado_pat.txt
pat = (
    #os.getenv("ADO_PAT") or
    (open("ado_pat.txt").read().strip() if os.path.exists("ado_pat.txt") else None)
)
pat = "G2jzdo870EXBrTmVpGTcDjZqD7ROyrdYWJo79GuSD8FArIIXQ2upJQQJ99BFACAAAAAqG6F6AAASAZDO1LW9"
if not pat:
    sys.exit("🔑 ADO_PAT not found in environment or ado_pat.txt")
token = base64.b64encode(f":{pat}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {token}",
    "Content-Type": "application/json; charset=utf-8"
}

def wiql_count_for_team(project_id: str, team_id: str, days: int) -> int:
    """
    Count work items changed in the last `days` for a given team.
    Uses the project/{team}/_apis/wit/wiql path to scope automatically.
    """
    cutoff = f"@Today - {days}"
    query = {
        "query": f"""
          SELECT [System.Id]
          FROM WorkItems
          WHERE [System.ChangedDate] >= {cutoff}
        """
    }
    url = f"{BASE_URL}/{project_id}/{team_id}/_apis/wit/wiql?api-version=7.1"
    resp = requests.post(url, json=query, headers=HEADERS)
    resp.raise_for_status()
    return len(resp.json().get("workItems", []))

# ─── Helpers ───
def get_paged(url: str) -> List[Dict]:
    """Generic pager (x-ms-continuationtoken)."""
    items, cont = [], None
    while True:
        resp = requests.get(url + (f"&continuationToken={cont}" if cont else ""), headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("value", []))
        cont = resp.headers.get("x-ms-continuationtoken")
        if not cont:
            break
    return items

def wiql_count(project_name: str, days: int) -> int:
    """Count work items changed in the last `days` via org-level WIQL."""
    cutoff = f"@Today - {days}"
    query = {
        "query": f"""
          SELECT [System.Id]
          FROM WorkItems
          WHERE [System.TeamProject] = '{project_name}'
            AND [System.ChangedDate] >= {cutoff}
        """
    }
    url = f"{BASE_URL}/_apis/wit/wiql?api-version=7.1"
    resp = requests.post(url, json=query, headers=HEADERS)
    resp.raise_for_status()
    return len(resp.json().get("workItems", []))

# ─── Audit Steps ───
def fetch_projects() -> pd.DataFrame:
    projs = get_paged(f"{BASE_URL}/_apis/projects?api-version=7.1")
    return pd.DataFrame([{"id": p["id"], "name": p["name"]} for p in projs])

def fetch_teams(project_id: str) -> List[Dict]:
    return get_paged(f"{BASE_URL}/_apis/projects/{project_id}/teams?api-version=7.1")

def build_team_audit() -> pd.DataFrame:
    projs = fetch_projects()
    rows = []

    for _, proj in projs.iterrows():
        proj_name, proj_id = proj["name"], proj["id"]
        teams = fetch_teams(proj_id)

        for team in teams:
            team_name, team_id = team["name"], team["id"]
            count = wiql_count_for_team(proj_id, team_id, DAYS_THRESHOLD)
            status = "Active" if count > 0 else "Stale"
            rows.append({
                "Project": proj_name,
                "Team": team_name,
                "Recent WI Count": count,
                "Status": status
            })

    return pd.DataFrame(rows)

# ─── Main ───
if __name__ == "__main__":
    audit_df = build_team_audit()
    now = datetime.now().strftime("%Y%m%d_%H%M")
    path = f"ado_team_audit_{now}.csv"
    audit_df.to_csv(path, index=False)
    print(f"✅ Team audit written to {path}  (stale cutoff = {DAYS_THRESHOLD} days)")
