#!/usr/bin/env python3
"""Parse organization-level process definitions from raw JSON into two CSV files.

Outputs:
1. process_org_summary_parsed_YYYYMMDD_HHMM.csv - Process summary with counts
2. process_org_wit_states_parsed_YYYYMMDD_HHMM.csv - Detailed WIT state definitions

Usage:
  python parsers/parse_process_org.py
"""
import os
import sys
import csv
import json
import glob
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure_devops.config import RAW_DATA_DIR, OUTPUT_DATA_DIR, CSV_TIMESTAMP_FORMAT
from azure_devops.utils import safe_name
from azure_devops.client import ORG


def load_json(filepath):
    """Load JSON file, return None on error."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {filepath}: {e}")
        return None


def _process_dir(raw_dir, process_name):
    """Return the per-process subfolder path under processes/."""
    return os.path.join(raw_dir, "processes", safe_name(process_name).lower())


def parse_process_summary(raw_dir):
    """Parse process summary with WIT counts and parent relationships.
    
    Returns:
        list: List of dictionaries with process summary data
    """
    rows = []
    
    # Load main process list
    org_processes_file = os.path.join(raw_dir, "org_processes.json")
    processes = load_json(org_processes_file)
    
    if not processes:
        print(f"Error: Could not load {org_processes_file}")
        return rows
    
    # Build process name lookup for parent references
    process_names = {p.get("typeId"): p.get("name") for p in processes}
    
    for process in processes:
        process_type_id = process.get("typeId")
        process_name = process.get("name", process_type_id)
        parent_type_id = process.get("parentProcessTypeId")
        is_default = process.get("isDefault", False)
        customization_type = process.get("customizationType", "")
        
        # Determine parent process name
        parent_name = ""
        if parent_type_id and parent_type_id != "00000000-0000-0000-0000-000000000000":
            parent_name = process_names.get(parent_type_id, parent_type_id)
        
        # Is Custom Inherited: true if customizationType is "inherited"
        is_custom_inherited = (customization_type == "inherited")
        
        # Load WIT count from process subfolder
        proc_dir = _process_dir(raw_dir, process_name)
        wits_file = os.path.join(proc_dir, f"{process_type_id}_wits.json")
        wits = load_json(wits_file)
        wit_count = len(wits) if wits else 0
        
        # Load custom field count (only exists for inherited/custom processes)
        fields_file = os.path.join(proc_dir, f"{process_type_id}_fields.json")
        custom_field_count = 0
        if os.path.isfile(fields_file):
            fields = load_json(fields_file)
            custom_field_count = len(fields) if fields else 0
        
        rows.append({
            "Process Type ID": process_type_id,
            "Process Name": process_name,
            "Parent Process Name": parent_name,
            "Is Custom Inherited": is_custom_inherited,
            "Is Default": is_default,
            "WIT Count": wit_count,
            "Custom Field Count": custom_field_count
        })
    
    return rows


def parse_wit_states(raw_dir):
    """Parse detailed WIT state definitions across all processes.
    
    Returns:
        list: List of dictionaries with WIT state data
    """
    rows = []
    
    # Load main process list to know which processes exist
    org_processes_file = os.path.join(raw_dir, "org_processes.json")
    processes = load_json(org_processes_file)
    
    if not processes:
        print(f"Error: Could not load {org_processes_file}")
        return rows
    
    for process in processes:
        process_type_id = process.get("typeId")
        process_name = process.get("name", process_type_id)
        
        # Load WITs for this process from subfolder
        proc_dir = _process_dir(raw_dir, process_name)
        wits_file = os.path.join(proc_dir, f"{process_type_id}_wits.json")
        wits = load_json(wits_file)
        
        if not wits:
            continue
        
        for wit in wits:
            wit_ref_name = wit.get("referenceName")
            wit_name = wit.get("name", wit_ref_name)
            
            if not wit_ref_name:
                continue
            
            # Load states for this WIT
            # Filename uses safe_name for wit ref name
            wsafe = safe_name(wit_ref_name)
            states_file = os.path.join(proc_dir, f"{process_type_id}_{wsafe}_states.json")
            states = load_json(states_file)
            
            if not states:
                continue
            
            for state in states:
                state_name = state.get("name", "")
                state_category = state.get("stateCategory", "")
                is_inherited = state.get("customizationType") == "inherited"
                # "customizationType" can be: "system", "inherited", "custom"
                # is_customized: true if customizationType is "custom"
                is_customized = state.get("customizationType") == "custom"
                
                rows.append({
                    "Process Type ID": process_type_id,
                    "Process Name": process_name,
                    "WIT Ref Name": wit_ref_name,
                    "WIT Name": wit_name,
                    "State Name": state_name,
                    "State Category": state_category,
                    "Is Inherited": is_inherited,
                    "Is Customized": is_customized
                })
    
    return rows


def write_csv(rows, output_file, fieldnames):
    """Write rows to CSV file."""
    with open(output_file, "w", newline='', encoding='utf-8') as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {output_file}")


def main():
    """Main execution."""
    # Use org-specific directories
    raw_dir = os.path.join(RAW_DATA_DIR, f"_{ORG}")
    output_dir = os.path.join(OUTPUT_DATA_DIR, f"_{ORG}")
    timestamp = datetime.now().strftime(CSV_TIMESTAMP_FORMAT)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Parse and write process summary
    print("Parsing process summary...")
    summary_rows = parse_process_summary(raw_dir)
    summary_fieldnames = [
        "Process Type ID", "Process Name", "Parent Process Name", 
        "Is Custom Inherited", "Is Default", "WIT Count", "Custom Field Count"
    ]
    summary_file = os.path.join(output_dir, f"process_org_summary_parsed_{timestamp}.csv")
    write_csv(summary_rows, summary_file, summary_fieldnames)
    
    # Parse and write WIT states
    print("Parsing WIT states...")
    states_rows = parse_wit_states(raw_dir)
    states_fieldnames = [
        "Process Type ID", "Process Name", "WIT Ref Name", "WIT Name", 
        "State Name", "State Category", "Is Inherited", "Is Customized"
    ]
    states_file = os.path.join(output_dir, f"process_org_wit_states_parsed_{timestamp}.csv")
    write_csv(states_rows, states_file, states_fieldnames)
    
    print("\nProcess org parsing complete!")


if __name__ == "__main__":
    main()
