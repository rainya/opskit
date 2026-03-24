"""Centralized configuration for Azure DevOps audit scripts.

This module consolidates all configuration constants to avoid hardcoding
values throughout the codebase. Values can be overridden via environment
variables for different deployment contexts.
"""
import os

# API Configuration
# API version keys used throughout the toolkit:
# - default: fallback for general endpoints
# - core: core API endpoints (projects, etc.)
# - work: work tracking API endpoints
# - wit: work item type endpoints
# - classification: area/iteration endpoints
# - teams: team endpoints
# - boards: board configuration endpoints
# - preview: preview API endpoints
API_VERSIONS = {
    "default": "7.1",
    "core": "7.1",
    "work": "7.1",
    "wit": "7.1",
    "classification": "7.1",
    "teams": "7.1",
    "boards": "7.1",
    "preview": "7.1-preview.1",
}

# Directory Configuration
RAW_DATA_DIR = os.getenv("DATA_RAW_DIR", "_data/raw")
OUTPUT_DATA_DIR = os.getenv("DATA_OUTPUT_DIR", "_data/output")
RAW_SAMPLES_DIR = os.getenv("DATA_SAMPLES_DIR", "_data/samples")
ARCHIVE_OUTPUT_DIR = os.getenv("ARCHIVE_OUTPUT_DIR", "archive_output")

# CSV Output Configuration
CSV_TIMESTAMP_FORMAT = "%Y%m%d_%H%M"

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# PAT Configuration
PAT_ENV_VAR = "ADO_PAT"
PAT_FILE = "ado_pat.txt"

# Filename Templates for Raw JSON Exports
# These can be used with .format() to generate consistent filenames
PROCESS_TEMPLATE_FILENAME = "{project}_process_template.json"
BACKLOG_CONFIG_FILENAME = "{project}_backlogconfig.json"
TEAM_SETTINGS_FILENAME = "{project}_{team}_teamsettings.json"
TEAM_BACKLOGS_FILENAME = "{project}_{team}_backlogs.json"
SWIMLANES_FILENAME = "{project}_{team}_{board}_swimlanes.json"
PLANS_FILENAME = "{project}_plans.json"
PLAN_DETAIL_FILENAME = "{project}_{planId}_plan_detail.json"
PROJECT_DASHBOARDS_FILENAME = "{project}_dashboards.json"
TEAM_DASHBOARDS_FILENAME = "{project}_{team}_dashboards.json"
