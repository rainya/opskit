#!/usr/bin/env python3
"""Base class for all exporters with common project iteration logic."""
import os
import sys
import logging
from abc import ABC, abstractmethod

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure_devops.client import BASE_URL, ADOClient, save_json, report_errors
from azure_devops.utils import read_pat, safe_name
from azure_devops.config import RAW_DATA_DIR, LOG_FORMAT, LOG_LEVEL, API_VERSIONS

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)


class BaseExporter(ABC):
    """Base class for ADO data exporters.
    
    Subclasses must implement:
    - export_project_data(client, project_id, project_name, project_dir)
    """
    
    def __init__(self):
        """Initialize the exporter with PAT, client, and project filter."""
        self.project_ids = sys.argv[1:]
        self.pat = read_pat()
        self.client = ADOClient(self.pat)
        self.out_dir = RAW_DATA_DIR
        
    def fetch_all_projects(self):
        """Fetch all projects from the organization."""
        url = f"{BASE_URL}/_apis/projects?api-version={API_VERSIONS['default']}"
        return self.client.get_paged(url)
    
    def get_filtered_projects(self):
        """Fetch and filter projects based on command line arguments.
        
        Returns:
            list: Filtered list of project dictionaries
        """
        logging.info("Fetching projects...")
        try:
            projects = self.fetch_all_projects()
        except Exception as e:
            logging.error(f"Failed to fetch projects list: {str(e)}")
            sys.exit(1)
        
        if not projects:
            logging.error("No projects fetched. Check auth and ADO_ORG.")
            return []
        
        # Filter projects if user specified ids (case-insensitive for names)
        if self.project_ids:
            project_ids_upper = [pid.upper() if isinstance(pid, str) else pid for pid in self.project_ids]
            projects = [p for p in projects 
                       if p.get("id") in self.project_ids 
                       or (p.get("name") and p.get("name").upper() in project_ids_upper)] # type: ignore
        
        return projects
    
    def setup_project_folder(self, project):
        """Create project subfolder and save project metadata.
        
        Args:
            project: Project dictionary with 'id', 'name', etc.
            
        Returns:
            tuple: (project_id, project_name, safe_name, project_dir)
        """
        pid = project.get("id")
        pname = project.get("name")
        safe = safe_name(pname or pid)
        safe_lower = safe.lower()
        
        if not pid:
            logging.warning(f"Skipping project with no ID: {pname}")
            return None
        
        # Create project subfolder
        project_dir = os.path.join(self.out_dir, safe_lower)
        os.makedirs(project_dir, exist_ok=True)
        
        # Save project metadata
        save_json(project, os.path.join(project_dir, f"{safe}_project.json"))
        logging.info(f"Saved project metadata for {pname} in {safe_lower}/")
        
        return pid, pname, safe, project_dir
    
    @abstractmethod
    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Export specific data for a project. Must be implemented by subclasses.
        
        Args:
            client: ADOClient instance
            project_id: Project GUID
            project_name: Human-readable project name
            project_safe_name: Filesystem-safe project name
            project_dir: Path to project's raw data directory
        """
        pass
    
    def export_org_data(self, client):
        """Export organization-level data (optional hook for subclasses).
        
        Called once before iterating through projects. Override in subclasses
        that need to export org-level data.
        
        Args:
            client: ADOClient instance
        """
        pass
    
    def run(self):
        """Main execution: fetch projects, iterate, and export data."""
        os.makedirs(self.out_dir, exist_ok=True)
        
        # Export org-level data first (if subclass implements it)
        try:
            self.export_org_data(self.client)
        except Exception as e:
            logging.error(f"Failed to export org-level data: {str(e)}")
            sys.exit(1)
        
        projects = self.get_filtered_projects()
        if not projects:
            return
        
        for proj in projects:
            result = self.setup_project_folder(proj)
            if result is None:
                continue
            
            pid, pname, safe, project_dir = result
            
            # Call subclass-specific export logic
            try:
                self.export_project_data(self.client, pid, pname, safe, project_dir)
            except Exception as e:
                logging.error(f"Failed to export data for {pname}: {str(e)}")
                continue
        
        report_errors()
