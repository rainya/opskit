#!/usr/bin/env python3
"""Parse process template JSON files from _data/raw/ and produce a CSV.

Produces columns: Project ID, Project Name, Template Name, Template Type ID, Is Custom Inherited
"""
import os
import sys

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json

# Known base process templates
BASE_TEMPLATES = {"Agile", "Scrum", "CMMI"}


class ProcessTemplateParser(BaseParser):
    """Parse process template JSON files."""
    
    def get_file_pattern(self):
        return "_process_template.json"
    
    def get_output_filename(self):
        return "process_template_parsed"
    
    def get_csv_fieldnames(self):
        return ["Project ID", "Project Name", "Template Name", "Template Type ID", "Is Custom Inherited"]

    def get_org_output_filename(self):
        return "process_template_org_summary"
    
    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse process template for a project."""
        filepath = os.path.join(project_raw_dir, files[0])
        data = load_json(filepath)
        if not data:
            return None
        
        # Extract project info
        project_id = data.get("id", "")
        project_name = data.get("name", "")
        
        # Extract process template info from capabilities
        capabilities = data.get("capabilities", {})
        process_template = capabilities.get("processTemplate", {})
        
        template_name = process_template.get("templateName", "")
        template_type_id = process_template.get("templateTypeId", "")
        
        # Determine if custom inherited (not one of the three base templates)
        is_custom = template_name not in BASE_TEMPLATES
        
        return [{
            "Project ID": project_id,
            "Project Name": project_name,
            "Template Name": template_name,
            "Template Type ID": template_type_id,
            "Is Custom Inherited": is_custom
        }]


if __name__ == "__main__":
    parser = ProcessTemplateParser()
    parser.run()
