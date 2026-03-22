"""
WHOOP API v2 client with OAuth2 authentication and token refresh.

All credentials are read from environment variables:
  WHOOP_CLIENT_ID     — OAuth2 client ID
  WHOOP_CLIENT_SECRET — OAuth2 client secret
  WHOOP_ACCESS_TOKEN  — current access token (updated in-place if refreshed)
  WHOOP_REFRESH_TOKEN — refresh token
"""

import os
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

WHOOP_BASE_URL = "https://api.prod.whoop.com/developer/v1"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"


class WhoopClient:
    def __init__(self) -> None:
        self.client_id = os.environ["WHOOP_CLIENT_ID"]
        self.client_secret = os.environ["WHOOP_CLIENT_SECRET"]
        self.access_token = os.environ["WHOOP_ACCESS_TOKEN"]
        self.refresh_token = os.environ["WHOOP_REFRESH_TOKEN"]
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def refresh_access_token(self) -> None:
        """Exchange refresh token for a new access token."""
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        self.access_token = payload["access_token"]
        self.refresh_token = payload.get("refresh_token", self.refresh_token)
        os.environ["WHOOP_ACCESS_TOKEN"] = self.access_token
        os.environ["WHOOP_REFRESH_TOKEN"] = self.refresh_token
        self._persist_tokens_to_env_file()
        logger.info("WHOOP access token refreshed successfully.")

    def _persist_tokens_to_env_file(self) -> None:
        """Write updated tokens back to the .env file so future runs use them."""
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_path = os.path.abspath(env_path)
        if not os.path.exists(env_path):
            return
        with open(env_path, "r") as f:
            content = f.read()
        content = re.sub(r"(?m)^WHOOP_ACCESS_TOKEN=.*$", f"WHOOP_ACCESS_TOKEN={self.access_token}", content)
        content = re.sub(r"(?m)^WHOOP_REFRESH_TOKEN=.*$", f"WHOOP_REFRESH_TOKEN={self.refresh_token}", content)
        with open(env_path, "w") as f:
            f.write(content)

    def _get(self, path: str, params: dict | None = None, retry: bool = True) -> Any:
        url = f"{WHOOP_BASE_URL}{path}"
        resp = self.session.get(url, headers=self._auth_headers(), params=params, timeout=30)
        if resp.status_code == 401 and retry:
            logger.warning("Access token expired — refreshing and retrying.")
            self.refresh_access_token()
            return self._get(path, params=params, retry=False)
        if resp.status_code == 404:
            logger.warning("No data found for %s (404) — skipping.", path)
            return {"records": []}
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Paginated collection helper
    # ------------------------------------------------------------------

    def _get_paginated(self, path: str, params: dict | None = None) -> list[dict]:
        """Iterate through all pages of a collection endpoint."""
        results: list[dict] = []
        params = dict(params or {})
        while True:
            page = self._get(path, params=params)
            records = page.get("records", [])
            results.extend(records)
            next_token = page.get("next_token")
            if not next_token:
                break
            params["nextToken"] = next_token
        return results

    # ------------------------------------------------------------------
    # Data fetch methods — each returns raw API payload(s)
    # ------------------------------------------------------------------

    def _date_window(self, target_date: datetime) -> dict[str, str]:
        """Build start/end params covering a single calendar day (UTC)."""
        start = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return {
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
        }

    def get_sleep(self, target_date: datetime) -> list[dict]:
        """Return sleep records for target_date."""
        params = self._date_window(target_date)
        return self._get_paginated("/activity/sleep", params)

    def get_recovery(self, target_date: datetime) -> list[dict]:
        """Return recovery records for target_date."""
        params = self._date_window(target_date)
        return self._get_paginated("/recovery", params)

    def get_workouts(self, target_date: datetime) -> list[dict]:
        """Return workout records for target_date."""
        params = self._date_window(target_date)
        return self._get_paginated("/activity/workout", params)

    def get_cycle(self, target_date: datetime) -> list[dict]:
        """Return physiological cycle records for target_date."""
        params = self._date_window(target_date)
        return self._get_paginated("/cycle", params)

    def fetch_previous_day(self) -> dict[str, list[dict]]:
        """Fetch all streams for yesterday (UTC). Returns a dict of raw records."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        logger.info("Fetching WHOOP data for %s", yesterday.date())
        return {
            "sleep": self.get_sleep(yesterday),
            "recovery": self.get_recovery(yesterday),
            "workouts": self.get_workouts(yesterday),
            "cycles": self.get_cycle(yesterday),
        }
