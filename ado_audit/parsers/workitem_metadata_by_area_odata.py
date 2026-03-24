#!/usr/bin/env python3
"""
Work item metadata by area path using Azure DevOps Analytics OData API.
Uses server-side $apply aggregation for efficient single-request-per-project queries.

Outputs counts grouped by area path, work item type, and state, with date ranges.

Primary strategy: OData $apply with groupby() and aggregate()
Fallback: Client-side aggregation if $apply is not supported by the org

Usage:
  python workitem_metadata_by_area_odata.py                    # All projects
  python workitem_metadata_by_area_odata.py PROJECT-NAME       # Single project
  python workitem_metadata_by_area_odata.py PROJ1 PROJ2        # Multiple projects

Options:
  --fallback    Force client-side aggregation (skip $apply attempt)
"""
import os
import sys
import csv
import json
import logging
import argparse
from datetime import datetime
from urllib.parse import quote

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from azure_devops.client import ADOClient, ORG
from azure_devops.utils import read_pat
from azure_devops.config import OUTPUT_DATA_DIR, API_VERSIONS, RAW_DATA_DIR

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

# OData Analytics base URL
ANALYTICS_BASE_URL = f"https://analytics.dev.azure.com/{ORG}"

# OData API version
ODATA_VERSION = "v3.0-preview"


# ---------------------------------------------------------------------------
# Strategy 1: Server-side aggregation with $apply
# ---------------------------------------------------------------------------

def query_odata_apply(client, project_name):
    """Query OData Analytics using $apply for server-side aggregation.

    Groups by Area/AreaPath, WorkItemType, and State.
    Aggregates: count, min/max CreatedDate, min/max ChangedDate.

    Returns:
        list of dicts on success, None if $apply is not supported
    """
    # Build $apply clause
    # groupby() defines the dimensions; aggregate() defines the measures
    apply_clause = (
        "groupby("
        "(Area/AreaPath,WorkItemType,State),"
        "aggregate("
        "$count as Count,"
        "CreatedDate with min as MinCreatedDate,"
        "CreatedDate with max as MaxCreatedDate,"
        "ChangedDate with min as MinChangedDate,"
        "ChangedDate with max as MaxChangedDate"
        "))"
    )

    # URL-encode the $apply value
    encoded_apply = quote(apply_clause, safe="")

    url = (
        f"{ANALYTICS_BASE_URL}/{quote(project_name, safe='')}"
        f"/_odata/{ODATA_VERSION}/WorkItems"
        f"?$apply={encoded_apply}"
    )

    logging.debug(f"  $apply URL: {url}")

    try:
        # $apply responses are typically small enough to not need pagination,
        # but handle @odata.nextLink defensively
        all_rows = []
        next_link = url

        while next_link:
            response = client.session.get(next_link)

            # If server returns 400/501, $apply may not be supported
            if response.status_code in (400, 501):
                logging.warning(f"  $apply not supported (HTTP {response.status_code}), falling back to client-side aggregation")
                return None

            if response.status_code != 200:
                logging.error(f"  OData $apply query failed: HTTP {response.status_code}")
                logging.error(f"  Response: {response.text[:500]}")
                return None

            data = response.json()
            all_rows.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")

        logging.info(f"  $apply returned {len(all_rows)} aggregated rows")
        return all_rows

    except Exception as e:
        logging.error(f"  $apply query failed for {project_name}: {e}")
        return None


def parse_apply_results(rows):
    """Parse $apply response rows into normalized dicts.

    OData $apply groupby returns rows shaped like:
    {
        "Area": {"AreaPath": "Project\\Team\\Sub"},
        "WorkItemType": "User Story",
        "State": "Active",
        "Count": 42,
        "MinCreatedDate": "2023-01-15T...",
        "MaxCreatedDate": "2025-11-20T...",
        "MinChangedDate": "2023-01-15T...",
        "MaxChangedDate": "2026-02-28T..."
    }
    """
    results = []
    for row in rows:
        # Area path may be nested under Area/ or flat depending on OData version
        area_path = ""
        if isinstance(row.get("Area"), dict):
            area_path = row["Area"].get("AreaPath", "")
        elif "Area.AreaPath" in row:
            area_path = row["Area.AreaPath"]
        elif "AreaPath" in row:
            area_path = row["AreaPath"]

        results.append({
            "area_path": area_path,
            "work_item_type": row.get("WorkItemType", "Unknown"),
            "state": row.get("State", "Unknown"),
            "count": row.get("Count", 0),
            "min_created": format_date(row.get("MinCreatedDate", "")),
            "max_created": format_date(row.get("MaxCreatedDate", "")),
            "min_changed": format_date(row.get("MinChangedDate", "")),
            "max_changed": format_date(row.get("MaxChangedDate", "")),
        })

    return results


# ---------------------------------------------------------------------------
# Strategy 2: Client-side aggregation (fallback)
# ---------------------------------------------------------------------------

def query_odata_client_side(client, project_name):
    """Fetch individual work items and aggregate client-side.

    Used when $apply is not supported by the org's Analytics configuration.
    Adds WorkItemType to the select to match $apply output shape.
    """
    odata_query = (
        f"$filter=Project/ProjectName eq '{project_name}'"
        f"&$select=Area/AreaPath,State,WorkItemType,CreatedDate,ChangedDate"
        f"&$expand=Area($select=AreaPath)"
    )

    url = f"{ANALYTICS_BASE_URL}/{quote(project_name, safe='')}/_odata/{ODATA_VERSION}/WorkItems?{odata_query}"

    try:
        all_items = []
        next_link = url

        while next_link:
            response = client.session.get(next_link)

            if response.status_code != 200:
                logging.error(f"  OData query failed: HTTP {response.status_code}")
                logging.error(f"  Response: {response.text[:500]}")
                return []

            data = response.json()
            all_items.extend(data.get("value", []))

            next_link = data.get("@odata.nextLink")
            if next_link:
                page_num = len(all_items) // 10000 + 1
                logging.info(f"  Fetching page {page_num}... ({len(all_items)} items so far)")

        logging.info(f"  Retrieved {len(all_items)} work items, aggregating client-side...")

        # Aggregate by area_path + work_item_type + state
        aggregates = {}

        for item in all_items:
            # Extract area path from expanded navigation property
            area_path = ""
            area = item.get("Area")
            if isinstance(area, dict):
                area_path = area.get("AreaPath", "")
            elif item.get("AreaSK"):
                # Fallback: older OData response shape
                area_sk = item["AreaSK"]
                if isinstance(area_sk, dict):
                    area_path = area_sk.get("AreaPath", "")

            wit = item.get("WorkItemType", "Unknown")
            state = item.get("State", "Unknown")
            created = item.get("CreatedDate", "")
            changed = item.get("ChangedDate", "")

            key = (area_path, wit, state)

            if key not in aggregates:
                aggregates[key] = {
                    "area_path": area_path,
                    "work_item_type": wit,
                    "state": state,
                    "count": 0,
                    "created_dates": [],
                    "changed_dates": [],
                }

            aggregates[key]["count"] += 1
            if created:
                aggregates[key]["created_dates"].append(created)
            if changed:
                aggregates[key]["changed_dates"].append(changed)

        # Reduce to min/max dates
        results = []
        for agg in aggregates.values():
            cd = agg["created_dates"]
            md = agg["changed_dates"]
            results.append({
                "area_path": agg["area_path"],
                "work_item_type": agg["work_item_type"],
                "state": agg["state"],
                "count": agg["count"],
                "min_created": format_date(min(cd)) if cd else "",
                "max_created": format_date(max(cd)) if cd else "",
                "min_changed": format_date(min(md)) if md else "",
                "max_changed": format_date(max(md)) if md else "",
            })

        return results

    except Exception as e:
        logging.error(f"  OData client-side query failed for {project_name}: {e}")
        return []


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def format_date(date_string):
    """Convert ISO datetime to YYYY-MM-DD format."""
    if not date_string:
        return ""
    try:
        dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return date_string.split("T")[0] if "T" in str(date_string) else str(date_string)


def calculate_area_totals(results):
    """Calculate total work item count per area path across all types and states."""
    totals = {}
    for row in results:
        area = row["area_path"]
        totals[area] = totals.get(area, 0) + row["count"]
    return totals


def save_raw_json(project_name, results, strategy_used):
    """Save raw aggregation results as JSON for audit trail.

    Follows toolkit convention: _data/raw/{project}_workitem_area_metadata.json
    """
    raw_dir = os.path.join(RAW_DATA_DIR, project_name.replace(" ", "_"))
    os.makedirs(raw_dir, exist_ok=True)

    raw_file = os.path.join(raw_dir, f"{project_name.replace(' ', '_')}_workitem_area_metadata.json")

    payload = {
        "project": project_name,
        "strategy": strategy_used,
        "exported_at": datetime.now().isoformat(),
        "row_count": len(results),
        "data": results,
    }

    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    logging.debug(f"  Saved raw JSON to {raw_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description="Work item metadata by area path via OData Analytics"
    )
    parser.add_argument(
        "projects", nargs="*", default=[],
        help="Project names or IDs to process (default: all)"
    )
    parser.add_argument(
        "--fallback", action="store_true",
        help="Force client-side aggregation (skip $apply attempt)"
    )
    parser.add_argument(
        "--no-raw", action="store_true",
        help="Skip saving raw JSON (CSV only)"
    )
    args = parser.parse_args()

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
    if args.projects:
        project_filter_upper = [pf.upper() for pf in args.projects]
        projects = [
            p for p in projects
            if p.get("id") in args.projects
            or (p.get("name") and p.get("name").upper() in project_filter_upper) # type: ignore
        ]

    if not projects:
        logging.error("No projects found matching filter")
        sys.exit(1)

    logging.info(f"Processing {len(projects)} project(s) via OData Analytics...\n")

    # Track whether $apply works for this org (try once, then remember)
    apply_supported = not args.fallback
    apply_tested = False

    # Prepare CSV output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = os.path.join(
        OUTPUT_DATA_DIR, f"workitem_metadata_by_area_odata_{timestamp}.csv"
    )
    os.makedirs(OUTPUT_DATA_DIR, exist_ok=True)

    all_csv_rows = []

    # Process each project
    for project in projects:
        project_id = project.get("id")
        project_name = project.get("name")

        if not project_id or not project_name:
            continue

        logging.info(f"📊 {project_name}")

        results = None
        strategy_used = "none"

        # --- Attempt $apply first ---
        if apply_supported:
            logging.info(f"  Attempting server-side $apply aggregation...")
            raw_rows = query_odata_apply(client, project_name)

            if raw_rows is not None:
                results = parse_apply_results(raw_rows)
                strategy_used = "$apply"
                if not apply_tested:
                    logging.info(f"  ✓ $apply supported — using server-side aggregation for all projects")
                    apply_tested = True
            else:
                # $apply failed — disable for remaining projects
                apply_supported = False
                logging.info(f"  Switching to client-side aggregation for all projects")

        # --- Fallback to client-side ---
        if results is None:
            logging.info(f"  Using client-side aggregation...")
            results = query_odata_client_side(client, project_name)
            strategy_used = "client-side"

        if not results:
            logging.info(f"  No data returned\n")
            continue

        # Save raw JSON
        if not args.no_raw:
            save_raw_json(project_name, results, strategy_used)

        # Calculate area totals for the summary column
        area_totals = calculate_area_totals(results)

        # Build CSV rows
        for item in results:
            area_path = item["area_path"]
            depth = area_path.count("\\") + 1 if area_path else 0

            all_csv_rows.append({
                "Project ID": project_id,
                "Project Name": project_name,
                "Area Path": area_path,
                "Depth": depth,
                "Work Item Type": item["work_item_type"],
                "State": item["state"],
                "Count": item["count"],
                "Min Created Date": item["min_created"],
                "Max Created Date": item["max_created"],
                "Min Changed Date": item["min_changed"],
                "Max Changed Date": item["max_changed"],
                "Total Area Count": area_totals.get(area_path, 0),
            })

        unique_areas = len(area_totals)
        total_items = sum(area_totals.values())
        logging.info(
            f"  ✓ {len(results)} groups across {unique_areas} areas "
            f"({total_items} total items) [{strategy_used}]\n"
        )

    # Write CSV
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
        writer.writerows(all_csv_rows)

    logging.info(f"✅ Wrote {len(all_csv_rows)} rows to {output_file}")


if __name__ == "__main__":
    main()