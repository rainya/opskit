#!/usr/bin/env python3
"""Parse backlog configuration JSON files from _data/raw/ and produce a CSV.

Produces columns: Project ID, Project Name, Backlog Level Name, Backlog Level Type, 
                  WIT Ref Names, WIT Display Names, Item Limit
"""
import os
import sys

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json, load_project_metadata, extract_project_info


class BacklogConfigParser(BaseParser):
    """Parse backlog configuration JSON files."""
    
    def get_file_pattern(self):
        return "_backlogconfig.json"
    
    def get_output_filename(self):
        return "backlog_config_parsed"
    
    def get_csv_fieldnames(self):
        return ["Project ID", "Project Name", "Backlog Level Name", "Backlog Level Type",
                "WIT Ref Names", "WIT Display Names", "Item Limit"]
    
    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse backlog configuration for a project."""
        rows = []
        
        # Load and parse the backlog config file
        filepath = os.path.join(project_raw_dir, files[0])
        data = load_json(filepath)
        if not data:
            return None
        
        # Extract project ID and name from metadata
        prefix = files[0].replace("_backlogconfig.json", "")
        proj_meta = load_project_metadata(prefix, project_raw_dir)
        project_id, project_name = extract_project_info(proj_meta, prefix)
        
        # Process portfolio backlogs (Epics, Features, Initiatives)
        portfolio_backlogs = data.get("portfolioBacklogs", [])
        for backlog in portfolio_backlogs:
            backlog_name = backlog.get("name", "")
            backlog_type = "Portfolio"
            
            wit_refs = [wit.get("name") for wit in backlog.get("workItemTypes", [])]
            wit_names = [wit.get("plural") or wit.get("name") for wit in backlog.get("workItemTypes", [])]
            item_limit = backlog.get("workItemCountLimit", "")
            
            rows.append({
                "Project ID": project_id,
                "Project Name": project_name,
                "Backlog Level Name": backlog_name,
                "Backlog Level Type": backlog_type,
                "WIT Ref Names": ", ".join(wit_refs) if wit_refs else "",
                "WIT Display Names": ", ".join(wit_names) if wit_names else "",
                "Item Limit": item_limit
            })
        
        # Process requirement backlog (Stories, User Stories, PBIs)
        requirement_backlog = data.get("requirementBacklog")
        if requirement_backlog:
            backlog_name = requirement_backlog.get("name", "")
            backlog_type = "Requirement"
            
            wit_refs = [wit.get("name") for wit in requirement_backlog.get("workItemTypes", [])]
            wit_names = [wit.get("plural") or wit.get("name") for wit in requirement_backlog.get("workItemTypes", [])]
            item_limit = requirement_backlog.get("workItemCountLimit", "")
            
            rows.append({
                "Project ID": project_id,
                "Project Name": project_name,
                "Backlog Level Name": backlog_name,
                "Backlog Level Type": backlog_type,
                "WIT Ref Names": ", ".join(wit_refs) if wit_refs else "",
                "WIT Display Names": ", ".join(wit_names) if wit_names else "",
                "Item Limit": item_limit
            })
        
        # Process task backlog
        task_backlog = data.get("taskBacklog")
        if task_backlog:
            backlog_name = task_backlog.get("name", "")
            backlog_type = "Task"
            
            wit_refs = [wit.get("name") for wit in task_backlog.get("workItemTypes", [])]
            wit_names = [wit.get("plural") or wit.get("name") for wit in task_backlog.get("workItemTypes", [])]
            item_limit = task_backlog.get("workItemCountLimit", "")
            
            rows.append({
                "Project ID": project_id,
                "Project Name": project_name,
                "Backlog Level Name": backlog_name,
                "Backlog Level Type": backlog_type,
                "WIT Ref Names": ", ".join(wit_refs) if wit_refs else "",
                "WIT Display Names": ", ".join(wit_names) if wit_names else "",
                "Item Limit": item_limit
            })
        
        return rows


if __name__ == '__main__':
    parser = BacklogConfigParser()
    parser.run()

