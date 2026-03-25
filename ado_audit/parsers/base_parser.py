#!/usr/bin/env python3
"""Base class for all parsers with common project folder iteration logic."""
import os
import sys
import csv
from abc import ABC, abstractmethod
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure_devops.config import RAW_DATA_DIR, OUTPUT_DATA_DIR, CSV_TIMESTAMP_FORMAT
from azure_devops.client import ORG


class BaseParser(ABC):
    """Base class for ADO data parsers.
    
    Subclasses must implement:
    - get_file_pattern() - return glob pattern to find files (e.g., "*_backlogconfig.json")
    - get_output_filename() - return output filename prefix (e.g., "backlog_config_parsed")
    - parse_project_data(project_folder, project_raw_dir, files) - return list of row dicts
    - get_csv_fieldnames() - return list of CSV column names
    """
    
    def __init__(self):
        """Initialize the parser."""
        self.raw_dir = RAW_DATA_DIR
        self.output_dir = OUTPUT_DATA_DIR
        self.timestamp = datetime.now().strftime(CSV_TIMESTAMP_FORMAT)
        # Get project filter from command line args (skip script name)
        self.project_filter = sys.argv[1:] if len(sys.argv) > 1 else []
        
    def find_project_folders(self):
        """Find all project subfolders under raw data directory.
        
        Filters out:
        - Folders starting with underscore (org-level data like _1id)
        - Projects not matching project_filter if specified
        
        Returns:
            list: List of project folder names
        """
        if not os.path.isdir(self.raw_dir):
            return []
        
        # Get all folders, exclude org-level folders (starting with _)
        all_folders = [d for d in os.listdir(self.raw_dir) 
                       if os.path.isdir(os.path.join(self.raw_dir, d)) and not d.startswith('_')]
        
        # Apply project filter if specified
        if self.project_filter:
            # Case-insensitive matching
            filter_upper = [pf.upper() for pf in self.project_filter]
            filtered = [f for f in all_folders if f.upper() in filter_upper]
            return filtered
        
        return all_folders
    
    @abstractmethod
    def get_file_pattern(self):
        """Return the file pattern to search for (e.g., '_backlogconfig.json').
        
        Returns:
            str: File suffix/pattern
        """
        pass
    
    @abstractmethod
    def get_output_filename(self):
        """Return the output filename prefix (e.g., 'backlog_config_parsed').
        
        Returns:
            str: Filename prefix
        """
        pass
    
    def get_org_output_filename(self):
        """Return the org-level rollup filename prefix, or None to skip.

        Override in subclasses to enable writing all project rows into a single
        org-level CSV at output/_{ORG}/{filename}_{timestamp}.csv.

        Returns:
            str | None: Filename prefix, or None to skip org rollup
        """
        return None

    @abstractmethod
    def get_csv_fieldnames(self):
        """Return the CSV column names.
        
        Returns:
            list: List of field names
        """
        pass
    
    @abstractmethod
    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse project data and return rows for CSV.
        
        Args:
            project_folder: Name of project folder
            project_raw_dir: Path to project's raw data directory
            files: List of matching files found
            
        Returns:
            list: List of dictionaries (one per CSV row), or None to skip
        """
        pass
    
    def write_csv(self, rows, output_file):
        """Write rows to CSV file.
        
        Args:
            rows: List of dictionaries to write
            output_file: Path to output CSV file
        """
        fieldnames = self.get_csv_fieldnames()
        with open(output_file, "w", newline='', encoding='utf-8') as csvf:
            writer = csv.DictWriter(csvf, fieldnames=fieldnames) # type: ignore
            writer.writeheader()
            writer.writerows(rows)
    
    def run(self):
        """Main execution: find projects, parse data, write CSVs."""
        project_folders = self.find_project_folders()
        if not project_folders:
            print(f"No project folders found in {self.raw_dir}")
            return
        
        total_projects = 0
        all_rows = []  # accumulated across all projects for org rollup
        file_pattern = self.get_file_pattern()
        
        for project_folder in project_folders:
            project_raw_dir = os.path.join(self.raw_dir, project_folder)
            
            # Find matching files in project folder
            try:
                all_files = os.listdir(project_raw_dir)
            except (FileNotFoundError, PermissionError):
                continue
                
            files = [f for f in all_files if f.endswith(file_pattern)] # type: ignore
            
            if not files:
                print(f"No {file_pattern} file(s) found for {project_folder}, skipping")
                continue
            
            # Parse project data (subclass implementation)
            try:
                rows = self.parse_project_data(project_folder, project_raw_dir, files)
            except Exception as e:
                print(f"Error parsing {project_folder}: {str(e)}")
                continue
            
            if rows is None or not rows:
                print(f"No data found for {project_folder}, skipping")
                continue
            
            # Create output directory and write CSV
            project_output_dir = os.path.join(self.output_dir, project_folder)
            os.makedirs(project_output_dir, exist_ok=True)
            
            output_filename = f"{self.get_output_filename()}_{self.timestamp}.csv"
            output_file = os.path.join(project_output_dir, output_filename)
            
            self.write_csv(rows, output_file)
            all_rows.extend(rows)
            
            # Extract project name from first row if available
            project_name = rows[0].get("Project Name", project_folder) if rows else project_folder
            print(f"[OK] Parsed {len(rows)} row(s) for {project_name} to {output_file}")
            total_projects += 1
        
        print(f"\n[OK] Completed parsing {total_projects} project(s)")

        # Write org-level rollup if the subclass opts in
        org_filename_prefix = self.get_org_output_filename()
        if org_filename_prefix and all_rows:
            org_output_dir = os.path.join(self.output_dir, f"_{ORG}")
            os.makedirs(org_output_dir, exist_ok=True)
            org_output_file = os.path.join(org_output_dir, f"{org_filename_prefix}_{self.timestamp}.csv")
            self.write_csv(all_rows, org_output_file)
            print(f"[OK] Org rollup: {len(all_rows)} row(s) written to {org_output_file}")
