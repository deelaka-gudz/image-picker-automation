"""
Core logic for the Image Picker Automation tool.

Given a list of keywords/names, search a source folder (recursively) for
every image file whose name *contains* that keyword and copy all matches
into an output folder. Matching is always case-insensitive, e.g. "batman"
matches "batman_01.jpg", "key_batman_01.png" and "BATMAN_cover.PNG" alike.

Can be used as a library (import and call `run`) or as a standalone CLI:

    python automation.py --names names.txt
    python automation.py --names "batman,img001,product_photo_15"
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
STATUS_NOT_FOUND = "Not found"
STATUS_ERROR = "Error"


@dataclass
class FileOutcome:
    """What happened when copying one matched file."""

    source: Path
    destination: Path | None = None
    status: str = ""
    detail: str = ""


@dataclass
class SearchResult:
    requested_name: str
    status: str
    matched_files: list[Path] = field(default_factory=list)
    outcomes: list[FileOutcome] = field(default_factory=list)


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
) -> list[tuple[str, Path]]:
    """
    Walk `source_dir` recursively and return a flat list of
    (lowercase filename stem, path) for every image file found.

    Doing one full walk up front is far faster than re-scanning the folder
    once per requested name, especially over a network share.
    """
    extensions = extensions or IMAGE_EXTENSIONS
    source_path = resolve_path(source_dir)

    if not source_path.exists():
        raise FileNotFoundError(f"Source folder not found: {source_path}")

    index: list[tuple[str, Path]] = []
    for root, _dirs, files in os.walk(source_path):
        for filename in files:
            file_path = Path(root) / filename
            if file_path.suffix.lower() not in extensions:
                continue
            index.append((file_path.stem.strip().lower(), file_path))

    return index


def _lookup_key(name: str) -> str:
    """Normalize a requested keyword (case-insensitive, extension optional)."""
    stripped = name.strip()
    candidate = Path(stripped)
    if candidate.suffix.lower() in IMAGE_EXTENSIONS:
        return candidate.stem.strip().lower()
    return stripped.lower()


def find_images(
    names: list[str],
    index: list[tuple[str, Path]],
) -> list[SearchResult]:
    """
    Match requested keywords against a pre-built file index (no copying).
    A keyword matches any file whose name contains it, case-insensitively.
    """
    results: list[SearchResult] = []
    for raw_name in names:
        name = raw_name.strip()
        if not name:
            continue
        key = _lookup_key(name)
        matches = sorted(
            (path for stem, path in index if key in stem),
            key=lambda p: str(p).lower(),
        )
        status = "Found" if matches else STATUS_NOT_FOUND
        results.append(SearchResult(name, status, matches))
    return results


def copy_result(
    result: SearchResult,
    output_dir: str | Path,
    overwrite: bool = False,
) -> SearchResult:
    """Copy every file matched for this keyword into output_dir."""
    if not result.matched_files:
        result.status = STATUS_NOT_FOUND
        return result

    output_path = resolve_path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for source_file in result.matched_files:
        destination = output_path / source_file.name
        if destination.exists() and not overwrite:
            result.outcomes.append(
                FileOutcome(source_file, destination, STATUS_ALREADY_EXISTS)
            )
            continue
        try:
            shutil.copy2(source_file, destination)
            result.outcomes.append(FileOutcome(source_file, destination, STATUS_COPIED))
        except OSError as exc:
            result.outcomes.append(
                FileOutcome(source_file, None, STATUS_ERROR, str(exc))
            )

    statuses = {o.status for o in result.outcomes}
    if STATUS_ERROR in statuses:
        result.status = STATUS_ERROR
    elif statuses == {STATUS_ALREADY_EXISTS}:
        result.status = STATUS_ALREADY_EXISTS
    else:
        result.status = STATUS_COPIED

    return result


def run(
    names: list[str],
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    index: list[tuple[str, Path]] | None = None,
) -> list[SearchResult]:
    """
    End-to-end: build (or reuse) an index of `source_dir`, match `names`
    against it (by substring, case-insensitive), and copy every match into
    `output_dir`.
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
    parser = argparse.ArgumentParser(description="Find and copy images by keyword.")
    parser.add_argument(
        "--names",
        required=True,
        help="Comma-separated keywords, or path to a .txt file with one keyword per line.",
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
    print(f"Indexed {len(index)} image files in {time.time() - start:.1f}s")

    results = run(
        names, args.source, args.output, overwrite=args.overwrite, index=index
    )

    found = sum(
        1 for r in results if r.status in (STATUS_COPIED, STATUS_ALREADY_EXISTS)
    )
    not_found = sum(1 for r in results if r.status == STATUS_NOT_FOUND)
    errors = sum(1 for r in results if r.status == STATUS_ERROR)

    print(f"\n{'Keyword':30} {'Status':20} {'Matched files'}")
    for r in results:
        files_str = (
            ", ".join(f.name for f in r.matched_files) if r.matched_files else ""
        )
        print(f"{r.requested_name:30} {r.status:20} {files_str}")

    print(
        f"\nDone. Found/copied: {found}  Not found: {not_found}  Errors: {errors}  "
        f"Total keywords: {len(results)}"
    )
    return 0 if not_found == 0 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
