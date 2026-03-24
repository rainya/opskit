#!/usr/bin/env python3
"""Export process template information for projects into _data/raw/.

Usage:
  python exporters/export_process_template_raw.py [project_id ...]

If no project IDs are provided, the script will export for all projects in the org.
"""
import os
import sys
import logging

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_exporter import BaseExporter
from azure_devops.client import BASE_URL, save_json
from azure_devops.config import API_VERSIONS


class ProcessTemplateExporter(BaseExporter):
    """Export process template information for projects."""
    
    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Export process template for a single project."""
        logging.info(f"Fetching process template for {project_name}...")
        
        url = f"{BASE_URL}/_apis/projects/{project_id}?includeCapabilities=true&api-version={API_VERSIONS['core']}"
        project_details = client.get_raw(url)
        
        save_json(project_details, os.path.join(project_dir, f"{project_safe_name}_process_template.json"))
        logging.info(f"Saved {project_safe_name}_process_template.json in {project_dir}/")


if __name__ == "__main__":
    exporter = ProcessTemplateExporter()
    exporter.run()
