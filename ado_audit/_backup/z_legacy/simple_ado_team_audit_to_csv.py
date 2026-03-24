#!/usr/bin/env python3
import os, sys, base64, requests, pandas as pd
from datetime import datetime
from typing import List, Dict

# ─── Configuration ───
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"
DAYS_THRESHOLD = 90  # “Stale” if no changes in this many days

# ─── Authentication ───
# PAT retrieval: env ADO_PAT or ado_pat.txt
pat = (
    (open("ado_pat.txt").read().strip() if os.path.exists("ado_pat.txt") else None)
)
if not pat:
    sys.exit("🔑 ADO_PAT not found in environment or ado_pat.txt")
token = base64.b64encode(f":{pat}".encode()).decode()
HEADERS = {"Authorization": f"Basic {token}", "Content-Type": "application/json; charset=utf-8"}

# ─── Helpers ───
def get_paged(url: str) -> List[Dict]:
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

def fetch_projects() -> pd.DataFrame:
    projs = get_paged(f"{BASE_URL}/_apis/projects?api-version=7.1")
    return pd.DataFrame([{"id": p["id"], "name": p["name"]} for p in projs])

def fetch_teams(project_id: str) -> List[Dict]:
    return get_paged(f"{BASE_URL}/_apis/projects/{project_id}/teams?api-version=7.1")

def fetch_team_area_paths(project_id: str, team_id: str) -> List[str]:
    url = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/teamsettings/teamfieldvalues?api-version=7.1"
    resp = requests.get(url, headers=HEADERS); resp.raise_for_status()
    return [v["value"] for v in resp.json().get("values", [])]

def wiql_count_for_team(project_name: str, area_paths: List[str], days: int) -> int:
    """
    Count WIs under the team's area paths changed in the last `days`.
    If the team has no areas, return 0.
    """
    if not area_paths:
        return 0

    cutoff = f"@Today - {days}"
    area_clause = " OR ".join(f"[System.AreaPath] UNDER '{p}'" for p in area_paths)
    query = {
        "query": (
            "SELECT [System.Id] FROM WorkItems "
            "WHERE "
            f"[System.TeamProject] = '{project_name}' AND "
            f"({area_clause}) AND "
            f"[System.ChangedDate] >= {cutoff}"
        )
    }
    url = f"{BASE_URL}/_apis/wit/wiql?api-version=7.1"
    resp = requests.post(url, json=query, headers=HEADERS)
    resp.raise_for_status()
    return len(resp.json().get("workItems", []))


# ─── Audit ───
def build_team_audit() -> pd.DataFrame:
    rows = []
    for _, proj in fetch_projects().iterrows():
        for team in fetch_teams(proj["id"]):
            areas = fetch_team_area_paths(proj["id"], team["id"])
            count = wiql_count_for_team(proj["name"], areas, DAYS_THRESHOLD)
            rows.append({
                "Project": proj["name"],
                "Team":    team["name"],
                "WI Count": count,
                "Status":   "Active" if count > 0 else "Stale"
            })
    return pd.DataFrame(rows)

def main():
    df = build_team_audit()
    fname = f"ado_team_audit_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df.to_csv(fname, index=False)
    print(f"✅ Team audit written to {fname}  (stale cutoff = {DAYS_THRESHOLD} days)")

if __name__ == "__main__":
    main()
