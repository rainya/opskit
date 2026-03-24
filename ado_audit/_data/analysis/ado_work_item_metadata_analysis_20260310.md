# ADO Work Item Metadata Analysis: 1id Organization Landscape

**Data source:** OData export, all projects in 1id ADO org
**Export date:** 2026-03-10
**Prepared for:** WMF program — C1 Work Structure and ADO consolidation planning
**Recency threshold:** 12 months (area paths with no changes since March 2025 classified as stale)

---

## Executive Summary

The 1id ADO organization contains **31 projects** holding **498,556 work items** across **657 area paths**. The landscape reflects OID's M&A history: multiple process templates coexist, state models are fragmented, and project boundaries do not map to the current delivery vertical structure.

Five findings are directly relevant to WMF and the ADO consolidation:

1. **Process template fragmentation is structural, not cosmetic.** The OID project runs the InCycle-configured Agile template (User Story). All legacy product projects run Scrum (Product Backlog Item). Starling is mixed. Consolidating into a single OID project means migrating Scrum-native work items into an Agile-template project — this is a WIT mapping decision that must be made before any migration proceeds.

2. **State sprawl makes cross-org reporting impossible without normalization.** 41 distinct states exist across active projects. The "Design" state (43,420 items, 9.6% of total) is a Test Case artifact, not a workflow state — but it will distort any rollup that doesn't filter by WIT. Beyond that, the real problem is 15+ custom workflow states scattered across projects that have no equivalent in the InCycle baseline.

3. **Work is heavily concentrated in a small number of area paths.** The top 10 area paths by volume hold 40% of all work items. Meanwhile, 28% of area paths (168 of 603) contain 10 or fewer items. The structure is simultaneously too deep (depth 6 in some projects) and too sparse (empty scaffolding that serves no reporting or routing purpose).

4. **~78% of all work items are in terminal states.** The org is carrying substantial historical weight. Only 13% of items are in active work states and 8% are queued. This matters for migration: moving 500K items including 390K closed items is a different decision than migrating only open work.

5. **TechComm's cross-project footprint is confirmed and quantified.** 49 TechComm-related area paths exist across 12 projects with 7 different naming conventions. The C1 v0.2 analysis correctly identified this as the central shared-services structural issue — this data validates the scale.

---

## 1. Project Landscape

### 1.1 Active Delivery Projects (16 projects, 453,897 items)

| Project | Items | Area Paths | WITs | States | Last Changed |
|---|---:|---:|---:|---:|---|
| Starling | 99,650 | 218 | 13 | 23 | 2026-03-10 |
| OID | 85,078 | 55 | 11 | 15 | 2026-03-10 |
| Identity Manager | 81,948 | 112 | 12 | 17 | 2026-03-10 |
| Active Roles | 43,998 | 63 | 11 | 17 | 2026-03-10 |
| SPS | 39,523 | 32 | 6 | 8 | 2026-03-10 |
| Safeguard Privileged Passwords | 31,505 | 3 | 10 | 16 | 2026-03-10 |
| Defender | 26,062 | 60 | 10 | 13 | 2026-03-10 |
| Password Manager | 14,878 | 13 | 10 | 14 | 2026-03-10 |
| Log Management | 14,040 | 14 | 8 | 10 | 2026-03-10 |
| Authentication Services | 5,705 | 2 | 7 | 13 | 2026-03-10 |
| Privilege Manager for Windows | 3,883 | 2 | 10 | 13 | 2026-03-10 |
| Capacity Testing | 2,545 | 11 | 8 | 10 | 2023-04-03 |
| TechComm | 2,512 | 9 | 4 | 8 | 2026-03-10 |
| Privilege Manager | 1,795 | 2 | 9 | 12 | 2026-02-24 |
| Operations | 489 | 5 | 7 | 8 | 2026-01-16 |
| OneLogin | 286 | 2 | 3 | 8 | 2026-03-10 |

### 1.2 Suspected Legacy/Test/Migration Projects (15 projects, 44,659 items)

| Project | Items | Last Changed | Reason Flagged |
|---|---:|---|---|
| SBox-OID-Migration | 32,180 | 2026-03-03 | Migration staging project |
| DBO | 3,791 | 2026-03-09 | Unknown/legacy |
| Shield | 2,782 | 2024-06-28 | No changes in 8+ months |
| DTox | 1,879 | 2023-11-16 | No changes in 2+ years |
| TPAM | 1,227 | 2026-02-12 | Legacy PAM product |
| Mainframe | 1,045 | 2026-02-26 | Legacy product |
| Common | 659 | 2026-03-05 | Shared/legacy |
| Rename Test | 549 | 2026-03-03 | Test artifact |
| Virtual Directory Server | 244 | 2023-05-03 | Legacy product, no changes in 3 years |
| Technical Integrations | 161 | 2020-11-20 | No changes in 5+ years |
| Global Enablement | 106 | 2026-03-05 | Unknown/legacy |
| Blackbird | 27 | 2018-11-09 | Abandoned |
| Sandbox - OID | 5 | 2026-03-03 | Test sandbox |
| Raven | 3 | 2018-11-09 | Abandoned |
| PgM Sandbox | 1 | 2025-11-21 | Test sandbox |

**Observation:** SBox-OID-Migration at 32K items is the largest legacy project. If this is the Starling migration staging area, its item count and recent activity date (Mar 3) suggest migration work is actively in flight. The remaining legacy projects hold ~12K items total and are candidates for archival or read-only status.

### 1.3 Project-to-Vertical Mapping Gap

OID's 6 delivery verticals (AR, IM, SG, OL, DF, EN) are served by 16 active projects. The mismatch:

- **SG (Safeguard)** spans 3 separate projects: SPS, Safeguard Privileged Passwords, and portions of Starling (PAM, SGOD, SRA)
- **OL (OneLogin)** spans 2 projects: OID (where teams migrated via InCycle) and a residual OneLogin project
- **AR (Active Roles)** has its own project but also presence in Starling and Defender
- **IM (Identity Manager)** has its own project — the cleanest vertical-to-project mapping
- **DF (Dev Foundations)** work lives primarily in OID and Starling, not in a dedicated project
- **EN (Enablers)** — TechComm has its own project plus area paths in 11 other projects; Security is in OID; UX footprint not fully visible in this data

This is the core argument for consolidation: you cannot get a vertical-level view of work without querying across 3-5 projects.

---

## 2. Work Item Types: What's Actually in Use

### 2.1 Global WIT Distribution (active projects)

| Work Item Type | Count | % of Total | Projects |
|---|---:|---:|---:|
| Task | 150,916 | 33.2% | 16 |
| Bug | 81,603 | 18.0% | 15 |
| Test Case | 70,619 | 15.6% | 12 |
| Product Backlog Item | 62,770 | 13.8% | 15 |
| User Story | 48,728 | 10.7% | 2 |
| Feature | 17,840 | 3.9% | 16 |
| Test Suite | 14,735 | 3.2% | 12 |
| Epic | 2,742 | 0.6% | 14 |
| System Change | 2,518 | 0.6% | 1 |
| Shared Steps | 408 | 0.1% | 7 |
| Test Plan | 404 | 0.1% | 12 |
| Known Issue | 351 | 0.1% | 1 |
| Impediment | 151 | <0.1% | 5 |
| Initiative | 76 | <0.1% | 4 |
| Shared Parameter | 33 | <0.1% | 6 |
| Issue | 3 | <0.1% | 1 |

### 2.2 Process Template Split

This is the most consequential finding for consolidation planning:

- **OID project: Agile process template** — uses User Story (48,725 items). This is the InCycle-configured target state.
- **14 other active projects: Scrum process template** — use Product Backlog Item (62,770 items across 15 projects).
- **Starling: Mixed** — 3 User Stories plus 20,994 PBIs, suggesting a tiny Agile experiment or migration artifact within a Scrum project.

**Implication:** Every team migrating from a Scrum-template project into the OID project faces a WIT conversion. PBIs become User Stories. The workflow states associated with each WIT are different (Scrum: New → Approved → Committed → Done; Agile: New → Active → Resolved → Closed, plus the InCycle additions of Waiting and Ready). This is not an automatic migration — it requires deliberate state mapping decisions.

### 2.3 Test Artifacts: A Hidden Volume Driver

Test Case (70,619), Test Suite (14,735), Test Plan (404), Shared Steps (408), and Shared Parameter (33) together account for **86,199 items — 19% of all work** in active projects. These are not tracked through the same lifecycle as delivery work items, and the "Design" state anomaly (43,420 items, Section 3.2) is exclusively Test Cases in their default Scrum-template state.

**Implication for consolidation:** Test artifacts must be accounted for in migration volume planning. They also need distinct treatment in the WMF reporting model — rolling them into delivery metrics would distort every measurement.

### 2.4 OID-Specific WITs

Two work item types exist in only one project:

- **System Change** (2,518 items, OID only): The CAB/change management WIT from InCycle. This is a legitimate OID-specific type that other projects don't have — teams migrating in will either adopt it or need an alternative.
- **Known Issue** (351 items, OID only): Appears to be a custom type. Low volume but its purpose and relationship to Bugs should be clarified.
- **Issue** (3 items, OID only): The InCycle escalation WIT. Only 3 items suggests it's either barely adopted or the escalation workflow hasn't materialized as designed.

---

## 3. State Distribution: What It Tells Us About Active vs. Stale

### 3.1 State Category Rollup

| Category | Items | % |
|---|---:|---:|
| Terminal (Closed, Done, Removed, Complete, Completed) | 357,083 | 78.7% |
| Active (in-progress, testing, resolving) | 59,593 | 13.1% |
| Queue (new, ready, approved, to do) | 36,558 | 8.1% |
| Blocked (waiting, inactive, postponed) | 574 | 0.1% |

**78.7% terminal** means the org is carrying nearly 360K closed/done/removed items across its projects. This is normal for a long-lived ADO org, but it directly impacts migration planning: migrating all items versus only open items is a 5x volume difference.

### 3.2 The "Design" State Anomaly

The "Design" state accounts for 43,420 items (9.6% of total). Investigation reveals these are **exclusively Test Case work items** in the Scrum process template's default state. "Design" is the initial state for Test Cases in Scrum — it means "test case authored but not yet executed."

This is spread across 11 projects, with the largest concentrations in Starling (13,681), Identity Manager (10,462), and Defender (10,385). It is not a custom workflow state and does not indicate anything about delivery process maturity — but it will create noise in any reporting that doesn't filter by WIT.

### 3.3 State Fragmentation by Project

The OID project (InCycle baseline) uses: New, Waiting, Ready, Active, Resolved, Closed, Removed, plus a "Validating" state (2,156 items) that does not appear in InCycle's documentation.

Other projects introduce states that have no OID equivalent:

| State | Items | Primary Projects |
|---|---:|---|
| Design | 43,420 | Test Case artifact (all Scrum projects) |
| In Planning | 1,142 | Active Roles (956), Identity Manager (186) |
| Tested on DevTest | 291 | Starling |
| Tested on Stage | 190 | Starling |
| Implementing | 191 | Starling (142), Active Roles (35) |
| Testing | 831 | Identity Manager |
| Ready for Test | 90 | OID (24), Starling (61) |
| Inactive | 140 | Active Roles (54), Identity Manager (45) |
| Code Review | 6 | Identity Manager |
| Prioritized | 46 | Safeguard Privileged Passwords (16), Starling (29) |

**Implication:** The Starling project alone introduces 6 custom workflow states (Tested on DevTest, Tested on Stage, Implementing, Ready for Test, Prioritized, Testing on DevTest) that reflect a more granular delivery pipeline than the InCycle model. Whether these collapse into the InCycle states (e.g., "Tested on DevTest" → "Resolved") or require the OID project's state model to expand is a C3 decision that blocks migration.

### 3.4 Per-Project Terminal Ratios

| Project | Terminal | Queue | Active | %Terminal |
|---|---:|---:|---:|---:|
| OID | 77,556 | 3,961 | 3,048 | 91.2% |
| SPS | 35,573 | 3,799 | 151 | 90.0% |
| TechComm | 2,254 | 227 | 29 | 89.7% |
| Authentication Services | 5,044 | 600 | 54 | 88.4% |
| Log Management | 11,909 | 1,881 | 250 | 84.8% |
| Capacity Testing | 2,119 | 267 | 159 | 83.3% |
| Starling | 80,149 | 3,012 | 16,457 | 80.4% |
| Active Roles | 34,565 | 6,020 | 3,359 | 78.6% |
| Identity Manager | 62,569 | 6,129 | 13,205 | 76.4% |
| Safeguard Privileged Passwords | 23,808 | 7,023 | 674 | 75.6% |
| Privilege Manager | 1,354 | 169 | 272 | 75.4% |
| Password Manager | 8,803 | 2,017 | 4,058 | 59.2% |
| OneLogin | 162 | 121 | 3 | 56.6% |
| Operations | 246 | 184 | 59 | 50.3% |
| Defender | 10,077 | 798 | 15,187 | 38.7% |
| Privilege Manager for Windows | 895 | 350 | 2,628 | 23.0% |

**Outliers:** Defender at 38.7% terminal and Privilege Manager for Windows at 23.0% terminal have unusually high proportions of active/queued work. Defender's 15,187 active items (mostly in the "Design" test case state — 10,385 items) and Privilege Manager for Windows's 2,628 active items warrant investigation. These may be projects with large test case backlogs that have never been formally resolved, or they may be legitimately high-activity areas.

---

## 4. Area Path Activity: Where Work Lives vs. Where Structure Exists

### 4.1 Active vs. Stale Area Paths

| Metric | Count | % |
|---|---:|---:|
| Total area paths (active projects) | 603 | 100% |
| Active (changed since Mar 2025) | 468 | 77.6% |
| Stale (no changes since Mar 2025) | 135 | 22.4% |
| Items in active area paths | 445,679 | 98.2% |
| Items in stale area paths | 8,218 | 1.8% |

135 stale area paths holding only 8,218 items — this is structural dead weight. The items are almost entirely terminal-state historical work that no one is touching.

### 4.2 Stale Area Path Distribution by Project

| Project | Active | Stale | Total | %Stale | Stale Items |
|---|---:|---:|---:|---:|---:|
| Defender | 15 | 45 | 60 | 75.0% | 2,509 |
| Starling | 174 | 44 | 218 | 20.2% | 824 |
| Active Roles | 48 | 15 | 63 | 23.8% | 220 |
| Capacity Testing | 0 | 11 | 11 | 100.0% | 2,545 |
| Identity Manager | 105 | 7 | 112 | 6.2% | 1,138 |
| Operations | 1 | 4 | 5 | 80.0% | 341 |
| Password Manager | 9 | 4 | 13 | 30.8% | 77 |
| SPS | 30 | 2 | 32 | 6.2% | 496 |

**Defender** is the most striking case: 75% of its area paths are stale. With 60 area paths total for what is a single product vertical, this suggests extensive reorganization or team restructuring left behind a trail of abandoned paths. Capacity Testing is 100% stale — the entire project appears dormant.

### 4.3 Low-Volume Area Paths (Structural Scaffolding)

**168 of 603 area paths (27.9%) contain 10 or fewer items.** These are not operational areas — they are structural scaffolding that either never gained adoption or was created speculatively.

| Project | Low-Volume Paths | Total Paths |
|---|---:|---:|
| Starling | 73 | 218 |
| Identity Manager | 26 | 112 |
| Active Roles | 20 | 63 |
| Defender | 19 | 60 |
| OID | 16 | 55 |

Starling leads with 73 low-volume area paths — one-third of its entire area path structure. Combined with 44 stale paths, Starling has significant structural cleanup needed before or during migration.

### 4.4 Depth Distribution

| Depth | Area Paths | Items |
|---:|---:|---:|
| 1 | 15 | 113,894 |
| 2 | 102 | 125,663 |
| 3 | 232 | 100,483 |
| 4 | 113 | 95,728 |
| 5 | 95 | 16,132 |
| 6 | 46 | 1,997 |

Depth 5 and 6 account for 141 area paths but only 18,129 items (4%). The C1 spec's depth rules (3 levels under Engineering, 4 under Product for shared-services) align well with where the actual work lives — depth 1-4 holds 96% of items.

---

## 5. Work Concentration

### 5.1 Top 10 Area Paths by Total Volume

| Area Path | Project | Total | Open |
|---|---|---:|---:|
| Starling\Connect Connectors | Starling | 34,577 | 11,616 |
| Safeguard Privileged Passwords | SPP | 31,343 | 7,678 |
| Active Roles | Active Roles | 25,596 | 7,924 |
| OID\Engineering\OneLogin\Platform | OID | 21,773 | 539 |
| Identity Manager\Identity Manager Modules | Identity Manager | 20,904 | 4,826 |
| Defender | Defender | 19,812 | 12,344 |
| Identity Manager\Identity Manager Web | Identity Manager | 17,507 | 2,493 |
| Identity Manager | Identity Manager | 16,982 | 5,382 |
| SPS\Archive\SCB | SPS | 10,294 | 1,004 |
| OID\Engineering\OneLogin\Directory | OID | 10,022 | 207 |

**These 10 area paths hold 208,810 items — 46% of all work in active projects.** The concentration is extreme. Starling\Connect Connectors alone holds 34,577 items (7.6% of the entire org).

### 5.2 Top 10 Area Paths by Open Work

| Area Path | Project | Open | Total | %Open |
|---|---|---:|---:|---:|
| Defender | Defender | 12,344 | 19,812 | 62.3% |
| Starling\Connect Connectors | Starling | 11,616 | 34,577 | 33.6% |
| Active Roles | Active Roles | 7,924 | 25,596 | 31.0% |
| Safeguard Privileged Passwords | SPP | 7,678 | 31,343 | 24.5% |
| Identity Manager | Identity Manager | 5,382 | 16,982 | 31.7% |
| Identity Manager\IM Modules | Identity Manager | 4,826 | 20,904 | 23.1% |
| Password Manager | Password Manager | 3,521 | 4,312 | 81.7% |
| Privilege Mgr for Windows | PMfW | 2,969 | 3,729 | 79.6% |
| Defender\Login\Desktop Login | Defender | 2,568 | 2,883 | 89.1% |
| Identity Manager\IM Web | Identity Manager | 2,493 | 17,507 | 14.2% |

**Password Manager and Privilege Manager for Windows** have unusually high open ratios (81.7% and 79.6%). Either these projects have large backlogs that have never been groomed, or their items are stacking up without resolution. Defender\Login\Desktop Login at 89.1% open may be a decommissioned product area with unresolved items.

---

## 6. OID Project Deep Dive

The OID project is the consolidation target — what currently exists there defines the landing zone.

**Current state:** 55 area paths, 85,078 items, 91.2% terminal.

The area path structure reveals the current organizational intent:

- `OID\Engineering\OneLogin\*` — 24 area paths, ~68K items. This is the OneLogin migration from Jira via InCycle. It's the largest area path cluster in OID and represents the most mature implementation of the InCycle process model.
- `OID\Engineering\Safeguard\*` — 6 area paths, ~6.3K items. Safeguard teams that have already migrated into OID.
- `OID\Engineering\Management Plane` — 1 area path, 1,016 items. The first Starling component to move into OID (the one that broke TechComm's parent-child links).
- `OID\Engineering\Active Roles` — 1 area path, 20 items. Placeholder only.
- `OID\Platform Engineering (D)` and `(M)` — InCycle team model in action with (D)/(M) suffixes.
- `OID\Security (D)` and `(M)` — Same pattern.
- `OID\TechComm` — 191 items. The OID-project-level TechComm area, distinct from the per-product TechComm paths.
- `OID\Engineering\OneLogin\TechComm` — 10 items. TechComm's OL-specific area path.
- `OID\ToDelete\*` — 5 area paths flagged for cleanup, including DevOps (3,761 items of which 0 are open).

**Key observation:** OID already has the `Engineering\{Vertical}\{Team}` pattern at depth 3-4, plus the InCycle (M)/(D) team type suffixes. The consolidation target structure exists — the question is whether it can absorb the volume and variety from the other 15 projects.

---

## 7. TechComm Cross-Project Footprint

49 TechComm-related area paths exist across 12 projects, confirming and extending the C1 v0.2 analysis:

| Naming Convention | Projects Using | Example |
|---|---|---|
| Documentation | 6 | Active Roles\Business\Documentation |
| Tech Comm | 9 (Starling sub-areas) | Starling\PAM\Tech Comm |
| TechComm | 2 | OID\TechComm, TechComm project |
| Technical Writer(s) | 3 | Authentication Services\Technical writers |
| TC | 1 | SPS\TC\Documentation |
| DOC-* | 1 | Log Management\Documentation\DOC-syslog-ng... |

**7 different naming conventions across 12 projects.** The C1 v0.2 specification's proposed Product Context Name Registry and standardized `Product\TechComm\{ProductContext}` pattern directly addresses this. The data validates the design choice.

**Largest TechComm area paths by volume:**

| Area Path | Project | Items |
|---|---|---:|
| SPS\TC\Documentation | SPS | 3,929 |
| Active Roles\Business\Documentation | Active Roles | 2,435 |
| TechComm\Multi-Product Requests | TechComm | 1,352 |
| Identity Manager\IM Core\Documentation | Identity Manager | 1,358 |
| Log Management\Documentation\DOC-syslog-ng PE | Log Management | 944 |

---

## 8. Implications for WMF and Consolidation

### 8.1 Process Template Decision (Blocking)

The OID project uses the Agile template (User Story). 14 of 15 other active projects use Scrum (PBI). Every migration requires a WIT mapping decision. The options are:

- **Map PBI → User Story during migration.** Maintains OID's current template. Requires state mapping (Scrum states → InCycle states). All migrating teams adopt the Agile process.
- **Switch OID to Scrum template.** Disrupts the 48K+ User Stories already in OID. Not realistic.
- **Create a custom inherited process that supports both.** Adds complexity but preserves existing items.

This is a C1/C3 joint decision that must be resolved before migration wave 1.

### 8.2 State Normalization (Blocking)

At minimum, the following state mappings need to be defined before migration:

| Source State | Count | Suggested Target |
|---|---:|---|
| Approved (Scrum) | 1,714 | Ready |
| Committed (Scrum) | 944 | Active |
| Done (Scrum) | 217,481 | Closed |
| To Do (Scrum) | 4,461 | New |
| In Progress (Scrum) | 10,988 | Active |
| Design (Test Case) | 43,420 | TBD — test artifact state |
| In Planning | 1,142 | New or Ready |
| Tested on DevTest | 291 | Resolved |
| Tested on Stage | 190 | Resolved |
| Implementing | 191 | Active |
| Testing | 831 | Resolved |

### 8.3 Migration Volume Strategy

The terminal ratio data (78.7% org-wide) creates a strategic choice:

- **Full migration:** Move all ~500K items. Preserves complete history but carries dead weight and requires state mapping for hundreds of thousands of closed items.
- **Open-only migration:** Move only non-terminal items (~96K). Faster, cleaner, but loses historical traceability and breaks any existing parent-child links between open and closed items.
- **Hybrid:** Migrate open items + direct parent/child chain items. Most operationally correct but most complex to execute.

### 8.4 Structural Cleanup Opportunity

Before migration, the following cleanup would reduce noise and risk:

- **135 stale area paths** across active projects — candidates for archival
- **168 low-volume area paths** (≤10 items) — evaluate for consolidation
- **Defender** needs attention: 75% stale area paths, 62% open items
- **Capacity Testing** is fully dormant — candidate for project archival
- **OID\ToDelete\*** paths — 5 paths with 3,770 items already flagged for cleanup

---

*This analysis was produced from the OData work item metadata export. It covers structural and state-level patterns. It does not include field-level completeness (e.g., whether items have acceptance criteria, story points, or parent links) — that analysis requires the field-level audit data from the ADO Audit Toolkit.*
