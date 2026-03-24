import os
import sys
import base64
from typing import List, Dict
from requests.exceptions import HTTPError

from azure_devops import client as adoc

# Re-export helpful constants for backward compatibility
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = adoc.BASE_URL
DAYS_THRESHOLD = 180


def _read_pat() -> str:
    pat = os.getenv("ADO_PAT")
    if pat:
        return pat
    # fallback to file
    try:
        with open("ado_pat.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        sys.exit("🔑 ADO_PAT not found in env or ado_pat.txt")


ADO_PAT = _read_pat()
TOKEN = base64.b64encode(f":{ADO_PAT}".encode()).decode()
HEADERS = {"Authorization": f"Basic {TOKEN}", "Content-Type": "application/json"}


def get_client() -> adoc.ADOClient:
    """Return a configured ADOClient instance."""
    return adoc.ADOClient(ADO_PAT)


def get_paged(url: str) -> List[Dict]:
    client = get_client()
    return client.get_paged(url)

def wiql_count(project, area="", days=DAYS_THRESHOLD, exact=False):
    """
    Returns count of work items changed in the last `days` days.
    If exact=True, filters [System.AreaPath] = area; otherwise uses UNDER.
    """
    cutoff     = f"@Today - {days}"
    if area:
        op = '=' if exact else 'UNDER'
        area_clause = f"AND [System.AreaPath] {op} '{area}' "
    else:
        area_clause = ""
    query = {
        "query":
            f"SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{project}' "
            f"{area_clause}"
            f"AND [System.ChangedDate] >= {cutoff}"
    }
    url = f"{BASE_URL}/_apis/wit/wiql?api-version=7.1"
    resp = requests.post(url, json=query, headers=HEADERS)
    try:
        resp.raise_for_status()
        return len(resp.json().get("workItems", []))
    except HTTPError as e:
        # API 400 when result set >20k
        if e.response.status_code == 400 and "maximum" in e.response.text.lower():
            return 20001
        raise


def wiql_count1(project: str, area: str = "", days: int = DAYS_THRESHOLD) -> int:
    """
    Returns count of work items changed in the last `days` days.
    If `area` is blank/None, searches the whole project.
    """
    cutoff     = f"@Today - {days}"
    # only add an AreaPath clause if area is provided
    area_clause = f"AND [System.AreaPath] UNDER '{area}' " if area else ""
    query = {
        "query":
            f"SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{project}' "
            f"{area_clause}"
            f"AND [System.ChangedDate] >= {cutoff}"
    }
    url  = f"{BASE_URL}/_apis/wit/wiql?api-version=7.1"
    resp = requests.post(url, json=query, headers=HEADERS)
    resp.raise_for_status()
    return len(resp.json().get("workItems", []))

