#!/usr/bin/env python3
"""Parse workitem_metadata_by_area consolidated JSON into a detailed CSV.

Reads _data/raw/_orgName/workitem_metadata_by_area.json and produces a CSV
with one row per project + area path + work item type + state combination.

Usage (cmd.exe):
  python parsers/parse_workitem_metadata.py
"""
import os
import sys
import csv
import json
import logging
from datetime import datetime

# Add parent directory to Python path for azure_devops imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from azure_devops.client import ORG
from azure_devops.config import RAW_DATA_DIR, OUTPUT_DATA_DIR

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

INPUT_FILENAME = "workitem_metadata_by_area.json"


def load_consolidated(raw_dir):
    """Load the consolidated JSON from the org-level raw folder."""
    path = os.path.join(raw_dir, INPUT_FILENAME)
    if not os.path.isfile(path):
        logging.error(f"Input file not found: {path}")
        logging.error("Run export_workitem_metadata_raw.py first.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.error(f"Could not read {path}: {e}")
        return None


def build_csv_rows(consolidated):
    """Build flat CSV rows from consolidated JSON."""
    rows = []
    for project_block in consolidated.get("projects", []):
        project_id = project_block.get("project_id", "")
        project_name = project_block.get("project", "")
        data = project_block.get("data", [])

        # Pre-compute area totals for the summary column
        area_totals = {}
        for item in data:
            area = item.get("area_path", "")
            area_totals[area] = area_totals.get(area, 0) + item.get("count", 0)

        for item in data:
            area_path = item.get("area_path", "")
            depth = area_path.count("\\") + 1 if area_path else 0

            rows.append({
                "Project ID": project_id,
                "Project Name": project_name,
                "Area Path": area_path,
                "Depth": depth,
                "Work Item Type": item.get("work_item_type", ""),
                "State": item.get("state", ""),
                "Count": item.get("count", 0),
                "Min Created Date": item.get("min_created", ""),
                "Max Created Date": item.get("max_created", ""),
                "Min Changed Date": item.get("min_changed", ""),
                "Max Changed Date": item.get("max_changed", ""),
                "Total Area Count": area_totals.get(area_path, 0),
            })

    return rows


def main():
    raw_dir = os.path.join(RAW_DATA_DIR, f"_{ORG}")
    output_dir = os.path.join(OUTPUT_DATA_DIR, f"_{ORG}")

    consolidated = load_consolidated(raw_dir)
    if consolidated is None:
        sys.exit(1)

    rows = build_csv_rows(consolidated)
    if not rows:
        logging.error("No data rows generated")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = os.path.join(output_dir, f"workitem_metadata_by_area_parsed_{timestamp}.csv")

    fieldnames = [
        "Project ID",
        "Project Name",
        "Area Path",
        "Depth",
        "Work Item Type",
        "State",
        "Count",
        "Min Created Date",
        "Max Created Date",
        "Min Changed Date",
        "Max Changed Date",
        "Total Area Count",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    project_count = len(consolidated.get("projects", []))
    logging.info(f"Wrote {len(rows)} rows ({project_count} projects) to {output_file}")


if __name__ == "__main__":
    main()
