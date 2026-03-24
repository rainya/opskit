#!/usr/bin/env python3
import sys
import logging
from datetime import datetime
import pandas as pd
import requests
from tqdm import tqdm

from ado_client import BASE_URL, HEADERS, get_paged

# ─── Logging ───
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ─── Fetch Helpers ───
def fetch_all_projects():
    """Return list of all project dicts in the org."""
    url = f"{BASE_URL}/_apis/projects?api-version=7.1"
    return get_paged(url)

def fetch_teams(project_id: str):
    """Return list of team dicts for a project."""
    url = f"{BASE_URL}/_apis/projects/{project_id}/teams?api-version=7.1"
    return get_paged(url)

def fetch_boards(project_id: str, team_id: str):
    """Return list of board dicts for a team."""
    url = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/boards?api-version=7.1"
    return get_paged(url)

def fetch_board_columns(project_id: str, team_id: str, board_name: str):
    """Return list of column dicts for a board."""
    url = (
        f"{BASE_URL}/{project_id}/{team_id}"
        f"/_apis/work/boards/{board_name}/columns?api-version=7.1"
    )
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get('value', [])

# ─── Main ───
def main():
    # 1) Collect target project IDs
    args = sys.argv[1:]
    if args:
        target_ids = set(args)
        all_projects = fetch_all_projects()
        projects = [p for p in all_projects if p['id'] in target_ids]
        missing = target_ids - {p['id'] for p in projects}
        if missing:
            logging.warning(f"These IDs not found and will be skipped: {missing}")
    else:
        projects = fetch_all_projects()

    if not projects:
        logging.error("No projects to process. Exiting.")
        sys.exit(1)

    # 2) Walk through each project → team → board → column
    rows = []
    for proj in tqdm(projects, desc="Projects"):
        pid   = proj['id']
        pname = proj['name']
        try:
            teams = fetch_teams(pid)
        except Exception as e:
            logging.warning(f"Failed to fetch teams for {pname}: {e}")
            continue

        for team in teams:
            tid   = team['id']
            tname = team['name']
            try:
                boards = fetch_boards(pid, tid)
            except Exception as e:
                logging.warning(f"  Failed to fetch boards for {pname}\\{tname}: {e}")
                continue

    for board in boards:
        bid   = board.get('id','')
        bname = board.get('name','')
        try:
            cols = fetch_board_columns(pid, tid, bname)
        except Exception as e:
            logging.warning(f"    Failed to fetch columns for {pname}\\{tname}\\{bname}: {e}")
            continue

        for idx, col in enumerate(cols, start=1):
            maps = col.get('stateMappings', {}) or {}
            state_str = next(iter(maps.values()), '-')
            rows.append({
                'Project ID':    pid,
                'Project Name':  pname,
                'Team ID':       tid,
                'Team Name':     tname,
                'Board ID':      bid,
                'Board Name':    bname,
                'Column ID':     col.get('id',''),
                'Column Name':   col.get('name',''),
                'Column Order':  idx,                         # ← new
                #'State Mapping': ", ".join(col.get('stateMappings',{}).values()) or '-',
                'State Mapping': state_str,
                'WIP Limit':     col.get('itemLimit',0),
                'Split Column':  col.get('isSplit',False)
            })

    # 3) Export to CSV
    df = pd.DataFrame(rows)
    now = datetime.now().strftime("%Y%m%d_%H%M")
    outfile = f"teams_boards_columns_{now}.csv"
    df.to_csv(outfile, index=False)
    print(f"✅ Exported {len(df)} rows to {outfile}")

if __name__ == "__main__":
    main()
