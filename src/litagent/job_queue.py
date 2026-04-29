from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from litagent.io import read_jsonl
from litagent.library_db import default_library_db_path, sync_workspace_to_library
from litagent.topic_run import run_topic, safe_error_text

JOB_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def default_jobs_db_path() -> Path:
    return Path.home() / ".autoresearch" / "jobs.db"


def new_job_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"job-{timestamp}-{uuid4().hex[:8]}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_jobs_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              topic TEXT NOT NULL,
              command TEXT NOT NULL,
              status TEXT NOT NULL,
              progress TEXT,
              workspace TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              started_at TEXT,
              finished_at TEXT,
              last_error TEXT,
              cancel_requested INTEGER NOT NULL DEFAULT 0,
              run_state_path TEXT,
              run_log_path TEXT,
              library_db TEXT,
              topic_slug TEXT,
              sync_library INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS job_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id TEXT NOT NULL,
              event TEXT NOT NULL,
              at TEXT NOT NULL,
              payload_json TEXT NOT NULL DEFAULT '{}',
              FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_created
              ON jobs(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_job_events_job
              ON job_events(job_id, id);
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations(version, applied_at)
            VALUES (?, ?)
            """,
            (SCHEMA_VERSION, utc_now()),
        )


def row_to_job(row: sqlite3.Row) -> dict[str, Any]:
    payload = json_loads(str(row["payload_json"]), {})
    return {
        "id": row["id"],
        "topic": row["topic"],
        "command": row["command"],
        "status": row["status"],
        "progress": row["progress"],
        "workspace": row["workspace"],
        "payload": payload,
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "last_error": row["last_error"],
        "cancel_requested": bool(row["cancel_requested"]),
        "run_state_path": row["run_state_path"],
        "run_log_path": row["run_log_path"],
        "library_db": row["library_db"],
        "topic_slug": row["topic_slug"],
        "sync_library": bool(row["sync_library"]),
    }


def add_event(
    conn: sqlite3.Connection,
    job_id: str,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO job_events(job_id, event, at, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, event, utc_now(), json_dumps(payload or {})),
    )


def create_job(
    *,
    jobs_db: Path | None = None,
    topic: str,
    workspace: Path,
    max_papers: int = 30,
    max_results_per_source: int = 50,
    mock: bool = False,
    mineru_mode: str = "off",
    mineru_timeout: int = 300,
    search_run_id: str | None = None,
    search_scope: str = "latest",
    wiki_out: Path | None = None,
    allow_selection_concerns: bool = False,
    sync_library: bool = False,
    library_db: Path | None = None,
    topic_slug: str | None = None,
) -> dict[str, Any]:
    jobs_db = jobs_db or default_jobs_db_path()
    init_jobs_db(jobs_db)
    job_id = new_job_id()
    now = utc_now()
    payload = {
        "topic": topic,
        "workspace": str(workspace),
        "max_papers": max_papers,
        "max_results_per_source": max_results_per_source,
        "mock": mock,
        "mineru_mode": mineru_mode,
        "mineru_timeout": mineru_timeout,
        "search_run_id": search_run_id,
        "search_scope": search_scope,
        "wiki_out": str(wiki_out) if wiki_out else None,
        "allow_selection_concerns": allow_selection_concerns,
        "sync_library": sync_library,
        "library_db": str(library_db or default_library_db_path()),
        "topic_slug": topic_slug,
    }
    with connect(jobs_db) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
              id, topic, command, status, progress, workspace, payload_json,
              created_at, library_db, topic_slug, sync_library
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                topic,
                "topic-run",
                "queued",
                "queued",
                str(workspace),
                json_dumps(payload),
                now,
                str(library_db or default_library_db_path()),
                topic_slug,
                1 if sync_library else 0,
            ),
        )
        add_event(conn, job_id, "job_created", {"workspace": str(workspace), "mock": mock})
        job = get_job(job_id, jobs_db=jobs_db, conn=conn)
    return {"ok": True, "jobs_db": str(jobs_db), "job": job}


def get_job(
    job_id: str,
    *,
    jobs_db: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    owns_conn = conn is None
    jobs_db = jobs_db or default_jobs_db_path()
    if conn is None:
        init_jobs_db(jobs_db)
        conn = connect(jobs_db)
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            msg = f"Unknown job id: {job_id}"
            raise KeyError(msg)
        return row_to_job(row)
    finally:
        if owns_conn:
            conn.close()


def list_jobs(
    *,
    jobs_db: Path | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    jobs_db = jobs_db or default_jobs_db_path()
    init_jobs_db(jobs_db)
    with connect(jobs_db) as conn:
        if status:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return {"ok": True, "jobs_db": str(jobs_db), "jobs": [row_to_job(row) for row in rows]}


def cancel_job(job_id: str, *, jobs_db: Path | None = None) -> dict[str, Any]:
    jobs_db = jobs_db or default_jobs_db_path()
    init_jobs_db(jobs_db)
    with connect(jobs_db) as conn:
        job = get_job(job_id, conn=conn)
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            add_event(conn, job_id, "cancel_ignored", {"status": job["status"]})
            return {"ok": True, "jobs_db": str(jobs_db), "job": job, "changed": False}
        now = utc_now()
        if job["status"] == "queued":
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, progress = ?, finished_at = ?, cancel_requested = 1
                WHERE id = ?
                """,
                ("cancelled", "cancelled before run", now, job_id),
            )
            add_event(conn, job_id, "job_cancelled", {"mode": "queued"})
        else:
            conn.execute(
                """
                UPDATE jobs
                SET cancel_requested = 1, progress = ?
                WHERE id = ?
                """,
                ("cancel requested; running process cannot be killed by SQLite queue", job_id),
            )
            add_event(conn, job_id, "cancel_requested", {"mode": "running"})
        updated = get_job(job_id, conn=conn)
    return {"ok": True, "jobs_db": str(jobs_db), "job": updated, "changed": True}


def next_queued_job(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM jobs
        WHERE status = 'queued'
        ORDER BY created_at ASC
        LIMIT 1
        """
    ).fetchone()
    return row_to_job(row) if row else None


def update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    status: str,
    progress: str,
    last_error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    run_state_path: str | None = None,
    run_log_path: str | None = None,
) -> None:
    if status not in JOB_STATUSES:
        msg = f"Invalid job status: {status}"
        raise ValueError(msg)
    conn.execute(
        """
        UPDATE jobs
        SET status = ?,
            progress = ?,
            last_error = ?,
            started_at = COALESCE(?, started_at),
            finished_at = COALESCE(?, finished_at),
            run_state_path = COALESCE(?, run_state_path),
            run_log_path = COALESCE(?, run_log_path)
        WHERE id = ?
        """,
        (
            status,
            progress,
            last_error,
            started_at,
            finished_at,
            run_state_path,
            run_log_path,
            job_id,
        ),
    )


def run_next_job(*, jobs_db: Path | None = None) -> dict[str, Any]:
    jobs_db = jobs_db or default_jobs_db_path()
    init_jobs_db(jobs_db)
    with connect(jobs_db) as conn:
        job = next_queued_job(conn)
        if job is None:
            return {"ok": True, "jobs_db": str(jobs_db), "job": None, "message": "no queued jobs"}
        now = utc_now()
        update_job_status(
            conn,
            job["id"],
            status="running",
            progress="topic-run started",
            started_at=now,
        )
        add_event(conn, job["id"], "job_started", {"command": job["command"]})

    payload = job["payload"]
    workspace = Path(str(payload["workspace"]))
    try:
        run_result = run_topic(
            str(payload["topic"]),
            workspace,
            max_papers=int(payload.get("max_papers") or 30),
            max_results_per_source=int(payload.get("max_results_per_source") or 50),
            mock=bool(payload.get("mock")),
            mineru_mode=str(payload.get("mineru_mode") or "off"),
            mineru_timeout=int(payload.get("mineru_timeout") or 300),
            search_run_id=payload.get("search_run_id"),
            search_scope=str(payload.get("search_scope") or "latest"),
            wiki_out=Path(str(payload["wiki_out"])) if payload.get("wiki_out") else None,
            resume=True,
            force=False,
            allow_selection_concerns=bool(payload.get("allow_selection_concerns")),
        )
        sync_result = None
        if payload.get("sync_library"):
            sync_result = sync_workspace_to_library(
                workspace,
                db_path=Path(str(payload.get("library_db") or default_library_db_path())),
                topic_slug=payload.get("topic_slug"),
            )
        with connect(jobs_db) as conn:
            update_job_status(
                conn,
                job["id"],
                status="succeeded",
                progress="succeeded",
                finished_at=utc_now(),
                run_state_path=str(workspace / "run_state.json"),
                run_log_path=str(workspace / "run_log.jsonl"),
            )
            add_event(
                conn,
                job["id"],
                "job_succeeded",
                {
                    "workspace": str(workspace),
                    "sync_library": bool(sync_result),
                    "quality_label": (
                        (((run_result.get("state") or {}).get("steps") or {})
                        .get("inspect-workspace")
                        or {})
                        .get("details", {})
                        .get("quality_label")
                    ),
                },
            )
            updated = get_job(job["id"], conn=conn)
        return {
            "ok": True,
            "jobs_db": str(jobs_db),
            "job": updated,
            "run_result": {
                "state_status": (run_result.get("state") or {}).get("status"),
                "manifest_missing": (run_result.get("manifest") or {}).get("missing", []),
            },
            "sync_result": sync_result,
        }
    except Exception as exc:  # noqa: BLE001 - queue must persist recoverable job failure
        error_text = safe_error_text(exc)
        with connect(jobs_db) as conn:
            update_job_status(
                conn,
                job["id"],
                status="failed",
                progress="failed",
                last_error=error_text,
                finished_at=utc_now(),
                run_state_path=str(workspace / "run_state.json"),
                run_log_path=str(workspace / "run_log.jsonl"),
            )
            add_event(conn, job["id"], "job_failed", {"error": error_text})
            updated = get_job(job["id"], conn=conn)
        return {"ok": False, "jobs_db": str(jobs_db), "job": updated, "error": error_text}


def job_logs(job_id: str, *, jobs_db: Path | None = None) -> dict[str, Any]:
    jobs_db = jobs_db or default_jobs_db_path()
    init_jobs_db(jobs_db)
    with connect(jobs_db) as conn:
        job = get_job(job_id, conn=conn)
        rows = conn.execute(
            """
            SELECT event, at, payload_json
            FROM job_events
            WHERE job_id = ?
            ORDER BY id ASC
            """,
            (job_id,),
        ).fetchall()
    events = [
        {
            "event": row["event"],
            "at": row["at"],
            "payload": json_loads(str(row["payload_json"]), {}),
        }
        for row in rows
    ]
    run_log_path = Path(str(job["run_log_path"] or Path(job["workspace"]) / "run_log.jsonl"))
    run_log = read_jsonl(run_log_path) if run_log_path.exists() else []
    return {
        "ok": True,
        "jobs_db": str(jobs_db),
        "job": job,
        "events": events,
        "run_log": run_log,
    }
