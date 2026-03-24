#!/usr/bin/env python3
"""Parse organization-level field definitions from fields.json into CSV.

Reads: _data/raw/fields.json
Outputs: _data/output/_orgName/fields_parsed_YYYYMMDD_HHMM.csv

Usage:
  python parsers/parse_fields.py
"""
import os
import sys
import csv
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure_devops.config import RAW_DATA_DIR, OUTPUT_DATA_DIR, CSV_TIMESTAMP_FORMAT
from azure_devops.client import ORG


def load_json(filepath):
    """Load JSON file, return None on error."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: Could not load {filepath}: {e}")
        return None


def parse_fields(fields_file):
    """Parse fields.json and return rows for CSV.
    
    Args:
        fields_file: Path to fields.json
        
    Returns:
        list: List of dictionaries with field metadata
    """
    rows = []
    
    fields_data = load_json(fields_file)
    if not fields_data:
        return rows
    
    # Extract field list
    field_list = fields_data.get("value", []) if isinstance(fields_data, dict) else fields_data
    
    for field in field_list:
        # Extract picklist info
        is_picklist = field.get("isPicklist", False)
        picklist_id = field.get("picklistId", "")
        is_picklist_suggested = field.get("isPicklistSuggested", False)
        
        # Count supported operations
        supported_ops = field.get("supportedOperations", [])
        num_operations = len(supported_ops) if supported_ops else 0
        
        rows.append({
            "Reference Name": field.get("referenceName", ""),
            "Display Name": field.get("name", ""),
            "Description": field.get("description", ""),
            "Type": field.get("type", ""),
            "Usage": field.get("usage", ""),
            "Is Queryable": field.get("isQueryable", False),
            "Can Sort By": field.get("canSortBy", False),
            "Is Identity": field.get("isIdentity", False),
            "Is Picklist": is_picklist,
            "Picklist ID": picklist_id,
            "Is Picklist Suggested": is_picklist_suggested,
            "Read Only": field.get("readOnly", False),
            "Is Locked": field.get("isLocked", False),
            "Supported Operations Count": num_operations,
            "URL": field.get("url", "")
        })
    
    return rows


def main():
    """Main execution."""
    # Org-level data paths
    org_folder = f"_{ORG}"
    raw_file = os.path.join(RAW_DATA_DIR, "fields.json")
    output_dir = os.path.join(OUTPUT_DATA_DIR, org_folder)
    
    # Check if input file exists
    if not os.path.exists(raw_file):
        print(f"Error: {raw_file} not found")
        print("Run exporters/export_wit_raw.py first to generate the data")
        sys.exit(1)
    
    # Parse fields
    print(f"Parsing {raw_file}...")
    rows = parse_fields(raw_file)
    
    if not rows:
        print("No field data found")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Write CSV
    timestamp = datetime.now().strftime(CSV_TIMESTAMP_FORMAT)
    output_file = os.path.join(output_dir, f"fields_parsed_{timestamp}.csv")
    
    fieldnames = [
        "Reference Name", "Display Name", "Description", "Type", "Usage",
        "Is Queryable", "Can Sort By", "Is Identity", "Is Picklist", 
        "Picklist ID", "Is Picklist Suggested", "Read Only", "Is Locked",
        "Supported Operations Count", "URL"
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"[OK] Parsed {len(rows)} fields to {output_file}")


if __name__ == "__main__":
    main()
