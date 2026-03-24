import requests
from requests.auth import HTTPBasicAuth

org = '1id'
url = f"https://analytics.dev.azure.com/{org}/_odata/v3.0-preview/WorkItems"

query = {
    "$apply": "filter(System.ChangedDate ge 2025-04-08T14:44:40Z)/"
              "groupby((System.TeamProject,System.WorkItemType,System.State),"
              "aggregate($count as WI_Count))"
}

response = requests.get(
    url,
    params=query,
    auth=HTTPBasicAuth('', 'G2jzdo870EXBrTmVpGTcDjZqD7ROyrdYWJo79GuSD8FArIIXQ2upJQQJ99BFACAAAAAqG6F6AAASAZDO1LW9')
)

print(response.url)  # Debug the final URL
response.raise_for_status()
print(response.json())
