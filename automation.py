"""
Core logic for the Image Picker Automation tool.

Given a list of image names (with or without extension), search a source
folder (recursively) for files matching those names and copy the matches
into an output folder.

Can be used as a library (import and call `run`) or as a standalone CLI:

    python automation.py --names names.txt
    python automation.py --names "img001,img002,img003"
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Default locations (as given). Override via CLI args or the Streamlit app.
# ---------------------------------------------------------------------------
DEFAULT_SOURCE_DIR = r"\\MBC-NT01\Documents\Ammar - Anuja\Image Fetch Tool\Images"
DEFAULT_OUTPUT_DIR = r"\\MBC-NT01\Documents\Ammar - Anuja\Image Fetch Tool\Out"

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
    ".psd",
    ".ai",
    ".eps",
    ".svg",
}

# Mapped network drives -> their real UNC path, so a user can type "S:\..."
# or "M:\..." and it resolves correctly even on a machine where that drive
# letter isn't mapped (e.g. a fresh Task Scheduler session).
DRIVE_UNC_MAP = {
    "s": r"\\MBC-NT01\Documents",
    "m": r"\\MBC-NT01\Management",
}

STATUS_COPIED = "Copied"
STATUS_ALREADY_EXISTS = "Already in output"
STATUS_MULTIPLE = "Multiple matches (copied first)"
STATUS_NOT_FOUND = "Not found"
STATUS_ERROR = "Error"


@dataclass
class SearchResult:
    requested_name: str
    status: str
    matched_files: list[Path] = field(default_factory=list)
    copied_to: Path | None = None
    detail: str = ""


def resolve_path(path: str | Path) -> Path:
    """
    Map a `S:\\...` or `M:\\...` path to its underlying UNC path
    (`\\\\MBC-NT01\\Documents\\...` / `\\\\MBC-NT01\\Management\\...`).
    Any other path (already-UNC, a different drive, etc.) is left as-is.
    """
    text = str(path).strip()
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        unc_root = DRIVE_UNC_MAP.get(text[0].lower())
        if unc_root:
            return Path(unc_root + text[2:])
    return Path(text)


def build_file_index(
    source_dir: str | Path,
    extensions: set[str] | None = None,
) -> dict[str, list[Path]]:
    """
    Walk `source_dir` recursively and build an index mapping the lowercase
    filename stem (no extension) -> list of matching file paths.

    Doing one full walk up front is far faster than re-scanning the folder
    once per requested name, especially over a network share.
    """
    extensions = extensions or IMAGE_EXTENSIONS
    source_path = resolve_path(source_dir)
    index: dict[str, list[Path]] = {}

    if not source_path.exists():
        raise FileNotFoundError(f"Source folder not found: {source_path}")

    for root, _dirs, files in os.walk(source_path):
        for filename in files:
            file_path = Path(root) / filename
            if file_path.suffix.lower() not in extensions:
                continue
            stem_key = file_path.stem.strip().lower()
            index.setdefault(stem_key, []).append(file_path)

    return index


def _lookup_key(name: str) -> str:
    """Normalize a requested name to match index keys (strip extension if present)."""
    stripped = name.strip()
    candidate = Path(stripped)
    if candidate.suffix.lower() in IMAGE_EXTENSIONS:
        return candidate.stem.strip().lower()
    return stripped.lower()


def find_images(
    names: list[str],
    index: dict[str, list[Path]],
) -> list[SearchResult]:
    """Match requested names against a pre-built file index (no copying)."""
    results: list[SearchResult] = []
    for raw_name in names:
        name = raw_name.strip()
        if not name:
            continue
        key = _lookup_key(name)
        matches = index.get(key, [])
        if not matches:
            results.append(SearchResult(name, STATUS_NOT_FOUND))
        elif len(matches) == 1:
            results.append(SearchResult(name, "Found", matches))
        else:
            results.append(SearchResult(name, "Found (multiple)", matches))
    return results


def copy_result(
    result: SearchResult,
    output_dir: str | Path,
    overwrite: bool = False,
) -> SearchResult:
    """Copy the (first) matched file for a single SearchResult into output_dir."""
    output_path = resolve_path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not result.matched_files:
        result.status = STATUS_NOT_FOUND
        return result

    source_file = result.matched_files[0]
    destination = output_path / source_file.name

    if destination.exists() and not overwrite:
        result.status = STATUS_ALREADY_EXISTS
        result.copied_to = destination
        return result

    try:
        shutil.copy2(source_file, destination)
        result.copied_to = destination
        result.status = (
            STATUS_MULTIPLE if len(result.matched_files) > 1 else STATUS_COPIED
        )
    except OSError as exc:
        result.status = STATUS_ERROR
        result.detail = str(exc)

    return result


def run(
    names: list[str],
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    index: dict[str, list[Path]] | None = None,
) -> list[SearchResult]:
    """
    End-to-end: build (or reuse) an index of `source_dir`, match `names`
    against it, and copy every match into `output_dir`.
    """
    if index is None:
        index = build_file_index(source_dir)

    results = find_images(names, index)
    for result in results:
        if result.matched_files:
            copy_result(result, output_dir, overwrite=overwrite)
    return results


def _read_names_from_file(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8-sig")
    return [line.strip() for line in text.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Find and copy images by name.")
    parser.add_argument(
        "--names",
        required=True,
        help="Comma-separated names, or path to a .txt file with one name per line.",
    )
    parser.add_argument(
        "--source", default=DEFAULT_SOURCE_DIR, help="Source images folder."
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT_DIR, help="Destination folder."
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files in output."
    )
    args = parser.parse_args()

    names_arg = Path(args.names)
    if names_arg.suffix.lower() == ".txt" and names_arg.exists():
        names = _read_names_from_file(args.names)
    else:
        names = [n.strip() for n in args.names.split(",") if n.strip()]

    print(f"Indexing '{args.source}' ...")
    start = time.time()
    index = build_file_index(args.source)
    print(
        f"Indexed {sum(len(v) for v in index.values())} image files in {time.time() - start:.1f}s"
    )

    results = run(
        names, args.source, args.output, overwrite=args.overwrite, index=index
    )

    found = sum(
        1
        for r in results
        if r.status in (STATUS_COPIED, STATUS_MULTIPLE, STATUS_ALREADY_EXISTS)
    )
    not_found = sum(1 for r in results if r.status == STATUS_NOT_FOUND)
    errors = sum(1 for r in results if r.status == STATUS_ERROR)

    print(f"\n{'Name':40} {'Status':30} {'File'}")
    for r in results:
        file_str = str(r.copied_to or (r.matched_files[0] if r.matched_files else ""))
        print(f"{r.requested_name:40} {r.status:30} {file_str}")

    print(
        f"\nDone. Found/copied: {found}  Not found: {not_found}  Errors: {errors}  Total: {len(results)}"
    )
    return 0 if not_found == 0 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
