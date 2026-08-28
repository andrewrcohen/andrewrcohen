"""HTTP client for FMCSA Motus public APIs, Motus SODA datasets, and QCMobile."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

MOTUS_API_BASE = "https://motus.dot.gov/api"
SODA_BASE = "https://data.transportation.gov/resource"
QCMOBILE_BASE = "https://mobile.fmcsa.dot.gov/qc/services"
DEFAULT_USER_AGENT = "Farelanes-FMCSA-Motus-Exercise/1.0"

# Motus SODA datasets published on data.transportation.gov after the May 2026 cutover.
MOTUS_SODA_DATASETS: dict[str, dict[str, str]] = {
    "carrier_history": {
        "id": "inys-ebih",
        "name": "Motus Carrier - All With History",
        "query_field": "usdot_number",
    },
    "carrier_daily": {
        "id": "nakq-58th",
        "name": "Motus Carrier",
        "query_field": "usdot_number",
    },
    "insur_history": {
        "id": "c5y8-a4uz",
        "name": "Motus Insur - All With History",
        "query_field": "usdot_number",
    },
    "insur_daily": {
        "id": "x96h-evps",
        "name": "Motus Insur",
        "query_field": "usdot_number",
    },
    "inshist_history": {
        "id": "3uet-3z4i",
        "name": "Motus InsHist - All With History",
        "query_field": "usdot_number",
    },
    "inshist_daily": {
        "id": "xe5s-wca7",
        "name": "Motus InsHist",
        "query_field": "usdot_number",
    },
    "boc3_history": {
        "id": "6snj-ed7q",
        "name": "Motus BOC3 - All With History",
        "query_field": "usdot_number",
    },
    "boc3_daily": {
        "id": "mhr5-hjyc",
        "name": "Motus BOC3",
        "query_field": "usdot_number",
    },
    "authhist_history": {
        "id": "yu5v-wbh6",
        "name": "Motus AuthHist - All With History",
        "query_field": "usdot_number",
    },
    "authhist_daily": {
        "id": "dm5j-zc6c",
        "name": "Motus AuthHist",
        "query_field": "usdot_number",
    },
    "revoke_history": {
        "id": "wb4f-neki",
        "name": "Motus RevokeSuspend - All With History",
        "query_field": "usdot_number",
    },
    "revoke_daily": {
        "id": "e67p-xyd5",
        "name": "Motus RevokeSuspend",
        "query_field": "usdot_number",
    },
}

SENSITIVE_KEYS = {
    "ein",
    "ssn",
    "mexicanTaxId",
    "rfc",
    "caBn",
    "caNcs",
    "taxId",
    "socialSecurityNumber",
}


@dataclass
class HttpResult:
    name: str
    method: str
    url: str
    status: Optional[int]
    ok: bool
    elapsed_ms: float
    body: Any = None
    error: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> Optional[int]:
        if isinstance(self.body, list):
            return len(self.body)
        if isinstance(self.body, dict) and isinstance(self.body.get("data"), list):
            return len(self.body["data"])
        return None


def redact_sensitive(value: Any) -> Any:
    """Replace tax-ID style fields before printing API bodies."""
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if str(key) in SENSITIVE_KEYS and item not in (None, "", []):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def soda_url(dataset_id: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode(params, safe="='$")
    return f"{SODA_BASE}/{dataset_id}.json?{query}"


def motus_url(path: str, params: Optional[dict[str, Any]] = None) -> str:
    path = path.lstrip("/")
    url = f"{MOTUS_API_BASE}/{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return url


def qcmobile_url(path: str, web_key: str, params: Optional[dict[str, Any]] = None) -> str:
    path = path.lstrip("/")
    query = dict(params or {})
    query["webKey"] = web_key
    return f"{QCMOBILE_BASE}/{path}?{urllib.parse.urlencode(query)}"


class HttpClient:
    def __init__(self, timeout: float = 30.0, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self._ssl_context = ssl.create_default_context()

    def get(self, name: str, url: str) -> HttpResult:
        import time

        started = time.perf_counter()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout, context=self._ssl_context
            ) as response:
                raw = response.read()
                elapsed_ms = (time.perf_counter() - started) * 1000
                body = _decode_body(raw)
                return HttpResult(
                    name=name,
                    method="GET",
                    url=url,
                    status=response.status,
                    ok=200 <= response.status < 300,
                    elapsed_ms=elapsed_ms,
                    body=body,
                )
        except urllib.error.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            raw = exc.read()
            return HttpResult(
                name=name,
                method="GET",
                url=url,
                status=exc.code,
                ok=False,
                elapsed_ms=elapsed_ms,
                body=_decode_body(raw),
                error=f"HTTP {exc.code}",
            )
        except Exception as exc:  # noqa: BLE001 - exercise harness should capture transport errors
            elapsed_ms = (time.perf_counter() - started) * 1000
            return HttpResult(
                name=name,
                method="GET",
                url=url,
                status=None,
                ok=False,
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )


def _decode_body(raw: bytes) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def extract_entity_id(carrier_search_body: Any) -> Optional[str]:
    if isinstance(carrier_search_body, dict):
        rows = carrier_search_body.get("data") or []
        if rows and isinstance(rows[0], dict):
            return rows[0].get("entityId")
    if isinstance(carrier_search_body, list) and carrier_search_body:
        first = carrier_search_body[0]
        if isinstance(first, dict):
            return first.get("entityId") or (first.get("entityDotNumber") or {}).get("entityId")
    if isinstance(carrier_search_body, dict):
        return carrier_search_body.get("entityId")
    return None
