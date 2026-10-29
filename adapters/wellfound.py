"""Wellfound resume upload using a local, persistent Playwright profile.

The adapter never attempts to solve CAPTCHAs, MFA challenges, or other access
controls.  When Wellfound requires one of those steps, it returns a manual
fallback record instead of treating the upload as successful.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .base import PlatformAdapter, SyncResult

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
PROFILE_DIR = DATA_DIR / "wellfound-playwright-profile"
CONVERTED_DIR = DATA_DIR / "wellfound-converted"
PLAYWRIGHT_BROWSERS_DIR = DATA_DIR / "playwright-browsers"
LOGIN_WAIT_SECONDS = 300
PAGE_WAIT_SECONDS = 30

# Persistent browser profiles cannot safely be opened by two Chromium processes.
_browser_lock = threading.Lock()
_open_contexts: list[tuple[object, object]] = []


class ResumeConversionError(RuntimeError):
    """Raised when a Wellfound-compatible PDF cannot be prepared."""


def prepare_resume_pdf(resume_path: str, converted_dir: Path = CONVERTED_DIR) -> Path:
    """Return a PDF for a browser-assisted platform, converting DOCX if needed."""
    source = Path(resume_path).expanduser().resolve()
    if not source.is_file():
        raise ResumeConversionError("The stored resume file is missing.")
    if source.suffix.lower() == ".pdf":
        return source
    if source.suffix.lower() != ".docx":
        raise ResumeConversionError("Browser-assisted upload supports PDF or DOCX resumes only.")

    converted_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    destination = converted_dir / f"{source.stem}-{fingerprint}.pdf"
    if destination.exists():
        return destination

    # docx2pdf uses Microsoft Word on macOS/Windows, which preserves layout well.
    try:
        from docx2pdf import convert

        convert(str(source), str(converted_dir))
        generated = converted_dir / f"{source.stem}.pdf"
        if generated.exists():
            generated.replace(destination)
            return destination
    except Exception:  # Fall through to LibreOffice where it is available.
        pass

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(converted_dir), str(source)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            generated = converted_dir / f"{source.stem}.pdf"
            if generated.exists():
                generated.replace(destination)
                return destination
        except (OSError, subprocess.SubprocessError):
            pass

    raise ResumeConversionError(
        "Could not convert DOCX to PDF. Install Microsoft Word (for docx2pdf) "
        "or LibreOffice, then try again."
    )


class WellfoundAdapter(PlatformAdapter):
    name = "wellfound"
    platform_label = "Wellfound"
    uses_playwright = True
    # Wellfound's dedicated resume editor exposes the actual file upload form.
    upload_page_url = "https://wellfound.com/profile/edit/resume"
    profile_dir = PROFILE_DIR
    converted_dir = CONVERTED_DIR

    def login(self) -> SyncResult:
        """Let the user complete the one-time interactive login in Chromium."""
        try:
            with _browser_lock:
                page, context, playwright = self._open_profile()
                try:
                    page.goto(self.upload_page_url, wait_until="domcontentloaded", timeout=PAGE_WAIT_SECONDS * 1000)
                    deadline = time.monotonic() + LOGIN_WAIT_SECONDS
                    while time.monotonic() < deadline:
                        if self._has_file_input(page):
                            return SyncResult(
                                platform=self.name,
                                status="completed",
                                message=f"{self.platform_label} login saved in this app's dedicated browser profile.",
                            )
                        time.sleep(1)
                    return self._manual_result(
                        "Login was not verified within five minutes. Complete any sign-in, CAPTCHA, or verification "
                        "yourself, then use the manual upload page."
                    )
                finally:
                    try:
                        context.close()
                    finally:
                        playwright.stop()
        except Exception as exc:  # Browser installation and navigation failures are recoverable.
            return self._manual_result(f"Could not open the Wellfound browser: {self._safe_error(exc)}")

    def upload(self, resume_path: str, profile: dict) -> SyncResult:
        try:
            pdf_path = prepare_resume_pdf(resume_path, self.converted_dir)
        except ResumeConversionError as exc:
            return self._manual_result(str(exc))

        try:
            with _browser_lock:
                page, context, playwright = self._open_profile()
                keep_open = False
                try:
                    page.goto(self.upload_page_url, wait_until="domcontentloaded", timeout=PAGE_WAIT_SECONDS * 1000)
                    if not self._wait_for_file_input(page, timeout_seconds=10):
                        keep_open = True
                        self._retain_open_browser(context, playwright)
                        return self._manual_result(
                            f"{self.platform_label} is not ready for an automated upload. Sign in or complete any verification in "
                            f"the dedicated {self.platform_label} browser window, then upload manually."
                        )

                    file_input = page.locator("input[type='file']").first
                    file_input.set_input_files(
                        self._upload_payload(pdf_path, profile.get("filename")),
                        timeout=PAGE_WAIT_SECONDS * 1000,
                    )
                    if self._save_if_present(page) and self._wait_for_save_confirmation(page):
                        return SyncResult(
                            platform=self.name,
                            status="success",
                            message=(
                                f"{self.platform_label} confirmed that {pdf_path.name} was saved. "
                                f"Please review your {self.platform_label} profile when convenient."
                            ),
                            manual_url=self.upload_page_url,
                        )

                    keep_open = True
                    self._retain_open_browser(context, playwright)
                    return SyncResult(
                        platform=self.name,
                        status="manual_required",
                        message=(
                            f"{pdf_path.name} was selected, but {self.platform_label} did not show a saved confirmation. "
                            f"The dedicated {self.platform_label} browser window is still open—review it and click its save "
                            "control yourself, then mark this sync complete."
                        ),
                        manual_url=self.upload_page_url,
                    )
                finally:
                    if not keep_open:
                        try:
                            context.close()
                        finally:
                            playwright.stop()
        except Exception as exc:  # Never claim success when the page changes or auth fails.
            return self._manual_result(
                f"Automatic {self.platform_label} upload could not be verified; no access control was bypassed. "
                f"Use the manual upload page instead. Details: {self._safe_error(exc)}"
            )

    def _open_profile(self):
        # Keep the browser binary alongside other app runtime data. This avoids
        # relying on a user-level cache and makes the app's browser dependency
        # explicit and self-contained.
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PLAYWRIGHT_BROWSERS_DIR))
        from playwright.sync_api import sync_playwright

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        playwright = sync_playwright().start()
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                accept_downloads=False,
            )
        except Exception:
            playwright.stop()
            raise
        page = context.pages[0] if context.pages else context.new_page()

        return page, context, playwright

    @staticmethod
    def _has_file_input(page) -> bool:
        try:
            return page.locator("input[type='file']").count() > 0
        except Exception:
            return False

    def _wait_for_file_input(self, page, timeout_seconds: int) -> bool:
        self.prepare_upload_form(page)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._has_file_input(page):
                return True
            time.sleep(0.5)
        return False

    def prepare_upload_form(self, page) -> None:
        """Give platform adapters a chance to reveal their file input."""

    def open_upload_page(self) -> SyncResult:
        """Open a durable manual-upload window in the dedicated profile."""
        try:
            with _browser_lock:
                page, context, playwright = self._open_profile()
                page.goto(self.upload_page_url, wait_until="domcontentloaded", timeout=PAGE_WAIT_SECONDS * 1000)
                self._retain_open_browser(context, playwright)
            return self._manual_result(
            f"Opened {self.platform_label} in the dedicated browser profile. Complete the upload there; "
                "the window stays open until you close it."
            )
        except Exception as exc:
            return self._manual_result(f"Could not open the dedicated Wellfound browser: {self._safe_error(exc)}")

    @staticmethod
    def _save_if_present(page) -> bool:
        """Use only explicit save/update controls; never submit unrelated forms."""
        for selector in (
            "button:has-text('Upload resume')",
            "button:has-text('Upload')",
            "button:has-text('Save changes')",
            "button:has-text('Save')",
            "button:has-text('Update')",
        ):
            button = page.locator(selector).first
            try:
                if button.is_visible():
                    button.click(timeout=5_000)
                    page.wait_for_timeout(1_000)
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _wait_for_save_confirmation(page, timeout_seconds: int = 8) -> bool:
        """Only accept an explicit Wellfound success message as upload confirmation."""
        deadline = time.monotonic() + timeout_seconds
        success_words = ("saved", "updated", "uploaded", "success")
        while time.monotonic() < deadline:
            try:
                notices = page.locator("[role='alert'], [role='status'], .toast, .notification")
                for index in range(notices.count()):
                    text = notices.nth(index).inner_text().lower()
                    if any(word in text for word in success_words):
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    @staticmethod
    def _upload_payload(pdf_path: Path, original_filename: str | None) -> dict:
        """Send Wellfound a stable, user-facing PDF filename.

        Local storage adds a timestamp when a duplicate filename is uploaded;
        that protects old files but should never leak into a platform profile.
        """
        if original_filename:
            filename = f"{Path(original_filename).stem}.pdf"
        else:
            filename = pdf_path.name
        return {
            "name": filename,
            "mimeType": "application/pdf",
            "buffer": pdf_path.read_bytes(),
        }

    @staticmethod
    def _retain_open_browser(context, playwright) -> None:
        """Keep a manual platform window alive after this API request returns."""
        item = (context, playwright)
        _open_contexts.append(item)

        def cleanup(*_args) -> None:
            try:
                _open_contexts.remove(item)
            except ValueError:
                pass
            try:
                playwright.stop()
            except Exception:
                pass

        context.on("close", cleanup)

    def _manual_result(self, detail: str) -> SyncResult:
        return SyncResult(
            platform=self.name,
            status="manual_required",
            message=detail,
            manual_url=self.upload_page_url,
        )

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace("\n", " ")[:300] or exc.__class__.__name__
