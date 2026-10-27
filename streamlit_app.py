"""Streamlit UI for the Resume Sync Agent.

Run with:

    streamlit run streamlit_app.py

Make sure the FastAPI backend is running first:

    resume-sync-agent
"""

from __future__ import annotations

import streamlit as st

API_BASE = "http://127.0.0.1:8000/api"


def _get(path: str):
    import urllib.request

    with urllib.request.urlopen(f"{API_BASE}{path}", timeout=10) as r:
        import json

        return json.loads(r.read())


def _post(path: str, payload: dict | None = None, files=None):
    import json
    import urllib.request

    if files:
        import urllib.request as _ur

        # multipart via requests-style encoding handled by http.client below
        raise NotImplementedError
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _post_file(path: str, file_obj, filename: str):
    import json
    import urllib.request

    boundary = "----ResumeSyncBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    body += file_obj.read()
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def status_badge(status: str):
    colors = {
        "success": "green",
        "failed": "red",
        "manual_required": "orange",
        "completed": "blue",
        "pending": "gray",
    }
    color = colors.get(status, "gray")
    st.markdown(f":{color}[{status}]")


def page_upload():
    st.header("Upload a resume")
    with st.expander("Set up Wellfound browser login", expanded=False):
        st.write(
            "The first Wellfound sync needs a sign-in in a dedicated Chromium profile. "
            "A browser window will open; complete login, CAPTCHA, or verification yourself."
        )
        if st.button("Open Wellfound login", key="wellfound_login"):
            try:
                with st.spinner("Waiting for you to finish signing in (up to five minutes)…"):
                    result = _post("/wellfound/login")
                if result["status"] == "completed":
                    st.success(result["message"])
                else:
                    st.warning(result["message"])
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not start Wellfound login: {exc}")
    uploaded = st.file_uploader("Resume (PDF/DOCX)", type=["pdf", "docx", "txt"])
    platforms = _get("/platforms")
    options = [p["name"] for p in platforms]
    selected = st.multiselect("Platforms to sync to", options, default=options)
    profile_note = st.text_input(
        "Note (stored with the sync record, optional)", placeholder="e.g. applied to SWE roles"
    )

    if st.button("Upload & sync", disabled=not uploaded or not selected):
        try:
            resume = _post_file("/resumes", uploaded, uploaded.name)
        except Exception as exc:  # noqa: BLE001 - surface connection issues to the user
            st.error(f"Upload failed: {exc}")
            return
        st.success(f"Stored resume: {resume['filename']}")
        resume_id = resume["id"]
        st.subheader("Sync results")
        try:
            with st.spinner("Syncing selected platforms… Wellfound may open its dedicated browser."):
                results = _post("/sync", {"resume_id": resume_id, "platforms": selected})
        except Exception as exc:  # noqa: BLE001
            st.error(f"Sync failed: {exc}")
            return
        for r in results:
            col1, col2, col3 = st.columns([2, 2, 4])
            with col1:
                st.write(r["platform"])
            with col2:
                status_badge(r["status"])
            with col3:
                st.write(r["message"])
                if r["manual_url"]:
                    if st.button(
                        "Open upload page",
                        key=f"open_{r['record_id']}",
                    ):
                        try:
                            opened = _post(f"/sync/{r['record_id']}/open")
                            if opened["ok"]:
                                st.info(opened["message"])
                            else:
                                st.error(opened["message"])
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Could not open browser: {exc}")
                    if r["status"] == "manual_required":
                        if st.button(
                            "Mark complete", key=f"complete_{r['record_id']}"
                        ):
                            try:
                                _post(f"/sync/{r['record_id']}/complete")
                                st.success("Marked complete.")
                                st.rerun()
                            except Exception as exc:  # noqa: BLE001
                                st.error(f"Could not mark complete: {exc}")


def page_history():
    st.header("Upload history")
    try:
        records = _get("/sync/history")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load history: {exc}")
        return
    if not records:
        st.info("No sync records yet.")
        return
    for r in records:
        with st.expander(
            f"{r['filename']} → {r['platform']} ({r['status']}) · {r['attempted_at'][:16]}"
        ):
            st.write(f"Resume: {r['filename']}")
            st.write(f"Platform: {r['platform']}")
            status_badge(r["status"])
            st.write(f"Message: {r['message']}")
            if r["manual_url"]:
                if st.button("Open upload page", key=f"hist_open_{r['id']}"):
                    try:
                        opened = _post(f"/sync/{r['id']}/open")
                        if opened["ok"]:
                            st.info(opened["message"])
                        else:
                            st.error(opened["message"])
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not open browser: {exc}")
                if r["status"] == "manual_required":
                    if st.button("Mark complete", key=f"hist_complete_{r['id']}"):
                        try:
                            _post(f"/sync/{r['id']}/complete")
                            st.success("Marked complete.")
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Could not mark complete: {exc}")


def main():
    st.set_page_config(page_title="Resume Sync Agent", page_icon="📄")
    st.title("Resume Sync Agent")
    st.caption("Upload a resume once, sync it across your selected platforms.")
    page = st.sidebar.radio("Go to", ["Upload", "History"], index=0)
    if page == "Upload":
        page_upload()
    else:
        page_history()


if __name__ == "__main__":
    main()
