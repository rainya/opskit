#!/usr/bin/env python3
"""Quick test to check board GET endpoint structure."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from azure_devops.client import ADOClient, BASE_URL
from azure_devops.config import PAT_ENV_VAR, PAT_FILE

# Get PAT
pat = os.getenv(PAT_ENV_VAR)
if not pat and os.path.exists(PAT_FILE):
    with open(PAT_FILE, 'r') as f:
        pat = f.read().strip()

if not pat:
    print("No PAT found")
    sys.exit(1)

client = ADOClient(pat)

# Test board detail endpoint with various $expand options
project_id = "a4c3e342-aef6-43ce-930a-fdf688dd1ed6"
team_id = "9afe4d3f-774f-473f-8233-d1abdc85f3ea"
board_id = "b87b8752-1ee8-41e0-bf56-89b59c8efe98"

print("=" * 80)
print("TEST 1: Board detail (no expand)")
print("=" * 80)
url1 = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/boards/{board_id}?api-version=7.1"
result1 = client.get_raw(url1)
print(json.dumps(result1, indent=2))

print("\n" + "=" * 80)
print("TEST 2: Board detail with $expand=boardColumns")
print("=" * 80)
url2 = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/boards/{board_id}?api-version=7.1&$expand=boardColumns"
result2 = client.get_raw(url2)
print(json.dumps(result2, indent=2)[:3000])

print("\n" + "=" * 80)
print("TEST 3: Rows (swimlanes) endpoint")
print("=" * 80)
url3 = f"{BASE_URL}/{project_id}/{team_id}/_apis/work/boards/{board_id}/rows?api-version=7.1"
result3 = client.get_raw(url3)
print(json.dumps(result3, indent=2))

print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"Board detail keys: {list(result1.keys())}") # type: ignore
print(f"Board with columns keys: {list(result2.keys())}") # type: ignore
print(f"Rows structure: count={result3.get('count')}, has value={('value' in result3)}") # type: ignore
