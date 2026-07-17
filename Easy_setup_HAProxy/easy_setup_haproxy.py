#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "Source"
sys.path.insert(0, str(SOURCE_DIRECTORY))

from octoprint_alexaoctoprint.haproxy_setup import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
