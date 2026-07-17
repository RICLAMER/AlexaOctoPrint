from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional


ALLOWED_COMMANDS = ("status", "install", "remove")
WEB_HELPER = "/usr/local/sbin/alexaoctoprint-haproxy"


def run_proxy_command(
    command: str,
    logger: Optional[Any] = None,
    timeout: int = 180,
) -> Dict[str, Any]:
    if command not in ALLOWED_COMMANDS:
        return {"ok": False, "error": "Unsupported HAProxy setup command"}

    if os.path.isfile(WEB_HELPER):
        module_command = ["sudo", "-n", WEB_HELPER, command]
    else:
        module_command = [
            sys.executable,
            "-m",
            "octoprint_alexaoctoprint.haproxy_setup",
            command,
            "--json",
            "--yes",
        ]
        if command != "status" and hasattr(os, "geteuid") and os.geteuid() != 0:
            module_command = ["sudo", "-n"] + module_command

    try:
        completed = subprocess.run(
            module_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "status": "helper_unavailable",
            "error": str(exc),
            "ssh_required": True,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "timeout",
            "error": "HAProxy setup command timed out",
        }

    output = (completed.stdout or "").strip()
    error_output = (completed.stderr or "").strip()
    for line in reversed(output.splitlines()):
        try:
            result = json.loads(line)
        except ValueError:
            continue
        if isinstance(result, dict):
            result.setdefault("returncode", completed.returncode)
            return result

    if logger is not None and error_output:
        logger.warning("HAProxy setup helper failed: %s", error_output)
    return {
        "ok": False,
        "status": "permission_required" if completed.returncode == 1 else "helper_failed",
        "error": error_output or output or "HAProxy setup helper returned no result",
        "returncode": completed.returncode,
        "ssh_required": "password" in error_output.lower() or "sudo" in error_output.lower(),
    }
