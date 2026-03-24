#!/usr/bin/env python3
"""Export work item metadata by area path via OData Analytics API.

Queries each project using server-side $apply aggregation (with client-side
fallback) and saves a single consolidated JSON file to _data/raw/_orgName/.

This is an org-level exporter — output goes to the org folder, not per-project.

Usage (cmd.exe):
  python exporters/export_workitem_metadata_raw.py
  python exporters/export_workitem_metadata_raw.py PROJECT-NAME
  python exporters/export_workitem_metadata_raw.py PROJ1 PROJ2

Options:
  --fallback    Force client-side aggregation (skip $apply attempt)
"""
import os
import sys
import logging
from datetime import datetime
from urllib.parse import quote

# Add parent directory to path so we can import azure_devops module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_exporter import BaseExporter
from azure_devops.client import ORG, save_json
from azure_devops.config import API_VERSIONS
from azure_devops.utils import safe_name

# OData Analytics configuration
ANALYTICS_BASE_URL = f"https://analytics.dev.azure.com/{ORG}"
ODATA_VERSION = "v3.0-preview"


class WorkitemMetadataExporter(BaseExporter):
    """Export work item metadata aggregated by area path, WIT, and state."""

    def __init__(self):
        super().__init__()
        # Org-level output folder
        self.out_dir = os.path.join(self.out_dir, f"_{ORG}")
        os.makedirs(self.out_dir, exist_ok=True)

        # Parse --fallback flag (argparse not used to stay compatible with BaseExporter)
        self.force_fallback = "--fallback" in sys.argv
        if self.force_fallback and "--fallback" in self.project_ids:
            self.project_ids.remove("--fallback")

        # Track $apply support across projects
        self._apply_supported = not self.force_fallback
        self._apply_tested = False

        # Accumulate all project results for consolidated output
        self._all_results = []

    def setup_project_folder(self, project):
        """Override: skip folder/metadata creation — all data goes to consolidated JSON."""
        pid = project.get("id")
        pname = project.get("name")
        if not pid:
            logging.warning(f"Skipping project with no ID: {pname}")
            return None
        safe = safe_name(pname or pid)
        return pid, pname, safe, self.out_dir

    # ------------------------------------------------------------------
    # BaseExporter hooks
    # ------------------------------------------------------------------

    def export_project_data(self, client, project_id, project_name, project_safe_name, project_dir):
        """Export work item metadata for a single project via OData."""
        results = None
        strategy_used = "none"

        # --- Attempt $apply first ---
        if self._apply_supported:
            logging.info(f"  Attempting server-side $apply aggregation...")
            raw_rows = self._query_odata_apply(client, project_name)

            if raw_rows is not None:
                results = self._parse_apply_results(raw_rows)
                strategy_used = "$apply"
                if not self._apply_tested:
                    logging.info("  $apply supported — using server-side aggregation for all projects")
                    self._apply_tested = True
            else:
                self._apply_supported = False
                logging.info("  Switching to client-side aggregation for all projects")

        # --- Fallback to client-side ---
        if results is None:
            logging.info(f"  Using client-side aggregation...")
            results = self._query_odata_client_side(client, project_name)
            strategy_used = "client-side"

        if not results:
            logging.info(f"  No work items found (project will be included with 0 counts)\n")
            results = []

        # Store for consolidated output (include even empty projects)
        self._all_results.append({
            "project_id": project_id,
            "project": project_name,
            "strategy": strategy_used,
            "row_count": len(results),
            "data": results,
        })

        if results:
            unique_areas = len({r["area_path"] for r in results})
            total_items = sum(r["count"] for r in results)
            logging.info(
                f"  {len(results)} groups across {unique_areas} areas "
                f"({total_items} total items) [{strategy_used}]\n"
            )

    def run(self):
        """Override run to save consolidated JSON after all projects."""
        super().run()
        self._save_consolidated()

    # ------------------------------------------------------------------
    # OData query strategies
    # ------------------------------------------------------------------

    def _query_odata_apply(self, client, project_name):
        """Server-side aggregation with $apply. Returns raw rows or None."""
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
        encoded_apply = quote(apply_clause, safe="")
        url = (
            f"{ANALYTICS_BASE_URL}/{quote(project_name, safe='')}"
            f"/_odata/{ODATA_VERSION}/WorkItems"
            f"?$apply={encoded_apply}"
        )

        try:
            all_rows = []
            next_link = url
            while next_link:
                response = client.session.get(next_link)
                if response.status_code in (400, 501):
                    logging.warning(f"  $apply not supported (HTTP {response.status_code})")
                    return None
                if response.status_code != 200:
                    logging.error(f"  OData $apply failed: HTTP {response.status_code}")
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

    def _query_odata_client_side(self, client, project_name):
        """Client-side aggregation fallback. Returns normalized result dicts."""
        odata_query = (
            f"$filter=Project/ProjectName eq '{project_name}'"
            f"&$select=Area/AreaPath,State,WorkItemType,CreatedDate,ChangedDate"
            f"&$expand=Area($select=AreaPath)"
        )
        url = (
            f"{ANALYTICS_BASE_URL}/{quote(project_name, safe='')}"
            f"/_odata/{ODATA_VERSION}/WorkItems?{odata_query}"
        )

        try:
            all_items = []
            next_link = url
            while next_link:
                response = client.session.get(next_link)
                if response.status_code != 200:
                    logging.error(f"  OData query failed: HTTP {response.status_code}")
                    return []
                data = response.json()
                all_items.extend(data.get("value", []))
                next_link = data.get("@odata.nextLink")
                if next_link:
                    page_num = len(all_items) // 10000 + 1
                    logging.info(f"  Fetching page {page_num}... ({len(all_items)} items)")

            logging.info(f"  Retrieved {len(all_items)} work items, aggregating client-side...")

            aggregates = {}
            for item in all_items:
                area_path = ""
                area = item.get("Area")
                if isinstance(area, dict):
                    area_path = area.get("AreaPath", "")

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

            results = []
            for agg in aggregates.values():
                cd = agg["created_dates"]
                md = agg["changed_dates"]
                results.append({
                    "area_path": agg["area_path"],
                    "work_item_type": agg["work_item_type"],
                    "state": agg["state"],
                    "count": agg["count"],
                    "min_created": _format_date(min(cd)) if cd else "",
                    "max_created": _format_date(max(cd)) if cd else "",
                    "min_changed": _format_date(min(md)) if md else "",
                    "max_changed": _format_date(max(md)) if md else "",
                })
            return results
        except Exception as e:
            logging.error(f"  OData client-side query failed for {project_name}: {e}")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_apply_results(rows):
        """Normalize $apply response rows into standard dicts."""
        results = []
        for row in rows:
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
                "min_created": _format_date(row.get("MinCreatedDate", "")),
                "max_created": _format_date(row.get("MaxCreatedDate", "")),
                "min_changed": _format_date(row.get("MinChangedDate", "")),
                "max_changed": _format_date(row.get("MaxChangedDate", "")),
            })
        return results

    def _save_consolidated(self):
        """Write all project results to a single consolidated JSON file."""
        if not self._all_results:
            logging.warning("No results to save")
            return

        payload = {
            "org": ORG,
            "exported_at": datetime.now().isoformat(),
            "project_count": len(self._all_results),
            "projects": self._all_results,
        }

        output_path = os.path.join(self.out_dir, "workitem_metadata_by_area.json")
        save_json(payload, output_path)
        logging.info(f"Saved consolidated JSON to {output_path}")


def _format_date(date_string):
    """Convert ISO datetime to YYYY-MM-DD format."""
    if not date_string:
        return ""
    try:
        dt = datetime.fromisoformat(str(date_string).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        s = str(date_string)
        return s.split("T")[0] if "T" in s else s


if __name__ == "__main__":
    exporter = WorkitemMetadataExporter()
    exporter.run()
