from __future__ import annotations

import json
import re
import socket
import urllib.error
from typing import Any

from litagent.providers import FetchBytes, SemanticScholarProvider, default_fetch_bytes
from litagent.secrets import get_config_value

DEFAULT_PROVIDER_SMOKE_QUERY = "literature review automation"


def _redact_known_secrets(text: str) -> str:
    redacted = text
    for name in ["SEMANTIC_SCHOLAR_API_KEY", "MINERU_API_TOKEN"]:
        value = get_config_value(name)
        if value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted


def _http_status_code(exc: Exception) -> int | None:
    if isinstance(exc, urllib.error.HTTPError):
        return int(exc.code)
    match = re.search(r"\bHTTP Error\s+(\d{3})\b", str(exc))
    if match:
        return int(match.group(1))
    return None


def _error_type(exc: Exception, status_code: int | None) -> str:
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 429:
        return "rate_limited"
    if status_code is not None:
        return "http_error"
    if isinstance(exc, json.JSONDecodeError):
        return "bad_json"
    if isinstance(exc, TimeoutError | socket.timeout):
        return "timeout"
    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    return "network_or_provider_error"


def _likely_action(error_type: str) -> str:
    if error_type == "forbidden":
        return (
            "Check API key validity/permission, auth header mode, base URL and endpoint path, "
            "proxy route permission, and whether the proxy expects a different auth format."
        )
    if error_type == "unauthorized":
        return "Check API key value, header mode, and whether the key is active."
    if error_type == "rate_limited":
        return (
            "Use a valid Semantic Scholar API key, wait/back off, or verify that the configured "
            "proxy has sufficient quota."
        )
    if error_type == "bad_json":
        return "Check whether the provider/proxy returned HTML or another non-JSON error body."
    if error_type == "timeout":
        return "Check provider reachability, proxy availability, and network timeout settings."
    if error_type == "http_error":
        return "Check provider status, endpoint path, query parameters, and credentials."
    return "Check network connectivity, provider compatibility, and local configuration."


def semantic_scholar_error_diagnostic(exc: Exception) -> dict[str, Any]:
    provider = SemanticScholarProvider()
    status_code = _http_status_code(exc)
    error_type = _error_type(exc, status_code)
    return {
        **provider.diagnostic_context(),
        "status_code": status_code,
        "success": False,
        "error_type": error_type,
        "error": _redact_known_secrets(str(exc)),
        "likely_action": _likely_action(error_type),
    }


def smoke_test_semantic_scholar(
    *,
    query: str = DEFAULT_PROVIDER_SMOKE_QUERY,
    limit: int = 1,
    fetch: FetchBytes = default_fetch_bytes,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 3))
    provider = SemanticScholarProvider(fetch=fetch)
    result: dict[str, Any] = {
        **provider.diagnostic_context(),
        "query": query,
        "limit": safe_limit,
        "success": False,
        "status_code": None,
        "error_type": None,
        "error": None,
        "result_count": 0,
        "sample_titles": [],
        "likely_action": "Provider smoke test has not run.",
    }
    try:
        raw = fetch(provider.endpoint_url(query, safe_limit), provider.headers())
        data = json.loads(raw.decode("utf-8"))
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            result.update(
                {
                    "error_type": "bad_json",
                    "error": "JSON response did not contain a data list.",
                    "likely_action": _likely_action("bad_json"),
                }
            )
            return result
        result.update(
            {
                "success": True,
                "status_code": 200,
                "result_count": len(rows),
                "sample_titles": [
                    str(item.get("title") or "")
                    for item in rows[:safe_limit]
                    if isinstance(item, dict)
                ],
                "likely_action": (
                    "Provider is reachable. Re-run search only after checking source diversity."
                ),
            }
        )
        return result
    except Exception as exc:  # noqa: BLE001 - diagnostics must classify provider failures
        result.update(semantic_scholar_error_diagnostic(exc))
        result.update({"query": query, "limit": safe_limit, "result_count": 0, "sample_titles": []})
        return result
