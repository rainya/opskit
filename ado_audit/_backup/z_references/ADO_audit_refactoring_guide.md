# ADO Audit Toolkit — Refactoring Guide

Quick reference for implementing the recommended improvements.

---

## 1. Fix Config Duplication (10 min)

### Change: azure_devops/client.py

**Remove the duplicate definitions:**

```python
# BEFORE (lines 8-16)
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"
API_VERSIONS = {
    "core": "7.1",
    "work": "7.1",
    "wit": "7.1",
    "preview": "7.1-preview.1"
}
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

**Replace with:**

```python
# AFTER
from azure_devops.config import LOG_LEVEL, API_VERSIONS

ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"
```

### Change: azure_devops/config.py

**Expand API_VERSIONS to include all keys used in client.py:**

```python
# BEFORE
API_VERSIONS = {
    "default": "7.1",
    "projects": "7.1",
    "wit": "7.1",
    "classification": "7.1",
    "teams": "7.1",
    "boards": "7.1",
}
```

**Replace with:**

```python
# AFTER (documented with comments showing usage)
API_VERSIONS = {
    "default": "7.1",      # Used for generic endpoints (projects, etc.)
    "projects": "7.1",     # Project listing
    "core": "7.1",         # Core APIs (currently unused, for future use)
    "work": "7.1",         # Work item tracking base
    "wit": "7.1",          # Work item type definitions and states
    "classification": "7.1",  # Areas and iterations
    "teams": "7.1",        # Teams and boards
    "boards": "7.1",       # Board definitions
    "preview": "7.1-preview.1",  # Preview features
}
```

---

## 2. Fix Parser Path Handling (10 min)

### Change: parsers/parse_wit_states.py

**Replace lines 16-17:**

```python
# BEFORE
import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import load_json, load_project_metadata, extract_project_info, safe_name

RAW_DIR = os.path.join("data", "raw")
```

**Replace with:**

```python
# AFTER
import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import load_json, load_project_metadata, extract_project_info, safe_name
from azure_devops.config import RAW_DATA_DIR, CSV_TIMESTAMP_FORMAT

RAW_DIR = RAW_DATA_DIR
```

**Also replace line 69 in parse_wit_states.py:**

```python
# BEFORE
now = datetime.now().strftime("%Y%m%d_%H%M")

# AFTER
now = datetime.now().strftime(CSV_TIMESTAMP_FORMAT)
```

### Change: parsers/parse_classification.py

Apply the same changes (add config imports, use RAW_DATA_DIR, use CSV_TIMESTAMP_FORMAT).

---

## 3. Create Missing __init__.py (1 min)

### New file: parsers/__init__.py

```python
"""Parser modules for ADO audit data."""
```

This is all that's needed (empty or with module docstring).

---

## 4. Add Error Reporting to All Exporters (5 min)

### Change: exporters/export_classification_raw.py

Add this import at the top:

```python
from azure_devops.client import BASE_URL, ADOClient, save_json, report_errors
```

Add this at the end of `main()`:

```python
def main():
    # ... existing code ...
    
    now = datetime.now().strftime(CSV_TIMESTAMP_FORMAT)
    logging.info(f"✅ Export complete. Raw JSON files are in {RAW_DATA_DIR} (timestamp {now})")
    
    # ADD THIS:
    report_errors()
```

### Change: exporters/export_teams_boards_raw.py

Apply the same pattern (import `report_errors`, call it at end of main).

---

## 5. Timestamp Consistency (5 min)

### Change: parsers/parse_wit_states.py

**Already fixed above, but summary:**
Replace `strftime("%Y%m%d_%H%M")` with `strftime(CSV_TIMESTAMP_FORMAT)`.

### Change: parsers/parse_classification.py

Same change — use imported `CSV_TIMESTAMP_FORMAT`.

---

## Validation Checklist

After making changes:

```bash
# 1. Test imports work
python -c "from azure_devops.config import LOG_LEVEL, API_VERSIONS; print('✓')"

# 2. Test exporters still work (dry-run if you have credentials)
# python exporters/export_wit_raw.py  # or similar

# 3. Test parsers work on sample data
python tests/run_parsers_on_samples.py

# 4. Verify no hardcoded paths in parsers
grep -n "os.path.join.*data.*raw" parsers/*.py
# Should return 0 results (only config.py should have the path)
```

---

## Optional: Enhanced Configuration

If you want to take it further, consider adding to `config.py`:

```python
# OPTIONAL: Add validation helper
def validate_config() -> bool:
    """Check that required config is set."""
    import sys
    
    if not os.path.exists(RAW_DATA_DIR):
        os.makedirs(RAW_DATA_DIR, exist_ok=True)
    
    pat = os.getenv("ADO_PAT") or (os.path.exists(PAT_FILE))
    if not pat:
        print("ERROR: ADO_PAT env var or ado_pat.txt file required")
        return False
    
    return True
```

Then call at start of each exporter:

```python
from azure_devops.config import validate_config

def main():
    if not validate_config():
        sys.exit(1)
    # ... rest of main ...
```

---

## Summary

| File | Changes | Est. Time |
|------|---------|-----------|
| `azure_devops/config.py` | Add missing API version keys | 5 min |
| `azure_devops/client.py` | Remove duplicate defs, import from config | 5 min |
| `parsers/parse_wit_states.py` | Add config imports, use constants | 5 min |
| `parsers/parse_classification.py` | Add config imports, use constants | 5 min |
| `exporters/export_*.py` | Add report_errors() calls | 5 min |
| `parsers/__init__.py` | Create empty file | 1 min |

**Total: ~26 minutes of focused work**

No functional changes needed — all improvements are about consistency and maintainability.
