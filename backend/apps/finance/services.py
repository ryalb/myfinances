import os

import requests


class PluggyClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("PLUGGY_BASE_URL", "https://api.pluggy.ai").rstrip("/")
        self.client_id = os.getenv("PLUGGY_CLIENT_ID", "")
        self.client_secret = os.getenv("PLUGGY_CLIENT_SECRET", "")

    def _headers(self) -> dict[str, str]:
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Pluggy credentials are not configured.")
        return {
            "X-Client-ID": self.client_id,
            "X-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> list[dict]:
        response = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params or {},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("results", [])

    def fetch_item_accounts(self, item_id: str) -> list[dict]:
        return self._get("/accounts", params={"itemId": item_id})

    def fetch_account_transactions(
        self, account_id: str, from_date: str | None = None
    ) -> list[dict]:
        params = {"accountId": account_id}
        if from_date:
            params["from"] = from_date
        return self._get("/transactions", params=params)

    def fetch_item_cards(self, item_id: str) -> list[dict]:
        return self._get("/credit-cards", params={"itemId": item_id})

    def fetch_item_investments(self, item_id: str) -> list[dict]:
        return self._get("/investments", params={"itemId": item_id})

    def create_connect_token(self, payload: dict) -> dict:
        response = requests.post(
            f"{self.base_url}/connect_token",
            headers=self._headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
