#!/usr/bin/env python3
"""Filter profiles that define what constitutes a cross-project topic.

Each profile specifies:
- team_patterns:   regex list matched against Team Name columns
- area_patterns:   regex list matched against area Path columns
- full_projects:   project folder names where ALL data is in-scope
- project_overrides: per-project pattern overrides (additive)

Profiles are intentionally data-only — no logic here.
"""


class FilterProfile:
    """A named set of matching rules for cross-project analysis."""

    def __init__(self, name, team_patterns, area_patterns,
                 full_projects=None, project_overrides=None):
        self.name = name
        self.team_patterns = list(team_patterns)
        self.area_patterns = list(area_patterns)
        self.full_projects = list(full_projects or [])
        # dict mapping lowercase project_folder -> {"team_patterns": [...], "area_patterns": [...]}
        self.project_overrides = {k.lower(): v for k, v in (project_overrides or {}).items()}

    def get_team_patterns(self, project_folder):
        """Return team patterns for a project (base + any overrides)."""
        extra = self.project_overrides.get(project_folder.lower(), {}).get("team_patterns", [])
        return self.team_patterns + extra

    def get_area_patterns(self, project_folder):
        """Return area patterns for a project (base + any overrides)."""
        extra = self.project_overrides.get(project_folder.lower(), {}).get("area_patterns", [])
        return self.area_patterns + extra


# ---------------------------------------------------------------------------
# TechComm profile
# ---------------------------------------------------------------------------
# Base patterns applied to every project (unless it's a full_project).
_TC_TEAM_PATTERNS = [
    r"(?i)TechComm",
    r"(?i)Tech[\s_]Comm",
    r"(?i)Technical[\s_]Writer",
    r"(?i)DOC-",
]

_TC_AREA_PATTERNS = [
    r"(?i)\\TechComm",
    r"(?i)\\Tech[\s_]Comm",
    r"(?i)\\Technical[\s_]Writer",
    r"(?i)\\DOC-",
]

# Per-project overrides add patterns that are safe ONLY in that project's context.
_TC_PROJECT_OVERRIDES = {
    # SPS uses "TC" as abbreviation; also match Documentation teams scoped to TC area
    "sps": {
        "team_patterns": [r"(?i)\bDocumentation\b"],
        "area_patterns": [r"(?i)\\TC\\"],
    },
    # Log Management's Documentation team is the parent of DOC- teams
    "log_management": {
        "team_patterns": [r"(?i)^Log.*Documentation$"],
        "area_patterns": [r"(?i)\\Documentation\\"],
    },
    # OneLogin has a Documentation area that is TechComm-owned
    "onelogin": {
        "area_patterns": [r"(?i)\\Documentation\b"],
    },
    # Projects whose Technical Writers teams work under \Documentation areas
    "active_roles": {
        "area_patterns": [r"(?i)\\Documentation\b"],
    },
    "defender": {
        "area_patterns": [r"(?i)\\Documentation\b"],
    },
    "identity_manager": {
        "area_patterns": [r"(?i)\\Documentation\b"],
    },
    "password_manager": {
        "area_patterns": [r"(?i)\\Documentation\b"],
    },
    "safeguard_privileged_passwords": {
        "area_patterns": [r"(?i)\\Documentation\b"],
    },
}

TECHCOMM_PROFILE = FilterProfile(
    name="TechComm",
    team_patterns=_TC_TEAM_PATTERNS,
    area_patterns=_TC_AREA_PATTERNS,
    full_projects=["techcomm"],
    project_overrides=_TC_PROJECT_OVERRIDES,
)
