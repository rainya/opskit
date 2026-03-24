#!/usr/bin/env python3
import sys
import logging
from datetime import datetime
import pandas as pd
import requests
from tqdm import tqdm

from ado_client import BASE_URL, ORG, get_paged, HEADERS

# ─── Logging ───
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ─── Parameters ───
PROJECT_IDS = sys.argv[1:]  # if empty, we’ll load all

# ─── Fetch Helpers ───

def fetch_all_projects():
    """Return list of all project dicts in the org."""
    url = f"{BASE_URL}/_apis/projects?api-version=7.1"
    return get_paged(url)

def fetch_wit_types(project_id):
    """Return list of WIT metadata for a given project."""
    url = f"{BASE_URL}/{project_id}/_apis/wit/workitemtypes?api-version=7.1"
    return requests.get(url, headers=HEADERS).json().get('value', [])

def fetch_wit_states(project_id, wit_name):
    """Return list of state dicts for a given WIT."""
    url = (f"{BASE_URL}/{project_id}"
           f"/_apis/wit/workitemtypes/{wit_name}/states?api-version=7.1")
    return requests.get(url, headers=HEADERS).json().get('value', [])

# ─── Main ───

def main():
    # 1) Determine projects to process
    if PROJECT_IDS:
        # We’ll need names too, so fetch all and filter
        all_projects = fetch_all_projects()
        projs = [p for p in all_projects if p['id'] in PROJECT_IDS]
    else:
        projs = fetch_all_projects()

    if not projs:
        logging.error("No matching projects found. Check your IDs.")
        sys.exit(1)

    rows = []
    for proj in tqdm(projs, desc="Projects"):
        pid   = proj['id']
        pname = proj['name']

        # 2) For each WIT in this project…
        try:
            wits = fetch_wit_types(pid)
        except Exception as e:
            logging.warning(f"Failed to fetch WIT types for {pname}: {e}")
            continue

        for wit in wits:
            wit_name = wit.get('name')
            # 3) …load its states
            try:
                states = fetch_wit_states(pid, wit_name)
            except Exception as e:
                logging.warning(f"  Could not fetch states for {pname}\\{wit_name}: {e}")
                continue

            for idx, st in enumerate(states, start=1):
                rows.append({
                    'Project ID':   pid,
                    'Project Name': pname,
                    'WIT Name':     wit_name,
                    'State Name':   st.get('name'),
                    'State Category': st.get('category'),
                    'State Order':  idx
                })

    # 4) Dump to CSV
    df = pd.DataFrame(rows)
    now = datetime.now().strftime("%Y%m%d_%H%M")
    outfile = f"wit_states_export_{now}.csv"
    df.to_csv(outfile, index=False)
    print(f"✅ Exported {len(df)} rows to {outfile}")

if __name__ == "__main__":
    main()
