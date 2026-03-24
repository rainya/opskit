#!/usr/bin/env python3
"""Parse board swimlanes (rows) from board detail JSON files into CSV.

The enhanced exporter saves complete board details including the rows array (swimlanes).
This parser extracts swimlanes/lanes configuration.

Output columns: Project ID, Project Name, Team ID, Team Name, Board ID, Board Name,
Row ID, Row Name, Row Order, Is Default
"""
import os
import sys

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json, load_project_metadata, extract_project_info, safe_name


DEFAULT_SWIMLANE_ID = "00000000-0000-0000-0000-000000000000"


def normalize_list(obj):
    if obj is None:
        return []
    if isinstance(obj, dict) and obj.get('value') is not None:
        return obj.get('value')
    if isinstance(obj, list):
        return obj
    return []


class SwimlanesParser(BaseParser):
    """Parse board swimlanes from board detail JSON files."""
    
    def get_file_pattern(self):
        return ".json"
    
    def get_output_filename(self):
        return "swimlanes_parsed"
    
    def get_csv_fieldnames(self):
        return ['Project ID', 'Project Name', 'Team ID', 'Team Name', 'Board ID', 'Board Name',
                'Row ID', 'Row Name', 'Row Order', 'Is Default']
    
    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse swimlanes for a project."""
        rows = []
        
        # Get project metadata
        prefix = None
        for f in files:
            if f.endswith('_teams.json'):
                prefix = f.replace('_teams.json', '')
                break
            elif f.endswith('_project.json'):
                prefix = f.replace('_project.json', '')
                
        if not prefix:
            prefix = project_folder
        
        proj_meta = load_project_metadata(prefix, project_raw_dir)
        project_id, project_name = extract_project_info(proj_meta, prefix)
        
        # Load teams to build team lookup
        teams_path = os.path.join(project_raw_dir, f"{prefix}_teams.json")
        teams = normalize_list(load_json(teams_path))
        team_map = {safe_name(t.get('name', t.get('id', ''))): t for t in teams} # type: ignore
        
        # Find all board detail JSON files
        exclude_suffixes = ['_teams.json', '_project.json', '_wits.json', '_areas.json', 
                           '_iterations.json', '_backlogconfig.json', '_process_template.json',
                           '_teamsettings.json', '_backlogs.json']
        
        board_files = []
        for f in files:
            if any(f.endswith(suffix) for suffix in exclude_suffixes):
                continue
            if f.startswith(prefix + '_') and f.count('_') >= 2:
                board_files.append(f)
        
        # Process each board detail file
        for board_file in board_files:
            board_data = load_json(os.path.join(project_raw_dir, board_file))
            if not board_data or not isinstance(board_data, dict):
                continue
            
            # Verify it's a board detail file (has columns and rows keys)
            if 'columns' not in board_data or 'rows' not in board_data:
                continue
            
            # Extract team and board from filename: {prefix}_{team}_{board}.json
            basename = board_file.replace('.json', '')
            expected_start = prefix + '_'
            if basename.startswith(expected_start):
                rest = basename[len(expected_start):]
            else:
                rest = basename
            
            rest_parts = rest.rsplit('_', 1)
            if len(rest_parts) < 2:
                continue
            
            team_safe = rest_parts[0]
            board_safe = rest_parts[1]
            
            # Get team info from team map
            team = team_map.get(team_safe, {})
            team_id = team.get('id', '') # type: ignore
            team_name = team.get('name', team_safe) # type: ignore
            
            # Get board info from board data
            board_id = board_data.get('id', '')
            board_name = board_data.get('name', board_safe)
            
            # Extract rows (swimlanes) from board data
            swimlanes = board_data.get('rows', [])
            
            for idx, swimlane in enumerate(swimlanes, start=1):
                row_id = swimlane.get('id', '')
                row_name = swimlane.get('name') or ''
                is_default = (row_id == DEFAULT_SWIMLANE_ID)
                
                rows.append({
                    'Project ID': project_id,
                    'Project Name': project_name,
                    'Team ID': team_id,
                    'Team Name': team_name,
                    'Board ID': board_id,
                    'Board Name': board_name,
                    'Row ID': row_id,
                    'Row Name': row_name,
                    'Row Order': idx,
                    'Is Default': is_default
                })
        
        return rows if rows else None


if __name__ == '__main__':
    parser = SwimlanesParser()
    parser.run()
