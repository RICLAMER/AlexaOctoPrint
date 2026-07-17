from __future__ import annotations

from typing import Any, Dict


GITHUB_USER = "RICLAMER"
GITHUB_REPOSITORY = "AlexaOctoPrint"
RELEASE_ARCHIVE_URL = (
    "https://github.com/RICLAMER/AlexaOctoPrint/archive/{target_version}.zip"
)


def build_update_information(
    identifier: str,
    display_name: str,
    current_version: str,
) -> Dict[str, Any]:
    return {
        identifier: {
            "displayName": display_name,
            "displayVersion": current_version,
            "type": "github_release",
            "user": GITHUB_USER,
            "repo": GITHUB_REPOSITORY,
            "current": current_version,
            "pip": RELEASE_ARCHIVE_URL,
        }
    }
