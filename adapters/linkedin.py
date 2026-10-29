"""LinkedIn resume upload using a dedicated persistent Playwright profile."""

from __future__ import annotations

from .wellfound import DATA_DIR, WellfoundAdapter


class LinkedInAdapter(WellfoundAdapter):
    name = "linkedin"
    platform_label = "LinkedIn"
    upload_page_url = "https://www.linkedin.com/jobs/application-settings/"
    profile_dir = DATA_DIR / "linkedin-playwright-profile"
    converted_dir = DATA_DIR / "linkedin-converted"

    def prepare_upload_form(self, page) -> None:
        """LinkedIn shows its file input after the Resume upload action."""
        if page.locator("input[type='file']").count() > 0:
            return
        for selector in (
            "button:has-text('Upload resume')",
            "button:has-text('Upload Resume')",
            "button:has-text('Upload')",
        ):
            button = page.locator(selector).first
            try:
                if button.is_visible():
                    button.click(timeout=5_000)
                    page.wait_for_timeout(500)
                    return
            except Exception:
                continue
