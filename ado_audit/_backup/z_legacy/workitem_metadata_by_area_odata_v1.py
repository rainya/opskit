#!/usr/bin/env python3
"""
Work item metadata by area path using Azure DevOps Analytics OData API.
Outputs counts by state with created/changed date ranges per area.

OData fetches all work items (no 20k WIQL limit), but aggregates client-side.
Performance: ~10k items/sec on 100Mbps connection.

For very large projects (>100k items), consider:
- Running during off-peak hours
- Using Power BI/Excel for interactive analytics
- Adding date filters to limit scope

Usage:
  python workitem_metadata_by_area_odata.py                    # All projects
  python workitem_metadata_by_area_odata.py PROJECT-NAME       # Single project
  python workitem_metadata_by_area_odata.py PROJ1 PROJ2        # Multiple projects
"""
import os
import sys
import csv
import logging
from datetime import datetime
from urllib.parse import quote

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from azure_devops.client import ADOClient
from azure_devops.utils import read_pat
from azure_devops.config import OUTPUT_DATA_DIR, API_VERSIONS
from azure_devops.client import ORG

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

# OData Analytics base URL
ANALYTICS_BASE_URL = f"https://analytics.dev.azure.com/{ORG}"


def format_date(date_string):
    """Convert ISO datetime to YYYY-MM-DD format."""
    if not date_string:
        return ""
    try:
        # Parse ISO format and return just the date part
        dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return date_string.split('T')[0] if 'T' in date_string else date_string


def get_workitem_metadata_by_area_odata(client, project_name):
    """Query OData Analytics for work item counts and metadata by area path and state.
    
    Args:
        client: ADOClient instance
        project_name: Project name
        
    Returns:
        list: List of dictionaries with aggregated data per area+state
    """
    # OData query - fetch work items with fields we need, aggregate client-side
    # $select limits the fields returned to minimize payload size
    # Note: Azure DevOps Analytics doesn't support $apply in all scenarios, so we aggregate client-side
    odata_query = f"$filter=Project/ProjectName eq '{project_name}'&$select=AreaSK,State,CreatedDate,ChangedDate"
    
    # OData endpoint - use WorkItems entity set
    url = f"{ANALYTICS_BASE_URL}/{project_name}/_odata/v3.0-preview/WorkItems?{odata_query}"
    
    try:
        logging.debug(f"  OData URL: {url}")
        
        # Fetch all work items (paginated)
        all_items = []
        next_link = url
        
        while next_link:
            response = client.session.get(next_link)
            
            if response.status_code != 200:
                logging.error(f"  ⚠️  OData query failed with status {response.status_code}")
                logging.error(f"     Error: {response.text[:500]}")
                return []
            
            data = response.json()
            all_items.extend(data.get('value', []))
            
            # Check for pagination
            next_link = data.get('@odata.nextLink')
            if next_link:
                logging.info(f"  Fetching page {len(all_items) // 10000 + 1}... ({len(all_items)} items so far)")
        
        logging.info(f"  Retrieved {len(all_items)} work items, aggregating by area+state...")
        
        # Aggregate client-side by area path + state
        aggregates = {}
        
        for item in all_items:
            # Extract area path from nested structure
            area_path = ''
            if item.get('AreaSK'):
                area_path = item['AreaSK'].get('AreaPath', '')
            
            state = item.get('State', 'Unknown')
            created = item.get('CreatedDate', '')
            changed = item.get('ChangedDate', '')
            
            # Create key for grouping
            key = (area_path, state)
            
            if key not in aggregates:
                aggregates[key] = {
                    'area_path': area_path,
                    'state': state,
                    'count': 0,
                    'created_dates': [],
                    'changed_dates': []
                }
            
            aggregates[key]['count'] += 1
            if created:
                aggregates[key]['created_dates'].append(created)
            if changed:
                aggregates[key]['changed_dates'].append(changed)
        
        # Calculate min/max dates for each group
        results = []
        for agg in aggregates.values():
            created_dates = agg['created_dates']
            changed_dates = agg['changed_dates']
            
            results.append({
                'area_path': agg['area_path'],
                'state': agg['state'],
                'count': agg['count'],
                'min_created': format_date(min(created_dates)) if created_dates else '',
                'max_created': format_date(max(created_dates)) if created_dates else '',
                'min_changed': format_date(min(changed_dates)) if changed_dates else '',
                'max_changed': format_date(max(changed_dates)) if changed_dates else ''
            })
        
        return results
        
    except Exception as e:
        logging.error(f"  ⚠️  OData query failed for {project_name}: {e}")
        return []


def calculate_area_totals(metadata_rows):
    """Calculate total counts per area across all states.
    
    Args:
        metadata_rows: List of metadata dictionaries
        
    Returns:
        dict: Mapping of area_path to total count
    """
    area_totals = {}
    for row in metadata_rows:
        area = row['area_path']
        count = row['count']
        area_totals[area] = area_totals.get(area, 0) + count
    return area_totals


def main():
    """Main execution."""
    project_filter = sys.argv[1:] if len(sys.argv) > 1 else []
    
    pat = read_pat()
    client = ADOClient(pat)
    
    # Fetch projects
    logging.info("Fetching projects...")
    url = f"https://dev.azure.com/{ORG}/_apis/projects?api-version={API_VERSIONS['default']}"
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
    
    logging.info(f"Processing {len(projects)} project(s) via OData Analytics...\n")
    
    # Prepare CSV output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = os.path.join(OUTPUT_DATA_DIR, f"workitem_metadata_by_area_odata_{timestamp}.csv")
    os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)
    
    rows = []
    
    # Process each project
    for project in projects:
        project_id = project.get("id")
        project_name = project.get("name")
        
        if not project_id or not project_name:
            continue
        
        logging.info(f"📊 {project_name}")
        logging.info(f"  Querying OData Analytics for area path metadata...")
        
        # Get metadata grouped by area + state
        metadata = get_workitem_metadata_by_area_odata(client, project_name)
        
        if not metadata:
            logging.info(f"  No data returned\n")
            continue
        
        # Calculate total counts per area
        area_totals = calculate_area_totals(metadata)
        
        # Build CSV rows
        for item in metadata:
            area_path = item['area_path']
            depth = area_path.count('\\') + 1 if area_path else 0
            
            rows.append({
                'Project ID': project_id,
                'Project Name': project_name,
                'Area Path': area_path,
                'Depth': depth,
                'State': item['state'],
                'State Count': item['count'],
                'Min Created Date': item['min_created'],
                'Max Created Date': item['max_created'],
                'Min Changed Date': item['min_changed'],
                'Max Changed Date': item['max_changed'],
                'Total Area Count': area_totals.get(area_path, 0)
            })
        
        logging.info(f"  ✓ Retrieved {len(metadata)} area+state combinations across {len(area_totals)} areas\n")
    
    # Write CSV
    fieldnames = [
        'Project ID', 'Project Name', 'Area Path', 'Depth', 'State', 'State Count',
        'Min Created Date', 'Max Created Date', 'Min Changed Date', 'Max Changed Date',
        'Total Area Count'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logging.info(f"✅ Wrote {len(rows)} rows to {output_file}")


if __name__ == "__main__":
    main()
