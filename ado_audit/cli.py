#!/usr/bin/env python3
"""Simple CLI to orchestrate exporters and parsers.

Examples (cmd.exe):

  python cli.py --all                            # export+parse everything
  python cli.py --all --targets project          # export+parse project-level only
  python cli.py --all --targets org              # export+parse org-level only
  python cli.py --export --targets wits teams    # export specific targets
  python cli.py --parse --targets processorg     # parse specific target
  python cli.py --export --targets org wits      # mix group alias + individual

"""
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


# Group aliases expand into individual targets
PROJECT_TARGETS = ['wits', 'classification', 'teams', 'process', 'backlogconfig', 'teamsettings']
ORG_TARGETS = ['processorg', 'fields', 'workitems']
ALL_TARGETS = PROJECT_TARGETS + ORG_TARGETS

SCRIPT_MAP = {
    'wits': {
        'export': 'exporters/export_wit_raw.py',
        'parse': 'parsers/parse_wit_states.py'
    },
    'classification': {
        'export': 'exporters/export_classification_raw.py',
        'parse': 'parsers/parse_classification.py'
    },
    'teams': {
        'export': 'exporters/export_teams_boards_raw.py',
        'parse': ['parsers/parse_teams_boards.py', 'parsers/parse_swimlanes.py']
    },
    'process': {
        'export': 'exporters/export_process_template_raw.py',
        'parse': 'parsers/parse_process_template.py'
    },
    'backlogconfig': {
        'export': 'exporters/export_backlog_config_raw.py',
        'parse': 'parsers/parse_backlog_config.py'
    },
    'teamsettings': {
        'export': 'exporters/export_team_settings_raw.py',
        'parse': ['parsers/parse_team_settings.py', 'parsers/parse_team_backlog_levels.py']
    },
    'processorg': {
        'export': 'exporters/export_process_org_raw.py',
        'parse': 'parsers/parse_process_org.py'
    },
    'fields': {
        'export': 'exporters/export_wit_raw.py',  # Fields export happens with WIT export
        'parse': 'parsers/parse_fields.py'
    },
    'workitems': {
        'export': 'exporters/export_workitem_metadata_raw.py',
        'parse': ['parsers/parse_workitem_metadata.py', 'parsers/workitem_project_summary.py']
    }
}

ANALYZE_MAP = {
    'techcomm': 'analyzers/analyze_techcomm.py',
}


def run_script(path: str, projects: List[str]) -> bool:
    """Run a script subprocess. Returns True on success, False on failure."""
    script_path = Path(path)
    if not script_path.is_absolute():
        script_path = (Path(__file__).resolve().parent / script_path).resolve()

    cmd = [sys.executable, str(script_path)]
    if projects:
        cmd += projects
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        if result.stdout:
            print(result.stdout)
        return True
    else:
        print(f"\nERROR: Script failed with exit code {result.returncode}")
        if result.stdout:
            print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return False


def main():
    valid_choices = list(SCRIPT_MAP.keys()) + ['all', 'project', 'org']
    p = argparse.ArgumentParser()
    p.add_argument('--export', action='store_true', help='Run exporters')
    p.add_argument('--parse', action='store_true', help='Run parsers')
    p.add_argument('--analyze', nargs='*', default=None,
                   choices=list(ANALYZE_MAP.keys()),
                   help='Run analyzers (default: techcomm)')
    p.add_argument('--all', action='store_true', help='Run exporters then parsers')
    p.add_argument('--targets', nargs='+', choices=valid_choices, default=['all'],
                   help='Which targets to run (project, org, all, or individual names)')
    p.add_argument('--projects', nargs='*', default=[], help='Optional project IDs or names to pass to exporters')
    args = p.parse_args()

    if args.all:
        args.export = True
        args.parse = True

    # Expand group aliases into individual targets (preserving order, no duplicates)
    expanded = []
    for t in args.targets:
        if t == 'all':
            additions = ALL_TARGETS
        elif t == 'project':
            additions = PROJECT_TARGETS
        elif t == 'org':
            additions = ORG_TARGETS
        else:
            additions = [t]
        for a in additions:
            if a not in expanded:
                expanded.append(a)
    targets = expanded

    if args.export:
        for t in targets:
            script = SCRIPT_MAP[t]['export']
            if not run_script(script, args.projects):
                print(f"\nExport failed for '{t}'. Aborting. Fix the issue and try again.")
                sys.exit(1)

    if args.parse:
        for t in targets:
            scripts = SCRIPT_MAP[t]['parse']
            # Handle both single parser and list of parsers
            if isinstance(scripts, str):
                scripts = [scripts]
            
            for script in scripts:
                if not run_script(script, args.projects):
                    print(f"\nParse failed for '{t}'. Aborting. Fix the issue and try again.")
                    sys.exit(1)

    # Run analyzers if requested
    if args.analyze is not None:
        analyze_targets = args.analyze if args.analyze else ['techcomm']
        for name in analyze_targets:
            script = ANALYZE_MAP[name]
            if not run_script(script, args.projects):
                print(f"\nAnalysis failed for '{name}'. Aborting.")
                sys.exit(1)

    print("\n[OK] All operations completed successfully!")


if __name__ == '__main__':
    main()
