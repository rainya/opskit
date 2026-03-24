#!/usr/bin/env python3
"""
Project-level summary rollup from consolidated workitem_metadata_by_area JSON.
Reads _data/raw/_orgName/workitem_metadata_by_area.json and produces a CSV
with one row per project containing aggregate counts and date ranges.

No API calls — reads only from _data/raw/.

Usage (cmd.exe):
  python parsers/workitem_project_summary.py
  python parsers/workitem_project_summary.py PROJECT-NAME
  python parsers/workitem_project_summary.py PROJ1 PROJ2
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


def summarize_project(metadata):
    """Aggregate metadata rows into project-level summary dict."""
    data = metadata.get("data", [])
    if not data:
        return {
            "distinct_area_paths": 0,
            "distinct_work_item_types": 0,
            "distinct_states": 0,
            "total_work_item_count": 0,
            "min_created_date": "",
            "max_created_date": "",
            "min_changed_date": "",
            "max_changed_date": "",
        }

    area_paths = set()
    work_item_types = set()
    states = set()
    total_count = 0
    min_created_dates = []
    max_created_dates = []
    min_changed_dates = []
    max_changed_dates = []

    for row in data:
        area_paths.add(row.get("area_path", ""))
        work_item_types.add(row.get("work_item_type", ""))
        state = row.get("state")
        if state:  # Skip null/empty states
            states.add(state)
        total_count += row.get("count", 0)

        # Collect non-empty date strings for min/max calculation
        mc = row.get("min_created", "")
        if mc:
            min_created_dates.append(mc)
        xc = row.get("max_created", "")
        if xc:
            max_created_dates.append(xc)
        md = row.get("min_changed", "")
        if md:
            min_changed_dates.append(md)
        xd = row.get("max_changed", "")
        if xd:
            max_changed_dates.append(xd)

    return {
        "distinct_area_paths": len(area_paths),
        "distinct_work_item_types": len(work_item_types),
        "distinct_states": len(states),
        "total_work_item_count": total_count,
        "min_created_date": min(min_created_dates) if min_created_dates else "",
        "max_created_date": max(max_created_dates) if max_created_dates else "",
        "min_changed_date": min(min_changed_dates) if min_changed_dates else "",
        "max_changed_date": max(max_changed_dates) if max_changed_dates else "",
    }


def main():
    """Main execution."""
    project_filter = sys.argv[1:] if len(sys.argv) > 1 else []

    raw_dir = os.path.join(RAW_DATA_DIR, f"_{ORG}")
    output_dir = os.path.join(OUTPUT_DATA_DIR, f"_{ORG}")

    consolidated = load_consolidated(raw_dir)
    if consolidated is None:
        sys.exit(1)

    project_blocks = consolidated.get("projects", [])

    # Filter projects if specified
    if project_filter:
        filter_upper = [pf.upper() for pf in project_filter]
        project_blocks = [
            p for p in project_blocks
            if p.get("project", "").upper() in filter_upper
            or p.get("project_id", "") in project_filter
        ]

    if not project_blocks:
        logging.error("No projects found matching filter")
        sys.exit(1)

    logging.info(f"Summarizing {len(project_blocks)} project(s)...\n")

    rows = []

    for block in project_blocks:
        project_name = block.get("project", "")
        project_id = block.get("project_id", "")

        summary = summarize_project(block)

        rows.append({
            "Project ID": project_id,
            "Project Name": project_name,
            "Distinct Area Paths": summary["distinct_area_paths"],
            "Distinct Work Item Types": summary["distinct_work_item_types"],
            "Distinct States": summary["distinct_states"],
            "Total Work Item Count": summary["total_work_item_count"],
            "Min Created Date": summary["min_created_date"],
            "Max Created Date": summary["max_created_date"],
            "Min Changed Date": summary["min_changed_date"],
            "Max Changed Date": summary["max_changed_date"],
        })

        logging.info(
            f"  {project_name}: {summary['total_work_item_count']} items, "
            f"{summary['distinct_area_paths']} areas, "
            f"{summary['distinct_work_item_types']} WITs, "
            f"{summary['distinct_states']} states"
        )

    if not rows:
        logging.error("No projects with metadata found")
        sys.exit(1)

    # Sort by project name
    rows.sort(key=lambda r: r["Project Name"].upper())

    # Write CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"workitem_project_summary_{timestamp}.csv")

    fieldnames = [
        "Project ID",
        "Project Name",
        "Distinct Area Paths",
        "Distinct Work Item Types",
        "Distinct States",
        "Total Work Item Count",
        "Min Created Date",
        "Max Created Date",
        "Min Changed Date",
        "Max Changed Date",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logging.info(f"\nWrote {len(rows)} project(s) to {output_file}")


if __name__ == "__main__":
    main()
