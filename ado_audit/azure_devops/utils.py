"""Shared utility functions for Azure DevOps audit scripts."""
import os
import sys
import json
from typing import Optional, Dict, Any


def read_pat() -> str:
    """Read PAT from ADO_PAT environment variable or ado_pat.txt file.

    Returns:
        str: Personal Access Token

    Raises:
        SystemExit: If PAT is not found
    """
    pat = os.getenv("ADO_PAT")
    if pat:
        return pat
    # fallback to file
    try:
        with open("ado_pat.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        sys.exit("ADO_PAT not found in environment or ado_pat.txt")


def safe_name(name: Optional[str]) -> str:
    """Convert a name to a filesystem-safe string.

    Args:
        name: The name to sanitize

    Returns:
        str: Sanitized name with special characters replaced with underscores
    """
    if not name:
        return ""
    return name.replace(" ", "_").replace("/", "_").replace("\\", "_")


def load_json(path: str) -> Optional[Dict[str, Any]]:
    """Load JSON data from a file.

    Args:
        path: Path to JSON file

    Returns:
        dict: Parsed JSON, or None if file not found
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Failed to parse JSON from {path}: {str(e)}")
        return None
