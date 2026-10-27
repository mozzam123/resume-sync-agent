"""Resume Sync Agent entry point.

Run the FastAPI backend:

    .venv/bin/python main.py

Then open the Streamlit UI separately:

    .venv/bin/streamlit run streamlit_app.py
"""

from __future__ import annotations

import uvicorn

from app import app


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)
