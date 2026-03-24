#!/usr/bin/env python3
"""Parse team backlog level configuration JSON files from _data/raw/ and produce a CSV.

Produces columns: Project ID, Project Name, Team ID, Team Name, Backlog Level Name, 
WIT Names, Is Visible, Is Enabled
"""
import os
import sys

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json, load_project_metadata, extract_project_info, safe_name


class TeamBacklogLevelsParser(BaseParser):
    """Parse team backlog level configuration from JSON files."""
    
    def get_file_pattern(self):
        return "_backlogs.json"
    
    def get_output_filename(self):
        return "team_backlog_levels_parsed"
    
    def get_csv_fieldnames(self):
        return ["Project ID", "Project Name", "Team ID", "Team Name", "Backlog ID", 
                "Backlog Level Name", "Rank", "Work Item Count Limit"]
    
    def _find_prefix(self, project_folder, project_raw_dir, files):
        """Determine the filename prefix from known metadata files."""
        try:
            all_files = os.listdir(project_raw_dir)
        except (FileNotFoundError, PermissionError):
            return project_folder
        for f in all_files:
            if f.endswith('_teams.json'):
                return f.replace('_teams.json', '')
            if f.endswith('_project.json'):
                return f.replace('_project.json', '')
        return project_folder

    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse team backlog levels for a project."""
        rows = []
        
        # Determine the project prefix from metadata files
        prefix = self._find_prefix(project_folder, project_raw_dir, files)
        
        # Load project metadata once
        proj_meta = load_project_metadata(prefix, project_raw_dir)
        project_id, project_name = extract_project_info(proj_meta, prefix)
        
        # Load teams lookup once
        teams_file = os.path.join(project_raw_dir, f"{prefix}_teams.json")
        teams_data = load_json(teams_file)
        team_map = {}
        if teams_data:
            teams_list = teams_data.get("value") if isinstance(teams_data, dict) else teams_data
            for t in teams_list or []:
                team_map[safe_name(t.get("name", ""))] = t
        
        for backlogs_file in files:
            # Extract team safe name by stripping known prefix and suffix
            filename = os.path.basename(backlogs_file)
            stem = filename.replace("_backlogs.json", "")
            expected_start = prefix + "_"
            if stem.startswith(expected_start):
                team_safe = stem[len(expected_start):]
            else:
                team_safe = stem
            
            # Load backlog levels
            filepath = os.path.join(project_raw_dir, backlogs_file)
            backlogs_data = load_json(filepath)
            if not backlogs_data:
                continue
            
            # Resolve team ID and display name from teams lookup
            team_id = ""
            team_name = team_safe  # Fallback
            team = team_map.get(team_safe, {})
            if team:
                team_id = team.get("id", "")
                team_name = team.get("name", team_safe)
            
            # Extract backlog levels
            backlogs = backlogs_data.get("value") if isinstance(backlogs_data, dict) else backlogs_data
            
            for backlog in backlogs or []:
                backlog_id = backlog.get("id", "")
                level_name = backlog.get("name", "")
                rank = backlog.get("rank", 0)
                work_item_limit = backlog.get("workItemCountLimit", 0)
                
                rows.append({
                    "Project ID": project_id,
                    "Project Name": project_name,
                    "Team ID": team_id,
                    "Team Name": team_name,
                    "Backlog ID": backlog_id,
                    "Backlog Level Name": level_name,
                    "Rank": rank,
                    "Work Item Count Limit": work_item_limit
                })
        
        return rows if rows else None


if __name__ == "__main__":
    parser = TeamBacklogLevelsParser()
    parser.run()
