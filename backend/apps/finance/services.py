import logging
import os
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

MEU_PLUGGY_CONNECTOR_ID = "200"
MEU_PLUGGY_BASE_URL = "https://api.pluggy.ai"


class PluggyClient:
    MEU_PLUGGY_CONNECTOR_ID = "200"
    MEU_PLUGGY_BASE_URL = "https://api.pluggy.ai"

    def __init__(self, force_production: bool = False) -> None:
        base_url = os.getenv("PLUGGY_BASE_URL", "https://api.pluggy.ai").rstrip("/")
        if force_production and "sandbox" in base_url:
            base_url = self.MEU_PLUGGY_BASE_URL
            logger.warning(
                "Sandbox is not supported for Meu Pluggy. Using production URL: %s", base_url
            )
        self.base_url = base_url
        self.client_id = os.getenv("PLUGGY_CLIENT_ID", "")
        self.client_secret = os.getenv("PLUGGY_CLIENT_SECRET", "")
        self._api_key: str | None = None
        self._api_key_expires_at: timezone.datetime | None = None

    def _invalidate_api_key(self) -> None:
        self._api_key = None
        self._api_key_expires_at = None

    def is_meu_pluggy_item(self, item_data: dict) -> bool:
        connector_id = item_data.get("connectorId")
        if connector_id is None:
            return False
        return str(connector_id) == self.MEU_PLUGGY_CONNECTOR_ID

    def discover_meu_pluggy(self, client_user_id: str | None = None) -> dict:
        if not client_user_id:
            raise ValueError("clientUserId é obrigatório para descobrir items do Meu Pluggy.")

        original_base_url = self.base_url

        try:
            if "sandbox.pluggy.ai" in self.base_url:
                self.base_url = self.MEU_PLUGGY_BASE_URL
                self._invalidate_api_key()
                logger.info(
                    "Meu Pluggy: switched base_url from %s to %s",
                    original_base_url,
                    self.base_url,
                )

            logger.info(
                "Pluggy discover_meu_pluggy client_user_id=%s base_url=%s",
                client_user_id,
                self.base_url,
            )
            token_data = self.create_connect_token(client_user_id)
        finally:
            self.base_url = original_base_url
            self._invalidate_api_key()

        return {
            "type": "connect_token",
            "accessToken": token_data.get("accessToken"),
        }

    def _get_api_key(self) -> str:
        if (
            self._api_key
            and self._api_key_expires_at
            and timezone.now() < self._api_key_expires_at - timedelta(minutes=5)
        ):
            return self._api_key

        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Pluggy credentials are not configured. "
                "Set PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET in backend/.env."
            )

        logger.info(
            "Pluggy authenticate base_url=%s client_id=%s",
            self.base_url,
            self.client_id,
        )
        url = f"{self.base_url}/auth"
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        }
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Pluggy authentication failed ({response.status_code}): {response.text}. "
                "Verify PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET."
            )

        data = response.json()
        api_key = data.get("apiKey")
        if not api_key:
            raise RuntimeError("Pluggy did not return an apiKey in the auth response.")
        logger.info(
            "Pluggy auth returned apiKey_length=%d has_expiresIn=%s",
            len(api_key),
            "expiresIn" in data,
        )
        self._api_key = api_key
        expires_in = data.get("expiresIn")
        if isinstance(expires_in, int | float) and expires_in > 0:
            self._api_key_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
        else:
            self._api_key_expires_at = timezone.now() + timedelta(hours=2)
        return api_key

    def _request(self, method: str, path: str, params: dict | None = None) -> list[dict]:
        api_key = self._get_api_key()
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        }

        logger.info(
            "Pluggy request method=%s url=%s",
            method,
            url,
        )

        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            timeout=20,
        )

        if response.status_code == 401:
            self._invalidate_api_key()
            api_key = self._get_api_key()
            headers["X-API-KEY"] = api_key
            logger.warning("Pluggy request retrying after 401 for %s", path)
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=20,
            )

        if response.status_code == 401:
            try:
                body = response.json()
                logger.error(
                    "Pluggy 401 body for %s: code=%s description=%s message=%s",
                    url,
                    body.get("code"),
                    body.get("codeDescription"),
                    body.get("message"),
                )
            except Exception:
                logger.error("Pluggy 401 for %s: %s", url, response.text[:300])

        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def fetch_items(self, client_user_id: str | None = None) -> list[dict]:
        params: dict[str, str] = {}
        if client_user_id:
            params["clientUserId"] = str(client_user_id)

        logger.info(
            "Pluggy fetch_items client_user_id=%s base_url=%s",
            client_user_id,
            self.base_url,
        )
        return self._request("GET", "/items", params=params if params else None)

    def fetch_user_items(self, client_user_id: str) -> list[dict]:
        return self.fetch_items(client_user_id=client_user_id)

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        api_key = self._get_api_key()
        headers = kwargs.pop("headers", {})
        headers["X-API-KEY"] = api_key
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=20,
            **kwargs,
        )
        if response.status_code == 401:
            self._invalidate_api_key()
            api_key = self._get_api_key()
            headers["X-API-KEY"] = api_key
            logger.warning("Pluggy request retrying after 401 for %s", url)
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=20,
                **kwargs,
            )
            if response.status_code == 401:
                try:
                    body = response.json()
                    logger.error(
                        "Pluggy 401 body for %s: code=%s description=%s message=%s",
                        url,
                        body.get("code"),
                        body.get("codeDescription"),
                        body.get("message"),
                    )
                except Exception:
                    logger.error("Pluggy 401 for %s: %s", url, response.text[:300])
        elif response.status_code == 409:
            try:
                body = response.json()
                code = body.get("codeDescription", "")
                if code in (
                    "ITEM_IS_ALREADY_UPDATING",
                    "ITEM_CREATION_LIMIT_EXCEEDED",
                ):
                    logger.warning("Pluggy 409 for %s: %s", url, body.get("message"))
            except Exception:
                pass
        return response

    def fetch_item_accounts(self, item_id: str) -> list[dict]:
        url = f"{self.base_url}/accounts"
        params = {"itemId": item_id}

        logger.info("Pluggy fetch_item_accounts item_id=%s", item_id)
        response = self._request_with_retry("GET", url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def fetch_account_transactions(
        self, account_id: str, from_date: str | None = None
    ) -> list[dict]:
        params: dict[str, str] = {"accountId": account_id}
        if from_date:
            params["dateFrom"] = from_date

        logger.info(
            "Pluggy fetch_account_transactions account_id=%s from_date=%s",
            account_id,
            from_date,
        )
        results: list[dict] = []
        while True:
            url = f"{self.base_url}/v2/transactions"
            response = self._request_with_retry("GET", url, params=params)
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("results", []))
            next_link = data.get("next")
            if not next_link:
                break
            after = parse_qs(urlparse(next_link).query).get("after", [None])[0]
            if not after:
                break
            params["after"] = after
        logger.info(
            "Pluggy fetch_account_transactions account_id=%s total=%d",
            account_id,
            len(results),
        )
        return results

    def fetch_item_cards(self, item_id: str) -> list[dict]:
        url = f"{self.base_url}/accounts"
        params = {"itemId": item_id, "type": "CREDIT"}

        logger.info("Pluggy fetch_item_cards item_id=%s", item_id)
        response = self._request_with_retry("GET", url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def fetch_item_identity(self, item_id: str) -> dict | None:
        """Titular do item. `GET /identity` responde 404 quando o produto nao foi coletado."""
        url = f"{self.base_url}/identity"
        params = {"itemId": item_id}

        logger.info("Pluggy fetch_item_identity item_id=%s", item_id)
        response = self._request_with_retry("GET", url, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "results" in data:
            results = data.get("results") or []
            return results[0] if results else None
        return data or None

    def fetch_item_investments(self, item_id: str) -> list[dict]:
        url = f"{self.base_url}/investments"
        params = {"itemId": item_id}

        logger.info("Pluggy fetch_item_investments item_id=%s", item_id)
        response = self._request_with_retry("GET", url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def create_connect_token(self, client_user_id: str | None = None) -> dict:
        url = f"{self.base_url}/connect_token"
        options: dict[str, str] = {}
        if client_user_id:
            options["clientUserId"] = str(client_user_id)

        webhook_url = os.getenv("PLUGGY_WEBHOOK_URL", "")
        if webhook_url:
            options["webhookUrl"] = webhook_url
        else:
            logger.warning(
                "PLUGGY_WEBHOOK_URL is not set. The item will be created without a webhook "
                "and no automatic synchronization will be triggered."
            )

        payload: dict[str, dict] = {"options": options} if options else {}

        logger.info(
            "Pluggy create_connect_token client_user_id=%s base_url=%s has_webhook=%s",
            client_user_id,
            self.base_url,
            bool(webhook_url),
        )
        response = self._request_with_retry("POST", url, json=payload)
        response.raise_for_status()
        data = response.json()
        logger.info(
            "Pluggy create_connect_token returned accessToken=%s",
            bool(data.get("accessToken")),
        )
        return data

    def register_webhook(self, url_to_register: str, event: str = "all") -> dict:
        """Register an application-level webhook, covering items created outside our widget."""
        url = f"{self.base_url}/webhooks"

        logger.info("Pluggy register_webhook url=%s event=%s", url_to_register, event)
        response = self._request_with_retry(
            "POST", url, json={"event": event, "url": url_to_register}
        )
        response.raise_for_status()
        return response.json()

    def list_webhooks(self) -> list[dict]:
        url = f"{self.base_url}/webhooks"

        logger.info("Pluggy list_webhooks base_url=%s", self.base_url)
        response = self._request_with_retry("GET", url)
        response.raise_for_status()
        return response.json().get("results", [])

    def delete_webhook(self, webhook_id: str) -> None:
        url = f"{self.base_url}/webhooks/{webhook_id}"

        logger.info("Pluggy delete_webhook id=%s", webhook_id)
        response = self._request_with_retry("DELETE", url)
        response.raise_for_status()

    def fetch_item(self, item_id: str) -> dict:
        url = f"{self.base_url}/items/{item_id}"

        logger.info("Pluggy fetch_item item_id=%s", item_id)
        response = self._request_with_retry("GET", url)
        response.raise_for_status()
        data = response.json()
        logger.info(
            "Pluggy fetch_item id=%s status=%s",
            data.get("id"),
            data.get("status"),
        )
        return data

    def fetch_transactions_from_link(self, link: str) -> list[dict]:
        """Fetch transactions from a `createdTransactionsLink` provided by a webhook payload."""
        if not link.startswith(self.base_url):
            raise ValueError(
                f"Refusing to follow a transactions link outside {self.base_url}: {link}"
            )

        logger.info("Pluggy fetch_transactions_from_link link=%s", link)
        results: list[dict] = []
        url: str | None = link
        while url:
            response = self._request_with_retry("GET", url)
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("results", []))
            next_link = data.get("next")
            url = next_link if next_link and next_link.startswith(self.base_url) else None
        logger.info("Pluggy fetch_transactions_from_link total=%d", len(results))
        return results

    def fetch_transactions_by_ids(self, transaction_ids: list[str]) -> list[dict]:
        results: list[dict] = []
        for transaction_id in transaction_ids:
            url = f"{self.base_url}/transactions/{transaction_id}"
            response = self._request_with_retry("GET", url)
            if response.status_code == 404:
                logger.info("Pluggy transaction %s not found; skipping", transaction_id)
                continue
            response.raise_for_status()
            results.append(response.json())
        return results

    def fetch_applications(self) -> list[dict]:
        url = f"{self.base_url}/applications"

        logger.info("Pluggy fetch_applications base_url=%s", self.base_url)
        response = self._request_with_retry("GET", url)
        response.raise_for_status()
        data = response.json()
        apps = data.get("results", [])
        logger.info(
            "Pluggy fetch_applications base_url=%s returned %d applications",
            self.base_url,
            len(apps),
        )
        for app in apps:
            logger.info(
                "Pluggy application id=%s name=%s clientId=%s",
                app.get("id"),
                app.get("name"),
                app.get("clientId"),
            )
        return apps
