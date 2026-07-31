"""
Streamlit app: paste/upload a list of image names, search for them in the
source images folder, and copy any matches into the output folder.
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

import automation as auto

st.set_page_config(page_title="Image Picker Automation", page_icon="🖼️", layout="wide")

if "index" not in st.session_state:
    st.session_state.index = None
    st.session_state.index_source = None
    st.session_state.index_built_at = None
if "results" not in st.session_state:
    st.session_state.results = None

st.title("🖼️ Image Picker Automation")
st.caption(
    "Search the images folder for the keywords you give it, and copy every matching file "
    '(e.g. "batman" matches batman_01.jpg and key_batman_01.png) to the output folder. '
    "Matching is case-insensitive."
)

# ---------------------------------------------------------------------------
# Sidebar: folder configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Folders")
    source_dir = st.text_input("Source images folder", value=auto.DEFAULT_SOURCE_DIR)
    output_dir = st.text_input("Output folder", value=auto.DEFAULT_OUTPUT_DIR)
    overwrite = st.checkbox("Overwrite files already in output folder", value=False)

    st.divider()
    st.header("Index")
    st.caption(
        "The source folder is scanned once and cached, so repeated searches are fast."
    )
    build_clicked = st.button("Build / Refresh index", use_container_width=True)

    if build_clicked:
        with st.spinner(f"Scanning '{source_dir}' ..."):
            try:
                start = time.time()
                st.session_state.index = auto.build_file_index(source_dir)
                st.session_state.index_source = source_dir
                st.session_state.index_built_at = time.time() - start
            except FileNotFoundError as exc:
                st.session_state.index = None
                st.error(str(exc))

    if st.session_state.index is not None:
        total_files = sum(len(v) for v in st.session_state.index.values())
        st.success(
            f"Indexed {total_files} files "
            f"({len(st.session_state.index)} unique names) "
            f"in {st.session_state.index_built_at:.1f}s"
        )
        if st.session_state.index_source != source_dir:
            st.warning("Source folder changed since last index — click Refresh.")

# ---------------------------------------------------------------------------
# Main: input names
# ---------------------------------------------------------------------------
st.subheader("1. Provide keywords")

tab_paste, tab_upload = st.tabs(["Paste keywords", "Upload a list"])

pasted_text = ""
uploaded_names: list[str] = []

with tab_paste:
    pasted_text = st.text_area(
        "One keyword per line — matches any filename containing it (case-insensitive)",
        height=200,
        placeholder="batman\nIMG_0001\nproduct_photo_15",
    )

with tab_upload:
    uploaded_file = st.file_uploader(
        "Upload a .txt or .csv file with one keyword per line/row", type=["txt", "csv"]
    )
    if uploaded_file is not None:
        raw = uploaded_file.read().decode("utf-8-sig")
        uploaded_names = [line.strip() for line in raw.splitlines() if line.strip()]
        st.write(f"{len(uploaded_names)} names loaded from file.")
        st.dataframe(
            pd.DataFrame({"name": uploaded_names}), use_container_width=True, height=200
        )

names = (
    uploaded_names
    if uploaded_names
    else [n.strip() for n in pasted_text.splitlines() if n.strip()]
)
# de-duplicate while preserving order
seen = set()
names = [n for n in names if not (n.lower() in seen or seen.add(n.lower()))]

if names:
    st.caption(f"{len(names)} unique name(s) ready to search.")

st.subheader("2. Search & copy")

run_disabled = len(names) == 0
run_clicked = st.button("Search & Copy", type="primary", disabled=run_disabled)

if run_clicked:
    if st.session_state.index is None or st.session_state.index_source != source_dir:
        with st.spinner(f"Scanning '{source_dir}' ..."):
            try:
                start = time.time()
                st.session_state.index = auto.build_file_index(source_dir)
                st.session_state.index_source = source_dir
                st.session_state.index_built_at = time.time() - start
            except FileNotFoundError as exc:
                st.error(str(exc))
                st.stop()

    with st.spinner(f"Copying matches into '{output_dir}' ..."):
        results = auto.run(
            names,
            source_dir=source_dir,
            output_dir=output_dir,
            overwrite=overwrite,
            index=st.session_state.index,
        )
    st.session_state.results = results

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if st.session_state.results:
    results = st.session_state.results
    found_statuses = {auto.STATUS_COPIED, auto.STATUS_ALREADY_EXISTS}

    total_keywords = len(results)
    found = sum(1 for r in results if r.status in found_statuses)
    not_found = sum(1 for r in results if r.status == auto.STATUS_NOT_FOUND)
    errors = sum(1 for r in results if r.status == auto.STATUS_ERROR)
    total_files = sum(len(r.matched_files) for r in results)

    st.subheader("3. Results")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Keywords searched", total_keywords)
    col2.metric("Keywords matched", found)
    col3.metric("Keywords not found", not_found)
    col4.metric("Keyword errors", errors)
    col5.metric("Files matched", total_files)

    # One row per matched file, so a keyword like "batman" that matches
    # several files (batman_01.jpg, key_batman_01.png, ...) shows each of
    # them individually rather than only the first.
    rows = []
    for r in results:
        if not r.matched_files:
            rows.append(
                {
                    "Keyword": r.requested_name,
                    "File": "",
                    "Status": auto.STATUS_NOT_FOUND,
                    "Copied to": "",
                    "Detail": "",
                }
            )
            continue
        for outcome in r.outcomes:
            rows.append(
                {
                    "Keyword": r.requested_name,
                    "File": outcome.source.name,
                    "Status": outcome.status,
                    "Copied to": (
                        str(outcome.destination) if outcome.destination else ""
                    ),
                    "Detail": outcome.detail,
                }
            )

    df = pd.DataFrame(rows)

    def _highlight_status(row: pd.Series) -> list[str]:
        # Explicit dark text color alongside each pale background — Streamlit's
        # dark theme otherwise renders default light text on these light
        # backgrounds, which is unreadable.
        style = ""
        if row["Status"] == auto.STATUS_NOT_FOUND:
            style = "background-color: #ffe0e0; color: #1a1a1a"
        elif row["Status"] == auto.STATUS_ERROR:
            style = "background-color: #ffcccc; color: #1a1a1a"
        elif row["Status"] == auto.STATUS_ALREADY_EXISTS:
            style = "background-color: #fff5cc; color: #1a1a1a"
        elif row["Status"] == auto.STATUS_COPIED:
            style = "background-color: #e0ffe0; color: #1a1a1a"
        return [style] * len(row)

    st.dataframe(
        df.style.apply(_highlight_status, axis=1), use_container_width=True, height=400
    )

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download results as CSV",
        data=csv_bytes,
        file_name="image_picker_results.csv",
        mime="text/csv",
    )

    if not_found:
        with st.expander(f"Keywords not found ({not_found})"):
            st.code(
                "\n".join(
                    r.requested_name
                    for r in results
                    if r.status == auto.STATUS_NOT_FOUND
                )
            )
