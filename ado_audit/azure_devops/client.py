import os
import base64
import json
import logging
from typing import Any, Dict, List, Optional
import requests

from azure_devops.config import API_VERSIONS, LOG_LEVEL

# Configuration
ORG = os.getenv("ADO_ORG", "1id")
BASE_URL = f"https://dev.azure.com/{ORG}"

# Global error tracker
ERRORS: List[Dict[str, Any]] = []


def save_json(obj: Any, filepath: str) -> None:
    """Save object as pretty JSON, creating parent directories as needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def report_errors() -> None:
    """Log and display accumulated API errors."""
    if ERRORS:
        logging.warning(f"Total API errors encountered: {len(ERRORS)}")
        for i, err in enumerate(ERRORS, 1):
            logging.warning(f"  Error {i}: {err}")
    else:
        logging.info("No API errors encountered.")


class ADOClient:
    """Handles HTTP interactions with Azure DevOps REST API and tracks errors."""

    def __init__(self, pat: str):
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json; charset=utf-8"
        })

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from URL. Raises exception on HTTP error."""
        resp = self.session.get(url)
        try:
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            error_detail = {"URL": url, "Status": resp.status_code, "Message": str(e)}
            ERRORS.append(error_detail)
            logging.error(f"API request failed: {url} - Status {resp.status_code}")
            raise
        except (json.JSONDecodeError, ValueError) as e:
            error_detail = {"URL": url, "Status": resp.status_code, "Message": f"JSON decode error: {str(e)}"}
            ERRORS.append(error_detail)
            logging.error(f"Failed to parse JSON from {url}: {str(e)}")
            raise

    def get_paged(self, url: str) -> List[Dict[str, Any]]:
        """Fetch all paginated items from URL. Raises exception on HTTP error."""
        items: List[Dict[str, Any]] = []
        page = 0
        while url:
            page += 1
            resp = self.session.get(url)
            try:
                resp.raise_for_status()
                data = resp.json()
                items.extend(data.get("value", []))
                token = resp.headers.get("x-ms-continuationtoken")
                url = f"{url}&continuationToken={token}" if token else None
            except requests.HTTPError as e:
                error_detail = {"URL": url, "Status": resp.status_code, "Page": page, "Message": str(e)}
                ERRORS.append(error_detail)
                logging.error(f"Pagination failed at page {page}: {url} - Status {resp.status_code}")
                raise
            except (json.JSONDecodeError, ValueError) as e:
                error_detail = {"URL": url, "Status": resp.status_code, "Page": page, "Message": f"JSON decode error: {str(e)}"}
                ERRORS.append(error_detail)
                logging.error(f"Failed to parse JSON at page {page}: {str(e)}")
                raise
        return items

    def get_raw(self, url: str) -> Optional[Any]:
        """Return the raw JSON payload for a URL. Raises exception on HTTP error."""
        resp = self.session.get(url)
        try:
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            error_detail = {"URL": url, "Status": resp.status_code, "Message": str(e)}
            ERRORS.append(error_detail)
            logging.error(f"API request failed: {url} - Status {resp.status_code}")
            raise
        except (json.JSONDecodeError, ValueError) as e:
            error_detail = {"URL": url, "Status": resp.status_code, "Message": f"JSON decode error: {str(e)}"}
            ERRORS.append(error_detail)
            logging.error(f"Failed to parse JSON from {url}: {str(e)}")
            raise