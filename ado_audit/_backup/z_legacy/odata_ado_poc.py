import requests
from requests.auth import HTTPBasicAuth
import pandas as pd

# === Configuration ===
organization = "1id"
odata_url = f"https://analytics.dev.azure.com/1id/_odata/v3.0-preview/WorkItems"
personal_access_token = "G2jzdo870EXBrTmVpGTcDjZqD7ROyrdYWJo79GuSD8FArIIXQ2upJQQJ99BFACAAAAAqG6F6AAASAZDO1LW9"

# === Authentication ===
# Use PAT as the password and an empty string as the username
auth = HTTPBasicAuth('', personal_access_token)

# === Optional: Filter last X days ===

from datetime import datetime, timedelta, timezone

days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ')

params = {
     '$filter': f"ChangedDate ge {days_ago}"
}
# === Make the request ===
response = requests.get(odata_url, auth=auth, params=params)

# === Check and parse ===
if response.status_code == 200:
    data = response.json()
    df = pd.DataFrame(data['value'])
    print(df.head())
else:
    print(f"Request failed: {response.status_code}")
    print(response.text)
