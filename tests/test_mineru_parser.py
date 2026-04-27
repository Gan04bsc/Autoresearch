from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from litagent.io import read_json, read_jsonl, write_jsonl
from litagent.mineru import HttpResponse, MinerUClient, parse_selected_pdfs


class FakeMinerUTransport:
    def __init__(self, *, mode: str) -> None:
        self.mode = mode
        self.requests: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        data: bytes | None = None,
    ) -> HttpResponse:
        self.requests.append((method, url, json_data))
        if self.mode == "agent":
            return self._agent_response(method, url)
        return self._precision_response(method, url)

    def _agent_response(self, method: str, url: str) -> HttpResponse:
        if method == "POST" and url.endswith("/api/v1/agent/parse/url"):
            return json_response({"code": 0, "msg": "ok", "data": {"task_id": "agent-task"}})
        if method == "GET" and url.endswith("/api/v1/agent/parse/agent-task"):
            return json_response(
                {
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "task_id": "agent-task",
                        "state": "done",
                        "markdown_url": "https://cdn.example/full.md",
                    },
                }
            )
        if method == "GET" and url == "https://cdn.example/full.md":
            return HttpResponse(200, b"# Parsed by MinerU Agent\n\nbody")
        raise AssertionError(f"unexpected agent request: {method} {url}")

    def _precision_response(self, method: str, url: str) -> HttpResponse:
        if method == "POST" and url.endswith("/api/v4/extract/task"):
            return json_response({"code": 0, "msg": "ok", "data": {"task_id": "precision-task"}})
        if method == "GET" and url.endswith("/api/v4/extract/task/precision-task"):
            return json_response(
                {
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "task_id": "precision-task",
                        "state": "done",
                        "full_zip_url": "https://cdn.example/result.zip",
                    },
                }
            )
        if method == "GET" and url == "https://cdn.example/result.zip":
            return HttpResponse(200, zip_bytes({"full.md": "# Parsed by MinerU Precision\n\nbody"}))
        raise AssertionError(f"unexpected precision request: {method} {url}")


def json_response(data: dict[str, Any]) -> HttpResponse:
    import json

    return HttpResponse(200, json.dumps(data).encode("utf-8"))


def zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def workspace_path(name: str) -> Path:
    path = Path(".tmp") / "tests" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_agent_url_parse_downloads_markdown() -> None:
    client = MinerUClient(transport=FakeMinerUTransport(mode="agent"), sleep=lambda _: None)

    result = client.parse_url_agent(
        "https://example.org/paper.pdf",
        timeout=1,
        poll_interval=0,
    )

    assert result.ok
    assert result.task_id == "agent-task"
    assert result.markdown == "# Parsed by MinerU Agent\n\nbody"


def test_precision_url_parse_downloads_full_zip_markdown() -> None:
    client = MinerUClient(
        token="test-token",
        transport=FakeMinerUTransport(mode="precision"),
        sleep=lambda _: None,
    )

    result = client.parse_url_precision(
        "https://example.org/paper.pdf",
        timeout=1,
        poll_interval=0,
    )

    assert result.ok
    assert result.task_id == "precision-task"
    assert result.markdown == "# Parsed by MinerU Precision\n\nbody"


def test_parse_selected_pdfs_writes_markdown_and_metadata() -> None:
    workspace = workspace_path("mineru")
    paper = {
        "paper_id": "p-123456789abc",
        "title": "MinerU Integration Paper",
        "authors": ["A"],
        "year": 2025,
        "abstract": "A test abstract.",
        "pdf_url": "https://example.org/paper.pdf",
        "source": ["arxiv"],
    }
    write_jsonl(workspace / "data" / "selected_papers.jsonl", [paper])
    write_jsonl(workspace / "data" / "papers.jsonl", [paper])
    client = MinerUClient(transport=FakeMinerUTransport(mode="agent"), sleep=lambda _: None)

    rows = parse_selected_pdfs(
        workspace,
        mode="agent",
        timeout=1,
        poll_interval=0,
        client=client,
    )

    assert rows[0]["parse_status"] == "success"
    assert rows[0]["parsed_markdown_path"] == "library/markdown/p-123456789abc.md"
    markdown = (workspace / "library" / "markdown" / "p-123456789abc.md").read_text(
        encoding="utf-8"
    )
    assert markdown.startswith("# Parsed by MinerU Agent")
    metadata = read_json(workspace / "library" / "metadata" / "p-123456789abc.json")
    assert metadata["parse_result"]["task_id"] == "agent-task"
    selected = read_jsonl(workspace / "data" / "selected_papers.jsonl")
    assert selected[0]["parse_provider"] == "agent"

