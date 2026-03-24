#!/usr/bin/env python3
"""Export classification nodes (areas and iterations) for projects into _data/raw/.

Usage:
  python exporters/export_classification_raw.py [project_id ...]

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


class ClassificationExporter(BaseExporter):
    """Export classification nodes (areas and iterations) for projects."""
    
    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Export classification nodes for a single project."""
        # Export areas
        logging.info(f"Fetching areas for {project_name}...")
        url_areas = f"{BASE_URL}/{project_id}/_apis/wit/classificationnodes/areas?$depth=10&api-version={API_VERSIONS['classification']}"
        areas = client.get_raw(url_areas)
        save_json(areas, os.path.join(project_dir, f"{project_safe_name}_areas.json"))
        logging.info(f"Saved {project_safe_name}_areas.json in {project_dir}/")
        
        # Export iterations
        logging.info(f"Fetching iterations for {project_name}...")
        url_iterations = f"{BASE_URL}/{project_id}/_apis/wit/classificationnodes/iterations?$depth=10&api-version={API_VERSIONS['classification']}"
        iterations = client.get_raw(url_iterations)
        save_json(iterations, os.path.join(project_dir, f"{project_safe_name}_iterations.json"))
        logging.info(f"Saved {project_safe_name}_iterations.json in {project_dir}/")


if __name__ == "__main__":
    exporter = ClassificationExporter()
    exporter.run()
