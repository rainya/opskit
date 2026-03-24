#!/usr/bin/env python3
"""
Fast work item counter by area path.
Outputs CSV with work item counts per area path for specified projects.

Usage:
  python workitem_counts_by_area.py                    # All projects
  python workitem_counts_by_area.py PROJECT-NAME       # Single project
  python workitem_counts_by_area.py PROJ1 PROJ2        # Multiple projects
"""
import os
import sys
import csv
import logging
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from azure_devops.client import BASE_URL, ADOClient
from azure_devops.utils import read_pat, safe_name
from azure_devops.config import API_VERSIONS, OUTPUT_DATA_DIR

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")


def get_area_paths(client, project_id, project_name):
    """Get all area paths for a project."""
    url = f"{BASE_URL}/{project_id}/_apis/wit/classificationnodes/areas?$depth=10&api-version={API_VERSIONS['classification']}"
    
    try:
        data = client.get_raw(url)
        paths = []
        
        def extract_paths(node, prefix=""):
            current = f"{prefix}\\{node['name']}" if prefix else node['name']
            paths.append(current)
            for child in node.get('children', []) or []:
                extract_paths(child, current)
        
        extract_paths(data)
        return paths
    except Exception as e:
        logging.warning(f"  Could not fetch area paths for {project_name}: {e}")
        return []


def count_work_items_in_area(client, project_name, area_path):
    """Count work items in an area path using WIQL."""
    # Escape single quotes for WIQL
    escaped_area = area_path.replace("'", "''")
    
    # WIQL query - using UNDER to include child areas
    query_text = f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{project_name}' AND [System.AreaPath] UNDER '{escaped_area}'"
    query = {"query": query_text}
    
    url = f"{BASE_URL}/_apis/wit/wiql?api-version={API_VERSIONS['wit']}"
    
    try:
        response = client.session.post(url, json=query)
        if response.status_code != 200:
            error_detail = response.text if hasattr(response, 'text') else ''
            # Check for >20k limit error
            if "VS402337" in error_detail or "20000" in error_detail:
                return -1  # Indicates >20k items
            logging.warning(f"    ⚠️  Query failed for '{area_path}': {response.status_code}")
            logging.debug(f"       Error: {error_detail[:200]}")
            logging.debug(f"       Query: {query_text}")
            return -2
        work_items = response.json().get("workItems", [])
        return len(work_items)
    except Exception as e:
        logging.warning(f"    ⚠️  Unexpected error for '{area_path}': {e}")
        return -2  # Indicates error


def main():
    """Main execution."""
    project_filter = sys.argv[1:] if len(sys.argv) > 1 else []
    
    pat = read_pat()
    client = ADOClient(pat)
    
    # Fetch projects
    logging.info("Fetching projects...")
    url = f"{BASE_URL}/_apis/projects?api-version={API_VERSIONS['default']}"
    try:
        projects = client.get_paged(url)
    except Exception as e:
        logging.error(f"Failed to fetch projects: {e}")
        sys.exit(1)
    
    # Filter projects if specified
    if project_filter:
        project_filter_upper = [pf.upper() for pf in project_filter]
        projects = [p for p in projects 
                   if p.get("id") in project_filter 
                   or (p.get("name") and p.get("name").upper() in project_filter_upper)] # type: ignore
    
    if not projects:
        logging.error("No projects found matching filter")
        sys.exit(1)
    
    logging.info(f"Processing {len(projects)} project(s)...\n")
    
    # Prepare CSV output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = os.path.join(OUTPUT_DATA_DIR, f"workitem_counts_by_area_{timestamp}.csv")
    os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)
    
    rows = []
    
    # Process each project
    for project in projects:
        project_id = project.get("id")
        project_name = project.get("name")
        
        if not project_id or not project_name:
            continue
        
        logging.info(f"📁 {project_name}")
        
        # Get area paths
        area_paths = get_area_paths(client, project_id, project_name)
        if not area_paths:
            logging.info(f"  No area paths found\n")
            continue
        
        logging.info(f"  Found {len(area_paths)} area paths, counting work items...")
        
        # Count work items in each area
        for area_path in area_paths:
            count = count_work_items_in_area(client, project_name, area_path)
            
            # Calculate depth (number of backslashes + 1)
            depth = area_path.count('\\') + 1
            
            # Format count for CSV
            if count == -1:
                count_display = '>20000'  # Exceeded API limit
            elif count == -2:
                count_display = 'ERROR'  # Query error
            else:
                count_display = str(count)
            
            rows.append({
                'Project ID': project_id,
                'Project Name': project_name,
                'Area Path': area_path,
                'Depth': depth,
                'Work Item Count': count_display
            })
        
        logging.info(f"  ✓ Counted {len(area_paths)} areas\n")
    
    # Write CSV
    fieldnames = ['Project ID', 'Project Name', 'Area Path', 'Depth', 'Work Item Count']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logging.info(f"✅ Wrote {len(rows)} rows to {output_file}")


if __name__ == "__main__":
    main()
