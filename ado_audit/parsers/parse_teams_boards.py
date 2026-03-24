#!/usr/bin/env python3
"""Parse board detail JSON files (columns data) into CSV.

The enhanced exporter now saves complete board details (columns, rows, metadata) in
{project}_{team}_{board}.json files. This parser extracts the columns array.

Output columns: Project ID, Project Name, Team ID, Team Name, Board ID, Board Name,
Column ID, Column Name, Column Order, State Mapping, WIP Limit, Split Column
"""
import os
import sys

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json, load_project_metadata, extract_project_info, safe_name


def normalize_list(obj):
    if obj is None:
        return []
    if isinstance(obj, dict) and obj.get('value') is not None:
        return obj.get('value')
    if isinstance(obj, list):
        return obj
    return []


class TeamsBoardsParser(BaseParser):
    """Parse board columns from board detail JSON files."""
    
    def get_file_pattern(self):
        # We match all .json files and filter in parse_project_data
        return ".json"
    
    def get_output_filename(self):
        return "teams_boards_columns_parsed"
    
    def get_csv_fieldnames(self):
        return ['Project ID', 'Project Name', 'Team ID', 'Team Name', 'Board ID', 'Board Name',
                'Column ID', 'Column Name', 'Column Order', 'State Mapping', 'WIP Limit', 'Split Column']
    
    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse teams, boards, and columns for a project."""
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
        # Exclude known metadata files
        exclude_suffixes = ['_teams.json', '_project.json', '_wits.json', '_areas.json', 
                           '_iterations.json', '_backlogconfig.json', '_process_template.json',
                           '_teamsettings.json', '_backlogs.json']
        
        board_files = []
        for f in files:
            if any(f.endswith(suffix) for suffix in exclude_suffixes):
                continue
            # Board detail files should have at least 3 parts when split by _
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
            
            # Split from the right to get board name (last part)
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
            
            # Extract columns from board data
            columns = board_data.get('columns', [])
            
            for idx, col in enumerate(columns, start=1):
                maps = col.get('stateMappings') or {}
                state_str = next(iter(maps.values()), '-') if maps else '-'
                
                rows.append({
                    'Project ID': project_id,
                    'Project Name': project_name,
                    'Team ID': team_id,
                    'Team Name': team_name,
                    'Board ID': board_id,
                    'Board Name': board_name,
                    'Column ID': col.get('id', ''),
                    'Column Name': col.get('name', ''),
                    'Column Order': idx,
                    'State Mapping': state_str,
                    'WIP Limit': col.get('itemLimit', 0),
                    'Split Column': col.get('isSplit', False)
                })
        
        return rows if rows else None


if __name__ == '__main__':
    parser = TeamsBoardsParser()
    parser.run()
