#!/usr/bin/env python3
"""Export organization-level process definitions as raw JSON into _data/raw/.

This exporter captures:
- All processes defined at org level (Agile, Scrum, CMMI, custom inherited)
- Process details (parent references for inherited processes)
- WIT inventory per process
- State definitions per WIT
- Custom fields per process
- Rules for Feature and User Story WITs (high diagnostic value)

Usage:
  python exporters/export_process_org_raw.py

This is org-level only — no project filtering applies.
"""
import os
import sys
import logging

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_exporter import BaseExporter
from azure_devops.client import BASE_URL, ORG, save_json
from azure_devops.utils import safe_name
from azure_devops.config import API_VERSIONS


class ProcessOrgExporter(BaseExporter):
    """Export organization-level process definitions."""
    
    def __init__(self):
        """Initialize with org-specific output directory."""
        super().__init__()
        # Override output directory to org-specific folder
        self.out_dir = os.path.join(self.out_dir, f"_{ORG}")
        os.makedirs(self.out_dir, exist_ok=True)
    
    def get_filtered_projects(self):
        """Override to skip project iteration — this is org-level only."""
        return []
    
    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Not used — this exporter only handles org-level data."""
        pass
    
    def export_org_data(self, client):
        """Export all org-level process data."""
        logging.info("Fetching organization-level processes...")
        
        # 1. Fetch all processes defined at org level
        url_processes = f"{BASE_URL}/_apis/work/processes?api-version={API_VERSIONS['work']}"
        processes = client.get_paged(url_processes)
        save_json(processes, os.path.join(self.out_dir, "org_processes.json"))
        logging.info(f"Saved org_processes.json ({len(processes)} processes)")
        
        # 2-6. For each process, fetch detail, WITs, states, fields, rules
        for process in processes:
            process_type_id = process.get("typeId")
            process_name = process.get("name", process_type_id)
            
            if not process_type_id:
                logging.warning(f"Skipping process with no typeId: {process}")
                continue
            
            # Create per-process subfolder under processes/
            process_folder = safe_name(process_name).lower()
            process_dir = os.path.join(self.out_dir, "processes", process_folder)
            os.makedirs(process_dir, exist_ok=True)
            
            logging.info(f"Processing: {process_name} -> {process_folder}/")
            
            # 2. Process detail (includes parent process reference)
            self._export_process_detail(client, process_type_id, process_name, process_dir)
            
            # 3. WIT list
            wits = self._export_process_wits(client, process_type_id, process_name, process_dir)
            
            # 4. States for each WIT
            if wits:
                self._export_wit_states(client, process_type_id, process_name, wits, process_dir)
            
            # 5. Fields defined in process
            self._export_process_fields(client, process_type_id, process_name, process_dir)
            
            # 6. Rules for Feature and User Story (scoped for initial audit)
            if wits:
                self._export_wit_rules(client, process_type_id, process_name, wits, process_dir)
    
    def _export_process_detail(self, client, process_type_id, process_name, process_dir):
        """Export process detail including parent reference."""
        logging.info(f"  Fetching process detail for {process_name}...")
        url = f"{BASE_URL}/_apis/work/processes/{process_type_id}?api-version={API_VERSIONS['work']}"
        
        try:
            detail = client.get_raw(url)
            save_json(detail, os.path.join(process_dir, f"{process_type_id}_process_detail.json"))
            logging.info(f"  Saved {process_type_id}_process_detail.json")
        except Exception as e:
            logging.error(f"  Failed to fetch process detail for {process_name}: {e}")
    
    def _export_process_wits(self, client, process_type_id, process_name, process_dir):
        """Export WIT list for a process. Returns WIT list for further processing."""
        logging.info(f"  Fetching WITs for {process_name}...")
        url = f"{BASE_URL}/_apis/work/processes/{process_type_id}/workitemtypes?api-version={API_VERSIONS['work']}"
        
        try:
            wits = client.get_paged(url)
            save_json(wits, os.path.join(process_dir, f"{process_type_id}_wits.json"))
            logging.info(f"  Saved {process_type_id}_wits.json ({len(wits)} WITs)")
            return wits
        except Exception as e:
            logging.error(f"  Failed to fetch WITs for {process_name}: {e}")
            return []
    
    def _export_wit_states(self, client, process_type_id, process_name, wits, process_dir):
        """Export states for each WIT in the process."""
        for wit in wits:
            wit_ref_name = wit.get("referenceName")
            wit_name = wit.get("name", wit_ref_name)
            
            if not wit_ref_name:
                logging.warning(f"  Skipping WIT with no referenceName: {wit}")
                continue
            
            logging.info(f"    Fetching states for {process_name}/{wit_name}...")
            url = f"{BASE_URL}/_apis/work/processes/{process_type_id}/workitemtypes/{wit_ref_name}/states?api-version={API_VERSIONS['work']}"
            
            try:
                states = client.get_paged(url)
                wsafe = safe_name(wit_ref_name)
                save_json(states, os.path.join(process_dir, f"{process_type_id}_{wsafe}_states.json"))
                logging.info(f"    Saved {process_type_id}_{wsafe}_states.json ({len(states)} states)")
            except Exception as e:
                logging.error(f"    Failed to fetch states for {wit_name}: {e}")
    
    def _export_process_fields(self, client, process_type_id, process_name, process_dir):
        """Export custom fields defined in the process."""
        logging.info(f"  Fetching fields for {process_name}...")
        url = f"{BASE_URL}/_apis/work/processes/{process_type_id}/fields?api-version={API_VERSIONS['work']}"
        
        try:
            fields = client.get_paged(url)
            save_json(fields, os.path.join(process_dir, f"{process_type_id}_fields.json"))
            logging.info(f"  Saved {process_type_id}_fields.json ({len(fields)} fields)")
        except Exception as e:
            logging.error(f"  Failed to fetch fields for {process_name}: {e}")
    
    def _export_wit_rules(self, client, process_type_id, process_name, wits, process_dir):
        """Export rules for Feature and User Story WITs only (scoped for initial audit)."""
        target_wits = ['Microsoft.VSTS.WorkItemTypes.Feature', 'Microsoft.VSTS.WorkItemTypes.UserStory']
        
        for wit in wits:
            wit_ref_name = wit.get("referenceName")
            wit_name = wit.get("name", wit_ref_name)
            
            if wit_ref_name not in target_wits:
                continue
            
            logging.info(f"    Fetching rules for {process_name}/{wit_name}...")
            url = f"{BASE_URL}/_apis/work/processes/{process_type_id}/workitemtypes/{wit_ref_name}/rules?api-version={API_VERSIONS['work']}"
            
            try:
                rules = client.get_paged(url)
                wsafe = safe_name(wit_ref_name)
                save_json(rules, os.path.join(process_dir, f"{process_type_id}_{wsafe}_rules.json"))
                logging.info(f"    Saved {process_type_id}_{wsafe}_rules.json ({len(rules)} rules)")
            except Exception as e:
                logging.error(f"    Failed to fetch rules for {wit_name}: {e}")


if __name__ == "__main__":
    exporter = ProcessOrgExporter()
    exporter.run()
