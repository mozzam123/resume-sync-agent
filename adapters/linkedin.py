"""LinkedIn adapter (browser-assisted, compliant)."""

from __future__ import annotations

from .base import PlatformAdapter, SyncResult


class LinkedInAdapter(PlatformAdapter):
    name = "linkedin"
    upload_page_url = "https://www.linkedin.com/in/me/edit/contact-info/"

    def upload(self, resume_path: str, profile: dict) -> SyncResult:
        # LinkedIn does not offer a free public resume-upload API for individuals.
        # Reuse the user's authenticated browser session for a manual upload.
        return super().upload(resume_path, profile)
