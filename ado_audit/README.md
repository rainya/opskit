# ADO Audit — Exporters and Parsers

This repository contains scripts to export Azure DevOps (ADO) project metadata and work item data, save raw JSON dumps, and parse those dumps into CSV/Excel-friendly outputs. The system uses a centralized configuration file with environment variable overrides for flexible deployment.

## Architecture Overview

The system is organized into three layers:

1. **Core Module** (`azure_devops/`): Handles authentication, API communication, and centralized configuration
   - `client.py` — ADO REST API client with pagination and error handling
   - `config.py` — Centralized configuration constants (paths, formats, API versions, logging)
   - `utils.py` — Utility functions (PAT reading, filename sanitization, JSON I/O)

2. **Exporters** (`exporters/`): Call ADO REST APIs and save raw JSON to `_data/raw/`
   - Independent of parsing logic
   - Can be run selectively by project ID
   - Includes null-check safety (skips projects with missing IDs)
   - **Base Class**: All exporters inherit from `BaseExporter` which provides:
     - Project fetching and filtering logic
     - Folder setup and metadata saving
     - Error handling and reporting
     - Template Method pattern for consistent workflow

3. **Parsers** (`parsers/`): Read raw JSON files and emit structured CSV outputs
   - Can be re-run without hitting the API
   - Uses centralized configuration for consistency
   - Located in project root directory
   - **Base Class**: All parsers inherit from `BaseParser` which provides:
     - Project folder discovery
     - File pattern matching
     - CSV writing with DictWriter
     - Orchestration loop for all projects
     - Template Method pattern for consistent workflow

### Base Class Architecture

The toolkit uses the **Template Method design pattern** to eliminate code duplication:

- **BaseExporter** (130 lines): Handles PAT setup, client initialization, project fetching/filtering (case-insensitive), folder creation, metadata saving, and error reporting. Subclasses implement only `export_project_data()`.

- **BaseParser** (156 lines): Handles timestamp generation, project folder discovery, file finding, CSV writing, and orchestration. Subclasses implement only 4 methods:
  - `get_file_pattern()` — Which files to process (e.g., "_wits.json")
  - `get_output_filename()` — Output filename prefix
  - `get_csv_fieldnames()` — CSV column headers
  - `parse_project_data()` — Business logic to extract data

## Quick Start

### 1. Authentication

Set environment variables in `cmd.exe`:

```bat
set ADO_ORG=your_org_name
set ADO_PAT=your_personal_access_token
```

**Alternative**: The scripts will look for a local `ado_pat.txt` file if `ADO_PAT` is not set.

### 2. Run Exporters (export raw JSON)

Export everything:

```bat
python exporters\export_wit_raw.py
python exporters\export_classification_raw.py
python exporters\export_teams_boards_raw.py
python exporters\export_process_template_raw.py
python exporters\export_backlog_config_raw.py
python exporters\export_team_settings_raw.py
```

Export specific projects by ID or name:

```bat
python exporters\export_wit_raw.py PROJECT-UUID-1 PROJECT-UUID-2
python exporters\export_classification_raw.py PROJECT-UUID-1
python exporters\export_teams_boards_raw.py PROJECT-NAME
python exporters\export_process_template_raw.py PROJECT-NAME
python exporters\export_backlog_config_raw.py PROJECT-NAME
python exporters\export_team_settings_raw.py PROJECT-NAME
```

### 3. Run Parsers (convert JSON → CSV)

```bat
python parsers\parse_wit_states.py
python parsers\parse_classification.py
python parsers\parse_teams_boards.py
python parsers\parse_swimlanes.py
python parsers\parse_process_template.py
python parsers\parse_backlog_config.py
python parsers\parse_team_settings.py
python parsers\parse_team_backlog_levels.py
```

### 4. Run Both Together (CLI Orchestration)

```bat
python cli.py --all                            # export+parse everything (project + org)
python cli.py --all --targets project          # export+parse project-level only
python cli.py --all --targets org              # export+parse org-level only
python cli.py --all --projects PROJECT-NAME    # everything, filtered to one project

python cli.py --export --targets project       # export all project-level targets
python cli.py --parse --targets org            # parse all org-level targets
python cli.py --export --targets org wits      # mix: all org + just wits from project
python cli.py --parse --targets processorg     # parse a single target
```

**Available targets:**

*Individual targets:*

- `wits` — Work item types and states
- `classification` — Areas and iterations
- `teams` — Teams, boards, columns, and swimlanes
- `process` — Process templates (Agile/Scrum/CMMI/Custom)
- `backlogconfig` — Backlog configuration (portfolio/requirement/task levels)
- `teamsettings` — Team settings (bug behavior, working days, backlog visibilities)
- `processorg` — Organization-level process definitions (WIT states, fields, rules)
- `fields` — Organization-level field definitions (reference names, types, picklists)
- `workitems` — Organization-level work item metadata by area path via OData (detailed + project summary)

*Group aliases:*

- `project` — All project-level targets (wits, classification, teams, process, backlogconfig, teamsettings)
- `org` — All organization-level targets (processorg, fields, workitems)
- `all` — Everything (project + org)

## Work Item Metadata (OData)

Exports work item metadata aggregated by area path, work item type, and state using the OData Analytics API. Data flows through the standard export → JSON → parse → CSV pipeline, with all data stored in the org-level folder (`_data/raw/_1id/` and `_data/output/_1id/`).

### Export

```bat
python exporters\export_workitem_metadata_raw.py
python exporters\export_workitem_metadata_raw.py PROJECT-NAME
python exporters\export_workitem_metadata_raw.py --fallback
```

**Saves:** `_data/raw/_1id/workitem_metadata_by_area.json` — consolidated JSON with all projects in a single file.

**Features:**
- Server-side `$apply` aggregation (single request per project, no item limit)
- Automatic fallback to client-side aggregation if `$apply` not supported
- `--fallback` flag to force client-side mode
- Requires PAT with **Analytics (Read)** permission

### Parse: Detailed Metadata

```bat
python parsers\parse_workitem_metadata.py
```

**Output:** `_data/output/_1id/workitem_metadata_by_area_parsed_YYYYMMDD_HHMM.csv`

**CSV Columns:**
- Project ID, Project Name, Area Path, Depth
- Work Item Type, State
- Count (items in this area+type+state group)
- Min/Max Created Date (YYYY-MM-DD)
- Min/Max Changed Date (YYYY-MM-DD)
- Total Area Count (sum across all types/states for this area)

### Parse: Project Summary

```bat
python parsers\workitem_project_summary.py
python parsers\workitem_project_summary.py PROJECT-NAME
```

**Output:** `_data/output/_1id/workitem_project_summary_YYYYMMDD_HHMM.csv`

**CSV Columns:**
- Project ID, Project Name
- Distinct Area Paths, Distinct Work Item Types, Distinct States
- Total Work Item Count
- Min/Max Created Date, Min/Max Changed Date (project-wide)

## Configuration System

All configuration is centralized in `azure_devops/config.py`. Override defaults using environment variables:

| Config Item | Environment Variable | Default | Notes |
|---|---|---|---|
| Output data directory | `DATA_RAW_DIR` | `_data/raw` | Where JSON files are saved/read |
| Raw data directory | `DATA_OUTPUT_DIR` | `_data/output` | Where parsed CSV files are saved |
| Sample data directory | `DATA_SAMPLES_DIR` | `_data/samples` | For test/sample data |
| Archive output directory | `ARCHIVE_OUTPUT_DIR` | `archive_output` | For archived outputs |
| CSV timestamp format | (hardcoded) | `%Y%m%d_%H%M` | Used in all timestamped filenames |
| Log level | `LOG_LEVEL` | `INFO` | Python logging level (DEBUG, INFO, WARNING, ERROR) |
| API versions | (hardcoded) | `7.1` | Centralized for all endpoints |

### Example: Override data directory

```bat
set DATA_RAW_DIR=C:\custom\data\path
python exporters\export_wit_raw.py
```

## Data Flow

```
ADO REST API
    ↓
[Exporters] → JSON files → _data/raw/ → [Parsers] → CSV files → _data/output
```

- **Export time**: Hits ADO API, saves JSON to `_data/raw/` with timestamped naming
- **Parse time**: Reads from `_data/raw/`, generates CSV and saves to `_data/output/` with timestamped name
- **Separation advantage**: Re-run parsers without API calls; inspect raw JSON independently

## Exporters Detail

### export_wit_raw.py

Exports work item types, states, and organization fields.

**Saves files:**

- `fields.json` — org-level field definitions (parse with `parse_fields.py`)
- `{project}_project.json` — project metadata
- `{project}_wits.json` — all work item types in project
- `{project}_{wit_type}_states.json` — states for each work item type

**Usage:**

```bat
python exporters\export_wit_raw.py                  # All projects
python exporters\export_wit_raw.py PROJECT-UUID     # Specific project
```

**Features:**

- Skips projects with missing IDs (logs warning)
- Saves project metadata alongside WIT definitions
- Fetches states for each work item type

### export_classification_raw.py

Exports areas and iterations hierarchies.

**Saves files:**

- `{project}_areas.json` — area classification nodes
- `{project}_iterations.json` — iteration classification nodes

**Usage:**

```bat
python exporters\export_classification_raw.py                  # All projects
python exporters\export_classification_raw.py PROJECT-UUID     # Specific project
```

**Features:**

- Handles hierarchical node structures
- Skips projects with missing IDs
- Supports configurable depth parameter

### export_teams_boards_raw.py

Exports teams and complete board details (columns, swimlanes, metadata) in optimized single API calls.

**Saves files:**

- `{project}_teams.json` — all teams in project
- `{project}_{team}_{board}.json` — complete board details for each board

**Board details include:**

- `columns` array — column definitions with state mappings, WIP limits, split flags
- `rows` array — swimlanes/lanes configuration
- `allowedMappings` — state mappings by column type (Incoming/InProgress/Outgoing)
- `fields` — custom field references (columnField, rowField, doneField)
- `revision`, `isValid`, `canEdit` — board metadata

**Usage:**

```bat
python exporters\export_teams_boards_raw.py                    # All projects
python exporters\export_teams_boards_raw.py PROJECT-UUID       # Specific project
```

**Features:**

- **50% fewer API calls** — uses GET board detail instead of separate columns endpoint
- Captures columns + swimlanes + metadata in one call per board
- Skips projects with missing IDs
- Handles safe filename generation from team/board names
- Per-board error handling for resilience

### export_process_template_raw.py

Exports process template information for each project.

**Saves files:**

- `{project}_process_template.json` — process template details including capabilities

**Usage:**

```bat
python exporters\export_process_template_raw.py                # All projects
python exporters\export_process_template_raw.py PROJECT-NAME   # Specific project
```

**Features:**

- Captures template name (Agile, Scrum, CMMI, or custom inherited)
- Includes template type ID for custom process identification
- Enables differentiation between base and inherited processes

### export_process_org_raw.py

Exports organization-level process definitions including WIT states, fields, and rules.

**Saves files (org-level, in _data/raw/_orgName/):**

- `org_processes.json` — all processes defined at org level (top-level)
- `processes/{processName}/` — per-process subfolder (lowercase, e.g., `processes/scrum/`, `processes/org_agile_process_-_prod/`)
  - `{processTypeId}_process_detail.json` — process detail with parent references
  - `{processTypeId}_wits.json` — WIT inventory per process
  - `{processTypeId}_{witRefName}_states.json` — state definitions per WIT
  - `{processTypeId}_fields.json` — custom fields per process (inherited processes only)
  - `{processTypeId}_{witRefName}_rules.json` — rules for Feature and User Story WITs

**Usage:**

```bat
python exporters\export_process_org_raw.py    # Org-level only, no project filtering
python cli.py --export --targets processorg   # Or via CLI
```

**Features:**

- Captures authoritative process template definitions independent of projects
- Shows parent process references for custom inherited processes
- Includes state customization flags (inherited vs custom)
- Scoped rules export (Feature and User Story only) for high diagnostic value
- Handles API 404 errors gracefully (fields endpoint not available for all processes)

### export_backlog_config_raw.py

Exports backlog configuration showing portfolio/requirement/task level hierarchy.

**Saves files:**

- `{project}_backlogconfig.json` — backlog level configuration

**Usage:**

```bat
python exporters\export_backlog_config_raw.py                  # All projects
python exporters\export_backlog_config_raw.py PROJECT-NAME     # Specific project
```

**Features:**

- Captures which WITs map to which backlog levels
- Shows rank fields used for ordering
- Validates WMF WIT model deployment

### export_team_settings_raw.py

Exports team settings including bug behavior, working days, and backlog visibilities.

**Saves files:**

- `{project}_{team}_teamsettings.json` — team configuration settings
- `{project}_{team}_backlogs.json` — backlog instances with hierarchy and limits

**Usage:**

```bat
python exporters\export_team_settings_raw.py                   # All projects
python exporters\export_team_settings_raw.py PROJECT-NAME      # Specific project
```

**Features:**

- Captures bug behavior (with stories/tasks/off backlogs)
- Records working days per team
- Extracts backlog visibility settings (which levels enabled)
- Includes default iteration settings and macros
- Per-team error handling for resilience

## Parsers Detail

### parse_wit_states.py

Parses work item type states into a normalized CSV format.

**Output file:** `wit_states_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, WIT Type, State Name, State Category, State Color

### parse_classification.py

Parses area and iteration hierarchies into a flat CSV.

**Output file:** `classification_nodes_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, Node Type, Path, Depth, Node ID, Start Date, Finish Date

**Features:**

- Flattens hierarchical structures using path notation (e.g., `Team/Sprint/Task`)
- Calculates depth based on path nesting
- Cross-platform path handling (works on Windows/Linux)

### parse_teams_boards.py

Parses board columns from board detail JSON files into a normalized CSV.

**Output file:** `teams_boards_columns_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, Team ID, Team Name, Board ID, Board Name, Column ID, Column Name, Column Order, State Mapping, WIP Limit, Split Column

**Features:**

- Extracts `columns` array from board detail files
- Preserves column ordering
- Extracts state mappings from columns
- Extracts WIP limits and split column flags
- Works with enhanced board detail JSON structure

### parse_swimlanes.py

Parses board swimlanes (rows) from board detail JSON files into CSV.

**Output file:** `swimlanes_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, Team ID, Team Name, Board ID, Board Name, Row ID, Row Name, Row Order, Is Default

**Features:**

- Extracts `rows` array from board detail files
- Identifies default swimlane (all-zeros GUID) vs custom lanes
- Preserves swimlane ordering
- Enables analysis of team-level board customization depth

### parse_process_template.py

Parses process template information to identify custom vs base templates.

**Output file:** `process_template_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, Template Name, Template Type ID, Is Custom Inherited

**Features:**

- Identifies base templates (Agile, Scrum, CMMI)
- Flags custom inherited processes
- Enables process compliance analysis

### parse_process_org.py

Parses organization-level process definitions into two comprehensive CSVs.

**Reads from:** `_data/raw/_orgName/` (e.g., `_data/raw/_1id/`)

**Output files (in _data/output/_orgName/):**

- `process_org_summary_parsed_YYYYMMDD_HHMM.csv` — Process summary with counts
- `process_org_wit_states_parsed_YYYYMMDD_HHMM.csv` — Detailed WIT state definitions

**Summary CSV Columns:** Process Type ID, Process Name, Parent Process Name, Is Custom Inherited, Is Default, WIT Count, Custom Field Count

**WIT States CSV Columns:** Process Type ID, Process Name, WIT Ref Name, WIT Name, State Name, State Category, Is Inherited, Is Customized

**Usage:**

```bat
python parsers\parse_process_org.py
python cli.py --parse --targets processorg    # Or via CLI
```

**Features:**

- Shows process hierarchy (base templates and their inherited children)
- Identifies default org process
- Captures state customization (inherited vs custom states)
- State categories (Proposed, InProgress, Completed, Removed)
- Enables cross-process comparison and compliance validation

### parse_fields.py

Parses organization-level field definitions from fields.json into CSV.

**Reads from:** `_data/raw/fields.json` (org-wide field metadata)

**Output file (in _data/output/_orgName/):** `fields_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Reference Name, Display Name, Description, Type, Usage, Is Queryable, Can Sort By, Is Identity, Is Picklist, Picklist ID, Is Picklist Suggested, Read Only, Is Locked, Supported Operations Count, URL

**Usage:**

```bat
python parsers\parse_fields.py
python cli.py --parse --targets fields         # Or via CLI
```

**Features:**

- Captures all custom and system fields in the organization
- Field metadata: type (string, integer, dateTime, html, identity, boolean), usage (workItem, workItemTypeExtension)
- Flags queryable, sortable, identity, and picklist fields
- Shows read-only and locked status
- Counts supported WIQL operators per field
- Enables field inventory and compliance analysis

### parse_backlog_config.py

Parses backlog configuration showing WIT-to-level mappings.

**Output file:** `backlog_config_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, Backlog Level Name, Backlog Level Type, WIT Ref Names, WIT Display Names, Rank Field Ref Name

**Features:**

- Flattens portfolio/requirement/task hierarchy
- Shows which WITs belong to which backlog levels
- Captures rank field configuration

### parse_team_settings.py

Parses team settings including bug behavior and backlog visibilities.

**Output file:** `team_settings_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, Team ID, Team Name, Bug Behavior, Bug Behavior Label, Working Days, Backlog Iteration Path, Default Iteration Path, Default Iteration Macro, Initiatives Visible, Epics Visible, Features Visible, Stories Visible

**Features:**

- Human-readable bug behavior labels (With Stories/Tasks/Not on Backlogs)
- Backlog visibility flags per portfolio level
- Default iteration settings including macros (@currentIteration, etc.)
- Working days configuration

### parse_team_backlog_levels.py

Parses team backlog instances showing hierarchy and limits.

**Output file:** `team_backlog_levels_parsed_YYYYMMDD_HHMM.csv`

**Columns:** Project ID, Project Name, Team ID, Team Name, Backlog ID, Backlog Level Name, Rank, Work Item Count Limit

**Features:**

- Shows actual backlog hierarchy per team (Initiatives→Epics→Features→Stories→Tasks)
- Rank indicates hierarchy order (5=highest, 1=lowest)
- Work item count limits per level

## Directory Structure

```
ADO_audit/
├── azure_devops/
│   ├── __init__.py
│   ├── client.py          # ADO REST API client
│   ├── config.py          # Centralized configuration
│   ├── utils.py           # Utility functions
│   └── audit.py           # Audit logic (legacy)
├── exporters/
│   ├── base_exporter.py       # Base class for all exporters
│   ├── export_wit_raw.py
│   ├── export_classification_raw.py
│   ├── export_teams_boards_raw.py
│   ├── export_process_template_raw.py
│   ├── export_process_org_raw.py
│   ├── export_backlog_config_raw.py
│   └── export_team_settings_raw.py
├── parsers/
│   ├── base_parser.py         # Base class for all parsers
│   ├── utils.py               # Parser utilities (file loading, metadata extraction)
│   ├── parse_wit_states.py
│   ├── parse_classification.py
│   ├── parse_teams_boards.py
│   ├── parse_swimlanes.py
│   ├── parse_process_template.py
│   ├── parse_process_org.py
│   ├── parse_fields.py
│   ├── parse_backlog_config.py
│   ├── parse_team_settings.py
│   └── parse_team_backlog_levels.py
├── tests/
│   ├── run_parsers_on_samples.py
│   └── test_parsers_unit.py
├── _references/
│   ├── ADO_Audit_Extension_Plan.md
│   ├── ADO_audit_refactoring_guide.md
│   ├── ADO_audit_toolkit_review.md
│   └── Power_BI_OData_Connection_Guide.md  # Power BI OData setup instructions
├── _data/
│   ├── raw/               # Exported JSON files (created at runtime)
│   ├── output/            # Parsed CSV files (created at runtime)
│   └── samples/           # Test/sample JSON files
├── cli.py                 # Orchestrator script
├── workitem_counts_by_area.py  # Standalone utility: count work items by area (WIQL)
├── workitem_metadata_by_area_odata.py  # Standalone utility: metadata by area (OData)
├── refactored_ado_audit_to_excel.py  # Main reporting script
└── README.md
```

## Output Locations

| Type | Location | Naming Convention |
|---|---|---|
| Raw JSON exports | `_data/raw/` | `{project}_{type}.json` |
| Raw JSON (org-level) | `_data/raw/_orgName/` | `process_org_{type}.json` |
| Parsed CSV files | `_data/output/` | `{data_type}_parsed_YYYYMMDD_HHMM.csv` |
| Parsed CSV (org-level) | `_data/output/_orgName/` | `process_org_{summary\|wit_states}_YYYYMMDD_HHMM.csv` |
| Utility outputs | `_data/output/` | `{utility_name}_YYYYMMDD_HHMM.csv` |
| Timestamp | All filenames | `CSV_TIMESTAMP_FORMAT = "%Y%m%d_%H%M"` |

## Error Handling & Safety Features

- **Null project IDs**: Exporters skip projects with missing IDs and log warnings
- **API errors**: Caught per-project; one failure doesn't stop the entire run
- **Logging**: All operations logged to console (configurable via `LOG_LEVEL`)
- **Type safety**: Includes type hints; use pylance/mypy for validation

## Legacy Code

The repo preserves original reporting scripts in `_legacy/` directory. Current recommended approach is to use the modular exporter/parser system:

- **Before**: Direct API calls → CSV in one monolithic script
- **After**: Clean separation between data collection (exporters) and formatting (parsers)

This allows you to:

- Inspect raw JSON independently
- Re-run parsers without API calls
- Cache data across multiple analysis runs
- Use parsers with sample/test data

## Development Notes

- Scripts use `sys.path` manipulation to allow relative imports; run from project root
- PNG files are avoided; all output is JSON/CSV
- Uses `pathlib.Path` for cross-platform path handling
- Environment variables override all hardcoded defaults
- All configuration constants live in one file for easy maintenance

## Troubleshooting

**Scripts fail with "No projects fetched"**

- Check `ADO_ORG` is set correctly
- Verify `ADO_PAT` has correct permissions (needs "Work Items (Read)" at minimum)

**Projects are skipped with "no project ID found"**

- This is normal; some projects may not have IDs (check ADO organization)
- Scripts log these as warnings and continue with other projects

**Import errors or module not found**

- Run scripts from project root directory
- Ensure you have Python 3.7+ with requests library installed

**CSV files are empty**

- Check `_data/raw/` has JSON files from exporters first
- Run exporters before running parsers
