# ADO Audit Toolkit — Extension Plan v2

## Context for Copilot

This repo uses a three-layer architecture: a core ADO client (`azure_devops/client.py`), exporters that hit the API and save raw JSON to `data/raw/`, and parsers that read those JSON files and emit CSVs. All configuration lives in `azure_devops/config.py`. The CLI orchestrator is `cli.py`. Follow existing patterns exactly — new exporters and parsers should be structurally identical to `export_teams_boards_raw.py` and `parse_teams_boards.py`.

---

## Existing Exporter Coverage and Verification Notes

Before building new exporters, verify the following in the existing toolkit:

| Exporter | Covers | Verification Action |
|---|---|---|
| `export_classification_raw.py` | Area path tree, iteration path tree | Confirm `$depth` parameter is set to 10 or higher |
| `export_wit_raw.py` | WIT definitions, states per WIT | Confirm WIT reference name strings match org's process (custom inherited processes may rename base types) |
| `export_teams_boards_raw.py` | Team list, board columns | Confirm full team list is captured, not only teams with boards configured |

---

## Extension 1: Process Template — Project Level

**Goal:** Capture the process template each project uses (Agile, Scrum, CMMI, or a custom inherited template) and its parent lineage.

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

`Is Custom Inherited`: boolean derived by checking whether `templateName` matches one of the three known base names (Agile, Scrum, CMMI). If it does not match, flag as custom/inherited.

**Wire into cli.py:** add `process` as a valid `--targets` value.

---

## Extension 2: Process Template — Org Level Detail ✅ COMPLETED

**Status:** Implemented (March 2026)

**Implementation:** Created `export_process_org_raw.py` exporter and `parse_process_org.py` parser to capture organization-level process definitions independent of projects.

**Files created:**

- **Exporter:** `exporters/export_process_org_raw.py` - Exports all org-level process data to `data/raw/` root
- **Parser:** `parsers/parse_process_org.py` - Parses into 2 CSVs (summary + detailed WIT states)

**Benefits achieved:**

- **Authoritative process baseline** captured at org level (independent of project instances)
- **Process hierarchy** visible (base templates: Scrum/Agile/CMMI/Basic + 20 inherited custom)
- **State customization tracking** via Is Inherited and Is Customized flags
- **Parent references** preserved for custom inherited processes
- **Default process identification** (e.g., "Scrum with Initiatives" marked as default)

**Data insights from testing:**

- 24 total processes (4 system base + 20 custom inherited)
- 928 WIT state rows captured across all processes
- Custom Field Count: 0 for all (API /fields endpoint returns 404 for most processes - expected limitation)
- Rules exported for Feature and User Story WITs only (scoped for diagnostic value)

**CLI integration:** `python cli.py --export --targets processorg` and `--parse --targets processorg`

---

## ~~Extension 2: Process Template — Org Level Detail~~ (Original Plan - Implementation Complete)

**Goal:** Capture the full process definition at the organization level — WIT inventory, state definitions per WIT, and custom fields — to establish what the template actually specifies independent of any individual project. This is more authoritative than project-level WIT state calls because it shows the template definition rather than the instance.

**API endpoints:**

```
# 1. List all processes defined at org level
GET https://dev.azure.com/{org}/_apis/work/processes?api-version=7.1

# 2. Process detail by ID (includes parent process reference for inherited processes)
GET https://dev.azure.com/{org}/_apis/work/processes/{processTypeId}?api-version=7.1

# 3. All WITs defined in a process
GET https://dev.azure.com/{org}/_apis/work/processes/{processTypeId}/workitemtypes?api-version=7.1

# 4. States for a specific WIT within a process
GET https://dev.azure.com/{org}/_apis/work/processes/{processTypeId}/workitemtypes/{witRefName}/states?api-version=7.1

# 5. Fields defined in a process (identifies org-level custom field additions)
GET https://dev.azure.com/{org}/_apis/work/processes/{processTypeId}/fields?api-version=7.1

# 6. Rules for a WIT within a process (deepest level the API exposes)
GET https://dev.azure.com/{org}/_apis/work/processes/{processTypeId}/workitemtypes/{witRefName}/rules?api-version=7.1
```

**API constraint note:** The REST API does not expose a full portable template export (no equivalent of export-to-XML). Endpoints 1–6 above are the ceiling of what the API provides. Form layout definitions are not accessible via REST. If a full template export is needed for archival or migration purposes, use `az devops invoke` with `exportLayout=true` as a one-time manual run — do not build this into the toolkit.

**New files to create:**

- `exporters/export_process_org_raw.py`
- `parsers/parse_process_org.py`

**Exporter behavior:**

- Call endpoint 1 to get all org-level processes and save `org_processes.json`
- For each process, call endpoint 2 (detail) and save `{processTypeId}_process_detail.json`
- For each process, call endpoint 3 (WIT list) and save `{processTypeId}_wits.json`
- For each WIT, call endpoint 4 (states) and save `{processTypeId}_{witRefName}_states.json`
- For each process, call endpoint 5 (fields) and save `{processTypeId}_fields.json`
- For Feature and User Story WITs specifically, call endpoint 6 (rules) and save `{processTypeId}_{witRefName}_rules.json`
- Scope endpoint 6 to Feature and User Story only for the initial audit — rules for all WITs is high call volume with limited additional diagnostic value

**Parser output — two CSVs:**

`process_org_summary_parsed_YYYYMMDD_HHMM.csv`

```
Process Type ID, Process Name, Parent Process Name, Is Custom Inherited, Is Default, WIT Count, Custom Field Count
```

`process_org_wit_states_parsed_YYYYMMDD_HHMM.csv`

```
Process Type ID, Process Name, WIT Ref Name, WIT Name, State Name, State Category, Is Inherited, Is Customized
```

`Is Inherited` and `Is Customized`: ADO returns these flags on state objects in process-level calls — preserve them. They distinguish states carried from the parent template versus states added or modified in the custom inherited process.

**Wire into cli.py:** add `processorg` as a valid `--targets` value.

---

## Extension 3: Team Settings

**Goal:** Capture backlog navigation levels, bug behavior, and working days per team — the three settings with the most variation and the most direct WMF compliance relevance.

**API endpoints:**

```
# Team settings (bug behavior, working days, backlog iteration)
GET https://dev.azure.com/{org}/{project}/_apis/work/teamsettings?api-version=7.1

# Backlog-level configuration (which WIT levels are enabled/disabled)
GET https://dev.azure.com/{org}/{project}/_apis/work/teamsettings/backlogs?api-version=7.1
```

Both calls require team context. Check how `export_teams_boards_raw.py` currently passes team context and follow that pattern exactly.

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
Project ID, Project Name, Team ID, Team Name, Bug Behavior, Bug Behavior Label, Working Days, Backlog Iteration Path
```

`team_backlog_levels_parsed_YYYYMMDD_HHMM.csv`

```
Project ID, Project Name, Team ID, Team Name, Backlog Level Name, WIT Names, Is Visible, Is Enabled
```

`Bug Behavior` raw ADO values: `asRequirements`, `asTasks`, `off` — preserve raw value in `Bug Behavior` column, add human-readable `Bug Behavior Label` column mapping to `With Stories`, `With Tasks`, `Not on Backlogs`.

**Wire into cli.py:** add `teamsettings` as a valid `--targets` value.

---

## Extension 4: Swimlanes ✅ COMPLETED (via Boards Refactoring)

**Status:** Implemented as part of boards exporter enhancement (March 2026)

**Implementation:** Instead of creating a separate swimlanes exporter, the `export_teams_boards_raw.py` exporter was refactored to call the board GET detail endpoint which returns columns, rows (swimlanes), and metadata in a single API call.

**Result:**

- **Exporter:** `exporters/export_teams_boards_raw.py` captures complete board details including swimlanes
- **Parsers:**
  - `parsers/parse_teams_boards.py` — extracts columns from board detail JSON
  - `parsers/parse_swimlanes.py` — extracts rows (swimlanes) from board detail JSON
- **CLI target:** `teams` — runs both parsers automatically

**Benefits achieved:**

- **50% fewer API calls** (eliminated separate /columns endpoint)
- **Captures swimlanes** without additional exporter
- **Captures additional metadata:** allowedMappings, fields (columnField, rowField, doneField), revision, canEdit

**Parser output file:** `swimlanes_parsed_YYYYMMDD_HHMM.csv`

**Parser columns:** Project ID, Project Name, Team ID, Team Name, Board ID, Board Name, Row ID, Row Name, Row Order, Is Default

**Data insights:**

- `Is Default`: Identifies default swimlane (00000000-0000-0000-0000-000000000000 GUID) vs custom lanes
- Custom swimlanes indicate team-level board customization depth
- Example: Product Management team in Starling has 10 custom swimlanes on Epics board (2FA, Connect, Governance, On Demand, Platform, etc.)

---

## ~~Extension 4: Swimlanes~~ (Original Plan - Superseded)

~~**Goal:** Capture swimlane configuration per board — names and order.~~

~~**API endpoint:** GET `/{project}/_apis/work/boards/{boardId}/rows`~~

~~**Status:** Superseded by boards refactoring. Swimlanes now captured via GET board detail endpoint which includes both columns and rows arrays in single response.~~

---

## Extension 5: Backlog Configuration

**Goal:** Capture which WITs are mapped to which backlog levels at the project level. Validates whether the WMF WIT model is deployed correctly and whether backlog level configuration has drifted from the process template definition.

**API endpoint:**

```
GET https://dev.azure.com/{org}/{project}/_apis/work/backlogconfiguration?api-version=7.1
```

This endpoint returns the full hierarchy of backlog levels (portfolio, requirement, task) and which WITs are mapped to each level. Does not require team context — this is project-scoped.

**New files to create:**

- `exporters/export_backlog_config_raw.py`
- `parsers/parse_backlog_config.py`

**Exporter behavior:**

- Iterate all projects
- For each project, call the endpoint above
- Save to `data/raw/{project}_backlogconfig.json`
- Skip projects with missing IDs, log warnings

**Parser output file:** `backlog_config_parsed_YYYYMMDD_HHMM.csv`

**Parser columns:**

```
Project ID, Project Name, Backlog Level Name, Backlog Level Type, WIT Ref Names, WIT Display Names, Rank Field Ref Name
```

**Wire into cli.py:** add `backlogconfig` as a valid `--targets` value.

---

## Extension 6: Delivery Plans

**Goal:** Inventory whether delivery plans exist and what they contain. Absence of plans is a finding — it means cross-team timeline visibility tooling is completely unconfigured.

**API endpoints:**

```
# List all delivery plans in the project
GET https://dev.azure.com/{org}/{project}/_apis/work/plans?api-version=7.1

# Detail for a specific plan (includes team and iteration config)
GET https://dev.azure.com/{org}/{project}/_apis/work/plans/{planId}?api-version=7.1
```

**New files to create:**

- `exporters/export_plans_raw.py`
- `parsers/parse_plans.py`

**Exporter behavior:**

- Iterate all projects
- For each project, call the list endpoint and save `{project}_plans.json`
- If plans exist, call the detail endpoint for each and save `{project}_{planId}_plan_detail.json`
- If no plans exist, save an empty result — absence must be recorded, not silently skipped

**Parser output file:** `plans_parsed_YYYYMMDD_HHMM.csv`

**Parser columns:**

```
Project ID, Project Name, Plan ID, Plan Name, Plan Type, Created By Role, Team Count, Iteration Range Start, Iteration Range End
```

**Wire into cli.py:** add `plans` as a valid `--targets` value.

---

## Extension 7: Dashboards

**Goal:** Inventory whether dashboards exist and what widgets are in use. Absence of dashboards signals reporting altitude is starting from zero.

**API endpoints:**

```
# Project-level dashboards
GET https://dev.azure.com/{org}/{project}/_apis/dashboard/dashboards?api-version=7.1-preview.3

# Team-scoped dashboards (requires team context)
GET https://dev.azure.com/{org}/{project}/_apis/dashboard/dashboards?api-version=7.1-preview.3

# Dashboard detail including widgets (for representative sample)
GET https://dev.azure.com/{org}/{project}/_apis/dashboard/dashboards/{dashboardId}?api-version=7.1-preview.3
```

**API version note:** Dashboard endpoints are on `7.1-preview.3`. This is stable in practice but document it in exporter comments.

**New files to create:**

- `exporters/export_dashboards_raw.py`
- `parsers/parse_dashboards.py`

**Exporter behavior:**

- Iterate projects, then teams within each project
- Call the list endpoint at project level and per team
- Save `{project}_dashboards.json` and `{project}_{team}_dashboards.json`
- Widget detail is high call volume — make it opt-in via a flag (e.g., `--include-widgets`) rather than default behavior
- Save empty results for projects/teams with no dashboards — absence is a finding

**Parser output file:** `dashboards_parsed_YYYYMMDD_HHMM.csv`

**Parser columns:**

```
Project ID, Project Name, Team ID, Team Name, Dashboard ID, Dashboard Name, Dashboard Scope, Widget Count, Owner Role
```

`Dashboard Scope`: project-level vs. team-level, derived from which call returned the dashboard.

**Wire into cli.py:** add `dashboards` as a valid `--targets` value.

---

## Config Updates (`azure_devops/config.py`)

Add the following constants:

```python
# Process template — project level
PROCESS_TEMPLATE_FILENAME = "{project}_process_template.json"

# Process template — org level
ORG_PROCESSES_FILENAME = "org_processes.json"
PROCESS_DETAIL_FILENAME = "{processTypeId}_process_detail.json"
PROCESS_WITS_FILENAME = "{processTypeId}_wits.json"
PROCESS_WIT_STATES_FILENAME = "{processTypeId}_{witRefName}_states.json"
PROCESS_FIELDS_FILENAME = "{processTypeId}_fields.json"
PROCESS_WIT_RULES_FILENAME = "{processTypeId}_{witRefName}_rules.json"

# Team settings
TEAM_SETTINGS_FILENAME = "{project}_{team}_teamsettings.json"
TEAM_BACKLOGS_FILENAME = "{project}_{team}_backlogs.json"

# Boards (includes columns and swimlanes/rows)
BOARD_DETAIL_FILENAME = "{project}_{team}_{board}.json"

# Backlog configuration
BACKLOG_CONFIG_FILENAME = "{project}_backlogconfig.json"

# Delivery plans
PLANS_FILENAME = "{project}_plans.json"
PLAN_DETAIL_FILENAME = "{project}_{planId}_plan_detail.json"

# Dashboards
PROJECT_DASHBOARDS_FILENAME = "{project}_dashboards.json"
TEAM_DASHBOARDS_FILENAME = "{project}_{team}_dashboards.json"
```

---

## CLI Target Summary (full)

| Target flag | Exporter | Parser | Notes |
|---|---|---|---|
| `wits` | export_wit_raw | parse_wit_states | Existing |
| `classification` | export_classification_raw | parse_classification | Existing — verify depth param |
| `teams` | export_teams_boards_raw | parse_teams_boards, parse_swimlanes | Enhanced — captures boards with columns and swimlanes |
| `process` | export_process_template_raw | parse_process_template | New — project-level template |
| `processorg` | export_process_org_raw | parse_process_org | New — org-level template detail |
| `teamsettings` | export_team_settings_raw | parse_team_settings | New |
| `backlogconfig` | export_backlog_config_raw | parse_backlog_config | New |
| `plans` | export_plans_raw | parse_plans | New — absence is a finding |
| `dashboards` | export_dashboards_raw | parse_dashboards | New — absence is a finding |

---

## Suggested Build Order

1. **Verify existing exporters** — confirm depth params on classification, full team list capture on teams. Fix before building anything new.
2. **Extension 1: process** — smallest scope, single API call per project, validates the extension pattern before tackling nested loops. ✅ COMPLETED
3. **Extension 2: processorg** — builds on Extension 1 logic; establishes the authoritative template baseline that all project-level findings are compared against. ✅ COMPLETED
4. **Extension 5: backlogconfig** — project-scoped, no team iteration required, high diagnostic value for WMF WIT model compliance. ✅ COMPLETED
5. **Extension 3: teamsettings** — more complex due to nested project → team iteration and two endpoints per team; highest per-team diagnostic value. ✅ COMPLETED
6. **Extension 4: swimlanes** — ✅ COMPLETED via boards refactoring. Swimlanes now captured by `export_teams_boards_raw.py` using board GET detail endpoint (columns + rows in single call). Parser `parse_swimlanes.py` extracts rows from board detail JSON.
7. **Extension 6: plans** — low implementation complexity; run after core structural exporters are complete.
8. **Extension 7: dashboards** — lowest priority; run last. Absence finding can be confirmed manually while other exporters are being built.
