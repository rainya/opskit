#!/usr/bin/env python3
import os
import sys
import base64
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict

# ─── Config & Auth (from your refactor) ───
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"
# PAT retrieval: env ADO_PAT or ado_pat.txt
pat = (
    os.getenv("ADO_PAT")
    or (open("ado_pat.txt").read().strip() if os.path.exists("ado_pat.txt") else None)
)
pat = "G2jzdo870EXBrTmVpGTcDjZqD7ROyrdYWJo79GuSD8FArIIXQ2upJQQJ99BFACAAAAAqG6F6AAASAZDO1LW9"
if not pat:
    sys.exit("🔑 ADO_PAT not found in environment or ado_pat.txt")
token = base64.b64encode(f":{pat}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {token}",
    "Content-Type": "application/json; charset=utf-8"
}

# ─── Helpers ───
def get_paged(url: str) -> List[Dict]:
    """Generic pager (x-ms-continuationtoken) from your ADOClient.get_paged."""
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

# === 3. WIQL Query for Work Item Counts (by project_id) ===
def wiql_count(project_name: str, days: int = 90) -> int:
    cutoff = f"@Today - {days}"
    query = {
        "query": f"""
          SELECT [System.Id]
          FROM WorkItems
          WHERE [System.TeamProject] = '{project_name}'
            AND [System.ChangedDate] >= {cutoff}
        """
    }
    # Generic endpoint—no project in the path
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

# === 4. Build Audit Loop ===
def build_audit(days_threshold: int = 90) -> pd.DataFrame:
    df_proj = fetch_projects()
    rows = []
    for _, proj in df_proj.iterrows():
        name, pid = proj["name"], proj["id"]
        team_list = fetch_teams(pid)
        count = wiql_count(name, days_threshold)
        status = "Active" if count > 0 else "Stale"
        rows.append({
            "Project": name,
            "Team Count": len(team_list),
            "Recent WI Count": count,
            "Status": status
        })
    return pd.DataFrame(rows)

# ─── Main ───
if __name__ == "__main__":
    audit_df = build_audit(days_threshold=90)
    now = datetime.now().strftime("%Y%m%d_%H%M")
    path = f"ado_simple_audit_{now}.csv"
    audit_df.to_csv(path, index=False)
    print(f"✅ Audit written to {path}")
