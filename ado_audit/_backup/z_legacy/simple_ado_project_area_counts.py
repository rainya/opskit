#!/usr/bin/env python3
from ado_client import BASE_URL, get_paged, wiql_count, HEADERS
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict

# ─── Fetch and Build Functions ───

def fetch_projects() -> pd.DataFrame:
    """Return a DataFrame of all projects in the organization."""
    projects = get_paged(f"{BASE_URL}/_apis/projects?api-version=7.1")
    return pd.DataFrame([{"id": p["id"], "name": p["name"]} for p in projects])


def fetch_teams(project_id: str) -> List[Dict]:
    """Return a list of teams for the given project."""
    return get_paged(f"{BASE_URL}/_apis/projects/{project_id}/teams?api-version=7.1")


def fetch_team_area_paths(project_id: str, team_id: str) -> List[str]:
    """Return all area paths assigned to this team."""
    url = (
        f"{BASE_URL}/{project_id}/{team_id}/"
        "_apis/work/teamsettings/teamfieldvalues?api-version=7.1"
    )
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return [v["value"] for v in resp.json().get("values", [])]


def build_project_area_summary() -> pd.DataFrame:
    """Build a DataFrame summarizing each project-area with WI count, status, and owning teams."""
    rows = []
    for _, proj in fetch_projects().iterrows():
        proj_name, proj_id = proj["name"], proj["id"]
        # Map each child area path to its teams
        area_teams: Dict[str, List[str]] = {}
        for team in fetch_teams(proj_id):
            team_name, team_id = team["name"], team["id"]
            for area in fetch_team_area_paths(proj_id, team_id):
                if area == proj_name:
                    continue  # skip project root area
                area_teams.setdefault(area, []).append(team_name)
        # Calculate counts and status per area
        for area, teams in area_teams.items():
            count = wiql_count(proj_name, area)
            status = "Active" if count > 0 else "Stale"
            rows.append({
                "Project": proj_name,
                "Area Path": area,
                "WI Count": count,
                "Status": status,
                "Teams": ",".join(teams)
            })
    return pd.DataFrame(rows)


def main():
    df = build_project_area_summary()
    filename = f"ado_project_area_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df.to_csv(filename, index=False)
    print(f"✅ CSV written to {filename}")


if __name__ == "__main__":
    main()
