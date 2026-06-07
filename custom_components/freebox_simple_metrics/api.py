"""Freebox OS API client for Freebox Simple Metrics."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import socket
from typing import Any
from urllib.parse import quote, urlparse

from aiohttp import ClientError, ClientSession


class FreeboxError(Exception):
    """Base Freebox error."""


class FreeboxConnectionError(FreeboxError):
    """Freebox connection error."""


class FreeboxAuthError(FreeboxError):
    """Freebox authentication error."""


class FreeboxApiError(FreeboxError):
    """Freebox API error."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_code: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.payload = payload or {}


def _normalize_origin(host: str) -> tuple[str, str]:
    value = host.strip().rstrip("/")
    if not value:
        raise FreeboxConnectionError("Freebox host is empty")
    if "://" not in value:
        value = f"http://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise FreeboxConnectionError(f"Invalid Freebox host: {host}")
    return f"{parsed.scheme}://{parsed.netloc}", parsed.hostname or parsed.netloc


class FreeboxApiClient:
    """Small async client for the Freebox OS API."""

    def __init__(
        self,
        session: ClientSession,
        *,
        host: str,
        app_id: str,
        app_token: str | None = None,
        timeout: int = 10,
    ) -> None:
        self._session = session
        self._origin, self.host = _normalize_origin(host)
        self.app_id = app_id
        self.app_token = app_token or None
        self.timeout = timeout
        self._discovery: dict[str, Any] | None = None
        self._session_token: str | None = None

    async def discover(self) -> dict[str, Any]:
        """Fetch and cache Freebox API discovery."""
        if self._discovery is not None:
            return self._discovery

        try:
            async with self._session.get(
                f"{self._origin}/api_version",
                timeout=self.timeout,
            ) as response:
                payload = await response.json(content_type=None)
        except (ClientError, asyncio.TimeoutError, json.JSONDecodeError) as err:
            raise FreeboxConnectionError(f"Cannot reach Freebox at {self._origin}") from err

        api_version = str(payload.get("api_version", "4"))
        major = int(api_version.split(".", maxsplit=1)[0])
        self._discovery = {
            **payload,
            "origin": self._origin,
            "api_major": major,
        }
        return self._discovery

    async def request_authorization(
        self,
        *,
        app_name: str,
        app_version: str,
        device_name: str | None = None,
    ) -> dict[str, Any]:
        """Request a new Freebox application token."""
        result = await self._request(
            "POST",
            "login/authorize/",
            auth=False,
            json_data={
                "app_id": self.app_id,
                "app_name": app_name,
                "app_version": app_version,
                "device_name": device_name or socket.gethostname(),
            },
        )
        self.app_token = result["app_token"]
        return result

    async def check_authorization(self, track_id: int) -> dict[str, Any]:
        """Check a Freebox authorization request status."""
        return await self._request(
            "GET",
            f"login/authorize/{track_id}",
            auth=False,
        )

    async def open_session(self) -> dict[str, Any]:
        """Open a Freebox API session using the app token."""
        if not self.app_token:
            raise FreeboxAuthError("Missing Freebox app token")

        login = await self._request("GET", "login/", auth=False)
        challenge = login.get("challenge")
        if not challenge:
            raise FreeboxAuthError("Freebox challenge is missing")

        password = hmac.new(
            self.app_token.encode(),
            challenge.encode(),
            hashlib.sha1,
        ).hexdigest()

        try:
            result = await self._request(
                "POST",
                "login/session/",
                auth=False,
                json_data={
                    "app_id": self.app_id,
                    "password": password,
                },
            )
        except FreeboxApiError as err:
            if err.status == 403 or err.error_code in {
                "auth_required",
                "denied_from_external_ip",
                "insufficient_rights",
                "invalid_token",
            }:
                raise FreeboxAuthError(str(err)) from err
            raise
        self._session_token = result["session_token"]
        return result

    async def close_session(self) -> None:
        """Close the current Freebox API session."""
        if not self._session_token:
            return
        try:
            await self._request("POST", "login/logout/")
        finally:
            self._session_token = None

    async def probe_authenticated(self) -> dict[str, Any]:
        """Validate discovery, token and a minimal read endpoint."""
        discovery = await self.discover()
        await self.open_session()
        await self.fetch("connection/")
        return discovery

    async def fetch_metrics(self) -> dict[str, Any]:
        """Fetch connection and switch metrics."""
        discovery = await self.discover()
        connection, ftth, xdsl, switch_status = await asyncio.gather(
            self._safe_fetch("connection/"),
            self._safe_fetch("connection/ftth/"),
            self._safe_fetch("connection/xdsl/"),
            self._safe_fetch("switch/status/"),
        )

        switch_ports = switch_status.get("data") if switch_status.get("ok") else []
        port_stats: dict[int, dict[str, Any]] = {}
        if isinstance(switch_ports, list):
            stats_results = await asyncio.gather(
                *[
                    self._safe_fetch(f"switch/port/{quote(str(port['id']))}/stats")
                    for port in switch_ports
                    if "id" in port
                ],
                return_exceptions=False,
            )
            stat_index = 0
            for port in switch_ports:
                if "id" not in port:
                    continue
                result = stats_results[stat_index]
                stat_index += 1
                port_stats[int(port["id"])] = result

        connected_ports = [
            port
            for port in switch_ports
            if isinstance(port, dict) and port.get("link") == "up"
        ]

        return {
            "api": {
                "host": self.host,
                "origin": discovery.get("origin"),
                "api_version": discovery.get("api_version"),
                "api_major": discovery.get("api_major"),
                "uid": discovery.get("uid"),
                "box_model": discovery.get("box_model"),
                "box_model_name": discovery.get("box_model_name"),
                "device_name": discovery.get("device_name"),
                "device_type": discovery.get("device_type"),
            },
            "connection": connection,
            "ftth": ftth,
            "xdsl": xdsl,
            "switch_status": switch_status,
            "switch_port_stats": port_stats,
            "summary": {
                "connected_ports": len(connected_ports),
                "total_ports": len(switch_ports) if isinstance(switch_ports, list) else 0,
            },
        }

    async def fetch(self, endpoint: str) -> Any:
        """Fetch an authenticated endpoint, refreshing the session once if needed."""
        if not self._session_token:
            await self.open_session()

        try:
            return await self._request("GET", endpoint)
        except FreeboxApiError as err:
            if err.error_code not in {"auth_required", "invalid_session"}:
                raise
            self._session_token = None
            await self.open_session()
            return await self._request("GET", endpoint)

    async def _safe_fetch(self, endpoint: str) -> dict[str, Any]:
        try:
            return {"ok": True, "data": await self.fetch(endpoint)}
        except FreeboxError as err:
            return {
                "ok": False,
                "error": {
                    "endpoint": endpoint,
                    "message": str(err),
                    "error_code": getattr(err, "error_code", None),
                    "status": getattr(err, "status", None),
                },
            }

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        auth: bool = True,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        discovery = await self.discover() if endpoint != "api_version" else {}
        version = discovery.get("api_major", 4)
        base_url = str(discovery.get("api_base_url", "/api/"))
        if not base_url.endswith("/"):
            base_url = f"{base_url}/"
        url = f"{self._origin}{base_url}v{version}/{endpoint.lstrip('/')}"

        headers = {"Accept": "application/json"}
        if auth:
            if not self._session_token:
                raise FreeboxAuthError("Missing Freebox session token")
            headers["X-Fbx-App-Auth"] = self._session_token

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=json_data,
                timeout=self.timeout,
            ) as response:
                payload = await response.json(content_type=None)
        except (ClientError, asyncio.TimeoutError, json.JSONDecodeError) as err:
            raise FreeboxConnectionError(f"Freebox request failed: {endpoint}") from err

        success = payload.get("success")
        if response.status >= 400 or success is False:
            error_code = payload.get("error_code")
            message = payload.get("msg") or error_code or f"HTTP {response.status}"
            raise FreeboxApiError(
                message,
                status=response.status,
                error_code=error_code,
                payload=payload,
            )

        if "result" in payload:
            return payload["result"]
        return payload
