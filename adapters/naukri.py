"""Naukri resume upload using a dedicated persistent Playwright profile."""

from __future__ import annotations

from .wellfound import DATA_DIR, WellfoundAdapter


class NaukriAdapter(WellfoundAdapter):
    name = "naukri"
    platform_label = "Naukri"
    upload_page_url = "https://www.naukri.com/mnjuser/profile"
    profile_dir = DATA_DIR / "naukri-playwright-profile"
    converted_dir = DATA_DIR / "naukri-converted"
