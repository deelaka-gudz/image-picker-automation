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
    "Search the images folder for the names you give it, and copy any matches to the output folder."
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
st.subheader("1. Provide image names")

tab_paste, tab_upload = st.tabs(["Paste names", "Upload a list"])

pasted_text = ""
uploaded_names: list[str] = []

with tab_paste:
    pasted_text = st.text_area(
        "One image name per line (extension optional)",
        height=200,
        placeholder="IMG_0001\nIMG_0002.jpg\nproduct_photo_15",
    )

with tab_upload:
    uploaded_file = st.file_uploader(
        "Upload a .txt or .csv file with one name per line/row", type=["txt", "csv"]
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
    found_statuses = {
        auto.STATUS_COPIED,
        auto.STATUS_MULTIPLE,
        auto.STATUS_ALREADY_EXISTS,
    }

    total = len(results)
    found = sum(1 for r in results if r.status in found_statuses)
    not_found = sum(1 for r in results if r.status == auto.STATUS_NOT_FOUND)
    errors = sum(1 for r in results if r.status == auto.STATUS_ERROR)

    st.subheader("3. Results")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total requested", total)
    col2.metric("Found & copied", found)
    col3.metric("Not found", not_found)
    col4.metric("Errors", errors)

    df = pd.DataFrame(
        [
            {
                "Requested name": r.requested_name,
                "Status": r.status,
                "Matched file": str(r.matched_files[0]) if r.matched_files else "",
                "Copied to": str(r.copied_to) if r.copied_to else "",
                "Other matches": (
                    len(r.matched_files) - 1 if len(r.matched_files) > 1 else 0
                ),
            }
            for r in results
        ]
    )

    def _highlight_status(row: pd.Series) -> list[str]:
        color = ""
        if row["Status"] == auto.STATUS_NOT_FOUND:
            color = "background-color: #ffe0e0"
        elif row["Status"] == auto.STATUS_ERROR:
            color = "background-color: #ffcccc"
        elif row["Status"] in (auto.STATUS_MULTIPLE, "Found (multiple)"):
            color = "background-color: #fff5cc"
        elif row["Status"] == auto.STATUS_COPIED:
            color = "background-color: #e0ffe0"
        return [color] * len(row)

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
        with st.expander(f"Names not found ({not_found})"):
            st.code(
                "\n".join(
                    r.requested_name
                    for r in results
                    if r.status == auto.STATUS_NOT_FOUND
                )
            )
