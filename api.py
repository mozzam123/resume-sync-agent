"""FastAPI routes for resume upload and sync tracking."""

from __future__ import annotations

import os
import shutil
import webbrowser
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

import storage
from adapters import ADAPTERS, get_adapter
from db import (
    add_resume,
    add_sync_record,
    connect,
    get_resume,
    list_resumes,
    list_sync_records,
    list_sync_records_for_resume,
    mark_complete,
)

router = APIRouter()


class SyncRequest(BaseModel):
    resume_id: int
    platforms: list[str]


# --- DB dependency: one sqlite connection per request -----------------------


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


# --- Routes -----------------------------------------------------------------


@router.get("/platforms")
def list_platforms():
    """Available platforms and their (manual) upload page URLs."""
    return [
        {"name": name, "upload_page_url": adapter.upload_page_url}
        for name, adapter in sorted(ADAPTERS.items())
    ]


def _save_upload(file: UploadFile) -> tuple[str, int, str]:
    """Persist an upload to local storage. Returns (stored_path, size, content_type)."""
    storage.ensure_dirs()
    tmp = Path(storage.RESUMES_DIR) / f".tmp_{os.getpid()}_{file.filename}"
    try:
        with tmp.open("wb") as dst:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
        stored_path, size_bytes = storage.store_resume(tmp, file.filename)
    finally:
        if tmp.exists():
            tmp.unlink()
    return str(stored_path), size_bytes, file.content_type or ""


@router.post("/resumes")
async def upload_resume(file: UploadFile = File(...)):
    """Store an uploaded resume locally and track it in SQLite."""
    stored_path, size_bytes, content_type = _save_upload(file)
    conn = connect()
    try:
        resume_id = add_resume(
            conn,
            filename=file.filename,
            stored_path=stored_path,
            content_type=content_type,
            size_bytes=size_bytes,
        )
        row = get_resume(conn, resume_id)
    finally:
        conn.close()
    return dict(row)


@router.get("/resumes")
def list_resumes_route():
    conn = connect()
    try:
        rows = list_resumes(conn)
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/resumes/{resume_id}")
def get_resume_route(resume_id: int):
    conn = connect()
    try:
        row = get_resume(conn, resume_id)
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="resume not found")
    return dict(row)


@router.get("/resumes/{resume_id}/file")
def serve_resume_file(resume_id: int):
    conn = connect()
    try:
        row = get_resume(conn, resume_id)
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="resume not found")
    path = Path(row["stored_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="stored resume missing")
    return FileResponse(path, filename=row["filename"])


@router.post("/sync")
def sync_resume(req: SyncRequest):
    """Trigger sync of a resume across the selected platforms."""
    conn = connect()
    try:
        resume = get_resume(conn, req.resume_id)
    finally:
        conn.close()
    if resume is None:
        raise HTTPException(status_code=404, detail="resume not found")

    results = []
    conn = connect()
    try:
        for platform in req.platforms:
            adapter = get_adapter(platform)
            if adapter is None:
                from adapters.base import SyncResult

                result = SyncResult(
                    platform=platform,
                    status="failed",
                    message=f"Unknown platform: {platform}",
                )
            else:
                result = adapter.upload(resume["stored_path"], {})
            record_id = add_sync_record(
                conn,
                resume_id=req.resume_id,
                platform=result.platform,
                status=result.status,
                message=result.message,
                manual_url=result.manual_url,
            )
            results.append(
                {
                    "platform": result.platform,
                    "status": result.status,
                    "message": result.message,
                    "manual_url": result.manual_url,
                    "record_id": record_id,
                }
            )
    finally:
        conn.close()
    return results


@router.get("/sync/history")
def sync_history():
    conn = connect()
    try:
        rows = list_sync_records(conn)
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/sync/history/{resume_id}")
def sync_history_for_resume(resume_id: int):
    conn = connect()
    try:
        rows = list_sync_records_for_resume(conn, resume_id)
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.post("/sync/{record_id}/complete")
def complete_manual_sync(record_id: int):
    conn = connect()
    try:
        ok = mark_complete(conn, record_id)
    finally:
        conn.close()
    if not ok:
        raise HTTPException(status_code=404, detail="manual sync record not found")
    return {"ok": True}


@router.post("/sync/{record_id}/open")
def open_upload_page(record_id: int):
    """Open the platform's upload page in the user's default browser."""
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT manual_url, platform FROM sync_records WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or not row["manual_url"]:
        raise HTTPException(status_code=404, detail="no upload page for this record")
    webbrowser.open(row["manual_url"])
    return {"ok": True, "url": row["manual_url"]}
