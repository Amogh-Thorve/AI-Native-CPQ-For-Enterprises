"""Thin async client for the Salesforce REST API (OAuth 2.0 + sObject CRUD + SOQL)."""
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from backend.app.core.config import settings

API_VERSION = "v60.0"


class SalesforceError(Exception):
    pass


def oauth_configured() -> bool:
    return bool(settings.SALESFORCE_CLIENT_ID and settings.SALESFORCE_CLIENT_SECRET)


def build_authorize_url(state: str) -> str:
    qs = urlencode({
        "response_type": "code",
        "client_id": settings.SALESFORCE_CLIENT_ID,
        "redirect_uri": settings.SALESFORCE_REDIRECT_URI,
        "scope": "api refresh_token",
        "state": state,
    })
    return f"{settings.SALESFORCE_LOGIN_URL}/services/oauth2/authorize?{qs}"


async def exchange_code(code: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{settings.SALESFORCE_LOGIN_URL}/services/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.SALESFORCE_CLIENT_ID,
            "client_secret": settings.SALESFORCE_CLIENT_SECRET,
            "redirect_uri": settings.SALESFORCE_REDIRECT_URI,
        })
    if r.status_code != 200:
        raise SalesforceError(f"Token exchange failed: {r.text[:300]}")
    return r.json()


def soql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class SalesforceClient:
    def __init__(
        self,
        instance_url: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        on_token_refreshed: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.instance_url = instance_url.rstrip("/")
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.on_token_refreshed = on_token_refreshed

    async def _refresh(self) -> bool:
        if not (self.refresh_token and oauth_configured()):
            return False
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{settings.SALESFORCE_LOGIN_URL}/services/oauth2/token", data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": settings.SALESFORCE_CLIENT_ID,
                "client_secret": settings.SALESFORCE_CLIENT_SECRET,
            })
        if r.status_code != 200:
            return False
        self.access_token = r.json()["access_token"]
        if self.on_token_refreshed:
            await self.on_token_refreshed(self.access_token)
        return True

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = path if path.startswith("http") else f"{self.instance_url}{path}"
        for attempt in (1, 2):
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.request(method, url, headers={"Authorization": f"Bearer {self.access_token}"}, **kwargs)
            if r.status_code == 401 and attempt == 1 and await self._refresh():
                continue
            break
        if r.status_code >= 400:
            try:
                detail = "; ".join(e.get("message", "") for e in r.json()) if isinstance(r.json(), list) else r.text
            except Exception:
                detail = r.text
            raise SalesforceError(f"Salesforce API {r.status_code}: {detail[:300]}")
        return r

    async def userinfo(self) -> Dict[str, Any]:
        return (await self._request("GET", "/services/oauth2/userinfo")).json()

    async def query(self, soql: str) -> List[Dict[str, Any]]:
        r = await self._request("GET", f"/services/data/{API_VERSION}/query", params={"q": soql})
        return r.json().get("records", [])

    async def create(self, sobject: str, data: Dict[str, Any]) -> str:
        r = await self._request("POST", f"/services/data/{API_VERSION}/sobjects/{sobject}", json=data)
        return r.json()["id"]

    async def update(self, sobject: str, record_id: str, data: Dict[str, Any]) -> None:
        await self._request("PATCH", f"/services/data/{API_VERSION}/sobjects/{sobject}/{record_id}", json=data)
