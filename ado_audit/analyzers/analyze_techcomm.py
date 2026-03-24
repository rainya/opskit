#!/usr/bin/env python3
"""Analyze TechComm-related configuration across all ADO projects.

Reads parsed CSVs from _data/output/, applies the TechComm filter profile,
joins work item counts, and writes consolidated analysis to _data/analysis/.

Usage (cmd.exe):
    python analyzers/analyze_techcomm.py
    python analyzers/analyze_techcomm.py --projects sps defender
    python analyzers/analyze_techcomm.py --dry-run
"""
import argparse
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzers.base_analyzer import (
    find_project_folders,
    load_workitem_counts,
    scan_areas,
    scan_boards,
    scan_teams,
    write_analysis_csv,
)
from analyzers.filter_profiles import TECHCOMM_PROFILE

# ---------------------------------------------------------------------------
# Inventory builder
# ---------------------------------------------------------------------------

def build_inventory(all_teams, all_areas, all_boards, wi_counts_by_key):
    """Build the techcomm_inventory rows: one per project+team.

    Joins area paths and work item counts into each team row.

    Args:
        all_teams: list of matched team dicts (across projects)
        all_areas: list of matched area dicts (across projects)
        all_boards: list of matched board column dicts (across projects)
        wi_counts_by_key: dict keyed by (project_id, area_path) -> count string

    Returns:
        list[dict]: Inventory rows
    """
    # Index areas by project
    areas_by_project = {}
    for a in all_areas:
        pid = a.get("Project ID", "")
        areas_by_project.setdefault(pid, []).append(a.get("Path", ""))

    # Index board names by (project, team_fragment)
    boards_by_project = {}
    for b in all_boards:
        pid = b.get("Project ID", "")
        board_name = b.get("Board Name", "")
        boards_by_project.setdefault(pid, set()).add(board_name)

    # Sum work item counts per project across matched areas
    wi_by_project = {}
    for a in all_areas:
        pid = a.get("Project ID", "")
        path = a.get("Path", "")
        count_str = wi_counts_by_key.get((pid, path), "")
        if count_str:
            wi_by_project.setdefault(pid, []).append(count_str)

    rows = []
    for t in all_teams:
        pid = t.get("Project ID", "")
        project = t.get("Project Name", "")
        team = t.get("Team Name", "")

        area_list = areas_by_project.get(pid, [])
        board_set = boards_by_project.get(pid, set())

        # Summarise work item counts for this project
        count_parts = wi_by_project.get(pid, [])
        total_display = _sum_counts(count_parts) if count_parts else ""

        # Backlog visibility flags
        vis = []
        for level in ("Initiatives", "Epics", "Features", "Stories"):
            if t.get(f"{level} Visible", "").lower() == "true":
                vis.append(level)

        rows.append({
            "Project ID": pid,
            "Project Name": project,
            "Team Name": team,
            "Team ID": t.get("Team ID", ""),
            "Bug Behavior": t.get("Bug Behavior Label", ""),
            "Backlog Iteration": t.get("Backlog Iteration Path", ""),
            "Default Iteration": t.get("Default Iteration Path", ""),
            "Backlog Levels Visible": "; ".join(vis),
            "Area Paths": "; ".join(sorted(set(area_list))),
            "Board Names": "; ".join(sorted(board_set)),
            "Work Item Count (areas total)": total_display,
            "Match Reason": t.get("Match Reason", ""),
        })
    return rows


def _sum_counts(parts):
    """Sum a list of count strings, handling '>20000' style values."""
    total = 0
    has_gt = False
    for p in parts:
        s = str(p).strip()
        if s.startswith(">"):
            has_gt = True
            try:
                total += int(s[1:])
            except ValueError:
                pass
        else:
            try:
                total += int(s)
            except ValueError:
                pass
    prefix = ">" if has_gt else ""
    return f"{prefix}{total}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

INVENTORY_FIELDS = [
    "Project ID", "Project Name", "Team Name", "Team ID",
    "Bug Behavior", "Backlog Iteration", "Default Iteration",
    "Backlog Levels Visible", "Area Paths", "Board Names",
    "Work Item Count (areas total)", "Match Reason",
]

AREA_FIELDS = [
    "Project ID", "Project Name", "Area Path", "Depth",
    "Node ID", "Work Item Count", "Match Reason",
]


def main():
    parser = argparse.ArgumentParser(description="TechComm cross-project analysis")
    parser.add_argument("--projects", nargs="*", default=[],
                        help="Limit to specific project folders (case-insensitive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show matches without writing files")
    args = parser.parse_args()

    profile = TECHCOMM_PROFILE

    # Discover project folders
    folders = find_project_folders()
    if args.projects:
        filter_set = {p.lower() for p in args.projects}
        folders = [f for f in folders if f.lower() in filter_set]

    if not folders:
        print("No project folders found in output directory.")
        return

    # Load work item counts and index by (project_id, area_path)
    wi_rows = load_workitem_counts()
    wi_counts = {
        (r.get("Project ID", ""), r.get("Area Path", "")): r.get("Work Item Count", "")
        for r in wi_rows
    }

    all_teams = []
    all_areas = []
    all_boards = []

    for folder in sorted(folders):
        teams = scan_teams(folder, profile)
        areas = scan_areas(folder, profile)

        if not teams and not areas:
            continue

        # Derive team name fragments for board matching
        team_names = {t.get("Team Name", "") for t in teams}
        boards = scan_boards(folder, profile, team_names)

        project_label = teams[0].get("Project Name", folder) if teams else folder
        print(f"  {project_label}: {len(teams)} team(s), {len(areas)} area(s), {len(boards)} board column(s)")

        all_teams.extend(teams)
        all_areas.extend(areas)
        all_boards.extend(boards)

    print(f"\nTotals: {len(all_teams)} teams, {len(all_areas)} areas, {len(all_boards)} board columns")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return

    # --- Build & write inventory ---
    inventory = build_inventory(all_teams, all_areas, all_boards, wi_counts)
    inv_path = write_analysis_csv("techcomm_inventory", INVENTORY_FIELDS, inventory)
    print(f"\n[OK] Wrote {len(inventory)} row(s) to {inv_path}")

    # --- Build & write areas detail ---
    area_rows = []
    for a in all_areas:
        area_path = a.get("Path", "")
        pid = a.get("Project ID", "")
        area_rows.append({
            "Project ID": pid,
            "Project Name": a.get("Project Name", ""),
            "Area Path": area_path,
            "Depth": a.get("Depth", ""),
            "Node ID": a.get("Node ID", ""),
            "Work Item Count": wi_counts.get((pid, area_path), ""),
            "Match Reason": a.get("Match Reason", ""),
        })
    area_path_out = write_analysis_csv("techcomm_areas", AREA_FIELDS, area_rows)
    print(f"[OK] Wrote {len(area_rows)} row(s) to {area_path_out}")


if __name__ == "__main__":
    main()
