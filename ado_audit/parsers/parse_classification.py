#!/usr/bin/env python3
"""Parse classification node JSON files in _data/raw/ and produce CSVs for areas and iterations."""
import os
import sys
from pathlib import Path

# Add current directory to path so we can import from utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_parser import BaseParser
from utils import load_json, load_project_metadata, extract_project_info


def extract_paths(node, prefix=""):
    """Extract hierarchical paths from classification nodes using pathlib for cross-platform paths."""
    if prefix:
        current_path = Path(prefix) / node.get('name')
        current = str(current_path)
    else:
        current = node.get('name')
    yield current, node
    for child in node.get('children', []) or []:
        yield from extract_paths(child, current)


def parse_node_file(path, node_type, project_id, project_name):
    obj = load_json(path)
    if not obj:
        return []
    rows = []
    # Some exporters saved the node root directly; others may save a dict with 'value'
    root = obj
    if isinstance(obj, dict) and obj.get('value'):
        # Unexpected but handle gracefully
        value = obj.get('value')
        if isinstance(value, list) and value:
            root = value[0]

    for path_str, node in extract_paths(root):
        # Calculate depth by counting path separators, works on all platforms
        depth = len(Path(path_str).parts) if path_str else 0
        start = node.get('attributes', {}).get('startDate') if node.get('attributes') else node.get('startDate')
        finish = node.get('attributes', {}).get('finishDate') if node.get('attributes') else node.get('finishDate')
        node_id = node.get('id') or node.get('identifier') or ''
        rows.append({
            'Project ID': project_id,
            'Project Name': project_name,
            'Node Type': node_type,
            'Path': path_str,
            'Depth': depth,
            'Node ID': node_id,
            'Start Date': start,
            'Finish Date': finish
        })
    return rows



class ClassificationParser(BaseParser):
    """Parse classification nodes (areas and iterations) from JSON files."""
    
    def get_file_pattern(self):
        # We look for both areas and iterations, so return a generic pattern
        return "_areas.json"
    
    def get_output_filename(self):
        return "classification_nodes_parsed"
    
    def get_csv_fieldnames(self):
        return ['Project ID', 'Project Name', 'Node Type', 'Path', 'Depth', 'Node ID', 'Start Date', 'Finish Date']
    
    def find_project_folders(self):
        """Override to handle both areas and iterations files."""
        if not os.path.isdir(self.raw_dir):
            return []
        # Return projects that have either areas or iterations files
        folders = []
        for d in os.listdir(self.raw_dir):
            dir_path = os.path.join(self.raw_dir, d)
            if os.path.isdir(dir_path):
                has_classification = any(
                    f.endswith("_areas.json") or f.endswith("_iterations.json")
                    for f in os.listdir(dir_path)
                )
                if has_classification:
                    folders.append(d)
        return folders
    
    def parse_project_data(self, project_folder, project_raw_dir, files):
        """Parse classification nodes for a project."""
        all_rows = []
        
        # Find all classification files (areas and iterations)
        all_files = os.listdir(project_raw_dir)
        areas_files = [f for f in all_files if f.endswith("_areas.json")]
        iterations_files = [f for f in all_files if f.endswith("_iterations.json")]
        
        # Process areas
        for areas_file in areas_files:
            prefix = areas_file.replace("_areas.json", "")
            proj_meta = load_project_metadata(prefix, project_raw_dir)
            project_id, project_name = extract_project_info(proj_meta, prefix)
            
            areas_path = os.path.join(project_raw_dir, areas_file)
            all_rows.extend(parse_node_file(areas_path, 'Area', project_id, project_name))
        
        # Process iterations
        for iterations_file in iterations_files:
            prefix = iterations_file.replace("_iterations.json", "")
            proj_meta = load_project_metadata(prefix, project_raw_dir)
            project_id, project_name = extract_project_info(proj_meta, prefix)
            
            iterations_path = os.path.join(project_raw_dir, iterations_file)
            all_rows.extend(parse_node_file(iterations_path, 'Iteration', project_id, project_name))
        
        return all_rows if all_rows else None


if __name__ == '__main__':
    parser = ClassificationParser()
    parser.run()
