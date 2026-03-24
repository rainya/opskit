# ADO Audit Toolkit — Extension Plan: Top 3 Exporters

## Context for Copilot

This repo uses a three-layer architecture: a core ADO client (`azure_devops/client.py`), exporters that hit the API and save raw JSON to `data/raw/`, and parsers that read those JSON files and emit CSVs. All configuration lives in `azure_devops/config.py`. The CLI orchestrator is `cli.py`. Follow existing patterns exactly — new exporters and parsers should be structurally identical to `export_teams_boards_raw.py` and `parse_teams_boards.py`.

---

## Extension 1: Process Template Exporter

**Goal:** Capture the process template each project uses (Agile, Scrum, CMMI, or a custom inherited template) and its parent if custom.

**API endpoint:**
```
GET https://dev.azure.com/{org}/_apis/projects/{projectId}?includeCapabilities=true&api-version=7.1
```

The `capabilities.processTemplate` object in the response contains `templateName` and `templateTypeId`.

**New files to create:**
- `exporters/export_process_template_raw.py`
- `parsers/parse_process_template.py`

**Exporter behavior:**
- Iterate all projects (same pattern as existing exporters)
- For each project, call the endpoint above
- Save raw response to `data/raw/{project}_process_template.json`
- Skip projects with missing IDs, log warnings

**Parser output file:** `process_template_parsed_YYYYMMDD_HHMM.csv`

**Parser columns:**
```
Project ID, Project Name, Template Name, Template Type ID, Is Custom Inherited
```

`Is Custom Inherited`: boolean derived by checking whether `templateName` matches one of the three known base names (Agile, Scrum, CMMI). If it doesn't match, flag as custom/inherited.

**Wire into cli.py:** add `process` as a valid `--targets` value.

---

## Extension 2: Team Settings Exporter

**Goal:** Capture backlog navigation levels, bug behavior, and working days per team — the three settings with the most variation and the most direct WMF compliance relevance.

**API endpoints:**
```
# Team settings (bug behavior, working days, backlog iteration)
GET https://dev.azure.com/{org}/{project}/_apis/work/teamsettings?api-version=7.1

# Backlog-level configuration (which WIT levels are enabled/disabled)
GET https://dev.azure.com/{org}/{project}/_apis/work/teamsettings/backlogs?api-version=7.1
```

Both calls require the team context header:
```
Headers: { "X-TFS-TeamContext": "{teamId}" }
```

Or pass team as query param — check how `export_teams_boards_raw.py` currently passes team context and follow that pattern.

**New files to create:**
- `exporters/export_team_settings_raw.py`
- `parsers/parse_team_settings.py`

**Exporter behavior:**
- Iterate projects → teams (reuse team list logic from `export_teams_boards_raw.py`)
- For each team, call both endpoints above
- Save to:
  - `data/raw/{project}_{team}_teamsettings.json`
  - `data/raw/{project}_{team}_backlogs.json`
- Skip teams/projects with missing IDs

**Parser output — two CSVs:**

`team_settings_parsed_YYYYMMDD_HHMM.csv`
```
Project ID, Project Name, Team ID, Team Name, Bug Behavior, Working Days, Backlog Iteration Path
```

`team_backlog_levels_parsed_YYYYMMDD_HHMM.csv`
```
Project ID, Project Name, Team ID, Team Name, Backlog Level Name, WIT Names, Is Visible, Is Enabled
```

`Bug Behavior` values from ADO: `asRequirements`, `asTasks`, `off` — preserve raw value, add a human-readable column mapping these to `With Stories`, `With Tasks`, `Not on Backlogs`.

**Wire into cli.py:** add `teamsettings` as a valid `--targets` value.

---

## Extension 3: Swimlane Exporter

**Goal:** Capture swimlane configuration per board — names and order. Presence and naming of swimlanes signals team-level customization depth and is not captured by the existing board columns exporter.

**API endpoint:**
```
GET https://dev.azure.com/{org}/{project}/_apis/work/boards/{boardId}/rows?api-version=7.1
```

Board IDs are already captured in `data/raw/{project}_{team}_boards.json` from the existing exporter — the swimlane exporter should read those files rather than re-calling the teams/boards endpoints.

**New files to create:**
- `exporters/export_swimlanes_raw.py`
- `parsers/parse_swimlanes.py`

**Exporter behavior:**
- Load existing `data/raw/{project}_{team}_boards.json` files (do not re-hit the boards API)
- For each board ID found, call the rows endpoint
- Save to `data/raw/{project}_{team}_{board}_swimlanes.json`
- If no rows endpoint returns data (board has no custom swimlanes), save an empty result rather than skipping — absence is meaningful data

**Parser output file:** `swimlanes_parsed_YYYYMMDD_HHMM.csv`

**Parser columns:**
```
Project ID, Project Name, Team ID, Team Name, Board ID, Board Name, Row ID, Row Name, Row Order, Is Default
```

`Is Default`: ADO returns a default row (usually empty name or "Default Lane") — flag it so you can filter it out in analysis and only count intentional custom swimlanes.

**Wire into cli.py:** add `swimlanes` as a valid `--targets` value.

---

## Config Updates (`azure_devops/config.py`)

Add the following constants so all new exporters and parsers use centralized naming:

```python
# Process template
PROCESS_TEMPLATE_FILENAME = "{project}_process_template.json"

# Team settings
TEAM_SETTINGS_FILENAME = "{project}_{team}_teamsettings.json"
TEAM_BACKLOGS_FILENAME = "{project}_{team}_backlogs.json"

# Swimlanes
SWIMLANES_FILENAME = "{project}_{team}_{board}_swimlanes.json"
```

---

## CLI Target Summary (updated)

| Target flag | Exporters | Parsers |
|---|---|---|
| `wits` | export_wit_raw | parse_wit_states |
| `classification` | export_classification_raw | parse_classification |
| `teams` | export_teams_boards_raw | parse_teams_boards |
| `process` | export_process_template_raw | parse_process_template |
| `teamsettings` | export_team_settings_raw | parse_team_settings |
| `swimlanes` | export_swimlanes_raw | parse_swimlanes |

---

## Suggested Build Order

1. **Process template** — smallest scope, single API call per project, validates your extension pattern before tackling nested loops
2. **Team settings** — more complex due to nested project → team iteration and two endpoints per team, but highest diagnostic value
3. **Swimlanes** — depends on existing board JSON being present, so run after `teams` export; reads from disk rather than re-hitting the API which is a slightly different pattern worth getting right cleanly
