#!/usr/bin/env python3
"""
ado_audit_refactor.py – Refactored audit of Azure DevOps Boards, Backlogs, and WIT settings, exporting to Excel.
Enhanced with tqdm progress bars for console feedback and error tracking for HTTP failures.
"""

import os
import sys
import argparse
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from tqdm import tqdm

# ───── Configuration ─────
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"
API_VERSIONS = {
    "core": "7.1",
    "work": "7.1",
    "wit": "7.1",
    "preview": "7.1-preview.1"
}
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# global error tracker
ERRORS: List[Dict[str, Any]] = []

# ───── Azure DevOps Client ─────
class ADOClient:
    """Handles HTTP interactions with Azure DevOps REST API and tracks errors."""

    def __init__(self, pat: str):
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json; charset=utf-8"
        })

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        resp = self.session.get(url)
        if resp.status_code in (403, 404, 500):
            ERRORS.append({"URL": url, "Status": resp.status_code})
            return None
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            ERRORS.append({"URL": url, "Status": resp.status_code})
            return None
        return resp.json()

    def get_paged(self, url: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        while url:
            resp = self.session.get(url)
            if resp.status_code != 200:
                ERRORS.append({"URL": url, "Status": resp.status_code})
                break
            data = resp.json()
            items.extend(data.get("value", []))
            token = resp.headers.get("x-ms-continuationtoken")
            url = f"{url}&continuationToken={token}" if token else None
        return items

# ───── Audit Extractor ─────
class AuditExtractor:
    """Extracts projects, teams, WIT states, board columns, and backlog levels using tqdm."""

    def __init__(self, client: ADOClient):
        self.client = client
        self.process_map = self._load_process_templates()

    def _load_process_templates(self) -> Dict[str, str]:
        url = f"{BASE_URL}/_apis/process/processes?api-version={API_VERSIONS['core']}"
        data = self.client.get(url) or {"value": []}
        return {item["id"]: item["name"] for item in data.get("value", [])}

    def _project_process(self, project_id: str) -> (str, str):
        url = (
            f"{BASE_URL}/_apis/projects/{project_id}/properties"
            f"?api-version={API_VERSIONS['preview']}"
        )
        data = self.client.get(url) or {"value": []}
        prop_map = {it["name"]: it["value"] for it in data.get("value", [])}
        proc_id = (
            prop_map.get("System.ProcessTemplateType") or
            prop_map.get("System.CurrentProcessTemplateId") or
            prop_map.get("System.OriginalProcessTemplateId", "")
        )
        name = (
            self.process_map.get(proc_id) or
            prop_map.get("System.Process Template", "Unknown")
        )
        return proc_id, name

    def extract_projects(self, selected: Optional[List[str]] = None) -> pd.DataFrame:
        url = f"{BASE_URL}/_apis/projects?api-version={API_VERSIONS['core']}"
        projects = self.client.get_paged(url)
        if selected:
            sel = {n.lower() for n in selected}
            projects = [p for p in projects if p["name"].lower() in sel]
            if not projects:
                sys.exit("No matching projects for specified names.")
        rows = []
        for proj in tqdm(projects, desc="Projects"):
            pid = proj["id"]
            proc_id, proc_name = self._project_process(pid)
            rows.append({
                "Project Name": proj["name"],
                "Project ID": pid,
                "Process ID": proc_id,
                "Process Name": proc_name,
                "State": proj.get("state"),
                "Visibility": proj.get("visibility")
            })
        return pd.DataFrame(rows)

    def extract_wit_states(self, projects_df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for pname, pid in tqdm(projects_df[["Project Name", "Project ID"]].values,
                               desc="WIT States by Project"):
            esc = requests.utils.quote(pname)
            url = f"{BASE_URL}/{esc}/_apis/wit/workitemtypes?api-version={API_VERSIONS['wit']}"
            data = self.client.get(url) or {}
            for wit in data.get("value", []):
                for order, state in enumerate(wit.get("states", []), 1):
                    rows.append({
                        "Project": pname,
                        "WorkItemType": wit["name"],
                        "State": state["name"],
                        "Category": state.get("category", ""),
                        "Order": order
                    })
        return pd.DataFrame(rows)

    def extract_teams_and_settings(self, projects_df: pd.DataFrame) -> (pd.DataFrame, pd.DataFrame):
        teams, settings = [], []
        for pname, pid in tqdm(projects_df[["Project Name", "Project ID"]].values,
                               desc="Teams by Project"):
            esc = requests.utils.quote(pname)
            team_list = self.client.get_paged(
                f"{BASE_URL}/_apis/projects/{pid}/teams?api-version={API_VERSIONS['core']}"
            )
            for team in tqdm(team_list, desc=f"Teams in {pname}", leave=False):
                tname, tid = team["name"], team["id"]
                teams.append({"Project": pname, "Team": tname, "Team ID": tid})
                url = (
                    f"{BASE_URL}/{esc}/{requests.utils.quote(tname)}/_apis/work/teamsettings?"
                    f"api-version={API_VERSIONS['work']}"
                )
                ts = self.client.get(url) or {}
                settings.append({
                    "Project": pname,
                    "Team": tname,
                    "Backlog Iteration": ts.get("backlogIteration", {}).get("path", ""),
                    "Working Days": ", ".join(ts.get("workingDays", [])),
                    "Bugs Behavior": ts.get("bugsBehavior", "")
                })
        return pd.DataFrame(teams), pd.DataFrame(settings)

    def extract_board_columns(self, projects_df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for pname in tqdm(projects_df["Project Name"].tolist(), desc="Boards by Project"):
            esc = requests.utils.quote(pname)
            _, teams_df = self.extract_teams_and_settings(
                projects_df[projects_df["Project Name"] == pname]
            )
            for tname in tqdm(teams_df[teams_df["Project"] == pname]["Team"].tolist(),
                               desc=f"Teams in {pname}", leave=False):
                esc_team = requests.utils.quote(tname)
                boards = (self.client.get(
                    f"{BASE_URL}/{esc}/{esc_team}/_apis/work/boards?"
                    f"api-version={API_VERSIONS['work']}"
                ) or {}).get("value", [])
                for board in tqdm(boards, desc=f"Boards in {pname}/{tname}", leave=False):
                    bid = board.get("id")
                    bname = board.get("name")
                    cols = (self.client.get(
                        f"{BASE_URL}/{esc}/{esc_team}/_apis/work/boards/{bid}/columns?"
                        f"api-version={API_VERSIONS['work']}"
                    ) or {}).get("value", [])
                    for col in cols:
                        state = ", ".join(set(col.get("stateMappings", {}).values())) or "-"
                        rows.append({
                            "Project": pname,
                            "Team": tname,
                            "Board": bname,
                            "Column": col.get("name"),
                            "WIP Limit": col.get("itemLimit", 0),
                            "Split": col.get("isSplit", False),
                            "State Mappings": state
                        })
        return pd.DataFrame(rows)

    def extract_backlogs(self, projects_df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for pname in tqdm(projects_df["Project Name"].tolist(), desc="Backlogs by Project"):
            esc = requests.utils.quote(pname)
            _, teams_df = self.extract_teams_and_settings(
                projects_df[projects_df["Project Name"] == pname]
            )
            for tname in tqdm(teams_df[teams_df["Project"] == pname]["Team"].tolist(),
                               desc=f"Teams in {pname}", leave=False):
                data = self.client.get(
                    f"{BASE_URL}/{esc}/{requests.utils.quote(tname)}/_apis/work/"
                    f"backlogconfiguration?api-version={API_VERSIONS['work']}"
                ) or {}
                for lvl in data.get("backlogLevels", []) + data.get("portfolioBacklogs", []):
                    rows.append({
                        "Project": pname,
                        "Team": tname,
                        "Backlog": lvl.get("name"),
                        "Type": lvl.get("type"),
                        "Rank": lvl.get("rank"),
                        "Hidden": lvl.get("isHidden"),
                        "WITs": "; ".join(w.get("name") for w in lvl.get("workItemTypes", []))
                    })
        return pd.DataFrame(rows)

# ───── Excel Exporter ─────
class ExcelExporter:
    """Writes multiple DataFrames to an Excel workbook."""

    def __init__(self, out_path: Path):
        self.out_path = out_path

    def write(self, sheets: Dict[str, pd.DataFrame]) -> None:
        with pd.ExcelWriter(self.out_path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)

# ───── CLI and Execution ─────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Azure DevOps boards, backlogs, and WIT settings"
    )
    parser.add_argument(
        "-p", "--project", action="append",
        help="Project name to include (repeat for multiple). Defaults to all."
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path.cwd(),
        help="Directory for output Excel file. Defaults to current directory."
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=LOG_LEVEL)
    args = parse_args()

    pat = (
        os.getenv("ADO_PAT") or
        (Path(__file__).with_name("ado_pat.txt").read_text().strip()
         if Path(__file__).with_name("ado_pat.txt").exists() else None)
    )
    if not pat:
        sys.exit("Azure DevOps PAT not found. Set ADO_PAT or place ado_pat.txt next to this script.")

    client = ADOClient(pat)
    extractor = AuditExtractor(client)

    projects_df = extractor.extract_projects(args.project)
    wit_df = extractor.extract_wit_states(projects_df)
    teams_df, settings_df = extractor.extract_teams_and_settings(projects_df)
    boards_df = extractor.extract_board_columns(projects_df)
    backlogs_df = extractor.extract_backlogs(projects_df)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    tag = ("_".join(n.replace(" ", "") for n in args.project) if args.project else "ALL")
    out_file = args.output_dir / f"ado_audit_{tag}_{timestamp}.xlsx"

    sheets = {
        "Projects": projects_df,
        "WIT_States": wit_df,
        "Teams": teams_df,
        "TeamSettings": settings_df,
        "BoardColumns": boards_df,
        "BacklogLevels": backlogs_df,
    }
    if ERRORS:
        sheets["Errors"] = pd.DataFrame(ERRORS)

    ExcelExporter(out_file).write(sheets)
    print(f"Audit complete. {len(ERRORS)} errors logged.")

if __name__ == "__main__":
    main()
