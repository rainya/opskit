#!/usr/bin/env python3
"""Export team settings (bug behavior, working days, backlog levels) as raw JSON into _data/raw/.

Usage:
  python exporters/export_team_settings_raw.py [project_id ...]

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


class TeamSettingsExporter(BaseExporter):
    """Export team settings and backlog level configuration."""
    
    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Export team settings and backlog levels for all teams in a project."""
        # Fetch teams
        logging.info(f"Fetching teams for {project_name}...")
        url_teams = f"{BASE_URL}/_apis/projects/{project_id}/teams?api-version={API_VERSIONS['teams']}"
        teams = client.get_paged(url_teams)
        
        if not teams:
            logging.warning(f"No teams found for {project_name}")
            return
        
        logging.info(f"Found {len(teams)} teams in {project_name}")
        
        # For each team, fetch settings and backlog levels
        for team in teams:
            tid = team.get("id")
            tname = team.get("name")
            tsafe = safe_name(tname or tid)
            
            logging.info(f"  Fetching team settings for {project_name}/{tname}...")
            
            try:
                # Fetch team settings (bug behavior, working days, backlog iteration)
                url_settings = f"{BASE_URL}/{project_id}/{tid}/_apis/work/teamsettings?api-version={API_VERSIONS['work']}"
                settings = client.get_raw(url_settings)
                save_json(settings, os.path.join(project_dir, f"{project_safe_name}_{tsafe}_teamsettings.json"))
                logging.info(f"  Saved {project_safe_name}_{tsafe}_teamsettings.json")
            except Exception as e:
                logging.warning(f"  Failed to fetch team settings for {project_name}/{tname}: {str(e)}")
            
            try:
                # Fetch backlog level configuration (which WIT levels are enabled/disabled)
                url_backlogs = f"{BASE_URL}/{project_id}/{tid}/_apis/work/backlogs?api-version={API_VERSIONS['work']}"
                backlogs = client.get_raw(url_backlogs)
                save_json(backlogs, os.path.join(project_dir, f"{project_safe_name}_{tsafe}_backlogs.json"))
                logging.info(f"  Saved {project_safe_name}_{tsafe}_backlogs.json")
            except Exception as e:
                logging.warning(f"  Failed to fetch backlog levels for {project_name}/{tname}: {str(e)}")


if __name__ == "__main__":
    exporter = TeamSettingsExporter()
    exporter.run()
