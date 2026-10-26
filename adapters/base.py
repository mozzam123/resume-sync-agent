"""Base class and result type for platform adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SyncResult:
    platform: str
    status: str  # "success" | "failed" | "manual_required" | "completed"
    message: str
    manual_url: str | None = None


class PlatformAdapter:
    """A single platform's resume upload path.

    Subclasses set ``name`` and implement ``upload``. The default implementation
    is compliant browser-assisted upload: open the platform's upload page in the
    user's already-authenticated browser and ask them to complete it manually.
    """

    name = "base"
    upload_page_url: str | None = None

    def upload(self, resume_path: str, profile: dict) -> SyncResult:
        if self.upload_page_url:
            return SyncResult(
                platform=self.name,
                status="manual_required",
                message=(
                    "No free public resume-upload API available for this platform. "
                    f"Open {self.upload_page_url} in your browser (you are already "
                    "signed in), upload the resume manually, then mark this sync as "
                    "complete below."
                ),
                manual_url=self.upload_page_url,
            )
        return SyncResult(
            platform=self.name,
            status="failed",
            message="No upload path configured for this platform.",
        )
