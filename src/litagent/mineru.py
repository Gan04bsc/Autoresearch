from __future__ import annotations

import io
import json
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from litagent.io import append_jsonl, read_json, read_jsonl, write_json, write_jsonl
from litagent.reader import extract_pdf_text
from litagent.schema import normalize_paper
from litagent.secrets import get_config_value

MINERU_BASE_URL = "https://mineru.net"
TERMINAL_STATES = {"done", "failed"}
RUNNING_STATES = {"waiting-file", "uploading", "pending", "running", "converting"}


@dataclass
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str] | None = None


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        data: bytes | None = None,
    ) -> HttpResponse:
        """Execute one HTTP request."""


class UrlLibTransport:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        data: bytes | None = None,
    ) -> HttpResponse:
        headers = {"User-Agent": "litagent/0.1", **(headers or {})}
        body = data
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            return HttpResponse(
                status_code=response.status,
                body=response.read(),
                headers=dict(response.headers.items()),
            )


@dataclass
class MinerUParseResult:
    state: str
    mode: str
    task_id: str | None = None
    markdown: str | None = None
    markdown_url: str | None = None
    full_zip_url: str | None = None
    error: str | None = None
    err_code: int | None = None

    @property
    def ok(self) -> bool:
        return self.state == "done" and bool(self.markdown)


class MinerUAPIError(RuntimeError):
    pass


def is_http_url(value: str | None) -> bool:
    return bool(value and value.startswith(("http://", "https://")))


def safe_json(response: HttpResponse) -> dict[str, Any]:
    try:
        return json.loads(response.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"MinerU returned non-JSON response with HTTP {response.status_code}"
        raise MinerUAPIError(msg) from exc


def read_markdown_from_zip(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        preferred = [name for name in names if name.endswith("/full.md") or name == "full.md"]
        markdown_files = preferred or [name for name in names if name.endswith(".md")]
        if not markdown_files:
            msg = "MinerU result zip did not contain a Markdown file"
            raise MinerUAPIError(msg)
        return archive.read(markdown_files[0]).decode("utf-8")


class MinerUClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str = MINERU_BASE_URL,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.token = token or get_config_value("MINERU_API_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.transport = transport or UrlLibTransport()
        self.sleep = sleep

    def _headers(self, *, auth: bool) -> dict[str, str]:
        headers = {"Accept": "*/*"}
        if auth:
            if not self.token:
                msg = "MINERU_API_TOKEN is required for MinerU precision mode"
                raise MinerUAPIError(msg)
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _json(
        self,
        method: str,
        url: str,
        *,
        auth: bool = False,
        json_data: dict[str, Any] | None = None,
        data: bytes | None = None,
    ) -> dict[str, Any]:
        response = self.transport.request(
            method,
            url,
            headers=self._headers(auth=auth),
            json_data=json_data,
            data=data,
        )
        if response.status_code >= 400:
            msg = f"MinerU HTTP error {response.status_code}"
            raise MinerUAPIError(msg)
        payload = safe_json(response)
        if payload.get("code") != 0:
            msg = f"MinerU API error {payload.get('code')}: {payload.get('msg')}"
            raise MinerUAPIError(msg)
        return payload

    def _download_bytes(self, url: str) -> bytes:
        response = self.transport.request("GET", url, headers={"Accept": "*/*"})
        if response.status_code >= 400:
            msg = f"MinerU result download failed with HTTP {response.status_code}"
            raise MinerUAPIError(msg)
        return response.body

    def _download_text(self, url: str) -> str:
        return self._download_bytes(url).decode("utf-8")

    def parse_url_agent(
        self,
        url: str,
        *,
        file_name: str | None = None,
        language: str = "ch",
        page_range: str | None = None,
        enable_table: bool = True,
        is_ocr: bool = False,
        enable_formula: bool = True,
        timeout: int = 300,
        poll_interval: float = 3,
    ) -> MinerUParseResult:
        data: dict[str, Any] = {
            "url": url,
            "language": language,
            "enable_table": enable_table,
            "is_ocr": is_ocr,
            "enable_formula": enable_formula,
        }
        if file_name:
            data["file_name"] = file_name
        if page_range:
            data["page_range"] = page_range

        payload = self._json(
            "POST",
            f"{self.base_url}/api/v1/agent/parse/url",
            json_data=data,
        )
        task_id = payload["data"]["task_id"]
        return self.poll_agent_result(task_id, timeout=timeout, poll_interval=poll_interval)

    def parse_file_agent(
        self,
        file_path: Path,
        *,
        language: str = "ch",
        page_range: str | None = None,
        enable_table: bool = True,
        is_ocr: bool = False,
        enable_formula: bool = True,
        timeout: int = 300,
        poll_interval: float = 3,
    ) -> MinerUParseResult:
        data: dict[str, Any] = {
            "file_name": file_path.name,
            "language": language,
            "enable_table": enable_table,
            "is_ocr": is_ocr,
            "enable_formula": enable_formula,
        }
        if page_range:
            data["page_range"] = page_range

        payload = self._json(
            "POST",
            f"{self.base_url}/api/v1/agent/parse/file",
            json_data=data,
        )
        task_id = payload["data"]["task_id"]
        upload_url = payload["data"]["file_url"]
        upload = self.transport.request("PUT", upload_url, data=file_path.read_bytes())
        if upload.status_code not in {200, 201}:
            return MinerUParseResult(
                state="failed",
                mode="agent-file",
                task_id=task_id,
                error=f"MinerU signed upload failed with HTTP {upload.status_code}",
            )
        return self.poll_agent_result(task_id, timeout=timeout, poll_interval=poll_interval)

    def poll_agent_result(
        self,
        task_id: str,
        *,
        timeout: int = 300,
        poll_interval: float = 3,
    ) -> MinerUParseResult:
        deadline = time.monotonic() + timeout
        while True:
            payload = self._json("GET", f"{self.base_url}/api/v1/agent/parse/{task_id}")
            data = payload["data"]
            state = data.get("state", "unknown")
            if state == "done":
                markdown_url = data.get("markdown_url")
                if not markdown_url:
                    return MinerUParseResult(
                        state="failed",
                        mode="agent",
                        task_id=task_id,
                        error="MinerU agent result did not include markdown_url",
                    )
                markdown = self._download_text(markdown_url)
                return MinerUParseResult(
                    state="done",
                    mode="agent",
                    task_id=task_id,
                    markdown=markdown,
                    markdown_url=markdown_url,
                )
            if state == "failed":
                return MinerUParseResult(
                    state="failed",
                    mode="agent",
                    task_id=task_id,
                    error=data.get("err_msg") or "MinerU agent parsing failed",
                    err_code=data.get("err_code"),
                )
            if state not in RUNNING_STATES:
                return MinerUParseResult(
                    state="failed",
                    mode="agent",
                    task_id=task_id,
                    error=f"Unknown MinerU task state: {state}",
                )
            if time.monotonic() >= deadline:
                return MinerUParseResult(
                    state="failed",
                    mode="agent",
                    task_id=task_id,
                    error="MinerU polling timed out",
                )
            self.sleep(poll_interval)

    def parse_url_precision(
        self,
        url: str,
        *,
        data_id: str | None = None,
        model_version: str = "vlm",
        language: str = "ch",
        page_ranges: str | None = None,
        enable_table: bool = True,
        is_ocr: bool = False,
        enable_formula: bool = True,
        timeout: int = 300,
        poll_interval: float = 3,
    ) -> MinerUParseResult:
        data: dict[str, Any] = {
            "url": url,
            "model_version": model_version,
            "language": language,
            "enable_table": enable_table,
            "is_ocr": is_ocr,
            "enable_formula": enable_formula,
        }
        if data_id:
            data["data_id"] = data_id
        if page_ranges:
            data["page_ranges"] = page_ranges

        payload = self._json(
            "POST",
            f"{self.base_url}/api/v4/extract/task",
            auth=True,
            json_data=data,
        )
        task_id = payload["data"]["task_id"]
        return self.poll_precision_result(task_id, timeout=timeout, poll_interval=poll_interval)

    def parse_file_precision(
        self,
        file_path: Path,
        *,
        data_id: str | None = None,
        model_version: str = "vlm",
        language: str = "ch",
        page_ranges: str | None = None,
        enable_table: bool = True,
        is_ocr: bool = False,
        enable_formula: bool = True,
        timeout: int = 300,
        poll_interval: float = 3,
    ) -> MinerUParseResult:
        file_spec: dict[str, Any] = {"name": file_path.name}
        if data_id:
            file_spec["data_id"] = data_id
        if is_ocr:
            file_spec["is_ocr"] = is_ocr
        if page_ranges:
            file_spec["page_ranges"] = page_ranges

        data = {
            "files": [file_spec],
            "model_version": model_version,
            "language": language,
            "enable_table": enable_table,
            "enable_formula": enable_formula,
        }
        payload = self._json(
            "POST",
            f"{self.base_url}/api/v4/file-urls/batch",
            auth=True,
            json_data=data,
        )
        batch_id = payload["data"]["batch_id"]
        upload_url = payload["data"]["file_urls"][0]
        upload = self.transport.request("PUT", upload_url, data=file_path.read_bytes())
        if upload.status_code not in {200, 201}:
            return MinerUParseResult(
                state="failed",
                mode="precision-file",
                task_id=batch_id,
                error=f"MinerU signed upload failed with HTTP {upload.status_code}",
            )
        return self.poll_precision_batch_result(
            batch_id,
            data_id=data_id,
            file_name=file_path.name,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def poll_precision_result(
        self,
        task_id: str,
        *,
        timeout: int = 300,
        poll_interval: float = 3,
    ) -> MinerUParseResult:
        deadline = time.monotonic() + timeout
        while True:
            payload = self._json(
                "GET",
                f"{self.base_url}/api/v4/extract/task/{task_id}",
                auth=True,
            )
            data = payload["data"]
            state = data.get("state", "unknown")
            if state == "done":
                full_zip_url = data.get("full_zip_url")
                if not full_zip_url:
                    return MinerUParseResult(
                        state="failed",
                        mode="precision",
                        task_id=task_id,
                        error="MinerU precision result did not include full_zip_url",
                    )
                markdown = read_markdown_from_zip(self._download_bytes(full_zip_url))
                return MinerUParseResult(
                    state="done",
                    mode="precision",
                    task_id=task_id,
                    markdown=markdown,
                    full_zip_url=full_zip_url,
                )
            if state == "failed":
                return MinerUParseResult(
                    state="failed",
                    mode="precision",
                    task_id=task_id,
                    error=data.get("err_msg") or "MinerU precision parsing failed",
                )
            if state not in RUNNING_STATES:
                return MinerUParseResult(
                    state="failed",
                    mode="precision",
                    task_id=task_id,
                    error=f"Unknown MinerU task state: {state}",
                )
            if time.monotonic() >= deadline:
                return MinerUParseResult(
                    state="failed",
                    mode="precision",
                    task_id=task_id,
                    error="MinerU polling timed out",
                )
            self.sleep(poll_interval)

    def poll_precision_batch_result(
        self,
        batch_id: str,
        *,
        data_id: str | None = None,
        file_name: str | None = None,
        timeout: int = 300,
        poll_interval: float = 3,
    ) -> MinerUParseResult:
        deadline = time.monotonic() + timeout
        while True:
            payload = self._json(
                "GET",
                f"{self.base_url}/api/v4/extract-results/batch/{batch_id}",
                auth=True,
            )
            results = payload["data"].get("extract_result") or []
            result = select_batch_result(results, data_id=data_id, file_name=file_name)
            state = result.get("state", "unknown")
            if state == "done":
                full_zip_url = result.get("full_zip_url")
                if not full_zip_url:
                    return MinerUParseResult(
                        state="failed",
                        mode="precision-batch",
                        task_id=batch_id,
                        error="MinerU precision batch result did not include full_zip_url",
                    )
                markdown = read_markdown_from_zip(self._download_bytes(full_zip_url))
                return MinerUParseResult(
                    state="done",
                    mode="precision-batch",
                    task_id=batch_id,
                    markdown=markdown,
                    full_zip_url=full_zip_url,
                )
            if state == "failed":
                return MinerUParseResult(
                    state="failed",
                    mode="precision-batch",
                    task_id=batch_id,
                    error=result.get("err_msg") or "MinerU precision batch parsing failed",
                )
            if state not in RUNNING_STATES:
                return MinerUParseResult(
                    state="failed",
                    mode="precision-batch",
                    task_id=batch_id,
                    error=f"Unknown MinerU batch state: {state}",
                )
            if time.monotonic() >= deadline:
                return MinerUParseResult(
                    state="failed",
                    mode="precision-batch",
                    task_id=batch_id,
                    error="MinerU batch polling timed out",
                )
            self.sleep(poll_interval)


def select_batch_result(
    results: list[dict[str, Any]],
    *,
    data_id: str | None,
    file_name: str | None,
) -> dict[str, Any]:
    if not results:
        return {"state": "pending"}
    for result in results:
        if data_id and result.get("data_id") == data_id:
            return result
        if file_name and result.get("file_name") == file_name:
            return result
    return results[0]


def choose_mineru_mode(requested_mode: str, client: MinerUClient) -> str:
    if requested_mode == "auto":
        return "precision" if client.token else "agent"
    return requested_mode


def parse_with_mineru(
    workspace: Path,
    paper: dict[str, Any],
    *,
    client: MinerUClient,
    mode: str,
    language: str,
    page_range: str | None,
    timeout: int,
    poll_interval: float,
) -> MinerUParseResult:
    chosen_mode = choose_mineru_mode(mode, client)
    local_pdf_path = paper.get("local_pdf_path")
    local_file = workspace / local_pdf_path if local_pdf_path else None
    pdf_url = paper.get("pdf_url")
    data_id = paper["paper_id"]

    if chosen_mode == "precision":
        if is_http_url(pdf_url):
            return client.parse_url_precision(
                pdf_url,
                data_id=data_id,
                language=language,
                page_ranges=page_range,
                timeout=timeout,
                poll_interval=poll_interval,
            )
        if local_file and local_file.exists():
            return client.parse_file_precision(
                local_file,
                data_id=data_id,
                language=language,
                page_ranges=page_range,
                timeout=timeout,
                poll_interval=poll_interval,
            )
    elif chosen_mode == "agent":
        if is_http_url(pdf_url):
            return client.parse_url_agent(
                pdf_url,
                file_name=f"{paper['paper_id']}.pdf",
                language=language,
                page_range=page_range,
                timeout=timeout,
                poll_interval=poll_interval,
            )
        if local_file and local_file.exists():
            return client.parse_file_agent(
                local_file,
                language=language,
                page_range=page_range,
                timeout=timeout,
                poll_interval=poll_interval,
            )
    else:
        return parse_local_pdf(local_file)

    return MinerUParseResult(
        state="skipped",
        mode=chosen_mode,
        error="No local PDF or HTTP PDF URL available for MinerU parsing",
    )


def parse_local_pdf(local_file: Path | None) -> MinerUParseResult:
    if not local_file or not local_file.exists():
        return MinerUParseResult(state="skipped", mode="local", error="No local PDF available")
    text, error = extract_pdf_text(local_file)
    if text.strip():
        return MinerUParseResult(state="done", mode="local", markdown=text)
    return MinerUParseResult(state="skipped", mode="local", error=error or "No PDF text extracted")


def update_rows(
    rows: list[dict[str, Any]],
    updated_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [normalize_paper(updated_by_id.get(row.get("paper_id"), row)) for row in rows]


def parse_selected_pdfs(
    workspace: Path,
    *,
    mode: str = "off",
    language: str = "ch",
    page_range: str | None = None,
    timeout: int = 300,
    poll_interval: float = 3,
    client: MinerUClient | None = None,
) -> list[dict[str, Any]]:
    selected_path = workspace / "data" / "selected_papers.jsonl"
    papers_path = workspace / "data" / "papers.jsonl"
    selected = [normalize_paper(paper) for paper in read_jsonl(selected_path)]
    all_papers = [normalize_paper(paper) for paper in read_jsonl(papers_path)]
    client = client or MinerUClient()
    updated: list[dict[str, Any]] = []
    updated_by_id: dict[str, dict[str, Any]] = {}

    for paper in selected:
        paper_id = paper["paper_id"]
        markdown_path = workspace / "library" / "markdown" / f"{paper_id}.md"
        relative_markdown_path = str(Path("library") / "markdown" / f"{paper_id}.md")

        if markdown_path.exists() and markdown_path.read_text(encoding="utf-8").strip():
            result = MinerUParseResult(
                state="done",
                mode=paper.get("parse_provider") or "cached",
                markdown=markdown_path.read_text(encoding="utf-8"),
            )
        else:
            result = parse_with_mineru(
                workspace,
                paper,
                client=client,
                mode=mode,
                language=language,
                page_range=page_range,
                timeout=timeout,
                poll_interval=poll_interval,
            )

        updates: dict[str, Any] = {
            "parse_provider": result.mode,
            "parse_status": "success" if result.ok else result.state,
            "parse_task_id": result.task_id,
            "parse_markdown_url": result.markdown_url,
            "parse_full_zip_url": result.full_zip_url,
            "parse_error": result.error,
        }
        if result.ok and result.markdown:
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(result.markdown, encoding="utf-8")
            updates["parsed_markdown_path"] = relative_markdown_path

        updated_paper = normalize_paper({**paper, **updates})
        write_parse_metadata(workspace, updated_paper, result)
        append_jsonl(
            workspace / "logs" / "parsing.jsonl",
            {
                "paper_id": paper_id,
                "mode": result.mode,
                "state": result.state,
                "ok": result.ok,
                "error": result.error,
            },
        )
        updated.append(updated_paper)
        updated_by_id[paper_id] = updated_paper

    write_jsonl(selected_path, updated)
    write_jsonl(papers_path, update_rows(all_papers, updated_by_id))
    return updated


def write_parse_metadata(
    workspace: Path,
    paper: dict[str, Any],
    result: MinerUParseResult,
) -> None:
    metadata_path = workspace / "library" / "metadata" / f"{paper['paper_id']}.json"
    existing = read_json(metadata_path, default={}) or {}
    data = {
        **existing,
        **paper,
        "parse_result": {
            "state": result.state,
            "mode": result.mode,
            "task_id": result.task_id,
            "markdown_url": result.markdown_url,
            "full_zip_url": result.full_zip_url,
            "error": result.error,
            "err_code": result.err_code,
        },
    }
    write_json(metadata_path, data)
