# Directory: azure_devops/audit.py
import requests
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from typing import Any, Dict, List, Optional
from azure_devops.client import ADOClient, ERRORS, BASE_URL, API_VERSIONS

class AuditExtractor:
    """Extracts projects, teams, WIT states, board columns, and backlog levels using tqdm."""

    def __init__(self, client: ADOClient):
        self.client = client
        self.process_map = self._load_process_templates()

    def _load_process_templates(self) -> Dict[str, str]:
        url = f"{BASE_URL}/_apis/process/processes?api-version={API_VERSIONS['core']}"
        data = self.client.get(url) or {"value": []}
        return {item['id']: item['name'] for item in data.get('value', [])}

    def _project_process(self, project_id: str) -> (str, str):
        url = (
            f"{BASE_URL}/_apis/projects/{project_id}/properties"
            f"?api-version={API_VERSIONS['preview']}"
        )
        data = self.client.get(url) or {"value": []}
        prop_map = {it['name']: it['value'] for it in data.get('value', [])}
        proc_id = prop_map.get('System.ProcessTemplateType') or \
                  prop_map.get('System.CurrentProcessTemplateId') or \
                  prop_map.get('System.OriginalProcessTemplateId', '')
        name = self.process_map.get(proc_id) or prop_map.get('System.Process Template', 'Unknown')
        return proc_id, name

    def extract_projects(self, selected: Optional[List[str]] = None) -> pd.DataFrame:
        url = f"{BASE_URL}/_apis/projects?api-version={API_VERSIONS['core']}"
        projects = self.client.get_paged(url)
        if selected:
            sel = {n.lower() for n in selected}
            projects = [p for p in projects if p['name'].lower() in sel]
            if not projects:
                raise ValueError(f"No matching projects for {selected}")
        rows = []
        for proj in tqdm(projects, desc='Projects'):
            pid = proj['id']
            proc_id, proc_name = self._project_process(pid)
            rows.append({
                'Project Name': proj['name'],
                'Project ID': pid,
                'Process ID': proc_id,
                'Process Name': proc_name,
                'State': proj.get('state'),
                'Visibility': proj.get('visibility')
            })
        return pd.DataFrame(rows)

    def extract_wit_states(self, projects_df: pd.DataFrame) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for pname, pid in tqdm(projects_df[['Project Name', 'Project ID']].values,
                               desc='WIT States by Project'):
            esc = requests.utils.quote(pname)
            url = (
                f"{BASE_URL}/{esc}/_apis/wit/workitemtypes"
                f"?api-version={API_VERSIONS['wit']}"
            )
            data = self.client.get(url) or {}
            for wit in data.get('value', []):
                for order, state in enumerate(wit.get('states', []), 1):
                    rows.append({
                        'Project': pname,
                        'WorkItemType': wit['name'],
                        'State': state['name'],
                        'Category': state.get('category', ''),
                        'Order': order
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

class ExcelExporter:
    """Writes multiple DataFrames to an Excel workbook."""

    def __init__(self, out_path: Path):
        self.out_path = out_path

    def write(self, sheets: Dict[str, pd.DataFrame]) -> None:
        with pd.ExcelWriter(self.out_path, engine='openpyxl') as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)