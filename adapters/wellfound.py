"""Wellfound adapter (browser-assisted, compliant)."""

from __future__ import annotations

from .base import PlatformAdapter, SyncResult


class WellfoundAdapter(PlatformAdapter):
    name = "wellfound"
    upload_page_url = "https://wellfound.com/user/edit"

    def upload(self, resume_path: str, profile: dict) -> SyncResult:
        return super().upload(resume_path, profile)
