#!/usr/bin/env python3
"""
Audit Azure DevOps projects → teams hierarchy and export to Excel.

Requires: requests, pandas, openpyxl, tqdm
"""

import os
import base64
import requests
from pathlib import Path
from datetime import datetime

import pandas as pd
from tqdm import tqdm

ORG         = "1id"
API_VERSION = "7.1-preview.3"
BASE_URL    = f"https://dev.azure.com/{ORG}"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def get_pat() -> str:
    pat = os.getenv("ADO_PAT")
    if pat:
        return pat.strip()

    pat_file = Path(__file__).with_name("ado_pat.txt")
    if pat_file.exists():
        return pat_file.read_text().strip()

    raise RuntimeError("Personal Access Token not found in ADO_PAT or ado_pat.txt")


def make_session(pat: str) -> requests.Session:
    token = base64.b64encode(f":{pat}".encode()).decode()
    sess = requests.Session()
    sess.headers.update({
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json; charset=utf-8"
    })
    return sess


def paged_get(sess: requests.Session, url: str):
    """Yield items, following x-ms-continuationtoken when present."""
    while url:
        resp = sess.get(url)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])

        token = resp.headers.get("x-ms-continuationtoken")
        url = f"{url}&continuationToken={token}" if token else None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    pat     = get_pat()
    session = make_session(pat)

    # -- projects ----------------------------------------------------------- #
    proj_url  = f"{BASE_URL}/_apis/projects?api-version={API_VERSION}"
    projects  = list(paged_get(session, proj_url))
    print(f"\nFound {len(projects)} projects in organization '{ORG}':\n")

    rows = []  # collect for Excel

    for project in tqdm(projects, desc="Projects", unit="proj"):
        project_id   = project["id"]
        project_name = project["name"]
        print(f"📁 Project: {project_name}")

        team_url = (
            f"{BASE_URL}/_apis/projects/{project_id}/teams"
            f"?api-version={API_VERSION}"
        )
        teams = list(paged_get(session, team_url))

        for team in teams:
            team_name = team["name"]
            team_url_rest = team["url"]            # REST URL (quick win)
            rows.append(
                {
                    "Project Name": project_name,
                    "Team Name"   : team_name,
                    "Team URL"    : team_url_rest,
                }
            )
            print(f"   └── 👥 Team: {team_name}")
        print()

    # -- export to Excel ---------------------------------------------------- #
    if rows:
        df = pd.DataFrame(rows)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        outfile = f"ado_projects_teams_{ts}.xlsx"
        df.to_excel(outfile, index=False, engine="openpyxl")
        print(f"\n✅ Data exported to '{outfile}' ({len(df)} rows).")
    else:
        print("\n⚠️  No teams found; nothing exported.")


if __name__ == "__main__":
    main()
