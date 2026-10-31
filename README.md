# Resume Sync Agent

A self-hosted tool (FastAPI + Streamlit) to update your resume across LinkedIn, Naukri, and Wellfound in one go using Playwright browser automation, with manual verification/CAPTCHA support and local SQLite tracking.

## Setup (pip + venv)

```bash
cd /Users/mozzaminamdar/Dev/resume-sync-agent
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/data/playwright-browsers" \
  .venv/bin/python -m playwright install chromium
```

For DOCX-to-PDF conversion, install Microsoft Word (macOS/Windows; used through `docx2pdf`) or LibreOffice (`soffice`) as a fallback.

## Wellfound behaviour

- PDF resumes are uploaded directly; DOCX resumes are first converted to a PDF copy under `data/wellfound-converted/`.
- The agent uses a persistent, visible Playwright Chromium profile. It does not collect or store passwords itself.
- If authentication, CAPTCHA, verification, conversion, or Wellfound page detection fails, the sync is saved as `manual_required` and provides Wellfound's profile page. No access controls are bypassed.
- A `success` result means the file was submitted to the visible Wellfound form; review the profile to confirm it was saved.
