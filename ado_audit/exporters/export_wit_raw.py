#!/usr/bin/env python3
"""Export work item types, states and fields as raw JSON into _data/raw/.

Usage:
  python exporters/export_wit_raw.py [project_id ...]

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


class WitExporter(BaseExporter):
    """Export work item types, states, and organization fields."""
    
    def export_org_data(self, client):
        """Export organization-level fields."""
        logging.info("Fetching organization fields...")
        url = f"{BASE_URL}/_apis/wit/fields?api-version={API_VERSIONS['wit']}"
        fields = client.get_raw(url)
        save_json(fields, os.path.join(self.out_dir, "fields.json"))
        logging.info("Saved fields.json")
    
    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Export work item types and states for a single project."""
        # Fetch WIT types for project
        logging.info(f"Fetching WIT types for {project_name}...")
        url_wits = f"{BASE_URL}/{project_id}/_apis/wit/workitemtypes?api-version={API_VERSIONS['wit']}"
        wits = client.get_raw(url_wits)
        save_json(wits, os.path.join(project_dir, f"{project_safe_name}_wits.json"))
        logging.info(f"Saved {project_safe_name}_wits.json")

        # For each WIT, fetch states
        wit_list = wits.get("value", []) if isinstance(wits, dict) else (wits or [])
        for wit in wit_list:
            wit_name = wit.get("name")
            if not wit_name:
                continue
            logging.info(f"  Fetching states for {project_name}/{wit_name}...")
            
            url_states = (f"{BASE_URL}/{project_id}"
                         f"/_apis/wit/workitemtypes/{wit_name}/states?api-version={API_VERSIONS['wit']}")
            states = client.get_raw(url_states)
            
            # Sanitize filename for wit name
            wsafe = safe_name(wit_name)
            save_json(states, os.path.join(project_dir, f"{project_safe_name}_{wsafe}_states.json"))


if __name__ == "__main__":
    exporter = WitExporter()
    exporter.run()
