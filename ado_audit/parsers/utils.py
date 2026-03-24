"""Shared utility functions for parser scripts."""
import os
import json
from typing import Optional, Dict, Any


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


def load_project_metadata(project_prefix: str, raw_dir: str) -> Dict[str, Any]:
    """Load project metadata JSON file.

    Args:
        project_prefix: Project name prefix (from filename)
        raw_dir: Directory containing raw JSON files

    Returns:
        dict: Project metadata with 'id' and 'name' keys, or empty dict if not found
    """
    proj_meta_path = os.path.join(raw_dir, f"{project_prefix}_project.json")
    proj_meta = load_json(proj_meta_path) or {}
    return proj_meta


def extract_project_info(proj_meta: Dict[str, Any], project_prefix: str) -> tuple:
    """Extract project ID and name from metadata.

    Args:
        proj_meta: Project metadata dictionary
        project_prefix: Fallback project name if metadata missing

    Returns:
        tuple: (project_id, project_name)
    """
    project_id = proj_meta.get('id') or proj_meta.get('projectId') or ''
    project_name = proj_meta.get('name') or project_prefix
    return project_id, project_name


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
