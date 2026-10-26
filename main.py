"""Resume Sync Agent entry point.

Run the FastAPI backend:

    uv run python main.py

Then open the Streamlit UI separately:

    uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import uvicorn

from app import app


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)
