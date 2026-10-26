"""Local storage for uploaded resumes."""

from __future__ import annotations

import shutil
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RESUMES_DIR = DATA_DIR / "resumes"


def ensure_dirs() -> None:
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)


def store_resume(source: Path, filename: str) -> tuple[Path, int]:
    """Copy an uploaded resume into local storage. Returns (stored_path, size_bytes)."""
    ensure_dirs()
    destination = RESUMES_DIR / filename
    # Avoid clobbering an existing file with the same name.
    if destination.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        destination = RESUMES_DIR / f"{stem}_{destination.stat().st_mtime_ns}{suffix}"
    shutil.copyfile(source, destination)
    return destination, destination.stat().st_size
