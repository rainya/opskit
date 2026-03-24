#!/usr/bin/env python3
"""
Audit Azure DevOps projects → teams hierarchy.

• Reads a Personal Access Token (PAT) from the ADO_PAT env-var
  (falls back to ado_pat.txt for convenience).
• Uses project *IDs* (GUIDs) when calling the Teams endpoint.
• Reuses a single requests.Session for efficiency.
• Transparently handles server-side pagination via the
  x-ms-continuationtoken header.
"""

import os
import base64
import requests
from pathlib import Path

ORG = "1id"
API_VERSION = "7.1-preview.3"   # bump when Microsoft bumps
BASE_URL = f"https://dev.azure.com/{ORG}"


def get_pat() -> str:
    """Return the PAT from env-var or ado_pat.txt (same dir)."""
    pat = os.getenv("ADO_PAT")
    if pat:
        return pat.strip()

    pat_file = Path(__file__).with_name("ado_pat.txt")
    if pat_file.exists():
        return pat_file.read_text().strip()

    raise RuntimeError("Personal Access Token not found in ADO_PAT or ado_pat.txt")


def make_session(pat: str) -> requests.Session:
    """Return a configured requests.Session with Basic-Auth header set."""
    token = base64.b64encode(f":{pat}".encode()).decode()
    sess = requests.Session()
    sess.headers.update({
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json; charset=utf-8"
    })
    return sess


def paged_get(sess: requests.Session, url: str):
    """Yield items from a paged Azure DevOps REST collection."""
    while url:
        resp = sess.get(url)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])

        # continuation token header means more pages
        token = resp.headers.get("x-ms-continuationtoken")
        url = f"{url}&continuationToken={token}" if token else None


def main():
    pat = get_pat()
    session = make_session(pat)

    # --- list projects ----------------------------------------------------
    proj_url = f"{BASE_URL}/_apis/projects?api-version={API_VERSION}"
    projects = list(paged_get(session, proj_url))
    print(f"\nFound {len(projects)} projects in organization '{ORG}':\n")

    # --- iterate projects -> teams ----------------------------------------
    for project in projects:
        project_id = project["id"]          # GUID
        project_name = project["name"]
        print(f"📁 Project: {project_name}")

        team_url = (
            f"{BASE_URL}/_apis/projects/{project_id}/teams"
            f"?api-version={API_VERSION}"
        )
        teams = list(paged_get(session, team_url))
        for team in teams:
            print(f"   └── 👥 Team: {team['name']}")
        print()  # blank line between projects


if __name__ == "__main__":
    main()