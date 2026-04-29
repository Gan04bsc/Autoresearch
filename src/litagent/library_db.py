from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from litagent.io import read_json, read_jsonl
from litagent.paper_roles import enrich_paper_role
from litagent.schema import normalize_paper, safe_slug

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def default_library_db_path() -> Path:
    return Path.home() / ".autoresearch" / "library.db"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def topic_slug_from_name(name: str) -> str:
    slug = safe_slug(name, max_length=72)
    if slug and slug != "paper":
        return slug
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"topic-{digest}"


def stable_evidence_id(item: dict[str, Any], topic_id: str) -> str:
    key = "|".join(
        [
            topic_id,
            str(item.get("paper_id") or ""),
            str(item.get("theme") or ""),
            str(item.get("claim") or ""),
            str(item.get("section") or ""),
            str(item.get("snippet") or ""),
        ]
    )
    return "ev-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_library_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS papers (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              authors_json TEXT NOT NULL DEFAULT '[]',
              year INTEGER,
              venue TEXT,
              abstract TEXT,
              doi TEXT,
              arxiv_id TEXT,
              semantic_scholar_id TEXT,
              openalex_id TEXT,
              url TEXT,
              pdf_url TEXT,
              pdf_path TEXT,
              markdown_path TEXT,
              source_json TEXT NOT NULL DEFAULT '[]',
              citation_count INTEGER NOT NULL DEFAULT 0,
              reference_count INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
            CREATE INDEX IF NOT EXISTS idx_papers_arxiv ON papers(arxiv_id);
            CREATE INDEX IF NOT EXISTS idx_papers_semantic
              ON papers(semantic_scholar_id);
            CREATE INDEX IF NOT EXISTS idx_papers_openalex ON papers(openalex_id);

            CREATE TABLE IF NOT EXISTS topics (
              id TEXT PRIMARY KEY,
              slug TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              workspace TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topic_papers (
              topic_id TEXT NOT NULL,
              paper_id TEXT NOT NULL,
              role TEXT,
              reading_intent_json TEXT NOT NULL DEFAULT '[]',
              relevance_score REAL NOT NULL DEFAULT 0,
              final_score REAL NOT NULL DEFAULT 0,
              selection_reason TEXT,
              reading_status TEXT NOT NULL DEFAULT 'selected',
              added_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (topic_id, paper_id),
              FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
              FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              topic_id TEXT NOT NULL,
              workspace TEXT NOT NULL,
              status TEXT,
              query TEXT,
              search_run_id TEXT,
              raw_results INTEGER NOT NULL DEFAULT 0,
              selected_count INTEGER NOT NULL DEFAULT 0,
              quality_label TEXT,
              started_at TEXT,
              finished_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS evidence_spans (
              id TEXT PRIMARY KEY,
              paper_id TEXT NOT NULL,
              topic_id TEXT NOT NULL,
              claim TEXT,
              section TEXT,
              snippet TEXT NOT NULL,
              confidence REAL,
              uncertainty TEXT,
              snippet_score REAL,
              quality_flags_json TEXT NOT NULL DEFAULT '[]',
              theme TEXT,
              source_workspace TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
              FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_topic_papers_topic
              ON topic_papers(topic_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_topic
              ON evidence_spans(topic_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_paper
              ON evidence_spans(paper_id);
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations(version, applied_at)
            VALUES (?, ?)
            """,
            (SCHEMA_VERSION, utc_now()),
        )


def score_reason(paper: dict[str, Any]) -> str:
    if paper.get("curation_reason"):
        return str(paper.get("curation_reason"))
    explanation = paper.get("score_explanation")
    if isinstance(explanation, dict):
        matched = explanation.get("matched_terms") or {}
        if isinstance(matched, dict):
            terms = [
                *(matched.get("high_value_title") or []),
                *(matched.get("high_value_abstract") or []),
                *(matched.get("include_title") or []),
                *(matched.get("include_abstract") or []),
            ]
            if terms:
                return "matched terms: " + ", ".join(str(term) for term in terms[:8])
    return "selected by litagent ranking"


def read_evidence_items(workspace: Path) -> list[dict[str, Any]]:
    evidence = read_json(workspace / "knowledge" / "evidence_table.json", default={}) or {}
    rows: list[dict[str, Any]] = []
    for theme in evidence.get("themes") or []:
        theme_name = str(theme.get("theme") or "unknown")
        for item in theme.get("evidence_snippets_or_sections") or []:
            if not item.get("paper_id") or not item.get("snippet"):
                continue
            rows.append({**item, "theme": theme_name})
    return rows


def latest_search_run_id(workspace: Path) -> str | None:
    latest = read_json(workspace / "data" / "search_runs" / "latest.json", default={}) or {}
    if latest.get("run_id"):
        return str(latest["run_id"])
    return None


def run_record_id(workspace: Path, topic_id: str, search_run_id: str | None) -> str:
    if search_run_id:
        return f"{topic_id}:{search_run_id}"
    digest = hashlib.sha1(str(workspace).encode("utf-8")).hexdigest()[:10]
    return f"{topic_id}:workspace-{digest}"


def upsert_paper(
    conn: sqlite3.Connection,
    paper: dict[str, Any],
    *,
    workspace: Path,
    now: str,
) -> None:
    normalized = normalize_paper(paper)
    existing = conn.execute("SELECT created_at FROM papers WHERE id = ?", (normalized["paper_id"],))
    row = existing.fetchone()
    created_at = str(row["created_at"]) if row else now
    conn.execute(
        """
        INSERT INTO papers (
          id, title, authors_json, year, venue, abstract, doi, arxiv_id,
          semantic_scholar_id, openalex_id, url, pdf_url, pdf_path, markdown_path,
          source_json, citation_count, reference_count, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          title=excluded.title,
          authors_json=excluded.authors_json,
          year=excluded.year,
          venue=excluded.venue,
          abstract=excluded.abstract,
          doi=excluded.doi,
          arxiv_id=excluded.arxiv_id,
          semantic_scholar_id=excluded.semantic_scholar_id,
          openalex_id=excluded.openalex_id,
          url=excluded.url,
          pdf_url=excluded.pdf_url,
          pdf_path=excluded.pdf_path,
          markdown_path=excluded.markdown_path,
          source_json=excluded.source_json,
          citation_count=excluded.citation_count,
          reference_count=excluded.reference_count,
          updated_at=excluded.updated_at
        """,
        (
            normalized["paper_id"],
            normalized.get("title") or "",
            json_dumps(normalized.get("authors") or []),
            normalized.get("year"),
            normalized.get("venue") or "",
            normalized.get("abstract") or "",
            normalized.get("doi"),
            normalized.get("arxiv_id"),
            normalized.get("semantic_scholar_id"),
            normalized.get("openalex_id"),
            normalized.get("url"),
            normalized.get("pdf_url"),
            str(workspace / str(normalized["local_pdf_path"]))
            if normalized.get("local_pdf_path")
            else None,
            str(workspace / str(normalized["parsed_markdown_path"]))
            if normalized.get("parsed_markdown_path")
            else None,
            json_dumps(normalized.get("source") or []),
            int(normalized.get("citation_count") or 0),
            int(normalized.get("reference_count") or 0),
            created_at,
            now,
        ),
    )


def upsert_topic(
    conn: sqlite3.Connection,
    *,
    topic_id: str,
    topic_name: str,
    workspace: Path,
    now: str,
) -> None:
    existing = conn.execute("SELECT created_at FROM topics WHERE id = ?", (topic_id,))
    row = existing.fetchone()
    created_at = str(row["created_at"]) if row else now
    conn.execute(
        """
        INSERT INTO topics(id, slug, name, workspace, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          name=excluded.name,
          workspace=excluded.workspace,
          updated_at=excluded.updated_at
        """,
        (topic_id, topic_id, topic_name, str(workspace), created_at, now),
    )


def upsert_topic_paper(
    conn: sqlite3.Connection,
    paper: dict[str, Any],
    *,
    topic_id: str,
    now: str,
) -> None:
    enriched = enrich_paper_role(paper)
    existing = conn.execute(
        "SELECT added_at FROM topic_papers WHERE topic_id = ? AND paper_id = ?",
        (topic_id, enriched["paper_id"]),
    )
    row = existing.fetchone()
    added_at = str(row["added_at"]) if row else now
    conn.execute(
        """
        INSERT INTO topic_papers (
          topic_id, paper_id, role, reading_intent_json, relevance_score,
          final_score, selection_reason, reading_status, added_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(topic_id, paper_id) DO UPDATE SET
          role=excluded.role,
          reading_intent_json=excluded.reading_intent_json,
          relevance_score=excluded.relevance_score,
          final_score=excluded.final_score,
          selection_reason=excluded.selection_reason,
          reading_status=excluded.reading_status,
          updated_at=excluded.updated_at
        """,
        (
            topic_id,
            enriched["paper_id"],
            enriched.get("paper_role"),
            json_dumps(enriched.get("reading_intent") or []),
            float(enriched.get("relevance_score") or 0.0),
            float(enriched.get("final_score") or 0.0),
            score_reason(enriched),
            "selected",
            added_at,
            now,
        ),
    )


def upsert_run(
    conn: sqlite3.Connection,
    *,
    workspace: Path,
    topic_id: str,
    topic_name: str,
    selected_count: int,
    now: str,
) -> str:
    run_state = read_json(workspace / "run_state.json", default={}) or {}
    inspect_result = read_json(workspace / "logs" / "inspect_workspace.json", default={}) or {}
    raw_count = len(read_jsonl(workspace / "data" / "raw_results.jsonl"))
    search_run_id = latest_search_run_id(workspace)
    run_id = str(run_state.get("run_id") or run_record_id(workspace, topic_id, search_run_id))
    existing = conn.execute("SELECT created_at FROM runs WHERE id = ?", (run_id,))
    row = existing.fetchone()
    created_at = str(row["created_at"]) if row else now
    conn.execute(
        """
        INSERT INTO runs (
          id, topic_id, workspace, status, query, search_run_id, raw_results,
          selected_count, quality_label, started_at, finished_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          workspace=excluded.workspace,
          status=excluded.status,
          query=excluded.query,
          search_run_id=excluded.search_run_id,
          raw_results=excluded.raw_results,
          selected_count=excluded.selected_count,
          quality_label=excluded.quality_label,
          started_at=excluded.started_at,
          finished_at=excluded.finished_at,
          updated_at=excluded.updated_at
        """,
        (
            run_id,
            topic_id,
            str(workspace),
            str(run_state.get("status") or "synced"),
            topic_name,
            search_run_id,
            raw_count,
            selected_count,
            inspect_result.get("quality_label") or inspect_result.get("quality_level"),
            run_state.get("started_at"),
            run_state.get("finished_at"),
            created_at,
            now,
        ),
    )
    return run_id


def upsert_evidence(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    *,
    topic_id: str,
    workspace: Path,
    now: str,
) -> None:
    evidence_id = stable_evidence_id(item, topic_id)
    existing = conn.execute("SELECT created_at FROM evidence_spans WHERE id = ?", (evidence_id,))
    row = existing.fetchone()
    created_at = str(row["created_at"]) if row else now
    conn.execute(
        """
        INSERT INTO evidence_spans (
          id, paper_id, topic_id, claim, section, snippet, confidence, uncertainty,
          snippet_score, quality_flags_json, theme, source_workspace, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          claim=excluded.claim,
          section=excluded.section,
          snippet=excluded.snippet,
          confidence=excluded.confidence,
          uncertainty=excluded.uncertainty,
          snippet_score=excluded.snippet_score,
          quality_flags_json=excluded.quality_flags_json,
          theme=excluded.theme,
          source_workspace=excluded.source_workspace,
          updated_at=excluded.updated_at
        """,
        (
            evidence_id,
            str(item.get("paper_id")),
            topic_id,
            str(item.get("claim") or item.get("theme") or ""),
            str(item.get("section") or "Unknown"),
            str(item.get("snippet") or ""),
            safe_float(item.get("confidence")),
            str(item.get("uncertainty_or_gap") or item.get("uncertainty") or ""),
            safe_float(item.get("snippet_score")),
            json_dumps(item.get("quality_flags") or []),
            str(item.get("theme") or "unknown"),
            str(workspace),
            created_at,
            now,
        ),
    )


def sync_workspace_to_library(
    workspace: Path,
    *,
    db_path: Path | None = None,
    topic_slug: str | None = None,
) -> dict[str, Any]:
    db_path = db_path or default_library_db_path()
    init_library_db(db_path)
    plan = read_json(workspace / "research_plan.json", default={}) or {}
    topic_name = str(plan.get("topic") or workspace.name)
    topic_id = topic_slug or topic_slug_from_name(topic_name)
    selected = [enrich_paper_role(normalize_paper(paper)) for paper in read_jsonl(
        workspace / "data" / "selected_papers.jsonl"
    )]
    evidence_items = read_evidence_items(workspace)
    now = utc_now()

    with connect(db_path) as conn:
        upsert_topic(conn, topic_id=topic_id, topic_name=topic_name, workspace=workspace, now=now)
        for paper in selected:
            upsert_paper(conn, paper, workspace=workspace, now=now)
            upsert_topic_paper(conn, paper, topic_id=topic_id, now=now)
        evidence_written = 0
        selected_ids = {paper["paper_id"] for paper in selected}
        for item in evidence_items:
            if str(item.get("paper_id")) not in selected_ids:
                continue
            upsert_evidence(conn, item, topic_id=topic_id, workspace=workspace, now=now)
            evidence_written += 1
        run_id = upsert_run(
            conn,
            workspace=workspace,
            topic_id=topic_id,
            topic_name=topic_name,
            selected_count=len(selected),
            now=now,
        )
        totals = library_counts(conn)

    return {
        "ok": True,
        "library_db": str(db_path),
        "workspace": str(workspace),
        "topic_id": topic_id,
        "topic": topic_name,
        "run_id": run_id,
        "papers_synced": len(selected),
        "topic_papers_synced": len(selected),
        "evidence_spans_synced": evidence_written,
        "totals": totals,
    }


def library_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("papers", "topics", "topic_papers", "runs", "evidence_spans"):
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        counts[table] = int(row["count"])
    return counts


def inspect_library(db_path: Path) -> dict[str, Any]:
    init_library_db(db_path)
    with connect(db_path) as conn:
        topics = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                  topics.id,
                  topics.name,
                  topics.workspace,
                  COUNT(DISTINCT topic_papers.paper_id) AS paper_count,
                  COUNT(DISTINCT evidence_spans.id) AS evidence_count
                FROM topics
                LEFT JOIN topic_papers ON topic_papers.topic_id = topics.id
                LEFT JOIN evidence_spans ON evidence_spans.topic_id = topics.id
                GROUP BY topics.id
                ORDER BY topics.updated_at DESC
                """
            )
        ]
        return {
            "ok": True,
            "library_db": str(db_path),
            "schema_version": SCHEMA_VERSION,
            "counts": library_counts(conn),
            "topics": topics,
        }
