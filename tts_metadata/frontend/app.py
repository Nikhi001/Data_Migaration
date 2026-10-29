"""TTS Metadata Management System — Gradio Frontend Interface.

Communicates exclusively with the FastAPI backend via HTTP requests.
Provides read-only exploration of TTS metadata with pagination, page-level search,
column filtering, and live system status indicators.
"""

import os
from typing import Any, Dict, List, Tuple
import pandas as pd
import requests
import gradio as gr

# Configuration: FastAPI Backend URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = 8  # seconds


# ==============================================================================
# Backend API Client Helper Functions
# ==============================================================================

def check_backend_health() -> Tuple[str, str]:
    """Check connectivity to FastAPI backend and PostgreSQL database.

    Returns:
        Tuple[str, str]: (api_status_badge, database_status_badge)
    """
    try:
        api_resp = requests.get(f"{API_BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        if api_resp.status_code == 200:
            api_status = "🟢 Online"
        else:
            api_status = f"🟡 Status {api_resp.status_code}"
    except Exception:
        return "🔴 Offline (Backend Unreachable)", "⚪ Unknown"

    try:
        db_resp = requests.get(f"{API_BASE_URL}/health/database", timeout=REQUEST_TIMEOUT)
        if db_resp.status_code == 200:
            db_status = "🟢 Connected"
        else:
            db_status = "🔴 Disconnected"
    except Exception:
        db_status = "🔴 Unreachable"

    return api_status, db_status


def fetch_total_count() -> int:
    """Fetch total metadata records count from FastAPI backend."""
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/metadata/count", timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.json().get("total_records", 0)
        return 0
    except Exception:
        return 0


def fetch_metadata_page(limit: int, offset: int) -> Tuple[pd.DataFrame, str]:
    """Fetch a page of metadata records from the backend API.

    Returns:
        Tuple[pd.DataFrame, str]: (dataframe_of_items, error_or_status_message)
    """
    try:
        url = f"{API_BASE_URL}/api/v1/metadata?limit={limit}&offset={offset}"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return pd.DataFrame(), "No metadata records found for this page."
            df = pd.DataFrame(items)
            return df, ""
        elif resp.status_code == 404:
            return pd.DataFrame(), "Error: The metadata table was not found on the database."
        elif resp.status_code == 503:
            return pd.DataFrame(), "Error: Database service is temporarily unavailable."
        else:
            return pd.DataFrame(), f"API returned status code {resp.status_code}: {resp.text}"
    except requests.exceptions.ConnectionError:
        return pd.DataFrame(), f"Cannot connect to FastAPI backend at {API_BASE_URL}. Ensure FastAPI is running."
    except requests.exceptions.Timeout:
        return pd.DataFrame(), "Request timed out while contacting FastAPI backend."
    except Exception as exc:
        return pd.DataFrame(), f"Unexpected error: {str(exc)}"


# ==============================================================================
# UI Logic and Event Handlers
# ==============================================================================

def load_data(
    offset: int,
    limit: int,
    search_query: str = "",
    language_filter: str = "All",
    gender_filter: str = "All",
    status_filter: str = "All",
):
    """Load metadata records, apply page filters/search, and update interface widgets."""
    api_status, db_status = check_backend_health()
    total_records = fetch_total_count()

    # Safety bounds for pagination
    if offset < 0:
        offset = 0

    df, error_msg = fetch_metadata_page(limit=limit, offset=offset)

    if not df.empty:
        # Extract unique filter options if columns present
        languages = ["All"] + sorted([str(x) for x in df["language"].dropna().unique()]) if "language" in df.columns else ["All"]
        genders = ["All"] + sorted([str(x) for x in df["gender"].dropna().unique()]) if "gender" in df.columns else ["All"]
        statuses = ["All"] + sorted([str(x) for x in df["status"].dropna().unique()]) if "status" in df.columns else ["All"]

        # Apply in-memory search across all string columns on the current page
        filtered_df = df.copy()
        if search_query.strip():
            query_lower = search_query.strip().lower()
            mask = filtered_df.astype(str).apply(
                lambda row: row.str.lower().str.contains(query_lower, na=False).any(),
                axis=1,
            )
            filtered_df = filtered_df[mask]

        # Apply dropdown filters
        if language_filter != "All" and "language" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["language"].astype(str) == language_filter]
        if gender_filter != "All" and "gender" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["gender"].astype(str) == gender_filter]
        if status_filter != "All" and "status" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["status"].astype(str) == status_filter]

        displayed_count = len(filtered_df)
    else:
        filtered_df = pd.DataFrame()
        displayed_count = 0
        languages = ["All"]
        genders = ["All"]
        statuses = ["All"]

    # Calculate pagination stats
    current_page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = max(1, (total_records + limit - 1) // limit) if limit > 0 else 1
    page_info = f"Page {current_page} of {total_pages} (Offset: {offset})"

    status_notice = (
        f"⚠️ {error_msg}"
        if error_msg
        else f"Displaying {displayed_count} records on current page (Total in DB: {total_records})"
    )

    return (
        filtered_df,
        f"{total_records:,}",
        str(displayed_count),
        page_info,
        f"API: {api_status} | DB: {db_status}",
        status_notice,
        offset,
        gr.update(choices=languages, value=language_filter if language_filter in languages else "All"),
        gr.update(choices=genders, value=gender_filter if gender_filter in genders else "All"),
        gr.update(choices=statuses, value=status_filter if status_filter in statuses else "All"),
    )


def go_previous(offset: int, limit: int, search: str, lang: str, gen: str, stat: str):
    """Handle Previous Page click."""
    new_offset = max(0, offset - limit)
    return load_data(new_offset, limit, search, lang, gen, stat)


def go_next(offset: int, limit: int, search: str, lang: str, gen: str, stat: str):
    """Handle Next Page click."""
    total_records = fetch_total_count()
    if offset + limit < total_records:
        new_offset = offset + limit
    else:
        new_offset = offset
    return load_data(new_offset, limit, search, lang, gen, stat)


def apply_page_search(search: str, offset: int, limit: int, lang: str, gen: str, stat: str):
    """Re-filter currently loaded page with search query."""
    return load_data(offset, limit, search, lang, gen, stat)


def reset_filters(offset: int, limit: int):
    """Reset search and column filters."""
    return load_data(offset, limit, "", "All", "All", "All")


# ==============================================================================
# Gradio Interface Construction
# ==============================================================================

custom_css = """
.metric-box {
    border-radius: 8px;
    padding: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
}
.notice-box {
    font-size: 0.92rem;
    color: #475569;
}
"""

with gr.Blocks(title="TTS Metadata Management System", css=custom_css, theme=gr.themes.Soft()) as demo:
    # State variables
    state_offset = gr.State(value=0)

    gr.Markdown(
        """
        # 🎙️ TTS Metadata Management System
        *Read-only metadata explorer powered by FastAPI and PostgreSQL.*
        """
    )

    # A. Dashboard Summary
    with gr.Row():
        metric_total = gr.Textbox(label="Total Records in DB", value="0", interactive=False)
        metric_displayed = gr.Textbox(label="Records Displayed on Page", value="0", interactive=False)
        metric_page = gr.Textbox(label="Pagination Status", value="Page 1 of 1", interactive=False)
        metric_connection = gr.Textbox(label="Service Status", value="Checking...", interactive=False)

    gr.Markdown("---")

    # Controls Row: Pagination, Refresh, Page Size
    with gr.Row():
        btn_refresh = gr.Button("🔄 Refresh Data", variant="primary", scale=2)
        dropdown_limit = gr.Dropdown(
            label="Page Size",
            choices=[10, 25, 50, 100],
            value=25,
            interactive=True,
            scale=1,
        )
        btn_prev = gr.Button("⬅️ Previous Page", scale=1)
        btn_next = gr.Button("Next Page ➡️", scale=1)

    # Search and Filter Section
    with gr.Accordion("🔍 Page Search & Filters (Operates on Current Page Records)", open=True):
        gr.Markdown(
            "*Note: The search and filter controls below apply strictly to the records loaded in the current page view.*"
        )
        with gr.Row():
            input_search = gr.Textbox(
                label="Search Keyword",
                placeholder="Search text in source, language, speaker, file name, remarks...",
                scale=3,
            )
            filter_language = gr.Dropdown(label="Filter Language", choices=["All"], value="All", scale=1)
            filter_gender = gr.Dropdown(label="Filter Gender", choices=["All"], value="All", scale=1)
            filter_status = gr.Dropdown(label="Filter Status", choices=["All"], value="All", scale=1)
            btn_reset = gr.Button("Reset Filters", scale=1)

    # Status / Alert Notification
    status_box = gr.Textbox(
        label="Notification",
        value="System initialized. Ready to fetch data.",
        interactive=False,
    )

    # B. Metadata Table
    with gr.Row():
        table_metadata = gr.Dataframe(
            label="Metadata Records (Read-Only)",
            interactive=False,
            wrap=True,
        )

    # Wire up Event Handlers
    all_outputs = [
        table_metadata,
        metric_total,
        metric_displayed,
        metric_page,
        metric_connection,
        status_box,
        state_offset,
        filter_language,
        filter_gender,
        filter_status,
    ]

    # Initial page load
    demo.load(
        fn=load_data,
        inputs=[state_offset, dropdown_limit, input_search, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    # Refresh
    btn_refresh.click(
        fn=load_data,
        inputs=[state_offset, dropdown_limit, input_search, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    # Limit change (resets offset to 0)
    dropdown_limit.change(
        fn=lambda limit, s, l, g, st: load_data(0, limit, s, l, g, st),
        inputs=[dropdown_limit, input_search, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    # Pagination
    btn_prev.click(
        fn=go_previous,
        inputs=[state_offset, dropdown_limit, input_search, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    btn_next.click(
        fn=go_next,
        inputs=[state_offset, dropdown_limit, input_search, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    # Search & Filter
    input_search.change(
        fn=apply_page_search,
        inputs=[input_search, state_offset, dropdown_limit, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    filter_language.change(
        fn=apply_page_search,
        inputs=[input_search, state_offset, dropdown_limit, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    filter_gender.change(
        fn=apply_page_search,
        inputs=[input_search, state_offset, dropdown_limit, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    filter_status.change(
        fn=apply_page_search,
        inputs=[input_search, state_offset, dropdown_limit, filter_language, filter_gender, filter_status],
        outputs=all_outputs,
    )

    btn_reset.click(
        fn=reset_filters,
        inputs=[state_offset, dropdown_limit],
        outputs=all_outputs,
    )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
