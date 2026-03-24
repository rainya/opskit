#!/usr/bin/env python3
"""
Simple Azure DevOps work item counter by area path.
Authenticates to ADO API and returns counts of work items within a specific project by area path.
"""

import os
import sys
import base64
import requests
import csv
from datetime import datetime
from typing import Dict, List, Optional


# Configuration
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"
ADO_PAT = os.getenv("ADO_PAT")

# Authentication setup
if not ADO_PAT:
    # Try reading from file if environment variable not set
    try:
        with open("ado_pat.txt", "r") as f:
            ADO_PAT = f.read().strip()
    except FileNotFoundError:
        sys.exit("🔑 ADO_PAT not found in environment or ado_pat.txt file")

if not ADO_PAT:
    sys.exit("🔑 ADO_PAT is empty")

TOKEN = base64.b64encode(f":{ADO_PAT}".encode()).decode()
HEADERS = {"Authorization": f"Basic {TOKEN}", "Content-Type": "application/json"}

# Test authentication
def test_auth() -> bool:
    """Test if authentication is working by trying to get projects."""
    url = f"{BASE_URL}/_apis/projects?api-version=7.1"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Authentication test failed: {e}")
        return False


def get_work_item_count_by_area(project_name: str, area_path: Optional[str] = None) -> int:
    """
    Get count of work items in a specific project and area path.
    
    Args:
        project_name: Name of the Azure DevOps project
        area_path: Area path to filter by (optional, if None gets all work items in project)
    
    Returns:
        Count of work items, or -1 if error occurred
    """
    # Build WIQL query - escape single quotes in area path
    if area_path:
        escaped_area = area_path.replace("'", "''")  # Escape single quotes for WIQL
        area_clause = f"AND [System.AreaPath] UNDER '{escaped_area}'"
    else:
        area_clause = ""
    
    # Use cleaner query format
    query_text = f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{project_name}' {area_clause}".strip()
    
    query = {"query": query_text}
    
    url = f"{BASE_URL}/_apis/wit/wiql?api-version=7.1"
    
    try:
        response = requests.post(url, json=query, headers=HEADERS)
        response.raise_for_status()
        
        work_items = response.json().get("workItems", [])
        return len(work_items)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            error_text = e.response.text if hasattr(e.response, 'text') else str(e)
            if "maximum" in error_text.lower() or "20000" in error_text:
                # Try to split into batches for large result sets
                print(f"⚠️  Result set too large for area '{area_path}', attempting to split into batches...")
                return get_work_item_count_by_batches(project_name, area_path)
            else:
                print(f"⚠️  Query error for area '{area_path}': {error_text}")
                print(f"   Query was: {query_text}")
                return -1  # Indicates query error
        else:
            print(f"❌ HTTP Error {e.response.status_code} for area '{area_path}': {e}")
            return -1
    except Exception as e:
        print(f"❌ Unexpected error for area '{area_path}': {e}")
        return -1


def get_work_item_count_by_batches(project_name: str, area_path: Optional[str] = None) -> int:
    """
    Count work items by splitting into batches when result set is too large.
    Uses different work item types to split the query.
    """
    print(f"   🔄 Splitting large area '{area_path}' into batches...")
    
    # Common work item types to split by
    work_item_types = [
        "Bug", "User Story", "Task", "Feature", "Epic", "Test Case", 
        "Product Backlog Item", "Issue", "Impediment", "Test Plan",
        "Test Suite", "Shared Steps", "Code Review Request", "Code Review Response",
        "Feedback Request", "Feedback Response", "Shared Parameter"
    ]
    
    total_count = 0
    successful_batches = 0
    
    if area_path:
        escaped_area = area_path.replace("'", "''")
        area_clause = f"AND [System.AreaPath] UNDER '{escaped_area}'"
    else:
        area_clause = ""
    
    for wit_type in work_item_types:
        query_text = f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{project_name}' {area_clause} AND [System.WorkItemType] = '{wit_type}'"
        query = {"query": query_text}
        url = f"{BASE_URL}/_apis/wit/wiql?api-version=7.1"
        
        try:
            response = requests.post(url, json=query, headers=HEADERS)
            response.raise_for_status()
            
            work_items = response.json().get("workItems", [])
            count = len(work_items)
            if count > 0:
                print(f"     - {wit_type}: {count} items")
                total_count += count
                successful_batches += 1
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400 and "maximum" in e.response.text.lower():
                # This work item type still has too many items, try date-based splitting
                date_count = get_work_item_count_by_date_batches(project_name, area_path, wit_type)
                if date_count > 0:
                    print(f"     - {wit_type}: {date_count} items (split by date)")
                    total_count += date_count
                    successful_batches += 1
                else:
                    print(f"     - {wit_type}: >20K items (couldn't split further)")
            # Continue with other types even if one fails
            continue
        except Exception:
            # Continue with other types even if one fails
            continue
    
    if successful_batches > 0:
        print(f"   ✅ Batched count for '{area_path}': {total_count} items from {successful_batches} batches")
        return total_count
    else:
        print(f"   ⚠️  Could not split area '{area_path}' - all batches too large")
        return 20001  # Indicate it's still too large


def get_work_item_count_by_date_batches(project_name: str, area_path: Optional[str], work_item_type: str) -> int:
    """
    Further split by date ranges when work item type batch is still too large.
    """
    date_ranges = [
        ("@Today - 30", "@Today"),          # Last 30 days
        ("@Today - 90", "@Today - 30"),     # 30-90 days ago
        ("@Today - 180", "@Today - 90"),    # 90-180 days ago
        ("@Today - 365", "@Today - 180"),   # 180-365 days ago
        ("@Today - 730", "@Today - 365"),   # 1-2 years ago
        ("@Today - 1095", "@Today - 730"),  # 2-3 years ago
        (None, "@Today - 1095")             # Older than 3 years
    ]
    
    total_count = 0
    
    if area_path:
        escaped_area = area_path.replace("'", "''")
        area_clause = f"AND [System.AreaPath] UNDER '{escaped_area}'"
    else:
        area_clause = ""
    
    for start_date, end_date in date_ranges:
        if start_date and end_date:
            date_clause = f"AND [System.ChangedDate] >= {start_date} AND [System.ChangedDate] < {end_date}"
        elif end_date:  # Only end_date (older items)
            date_clause = f"AND [System.ChangedDate] < {end_date}"
        else:
            continue
            
        query_text = f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{project_name}' {area_clause} AND [System.WorkItemType] = '{work_item_type}' {date_clause}"
        query = {"query": query_text}
        url = f"{BASE_URL}/_apis/wit/wiql?api-version=7.1"
        
        try:
            response = requests.post(url, json=query, headers=HEADERS)
            response.raise_for_status()
            
            work_items = response.json().get("workItems", [])
            count = len(work_items)
            total_count += count
            
        except requests.exceptions.HTTPError:
            # If even date batching fails, we can't count this portion
            return 0
        except Exception:
            return 0
    
    return total_count


def get_all_area_paths(project_name: str) -> List[str]:
    """
    Get all area paths for a project.
    
    Args:
        project_name: Name of the Azure DevOps project
    
    Returns:
        List of area path strings
    """
    url = f"{BASE_URL}/{project_name}/_apis/wit/classificationnodes/areas?$depth=10&api-version=7.1"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        def extract_paths(node, prefix=""):
            paths = []
            current_path = f"{prefix}\\{node['name']}" if prefix else node['name']
            paths.append(current_path)
            
            # Recursively get child area paths
            for child in node.get('children', []):
                paths.extend(extract_paths(child, current_path))
            
            return paths
        
        data = response.json()
        return extract_paths(data)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching area paths: {e}")
        return []


def main():
    """Main function to demonstrate the work item counting functionality."""
    
    print(f"🔍 Connecting to Azure DevOps: {BASE_URL}")
    
    # Test authentication first
    print("🔐 Testing authentication...")
    if not test_auth():
        print("❌ Authentication failed. Please check your PAT token.")
        return
    print("✅ Authentication successful!")
    
    # Configuration - modify these values for your specific needs
    PROJECT_NAME = "OID"  # Change this to your project name
    SPECIFIC_AREA = None  # Set to a specific area path or leave None for all areas
    MAX_AREAS_TO_TEST = 82  # Process all areas
    
    print(f"📁 Project: {PROJECT_NAME}")
    
    if SPECIFIC_AREA:
        # Count work items for a specific area
        print(f"📍 Area Path: {SPECIFIC_AREA}")
        count = get_work_item_count_by_area(PROJECT_NAME, SPECIFIC_AREA)
        print(f"📊 Work Item Count: {count}")
    else:
        # Get counts for all area paths in the project
        print("📍 Getting counts for all area paths...")
        
        area_paths = get_all_area_paths(PROJECT_NAME)
        if not area_paths:
            print("❌ No area paths found or error occurred")
            return
        
        print(f"📋 Found {len(area_paths)} area paths")
        print(f"🧪 Testing first {MAX_AREAS_TO_TEST} areas for debugging...")
        print("\n" + "="*60)
        
        total_count = 0
        error_count = 0
        test_areas = area_paths[:MAX_AREAS_TO_TEST]  # Only test first few areas
        
        # Prepare data for CSV export
        csv_data = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        
        for i, area_path in enumerate(test_areas, 1):
            print(f"Processing {i}/{len(test_areas)}: {area_path[:35]}{'...' if len(area_path) > 35 else ''}")
            count = get_work_item_count_by_area(PROJECT_NAME, area_path)
            
            if count == -1:
                error_count += 1
                print(f"{area_path:<40} | {'ERROR':>6}")
                csv_data.append({
                    'Project': PROJECT_NAME,
                    'Area_Path': area_path,
                    'Work_Item_Count': 'ERROR',
                    'Status': 'Query Error',
                    'Timestamp': timestamp
                })
            elif count > 20000:
                print(f"{area_path:<40} | {'>20K':>6} items")
                csv_data.append({
                    'Project': PROJECT_NAME,
                    'Area_Path': area_path,
                    'Work_Item_Count': '>20000',
                    'Status': 'Exceeded API Limit',
                    'Timestamp': timestamp
                })
            else:
                total_count += count
                print(f"{area_path:<40} | {count:>6} items")
                csv_data.append({
                    'Project': PROJECT_NAME,
                    'Area_Path': area_path,
                    'Work_Item_Count': count,
                    'Status': 'Success' if count < 20000 else 'Batched Count',
                    'Timestamp': timestamp
                })
        
        print("="*60)
        print(f"{'TOTAL (tested areas)':<40} | {total_count:>6} items")
        if error_count > 0:
            print(f"{'ERRORS':<40} | {error_count:>6} areas")
        
        # Write CSV file
        csv_filename = f"workitem_count_by_area_{PROJECT_NAME}_{timestamp}.csv"
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Project', 'Area_Path', 'Work_Item_Count', 'Status', 'Timestamp']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
        
        print(f"\n📄 Results exported to: {csv_filename}")
        print(f"💡 Tested {len(test_areas)} of {len(area_paths)} total area paths.")
        print(f"   To test all areas, set MAX_AREAS_TO_TEST = {len(area_paths)} in the script.")


if __name__ == "__main__":
    main()