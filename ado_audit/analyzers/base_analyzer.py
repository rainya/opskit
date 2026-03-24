#!/usr/bin/env python3
"""Base analyzer — reads parsed CSVs across projects and applies filter profiles."""
import csv
import glob
import os
import re
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure_devops.config import OUTPUT_DATA_DIR, CSV_TIMESTAMP_FORMAT

ANALYSIS_DIR = os.getenv("DATA_ANALYSIS_DIR", "_data/analysis")


def find_latest_csv(directory, filename_prefix):
    """Find the most recent CSV matching a filename prefix in a directory.

    Args:
        directory: Folder to search
        filename_prefix: e.g. "classification_nodes_parsed"

    Returns:
        str or None: Path to the most recent matching file
    """
    pattern = os.path.join(directory, f"{filename_prefix}_*.csv")
    files = glob.glob(pattern)
    if not files:
        return None
    # Sort by name descending — timestamp suffix ensures lexicographic = chronological
    return sorted(files)[-1]


def load_csv_rows(path):
    """Load all rows from a CSV file as list of dicts.

    Args:
        path: Path to CSV file

    Returns:
        list[dict]: Rows, or empty list if file missing
    """
    if not path or not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_project_folders():
    """Return all project subfolder names under OUTPUT_DATA_DIR.

    Excludes folders starting with underscore (org-level data).
    """
    if not os.path.isdir(OUTPUT_DATA_DIR):
        return []
    return [d for d in os.listdir(OUTPUT_DATA_DIR)
            if os.path.isdir(os.path.join(OUTPUT_DATA_DIR, d)) and not d.startswith('_')]


def matches_any(value, patterns):
    """Test whether *value* matches any regex in *patterns* (case-insensitive).

    Args:
        value: String to test
        patterns: List of regex pattern strings

    Returns:
        str or None: The pattern that matched, or None
    """
    if not value:
        return None
    for pat in patterns:
        if re.search(pat, value, re.IGNORECASE):
            return pat
    return None


def scan_teams(project_folder, profile):
    """Load team_settings CSV for a project, return rows matching the profile.

    Args:
        project_folder: e.g. "defender"
        profile: A FilterProfile instance

    Returns:
        list[dict]: Matched team rows, each with an added 'Match Reason' key
    """
    proj_dir = os.path.join(OUTPUT_DATA_DIR, project_folder)
    csv_path = find_latest_csv(proj_dir, "team_settings_parsed")
    rows = load_csv_rows(csv_path)

    is_full = project_folder.lower() in [p.lower() for p in profile.full_projects]
    team_pats = profile.get_team_patterns(project_folder)

    matched = []
    for row in rows:
        team_name = row.get("Team Name", "")
        if is_full:
            row["Match Reason"] = "full_project"
            matched.append(row)
        else:
            pat = matches_any(team_name, team_pats)
            if pat:
                row["Match Reason"] = f"team_name ~ {pat}"
                matched.append(row)
    return matched


def scan_areas(project_folder, profile):
    """Load classification_nodes CSV, return Area rows matching the profile.

    Args:
        project_folder: e.g. "defender"
        profile: A FilterProfile instance

    Returns:
        list[dict]: Matched area rows, each with an added 'Match Reason' key
    """
    proj_dir = os.path.join(OUTPUT_DATA_DIR, project_folder)
    csv_path = find_latest_csv(proj_dir, "classification_nodes_parsed")
    rows = load_csv_rows(csv_path)

    is_full = project_folder.lower() in [p.lower() for p in profile.full_projects]
    area_pats = profile.get_area_patterns(project_folder)

    matched = []
    for row in rows:
        if row.get("Node Type") != "Area":
            continue
        path = row.get("Path", "")
        if is_full:
            row["Match Reason"] = "full_project"
            matched.append(row)
        else:
            pat = matches_any(path, area_pats)
            if pat:
                row["Match Reason"] = f"area_path ~ {pat}"
                matched.append(row)
    return matched


def scan_boards(project_folder, profile, matched_team_names):
    """Load boards CSV, return rows for matched teams.

    Args:
        project_folder: e.g. "defender"
        profile: A FilterProfile instance
        matched_team_names: set of team names already matched

    Returns:
        list[dict]: Board column rows belonging to matched teams
    """
    proj_dir = os.path.join(OUTPUT_DATA_DIR, project_folder)
    csv_path = find_latest_csv(proj_dir, "teams_boards_columns_parsed")
    rows = load_csv_rows(csv_path)

    is_full = project_folder.lower() in [p.lower() for p in profile.full_projects]
    team_pats = profile.get_team_patterns(project_folder)

    # Board CSVs encode team name inside the Team Name column
    # (e.g. "TechComm" or "TechComm_Backlog")
    matched = []
    for row in rows:
        board_team = row.get("Team Name", "")
        if is_full:
            matched.append(row)
        elif matches_any(board_team, team_pats):
            matched.append(row)
        elif any(tn in board_team for tn in matched_team_names):
            matched.append(row)
    return matched


def load_workitem_counts():
    """Load the most recent workitem_counts_by_area CSV from the output root.

    Returns:
        list[dict]: Rows from the CSV, or empty list
    """
    csv_path = find_latest_csv(OUTPUT_DATA_DIR, "workitem_counts_by_area")
    return load_csv_rows(csv_path)


def write_analysis_csv(filename, fieldnames, rows):
    """Write rows to a timestamped CSV in the analysis directory.

    Args:
        filename: Base name without timestamp, e.g. "techcomm_inventory"
        fieldnames: Column headers
        rows: List of dicts

    Returns:
        str: Path to the written file
    """
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    ts = datetime.now().strftime(CSV_TIMESTAMP_FORMAT)
    path = os.path.join(ANALYSIS_DIR, f"{filename}_{ts}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path
