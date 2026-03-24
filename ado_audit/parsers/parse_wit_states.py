#!/usr/bin/env python3
"""Parse raw WIT and state JSON files from _data/raw/ and produce a CSV.

Produces columns: Project ID, Project Name, WIT Name, State Name, State Category, State Order
"""
import os
import sys

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json, load_project_metadata, extract_project_info, safe_name



class WitStatesParser(BaseParser):
    """Parse work item type states from JSON files."""
    
    def get_file_pattern(self):
        return "_wits.json"
    
    def get_output_filename(self):
        return "wit_states_parsed"
    
    def get_csv_fieldnames(self):
        return ["Project ID", "Project Name", "WIT Name", "State Name", "State Category", "State Order"]
    
    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse WIT states for a project."""
        rows = []
        
        for wf in files:
            wpath = os.path.join(project_raw_dir, wf)
            wits = load_json(wpath) or {}
            
            # Derive project safe name (prefix before _wits.json)
            prefix = wf.replace("_wits.json", "")
            
            # Load project metadata
            proj_meta = load_project_metadata(prefix, project_raw_dir)
            project_id, project_name = extract_project_info(proj_meta, prefix)
            
            # Process each work item type
            wit_list = wits.get("value") if isinstance(wits, dict) else wits
            for wit in wit_list or []:
                wit_name = wit.get("name")
                if not wit_name:
                    continue
                    
                # Load states for this WIT
                wsafe = safe_name(wit_name)
                states_file = os.path.join(project_raw_dir, f"{prefix}_{wsafe}_states.json")
                states = load_json(states_file) or {}
                state_list = states.get("value") if isinstance(states, dict) else states
                if not state_list:
                    # Fallback: states might be included in wit object
                    state_list = wit.get("states") or []
                
                # Add each state as a row
                for idx, st in enumerate(state_list, start=1):
                    rows.append({
                        "Project ID": project_id,
                        "Project Name": project_name,
                        "WIT Name": wit_name,
                        "State Name": st.get("name"),
                        "State Category": st.get("category"),
                        "State Order": idx
                    })
        
        return rows if rows else None


if __name__ == "__main__":
    parser = WitStatesParser()
    parser.run()
