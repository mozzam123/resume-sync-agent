# Resume Sync Agent

Local FastAPI and Streamlit tool for storing a resume and tracking uploads across job platforms.

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

## Run

### Easiest: one command

```bash
./start.command
```

On macOS you can also double-click `start.command` in Finder. It creates the local virtual environment if needed, installs dependencies, downloads the dedicated Playwright browser on the first run, starts the backend, and then opens the Streamlit app. Keep its Terminal window open while using the app; press Control-C there to stop it. When code changes, stop the existing process first; the launcher intentionally refuses to reuse an already-running backend.

### Run the services separately

In one terminal:

```bash
.venv/bin/python main.py
```

In another terminal:

```bash
.venv/bin/streamlit run streamlit_app.py
```

Open the local Streamlit URL shown in the second terminal. Choose your platforms, then use **First time with these platforms?** → **Set up selected platforms**. Sign in in the browser tabs that open and complete any CAPTCHA or verification yourself. The shared session is saved under `data/job-platform-playwright-profile/` and is not your default browser profile. The Playwright Chromium download is kept at `data/playwright-browsers/`.

## Wellfound behaviour

- PDF resumes are uploaded directly; DOCX resumes are first converted to a PDF copy under `data/wellfound-converted/`.
- The agent uses a persistent, visible Playwright Chromium profile. It does not collect or store passwords itself.
- If authentication, CAPTCHA, verification, conversion, or Wellfound page detection fails, the sync is saved as `manual_required` and provides Wellfound's profile page. No access controls are bypassed.
- A `success` result means the file was submitted to the visible Wellfound form; review the profile to confirm it was saved.
