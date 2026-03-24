#!/usr/bin/env python3
"""Export teams and full board details (columns, swimlanes, metadata) as raw JSON into _data/raw/.

This exporter calls the board GET detail endpoint which returns:
- Board metadata (id, name, revision, isValid, canEdit)
- Columns array (with state mappings, WIP limits, split flags)
- Rows array (swimlanes/lanes)
- Allowed state mappings per column type
- Custom field references (columnField, rowField, doneField)

Usage:
  python exporters/export_teams_boards_raw.py [project_id ...]

If no project IDs are provided, the script will export for all projects in the org.
"""
import os
import sys
import logging

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_exporter import BaseExporter
from azure_devops.client import BASE_URL, save_json
from azure_devops.utils import safe_name
from azure_devops.config import API_VERSIONS


class TeamsboardsExporter(BaseExporter):
    """Export teams and complete board details for projects."""
    
    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Export teams and full board details for a single project."""
        # Fetch teams
        logging.info(f"Fetching teams for {project_name}...")
        url_teams = f"{BASE_URL}/_apis/projects/{project_id}/teams?api-version={API_VERSIONS['teams']}"
        teams = client.get_paged(url_teams)
        save_json(teams, os.path.join(project_dir, f"{project_safe_name}_teams.json"))
        logging.info(f"Saved {project_safe_name}_teams.json in {project_dir}/")

        # For each team, fetch board list to get board IDs, then fetch full details
        for team in teams:
            tid = team.get("id")
            tname = team.get("name")
            tsafe = safe_name(tname or tid)

            try:
                logging.info(f"  Fetching boards list for {project_name}/{tname}...")
                url_boards_list = f"{BASE_URL}/{project_id}/{tid}/_apis/work/boards?api-version={API_VERSIONS['boards']}"
                boards_list = client.get_paged(url_boards_list)
                
                if not boards_list:
                    logging.info(f"  No boards found for {project_name}/{tname}")
                    continue

                # For each board, fetch full details (includes columns, rows, mappings, fields)
                for board_summary in boards_list:
                    board_id = board_summary.get("id")
                    bname = board_summary.get("name") or board_id
                    bsafe = safe_name(bname)
                    
                    logging.info(f"    Fetching board detail for {project_name}/{tname}/{bname}...")
                    
                    try:
                        # GET board detail - returns columns, rows (swimlanes), allowedMappings, fields
                        url_board_detail = f"{BASE_URL}/{project_id}/{tid}/_apis/work/boards/{board_id}?api-version={API_VERSIONS['boards']}"
                        board_detail = client.get_raw(url_board_detail)
                        
                        # Save complete board detail
                        save_json(board_detail, os.path.join(project_dir, f"{project_safe_name}_{tsafe}_{bsafe}.json"))
                        
                        col_count = len(board_detail.get('columns', []))
                        row_count = len(board_detail.get('rows', []))
                        logging.info(f"    Saved {project_safe_name}_{tsafe}_{bsafe}.json ({col_count} columns, {row_count} swimlanes)")
                        
                    except Exception as e:
                        logging.error(f"    Failed to fetch board detail for {bname}: {e}")
                        continue
                        
            except Exception as e:
                logging.error(f"  Failed to fetch boards for team {tname}: {e}")
                continue


if __name__ == "__main__":
    exporter = TeamsboardsExporter()
    exporter.run()

