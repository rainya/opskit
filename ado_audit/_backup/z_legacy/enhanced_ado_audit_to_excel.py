#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
import logging
from tqdm import tqdm
from ado_client import BASE_URL, ORG, get_paged, HEADERS, wiql_count

# Configure logging to capture warnings for graceful failures
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

# ─── Parameters ───
PROJECT_FILTER = sys.argv[1] if len(sys.argv) > 1 else None
DAYS_THRESHOLD = 180  # days to look back from today

# ─── Fetch Functions ───

def fetch_projects(filter_name=None):
    base_url = f"{BASE_URL}/_apis/projects?api-version=7.1&includeCapabilities=true"
    projects = get_paged(base_url)
    if filter_name:
        projects = [p for p in projects if p['name'].lower() == filter_name.lower()]
    return projects


def fetch_project_properties(project_id: str) -> dict:
    """Return project-level properties used to derive process template info."""
    url = f"{BASE_URL}/_apis/projects/{project_id}/properties?api-version=7.1-preview"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    props = resp.json().get('value', [])
    return {p['name']: p.get('value') for p in props}


def fetch_process_templates():
    return get_paged(f"{BASE_URL}/_apis/process/processes?api-version=7.1")


def fetch_work_processes():
    return get_paged(f"{BASE_URL}/_apis/work/processes?api-version=7.1")


def fetch_teams(project_id):
    return get_paged(f"{BASE_URL}/_apis/projects/{project_id}/teams?api-version=7.1")


def fetch_team_settings(project_id, team_id):
    url = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/teamsettings?api-version=7.1"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def fetch_area_paths(project_id, team_id):
    url = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/teamsettings/teamfieldvalues?api-version=7.1"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return [v['value'] for v in resp.json().get('values', [])]


def fetch_area_nodes(project_id, depth=10):
    """
    Retrieves all area nodes for a project and returns a flat list of paths and IDs.
    """
    url = f"{BASE_URL}/{project_id}/_apis/wit/classificationnodes/areas?$depth={depth}&api-version=7.1"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    root = resp.json()
    nodes = []
    def recurse(node, parent_path=None):
        full_path = node['name'] if parent_path is None else f"{parent_path}\\{node['name']}"
        nodes.append({'Area Path': full_path, 'Area Path ID': node['identifier']})
        for child in node.get('children', []):
            recurse(child, full_path)
    recurse(root)
    return nodes


def fetch_wit_types(project_id):
    return get_paged(f"{BASE_URL}/{project_id}/_apis/wit/workitemtypes?api-version=7.1")


def fetch_wit_states(project_id, wit_name):
    url = f"{BASE_URL}/{project_id}/_apis/wit/workitemtypes/{wit_name}/states?api-version=7.1"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get('value', [])


def fetch_boards(project_id, team_id):
    return get_paged(f"{BASE_URL}/{project_id}/{team_id}/_apis/work/boards?api-version=7.1")


def fetch_board_columns(project_id, team_id, board_name):
    url = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/boards/{board_name}/columns?api-version=7.1"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get('value', [])


def fetch_backlog_config(project_id, team_id):
    url = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/backlogconfiguration?api-version=7.1"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json() or {}
    return data.get('backlogLevels', []) + data.get('portfolioBacklogs', [])

# ─── Build DataFrames ───

def build_process_templates_df():
    rows = []
    for pt in tqdm(fetch_process_templates(), desc='Process Templates'):
        rows.append({
            'Process Template ID': pt.get('id',''),
            'Name':              pt.get('name',''),
            'Type':              pt.get('type',''),
            'Description':       pt.get('description','')
        })
    return pd.DataFrame(rows)


def build_work_processes_df():
    rows = []
    for wp in tqdm(fetch_work_processes(), desc='Work Processes'):
        rows.append({
            'Process ID':   wp.get('typeId',''),
            'Name':        wp.get('name',''),
            'Parent ID':    wp.get('parentProcessTypeId',''),
            'Default':     wp.get('isDefault', False),
            'Enabled':     wp.get('isEnabled', False),
            'Reference':    wp.get('referenceName',''),
            'Description': wp.get('description','')
        })
    return pd.DataFrame(rows)


def build_projects_df(projects, process_map):
    rows = []
    for p in projects:
        pid = p['id']
        props = fetch_project_properties(pid)
        proc_id = (
            props.get('System.ProcessTemplateType')
            or props.get('System.CurrentProcessTemplateId')
            or props.get('System.OriginalProcessTemplateId','')
        )
        proc_name = (
            process_map.get(proc_id)
            or props.get('System.Process Template','')
        )
        #try:
            #total_wi_count = wiql_count(p.get('name',''))
        #except requests.exceptions.HTTPError as e:
        #    logging.warning(f"Failed to fetch total WI count for project {p.get('name','')}: {e}")
        #    total_wi_count = 0
        rows.append({
            'Project ID':      pid,
            'Process ID':      proc_id,
            'Project':    p.get('name',''),
            'Process':    proc_name,
            'State':           p.get('state',''),
            'Visibility':      p.get('visibility','')
            #, 'Total WI Count':  total_wi_count
        })
    return pd.DataFrame(rows)


def build_teams_df(projects):
    rows = []
    for proj in tqdm(projects, desc='Projects'):
        pid, pname = proj['id'], proj['name']
        for t in fetch_teams(pid):
            tid, tnm = t['id'], t['name']
            ts = fetch_team_settings(pid, tid)
            rows.append({
                'Project ID':        pid,
                'Team ID':           tid,
                'Project':           pname,
                'Team':              tnm,
                'Working Days':      ", ".join(ts.get('workingDays',[])),
                'Bugs Behavior':     ts.get('bugsBehavior',''),
                'Backlog Iteration': ts.get('backlogIteration',{}).get('path','')
            })
    return pd.DataFrame(rows)


def build_area_paths_df(teams):
    """
    Builds a DataFrame of *all* area paths in each project (not just team-scoped),
    with their surrogate key, WI count (last DAYS_THRESHOLD days) and status.
    """
    # 1) Determine which projects we need
    projects = fetch_projects(PROJECT_FILTER)
    rows = []

    for proj in tqdm(projects, desc='Projects→Areas'):
        proj_name = proj['name']
        proj_id   = proj['id']

        # 2) Grab the full tree of area nodes once
        try:
            nodes = fetch_area_nodes(proj_id)
        except requests.exceptions.HTTPError as e:
            logging.warning(f"Could not fetch area nodes for {proj_name}: {e}")
            continue

        for node in nodes:
            area_path   = node['Area Path']
            area_skey   = node['Area Path ID']

            # 3) Count work items in that area (DAYS_THRESHOLD window)
            try:
                #count = wiql_count(proj_name, area_path, DAYS_THRESHOLD)
                count = wiql_count(proj_name, area_path, exact=True)
            except requests.exceptions.HTTPError as e:
                logging.warning(f"WIQL count failed for {proj_name}\\{area_path}: {e}")
                count = 0

            status = 'Active' if count > 0 else 'Stale'
            rows.append({
                'ProjectSK':   proj_id,
                'AreaPathSK':  area_skey,
                'Project':     proj_name,
                'Area Path':   area_path,
                'WI Count':    count,
                'Status':      status
            })

    return pd.DataFrame(rows)

def build_area_paths_df1(teams):
    """
    Builds a DataFrame of unique area paths per project using ADO surrogate keys, WI count, and status.
    """
    # map project name to project ID
    proj_map = {proj['name']: proj['id'] for proj in fetch_projects(PROJECT_FILTER or None)}
    # preload classification node IDs
    ap_id_cache = {}
    for name, pid in proj_map.items():
        try:
            nodes = fetch_area_nodes(pid)
            ap_id_cache[name] = {n['Area Path']: n['Area Path ID'] for n in nodes}
        except requests.exceptions.HTTPError:
            ap_id_cache[name] = {}

    seen = set()
    rows = []
    for _, row in tqdm(teams.iterrows(), total=len(teams), desc='Teams'):
        project = row['Project']
        proj_id = proj_map.get(project)
        try:
            aps = fetch_area_paths(project, row['Team ID'])
        except requests.exceptions.HTTPError as e:
            logging.warning(f"Failed to fetch area paths for {project}: {e}")
            continue
        for ap in aps:
            key = (project, ap)
            if key in seen:
                continue
            seen.add(key)
            try:
                count = wiql_count(project, ap)
            except requests.exceptions.HTTPError as e:
                logging.warning(f"Failed WIQL count for {project} area '{ap}': {e}")
                count = 0
            status = 'Active' if count > 0 else 'Stale'
            rows.append({
                'Project ID':       proj_id,
                'Area Path ID':     ap_id_cache[project].get(ap),
                'Project':         project,
                'Area Path':       ap,
                'Status':          status,
                'WI Count':        count
            })
    return pd.DataFrame(rows)


def build_team_area_paths_df(teams_df):
    """Construct DataFrame mapping each team and area path to IDs."""
    rows = []
    ap_id_cache = {}
    for _, row in tqdm(teams_df.iterrows(), total=len(teams_df), desc='Team Area Paths'):
        project = row['Project']
        team_id = row['Team ID']
        # cache area node IDs per project
        if project not in ap_id_cache:
            try:
                pid = fetch_projects(project)[0]['id']
                nodes = fetch_area_nodes(pid)
                ap_id_cache[project] = {n['Area Path']: n['Area Path ID'] for n in nodes}
            except Exception:
                ap_id_cache[project] = {}
        for ap in fetch_area_paths(project, team_id):
            rows.append({
                'Project ID':    pid,
                'Team ID':       team_id,
                'Area Path ID':  ap_id_cache[project].get(ap),
                'Project':       project,
                'Team':          row['Team'],
                'Area Path':     ap
            })
    return pd.DataFrame(rows)


def build_wit_types_df(projects):
    rows = []
    for proj in tqdm(projects, desc='WIT Types'):
        for wit in fetch_wit_types(proj['id']):
            rows.append({
                'Project ID':  proj['id'],
                'Project':     proj['name'],
                'WIT':    wit['name'],
                'Description': wit.get('description','')
            })
    return pd.DataFrame(rows)


def build_wit_states_df(projects, wit_types_df):
    rows = []
    for _, row in tqdm(wit_types_df.iterrows(), total=len(wit_types_df), desc='WIT States'):
        pid = next(p['id'] for p in projects if p['name']==row['Project'])
        for order, st in enumerate(fetch_wit_states(pid, row['WIT']), start=1):
            rows.append({
                'Project ID': pid,
                'Project':    row['Project'],
                'WIT':        row['WIT'],
                'State':      st['name'],
                'Category':   st.get('category',''),
                'Order':      order
            })
    return pd.DataFrame(rows)


def build_boards_df(teams_df):
    rows = []
    for _, row in tqdm(teams_df.iterrows(), total=len(teams_df), desc='Boards'):
        project_id = row['Project ID']
        project    = row['Project']
        team_id    = row['Team ID']
        team_name  = row['Team']
        try:
            boards = fetch_boards(project, team_id)
        except requests.exceptions.HTTPError:
            continue
        for b in boards:
            rows.append({
                'Project ID': project_id,
                'Team ID':    team_id,
                'Board ID':   b.get('id',''),
                'Project':    project,
                'Team':       team_name,
                'Board':      b.get('name','')
            })
    return pd.DataFrame(rows)


def build_board_columns_df(projects, teams_df, boards_df):
    rows = []
    recs = teams_df.to_dict('records')
    for _, row in tqdm(boards_df.iterrows(), total=len(boards_df), desc='Columns'):
        project_id = row['Project ID']
        board_id   = row['Board ID']
        project    = row['Project']
        board_name = row['Board']
        team_name  = row['Team']
        # find matching team record to get Team ID
        match = [
            t for t in recs
            if t['Project'] == project and t['Team'] == team_name
        ]
        if not match:
            continue
        team_id = match[0]['Team ID']

        try:
            cols = fetch_board_columns(project_id, team_id, board_name)
        except requests.exceptions.HTTPError:
            continue

        for col in cols:
            maps = col.get('stateMappings', {}) or {}
            rows.append({
                'Project ID': project_id,
                'Team ID':    team_id,
                'Board ID':   board_id,
                'Column ID':  col.get('id', ''),
                'Project':    project,
                'Team':       team_name,
                'Board':      board_name,
                'Column':     col.get('name', ''),
                'State':      ", ".join(set(maps.values())) or '-',
                'WIP Limit':  col.get('itemLimit', 0),
                'Split':      col.get('isSplit', False)
            })
    return pd.DataFrame(rows)


def build_backlogs_df(projects, teams_df):
    rows = []
    for _, row in tqdm(teams_df.iterrows(), total=len(teams_df), desc='Backlogs'):
        project, team, tid = row['Project'], row['Team'], row['Team ID']
        pid = next((p['id'] for p in projects if p['name']==project), None)
        if not pid: continue
        try:
            bks = fetch_backlog_config(pid, tid)
        except requests.exceptions.HTTPError:
            continue
        for lvl in bks:
            rows.append({
                'Project ID': pid,
                'Team ID': tid,
                'Project': project,
                'Team':    team,
                'Backlog': lvl.get('name'),
                'Type':    lvl.get('type'),
                'Rank':    lvl.get('rank'),
                'Hidden':  lvl.get('isHidden'),
                'WITs':    "; ".join(w.get('name') for w in lvl.get('workItemTypes', []))
            })
    return pd.DataFrame(rows)

# ─── Main ───

def main():
    projects      = fetch_projects(PROJECT_FILTER)
    process_tpls  = build_process_templates_df()
    process_map   = dict(zip(process_tpls['Process Template ID'], process_tpls['Name']))
    work_procs    = build_work_processes_df()
    teams_df      = build_teams_df(projects)
    boards_df     = build_boards_df(teams_df)
    projects_df   = build_projects_df(projects, process_map)
    area_paths_df = build_area_paths_df(teams_df)
    team_area_df  = build_team_area_paths_df(teams_df)
    wit_types_df  = build_wit_types_df(projects)
    wit_states_df = build_wit_states_df(projects, wit_types_df)
    board_cols_df = build_board_columns_df(projects, teams_df, boards_df)
    backlogs_df   = build_backlogs_df(projects, teams_df)

    tag = PROJECT_FILTER.replace(' ', '_') if PROJECT_FILTER else 'ALL'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"ado_audit_{tag}_{timestamp}.xlsx"

    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        projects_df.to_excel(writer, sheet_name='Projects', index=False)
        teams_df.to_excel(writer, sheet_name='Teams', index=False)
        area_paths_df.to_excel(writer, sheet_name='Area_Paths', index=False)
        team_area_df.to_excel(writer, sheet_name='Team_Area_Paths', index=False)
        wit_types_df.to_excel(writer, sheet_name='WIT_Types', index=False)
        wit_states_df.to_excel(writer, sheet_name='WIT_States', index=False)
        boards_df.to_excel(writer, sheet_name='Boards', index=False)
        board_cols_df.to_excel(writer, sheet_name='Board_Columns', index=False)
        backlogs_df.to_excel(writer, sheet_name='Backlogs', index=False)
        process_tpls.to_excel(writer, sheet_name='Process_Templates', index=False)
        work_procs.to_excel(writer, sheet_name='Work_Processes', index=False)

    print(f"✅ Audit workbook written to {filename}")

if __name__ == '__main__':
    main()
