from __future__ import annotations

import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from litagent.io import append_jsonl, read_jsonl, write_jsonl
from litagent.schema import normalize_paper


def build_minimal_mock_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 20 100 Td ({escaped}) Tj ET\n".encode()
    stream_object = (
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\n"
        b"stream\n" + stream + b"endstream"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        stream_object,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    content = b"%PDF-1.4\n"
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

    xref_offset = len(content)
    content += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    content += b"0000000000 65535 f \n"
    for offset in offsets:
        content += f"{offset:010d} 00000 n \n".encode("ascii")
    content += (
        f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return content


MINIMAL_MOCK_PDF = build_minimal_mock_pdf("litagent mock open access PDF")


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "litagent/0.1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def resolve_unpaywall_pdf_url(doi: str) -> tuple[str | None, str | None]:
    email = os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("LITAGENT_CONTACT_EMAIL")
    if not email:
        return None, "UNPAYWALL_EMAIL or LITAGENT_CONTACT_EMAIL is required for DOI OA lookup"
    params = urllib.parse.urlencode({"email": email})
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?{params}"
    try:
        import json

        data = json.loads(fetch_bytes(url).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, f"Unpaywall lookup failed: {exc}"

    best_location = data.get("best_oa_location") or {}
    pdf_url = best_location.get("url_for_pdf")
    if pdf_url:
        return pdf_url, None
    return None, "Unpaywall did not return an open PDF URL"


def candidate_pdf_url(paper: dict[str, Any]) -> tuple[str | None, str | None]:
    if paper.get("pdf_url"):
        return str(paper["pdf_url"]), None
    if paper.get("arxiv_id"):
        return f"https://arxiv.org/pdf/{paper['arxiv_id']}.pdf", None
    if paper.get("doi"):
        return resolve_unpaywall_pdf_url(str(paper["doi"]))
    return None, "No open PDF URL available"


def write_pdf(path: Path, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("mock://pdf/"):
        path.write_bytes(MINIMAL_MOCK_PDF)
        return

    content = fetch_bytes(url)
    if not content.startswith(b"%PDF"):
        msg = "Downloaded content is not a valid PDF"
        raise ValueError(msg)
    path.write_bytes(content)


def update_rows_with_download(
    rows: list[dict[str, Any]], paper_id: str, updates: dict[str, Any]
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for row in rows:
        if row.get("paper_id") == paper_id:
            updated.append(normalize_paper({**row, **updates}))
        else:
            updated.append(normalize_paper(row))
    return updated


def download_pdfs(workspace: Path) -> list[dict[str, Any]]:
    selected_path = workspace / "data" / "selected_papers.jsonl"
    papers_path = workspace / "data" / "papers.jsonl"
    selected = [normalize_paper(paper) for paper in read_jsonl(selected_path)]
    all_papers = [normalize_paper(paper) for paper in read_jsonl(papers_path)]
    results: list[dict[str, Any]] = []

    for paper in selected:
        paper_id = paper["paper_id"]
        local_path = workspace / "library" / "pdfs" / f"{paper_id}.pdf"
        relative_path = str(Path("library") / "pdfs" / f"{paper_id}.pdf")

        existing_pdf_url = paper.get("pdf_url")
        is_mock_pdf = bool(
            existing_pdf_url and str(existing_pdf_url).startswith("mock://pdf/")
        )

        if local_path.exists() and local_path.read_bytes().startswith(b"%PDF") and not is_mock_pdf:
            status = {
                "local_pdf_path": relative_path,
                "download_status": "success",
                "download_error": None,
            }
            paper.update(status)
            append_jsonl(workspace / "logs" / "downloads.jsonl", {"paper_id": paper_id, **status})
            results.append(paper)
            continue

        pdf_url, error = candidate_pdf_url(paper)
        if not pdf_url:
            status = {"local_pdf_path": None, "download_status": "skipped", "download_error": error}
        else:
            try:
                write_pdf(local_path, pdf_url)
                status = {
                    "pdf_url": pdf_url,
                    "local_pdf_path": relative_path,
                    "download_status": "success",
                    "download_error": None,
                }
            except Exception as exc:  # noqa: BLE001
                status = {
                    "pdf_url": pdf_url,
                    "local_pdf_path": None,
                    "download_status": "failed",
                    "download_error": str(exc),
                }
        paper.update(status)
        append_jsonl(workspace / "logs" / "downloads.jsonl", {"paper_id": paper_id, **status})
        results.append(normalize_paper(paper))

    write_jsonl(selected_path, results)
    for paper in results:
        all_papers = update_rows_with_download(all_papers, paper["paper_id"], paper)
    write_jsonl(papers_path, all_papers)
    return results
