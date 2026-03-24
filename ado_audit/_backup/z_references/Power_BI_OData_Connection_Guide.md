# Power BI OData Connection Guide

Azure DevOps Analytics OData Endpoint with Power BI Desktop

## Overview

Azure DevOps Analytics provides an OData v4 endpoint optimized for reporting and analytics. Power BI can connect directly to this endpoint for interactive work item analysis with no Python scripting required.

**Benefits vs Python Scripts:**

- Interactive filtering and grouping
- Visual query builder (no code)
- Automatic refresh capabilities
- Built-in caching for performance
- Rich visualizations and dashboards
- Cross-project reporting

## Prerequisites

1. **Power BI Desktop** - Download from [Microsoft Store](https://aka.ms/pbidesktopstore) or microsoft.com/power-bi
2. **Azure DevOps PAT** - Personal Access Token with **Analytics (Read)** permission
3. **Analytics Enabled** - Your Azure DevOps organization must have Analytics enabled (default for most orgs)

## Connection Steps

### 1. Get Your OData Endpoint URL

The base OData endpoint format:

```
https://analytics.dev.azure.com/{organization}/{project}/_odata/v3.0-preview
```

**Examples:**

```
https://analytics.dev.azure.com/1id/OID/_odata/v3.0-preview
https://analytics.dev.azure.com/1id/Starling/_odata/v3.0-preview
```

**Entity Sets Available:**

- `WorkItems` - All work items with full metadata
- `WorkItemLinks` - Parent/child and related links
- `Areas` - Area path hierarchy
- `Iterations` - Iteration path hierarchy
- `Teams` - Team information
- `Projects` - Project metadata

### 2. Open Power BI Desktop

1. Launch Power BI Desktop
2. Click **Get Data** (or Home ribbon → Get Data)
3. Search for **OData Feed**
4. Select **OData Feed** and click **Connect**

### 3. Enter OData URL

**For specific entity set** (e.g., WorkItems):

```
https://analytics.dev.azure.com/1id/OID/_odata/v3.0-preview/WorkItems
```

**Power BI Tips:**

- You can add query parameters in the URL or use the Query Editor later
- Leave Basic authentication for now (next step)

### 4. Authenticate

When prompted for credentials:

1. Select **Basic** authentication
2. **User name:** Leave blank (or enter anything - it's ignored)
3. **Password:** Paste your Azure DevOps PAT (Personal Access Token)
4. Click **Connect**

**Important:** The PAT must have **Analytics (Read)** scope enabled.

### 5. Navigator - Select Data

Power BI's Navigator window appears showing the OData metadata:

**Option A: Load Entity Directly**

- Check **WorkItems** to see preview
- Click **Load** to import all work items into Power BI

**Option B: Transform Data (Recommended)**

- Check **WorkItems**
- Click **Transform Data** to open Power Query Editor
- Apply filters and transformations before loading (much faster)

### 6. Power Query Editor - Apply Filters

**Recommended transformations to improve performance:**

**Filter by Date Range:**

```power-query
= Table.SelectRows(Source, each [ChangedDate] >= #date(2025, 1, 1))
```

**Select Specific Columns:**
Right-click column headers → **Remove Other Columns**

Keep only what you need:

- WorkItemId
- Title
- State
- AreaSK (expand to get AreaPath)
- IterationSK (expand to get IterationPath)
- WorkItemType
- CreatedDate
- ChangedDate
- AssignedTo
- etc.

**Expand Navigation Properties:**

- Click the expand icon (⟨→⟩) on columns like `AreaSK`, `Project`, `AssignedTo`
- Select fields to expand (e.g., AreaPath from AreaSK)
- Uncheck "Use original column name as prefix" for cleaner names

### 7. Create Visual Reports

Once data is loaded, create visuals:

**Work Items by Area Path and State:**

1. Insert **Matrix** visual
2. Rows: AreaSK.AreaPath
3. Columns: State
4. Values: Count of WorkItemId

**Work Item Trend by Created Date:**

1. Insert **Line Chart**
2. X-axis: CreatedDate (by Month)
3. Y-axis: Count of WorkItemId
4. Legend: WorkItemType

**Date Range Analysis:**

1. Insert **Table**
2. Rows: AreaSK.AreaPath
3. Values:
   - Count of WorkItemId
   - Min of CreatedDate
   - Max of CreatedDate
   - Min of ChangedDate
   - Max of ChangedDate

## Advanced OData Query Parameters

Add parameters directly in the URL or in Power Query's Advanced Editor.

**Filter by Project:**

```
https://analytics.dev.azure.com/1id/_odata/v3.0-preview/WorkItems?
$filter=Project/ProjectName eq 'OID'
```

**Filter by Area Path:**

```
$filter=startswith(AreaSK/AreaPath, 'OID\Platform')
```

**Filter by State:**

```
$filter=State eq 'Active' or State eq 'New'
```

**Filter by Date Range:**

```
$filter=ChangedDate ge 2025-01-01T00:00:00Z
```

**Select Specific Fields:**

```
$select=WorkItemId,Title,State,CreatedDate,ChangedDate
```

**Expand Related Entities:**

```
$expand=AreaSK($select=AreaPath),AssignedTo($select=UserName)
```

**Combine Multiple Parameters:**

```
https://analytics.dev.azure.com/1id/OID/_odata/v3.0-preview/WorkItems?
$filter=State eq 'Active'&
$select=WorkItemId,Title,State,AreaSK&
$expand=AreaSK($select=AreaPath)
```

## Performance Optimization Tips

### 1. Use Date Filters

Always filter by `ChangedDate` or `CreatedDate` to limit data volume:

```
ChangedDate ge 2025-01-01T00:00:00Z
```

### 2. Select Only Required Columns

Don't fetch all 100+ columns if you only need 10:

```
$select=WorkItemId,Title,State,AreaSK,CreatedDate
```

### 3. Avoid Loading Closed Items

If you only care about active work:

```
$filter=State ne 'Closed' and State ne 'Removed'
```

### 4. Use Incremental Refresh (Power BI Premium)

Configure incremental refresh to only fetch recent changes:

- Right-click table → Incremental Refresh
- Define date range parameters
- Archive historical data locally

### 5. Aggregate Before Loading

Use `$apply` for pre-aggregation (if your query is simple):

```
$apply=groupby((AreaSK/AreaPath, State), aggregate($count as Count))
```

## Common Use Cases

### Use Case 1: Work Item Counts by Area + State

**Power Query M Code:**

```m
let
    Source = OData.Feed(
        "https://analytics.dev.azure.com/1id/OID/_odata/v3.0-preview/WorkItems",
        null,
        [
            Query=[
                #"$filter"="State ne 'Removed'",
                #"$select"="WorkItemId,State,AreaSK",
                #"$expand"="AreaSK($select=AreaPath)"
            ]
        ]
    ),
    ExpandArea = Table.ExpandRecordColumn(Source, "AreaSK", {"AreaPath"}),
    GroupedRows = Table.Group(
        ExpandArea, 
        {"AreaPath", "State"}, 
        {{"Count", each Table.RowCount(_), Int64.Type}}
    )
in
    GroupedRows
```

### Use Case 2: Work Item Age Analysis

**Power Query M Code:**

```m
let
    Source = OData.Feed(
        "https://analytics.dev.azure.com/1id/OID/_odata/v3.0-preview/WorkItems",
        null,
        [
            Query=[
                #"$filter"="State ne 'Closed' and State ne 'Removed'",
                #"$select"="WorkItemId,Title,State,CreatedDate,AreaSK",
                #"$expand"="AreaSK($select=AreaPath)"
            ]
        ]
    ),
    ExpandArea = Table.ExpandRecordColumn(Source, "AreaSK", {"AreaPath"}),
    AddAge = Table.AddColumn(
        ExpandArea, 
        "Age (Days)", 
        each Duration.Days(DateTime.LocalNow() - [CreatedDate])
    )
in
    AddAge
```

### Use Case 3: Date Range Metadata by Area

**DAX Measures (after loading WorkItems table):**

```dax
Min Created Date = MIN(WorkItems[CreatedDate])
Max Created Date = MAX(WorkItems[CreatedDate])
Min Changed Date = MIN(WorkItems[ChangedDate])
Max Changed Date = MAX(WorkItems[ChangedDate])
Total Count = COUNT(WorkItems[WorkItemId])
```

**Table Visual:**

- Rows: AreaPath
- Values: All 5 measures above

## Troubleshooting

### Error: "Unable to connect"

- Verify OData URL is correct (check organization and project names)
- Ensure Analytics is enabled in Azure DevOps
- Check PAT has not expired

### Error: "401 Unauthorized"

- PAT missing or expired
- PAT doesn't have **Analytics (Read)** permission
- Re-enter credentials in Power BI (File → Options → Data source settings)

### Error: "Query timeout"

- Query is too broad (fetching too much data)
- Add date filters: `ChangedDate ge 2025-01-01`
- Use `$select` to limit columns
- Consider incremental refresh

### Performance is Slow

- Remove unnecessary columns in Power Query Editor
- Add filters early (before expanding columns)
- Limit to recent data (e.g., last 12 months)
- Use query folding (avoid custom M functions)

## Comparison: Python Script vs Power BI

| Feature | Python Script | Power BI |
|---------|--------------|----------|
| **Setup Time** | Minutes (install Python) | Minutes (install Power BI) |
| **Ease of Use** | Command line, technical | GUI, visual, no-code |
| **Automation** | Easy (scheduled scripts) | Easy (scheduled refresh) |
| **Interactive Analysis** | No | Yes (filters, drill-down) |
| **Visualization** | Requires separate tool | Built-in charts/dashboards |
| **Performance** | Client-side aggregation | Query folding + caching |
| **Data Volume** | Fetch all, then filter | Filter before fetch |
| **Best For** | Automation, integration | Exploration, reporting |

## Additional Resources

**Microsoft Docs:**

- [Azure DevOps Analytics OData API](https://learn.microsoft.com/en-us/azure/devops/report/extend-analytics/)
- [Power BI OData Feed Connector](https://learn.microsoft.com/en-us/power-query/connectors/odatafeed)
- [OData v4 Query Options](https://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part2-url-conventions.html)

**Quick Reference:**

- Analytics Endpoint: `https://analytics.dev.azure.com/{org}/{project}/_odata/v3.0-preview`
- Entity Sets: WorkItems, Areas, Iterations, Teams, Projects
- Authentication: Basic auth with PAT as password
- Required PAT Scope: **Analytics (Read)**

## Example: Replicating Python Script in Power BI

The toolkit's `workitem_metadata_by_area_odata.py` script can be replicated in Power BI:

**Python Script Output:**

```
Project | Area Path | State | Count | Min Created | Max Created | Min Changed | Max Changed | Total
```

**Power BI Equivalent:**

1. **Load Data:**
   - Connect to WorkItems OData feed
   - Expand AreaSK to get AreaPath
   - Select: WorkItemId, AreaPath, State, CreatedDate, ChangedDate

2. **Create Matrix Visual:**
   - Rows: AreaPath
   - Columns: State
   - Values: Count of WorkItemId

3. **Create Table Visual:**
   - Rows: AreaPath
   - Values (DAX measures):
     - `Min Created = MIN(WorkItems[CreatedDate])`
     - `Max Created = MAX(WorkItems[CreatedDate])`
     - `Min Changed = MIN(WorkItems[ChangedDate])`
     - `Max Changed = MAX(WorkItems[ChangedDate])`
     - `Total = COUNT(WorkItems[WorkItemId])`

**Result:** Same data, but interactive with drill-down, filtering, and visual charts.
