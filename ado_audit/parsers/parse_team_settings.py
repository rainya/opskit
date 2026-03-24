#!/usr/bin/env python3
"""Parse team settings JSON files from _data/raw/ and produce a CSV.

Produces columns: Project ID, Project Name, Team ID, Team Name, Bug Behavior, 
Bug Behavior Label, Working Days, Backlog Iteration Path
"""
import os
import sys

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json, load_project_metadata, extract_project_info, safe_name


# Bug behavior mapping to human-readable labels
BUG_BEHAVIOR_LABELS = {
    "asRequirements": "With Stories",
    "asTasks": "With Tasks",
    "off": "Not on Backlogs"
}


class TeamSettingsParser(BaseParser):
    """Parse team settings from JSON files."""
    
    def get_file_pattern(self):
        return "_teamsettings.json"
    
    def get_output_filename(self):
        return "team_settings_parsed"
    
    def get_csv_fieldnames(self):
        return ["Project ID", "Project Name", "Team ID", "Team Name", "Bug Behavior", 
                "Bug Behavior Label", "Working Days", "Backlog Iteration Path", 
                "Default Iteration Path", "Default Iteration Macro", 
                "Initiatives Visible", "Epics Visible", "Features Visible", "Stories Visible"]
    
    def _find_prefix(self, project_folder, project_raw_dir, files):
        """Determine the filename prefix from known metadata files."""
        for f in files:
            if f.endswith('_teamsettings.json'):
                continue
        # Look at all files in the directory for metadata markers
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
        """Parse team settings for a project."""
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
        
        for settings_file in files:
            # Extract team safe name by stripping known prefix and suffix
            filename = os.path.basename(settings_file)
            stem = filename.replace("_teamsettings.json", "")
            expected_start = prefix + "_"
            if stem.startswith(expected_start):
                team_safe = stem[len(expected_start):]
            else:
                # Fallback: cannot determine team portion
                team_safe = stem
            
            # Load team settings
            filepath = os.path.join(project_raw_dir, settings_file)
            settings = load_json(filepath)
            if not settings:
                continue
            
            # Resolve team ID and display name from teams lookup
            team_id = ""
            team_name = team_safe  # Fallback
            team = team_map.get(team_safe, {})
            if team:
                team_id = team.get("id", "")
                team_name = team.get("name", team_safe)
            
            # Extract settings
            bug_behavior = settings.get("bugsBehavior", "")
            bug_label = BUG_BEHAVIOR_LABELS.get(bug_behavior, bug_behavior)
            
            working_days = settings.get("workingDays", [])
            working_days_str = ", ".join(working_days) if working_days else ""
            
            backlog_iteration = settings.get("backlogIteration", {})
            backlog_path = backlog_iteration.get("path", "") if backlog_iteration else ""
            
            default_iteration = settings.get("defaultIteration", {})
            default_path = default_iteration.get("path", "") if default_iteration else ""
            
            default_iteration_macro = settings.get("defaultIterationMacro", "")
            
            # Extract backlog visibilities for common levels
            backlog_vis = settings.get("backlogVisibilities", {})
            # Common backlog level IDs - look for these patterns
            initiatives_visible = None
            epics_visible = None
            features_visible = None
            stories_visible = None
            
            for key, value in backlog_vis.items():
                if "Initiative" in key or key.startswith("Custom."):
                    initiatives_visible = value
                elif "Epic" in key:
                    epics_visible = value
                elif "Feature" in key:
                    features_visible = value
                elif "Requirement" in key or "Story" in key or "Backlog" in key:
                    stories_visible = value
            
            rows.append({
                "Project ID": project_id,
                "Project Name": project_name,
                "Team ID": team_id,
                "Team Name": team_name,
                "Bug Behavior": bug_behavior,
                "Bug Behavior Label": bug_label,
                "Working Days": working_days_str,
                "Backlog Iteration Path": backlog_path,
                "Default Iteration Path": default_path,
                "Default Iteration Macro": default_iteration_macro,
                "Initiatives Visible": initiatives_visible,
                "Epics Visible": epics_visible,
                "Features Visible": features_visible,
                "Stories Visible": stories_visible
            })
        
        return rows if rows else None


if __name__ == "__main__":
    parser = TeamSettingsParser()
    parser.run()
