from __future__ import annotations

import os
from pathlib import Path

SITE_REPO_ROOT = Path(__file__).resolve().parents[2]
BOOK_SOURCE_DIR_ENV = "BOOK_SOURCE_DIR"


def default_book_source_dir() -> Path:
    override = os.environ.get(BOOK_SOURCE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return SITE_REPO_ROOT.parent / "broad-listening-book"


def default_site_output_dir() -> Path:
    return SITE_REPO_ROOT / "site"
