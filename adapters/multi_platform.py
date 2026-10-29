"""Shared-browser session for syncing several job platforms in separate tabs."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from .base import SyncResult
from .wellfound import DATA_DIR, LOGIN_WAIT_SECONDS, PAGE_WAIT_SECONDS, PLAYWRIGHT_BROWSERS_DIR, prepare_resume_pdf

SHARED_PROFILE_DIR = DATA_DIR / "job-platform-playwright-profile"
_lock = threading.Lock()
_open_contexts: list[tuple[object, object]] = []


class MultiPlatformBrowser:
    """Uses one persistent profile, with one visible tab for each platform."""

    def login(self, adapters: list) -> bool:
        with _lock:
            pages, context, playwright = self._open_tabs(adapters)
            try:
                deadline = time.monotonic() + LOGIN_WAIT_SECONDS
                while time.monotonic() < deadline:
                    if all(page.locator("input[type='file']").count() > 0 for page in pages.values()):
                        return True
                    time.sleep(1)
                self._retain(context, playwright)
                return False
            finally:
                if not any(item[0] is context for item in _open_contexts):
                    try:
                        context.close()
                    finally:
                        playwright.stop()

    def upload(self, adapters: list, resume_path: str, filename: str) -> dict[str, SyncResult]:
        with _lock:
            pages, context, playwright = self._open_tabs(adapters)
            results: dict[str, SyncResult] = {}
            keep_open = False
            try:
                for adapter in adapters:
                    page = pages[adapter.name]
                    try:
                        if not self._wait_for_file_input(page):
                            raise RuntimeError("the upload form was not available; sign in or complete verification")
                        pdf_path = prepare_resume_pdf(resume_path, adapter.converted_dir)
                        page.locator("input[type='file']").first.set_input_files(
                            adapter._upload_payload(pdf_path, filename), timeout=PAGE_WAIT_SECONDS * 1000
                        )
                        if adapter._save_if_present(page) and adapter._wait_for_save_confirmation(page):
                            results[adapter.name] = SyncResult(
                                platform=adapter.name,
                                status="success",
                                message=f"{adapter.platform_label} confirmed that {pdf_path.name} was saved.",
                                manual_url=adapter.upload_page_url,
                            )
                        else:
                            keep_open = True
                            results[adapter.name] = self._manual(adapter, "no saved confirmation appeared")
                    except Exception as exc:  # A page change or verification requirement is manual fallback.
                        keep_open = True
                        results[adapter.name] = self._manual(adapter, str(exc).replace("\n", " ")[:250])
                if keep_open:
                    self._retain(context, playwright)
                return results
            finally:
                if not keep_open:
                    try:
                        context.close()
                    finally:
                        playwright.stop()

    def _open_tabs(self, adapters: list):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PLAYWRIGHT_BROWSERS_DIR))
        from playwright.sync_api import sync_playwright

        SHARED_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        playwright = sync_playwright().start()
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(SHARED_PROFILE_DIR), headless=False, accept_downloads=False
            )
            pages = {}
            for index, adapter in enumerate(adapters):
                page = context.pages[0] if index == 0 and context.pages else context.new_page()
                page.goto(adapter.upload_page_url, wait_until="domcontentloaded", timeout=PAGE_WAIT_SECONDS * 1000)
                adapter.prepare_upload_form(page)
                pages[adapter.name] = page
            return pages, context, playwright
        except Exception:
            playwright.stop()
            raise

    @staticmethod
    def _wait_for_file_input(page) -> bool:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                if page.locator("input[type='file']").count() > 0:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    @staticmethod
    def _manual(adapter, detail: str) -> SyncResult:
        return SyncResult(
            platform=adapter.name,
            status="manual_required",
            message=(
                f"{adapter.platform_label} needs attention: {detail}. Its tab is still open in the shared browser. "
                "Complete any verification or save step yourself, then mark this sync complete."
            ),
            manual_url=adapter.upload_page_url,
        )

    @staticmethod
    def _retain(context, playwright) -> None:
        item = (context, playwright)
        if item in _open_contexts:
            return
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
