"""Naukri adapter (browser-assisted, compliant)."""

from __future__ import annotations

from .base import PlatformAdapter, SyncResult


class NaukriAdapter(PlatformAdapter):
    name = "naukri"
    upload_page_url = "https://www.naukri.com/mnjuser/profile"

    def upload(self, resume_path: str, profile: dict) -> SyncResult:
        return super().upload(resume_path, profile)
