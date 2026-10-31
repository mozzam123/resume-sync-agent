"""A focused local UI for keeping a resume ready across job platforms."""

from __future__ import annotations

import json
import urllib.request

import streamlit as st

API_BASE = "http://127.0.0.1:8000/api"
REQUIRED_BACKEND_BUILD = "streamlined-ui-2026-10-29"
STATUS_LABELS = {
    "success": "Synced",
    "completed": "Completed",
    "manual_required": "Needs your attention",
    "failed": "Could not sync",
}


def _get(path: str):
    with urllib.request.urlopen(f"{API_BASE}{path}", timeout=10) as response:
        return json.loads(response.read())


def _post(path: str, payload: dict | None = None, timeout: int = 30):
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(payload or {}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _post_file(file_obj):
    boundary = "----ResumeSyncBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_obj.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_obj.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{API_BASE}/resumes",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def _status(status: str) -> None:
    label = STATUS_LABELS.get(status, status.replace("_", " ").title())
    if status in {"success", "completed"}:
        st.success(label)
    elif status == "manual_required":
        st.warning(label)
    else:
        st.error(label)


def _platform_label(platforms: list[dict], name: str) -> str:
    return next((platform["label"] for platform in platforms if platform["name"] == name), name.title())


def page_sync(platforms: list[dict]) -> None:
    st.header("Sync your resume")
    st.caption("Choose where to keep your latest resume ready.")

    selected = st.pills(
        "Platforms",
        options=[platform["name"] for platform in platforms],
        format_func=lambda name: _platform_label(platforms, name),
        selection_mode="multi",
        key="sync_platforms",
    )

    if selected:
        with st.expander("First time with these platforms?", expanded=False):
            st.write("Sign in once in the shared browser. A tab opens for each platform you selected.")
            if st.button("Set up selected platforms", use_container_width=True):
                try:
                    with st.spinner("Waiting for you to sign in in the browser…"):
                        setup = _post("/browser/setup", {"platforms": selected}, timeout=330)
                    (st.success if setup["ready"] else st.warning)(setup["message"])
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not open the browser: {exc}")

    resume = st.file_uploader("Resume", type=["pdf", "docx"], key="sync_resume", help="DOCX files are converted to PDF when needed.")
    if st.button("Sync resume", type="primary", use_container_width=True, disabled=not resume or not selected):
        try:
            with st.spinner("Saving your resume…"):
                stored = _post_file(resume)
            with st.spinner("Syncing your selected platforms…"):
                st.session_state["latest_results"] = _post(
                    "/sync", {"resume_id": stored["id"], "platforms": selected}, timeout=180
                )
                st.session_state["latest_filename"] = stored["filename"]
        except Exception as exc:  # noqa: BLE001
            st.error(f"Sync could not start: {exc}")
        else:
            for key in ("sync_platforms", "sync_resume", "latest_results", "latest_filename"):
                st.session_state.pop(key, None)
            st.rerun()

def page_history(platforms: list[dict]) -> None:
    st.header("History")
    try:
        records = _get("/sync/history")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load history: {exc}")
        return
    if not records:
        st.info("Your sync history will appear here.")
        return
    for record in records:
        label = _platform_label(platforms, record["platform"])
        with st.expander(f"{record['filename']} · {label} · {STATUS_LABELS.get(record['status'], record['status'])}"):
            _status(record["status"])
            if record["status"] in {"manual_required", "failed"}:
                st.write(record.get("message") or "")
            if record.get("manual_url") and record["status"] == "manual_required":
                left, right = st.columns(2)
                with left:
                    if st.button("Open in browser", key=f"history_open_{record['id']}"):
                        try:
                            st.info(_post(f"/sync/{record['id']}/open", timeout=60)["message"])
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Could not open the browser: {exc}")
                with right:
                    if st.button("Mark complete", key=f"history_complete_{record['id']}"):
                        _post(f"/sync/{record['id']}/complete")
                        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Resume Sync", page_icon="📄", layout="centered")
    try:
        health = _get("/health")
        platforms = _get("/platforms")
    except Exception:
        st.error("The app backend is not running. Start it with ./start.command, then refresh this page.")
        st.stop()
    if health.get("build") != REQUIRED_BACKEND_BUILD:
        st.error("The backend needs restarting to use this version. Stop it, run ./start.command, then refresh.")
        st.stop()

    st.title("Resume Sync")
    page = st.sidebar.radio("", ["Sync", "History"], label_visibility="collapsed")
    if page == "Sync":
        page_sync(platforms)
    else:
        page_history(platforms)


if __name__ == "__main__":
    main()
