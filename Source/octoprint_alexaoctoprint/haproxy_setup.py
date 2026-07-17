from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


CONFIG_PATH = Path("/etc/haproxy/haproxy.cfg")
STATE_DIR = Path("/var/lib/alexaoctoprint-haproxy")
STATE_PATH = STATE_DIR / "state.json"
WEB_HELPER_PATH = Path("/usr/local/sbin/alexaoctoprint-haproxy")
SUDOERS_PATH = Path("/etc/sudoers.d/alexaoctoprint-haproxy")
FRONTEND_BEGIN = "        # BEGIN Alexa OctoPrint managed routes"
FRONTEND_END = "        # END Alexa OctoPrint managed routes"
BACKEND_BEGIN = "# BEGIN Alexa OctoPrint managed backend"
BACKEND_END = "# END Alexa OctoPrint managed backend"
SECTION_PATTERN = re.compile(r"^(global|defaults|frontend|backend|listen|peers|resolvers)\b")
LEGACY_BACKEND_PATTERN = re.compile(r"^backend\s+alexaoctoprint_hue\s*$", re.IGNORECASE)
PORT_80_BIND_PATTERN = re.compile(r"(?:^|\s)(?:\[[^\]]+\]|[^ ]*):80(?:\s|$)")
MANAGED_USERNAME_PATTERN = r"[0-9a-fA-F]{40}"


def _run(
    command: List[str],
    timeout: int = 300,
    check: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json_atomic(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(str(path.parent), 0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, str(path))
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _service_property(property_name: str) -> str:
    result = _run(
        ["systemctl", "show", "haproxy", "-p", property_name, "--value"],
        timeout=15,
    )
    return (result.stdout or "").strip()


def _port_80_listener() -> Dict[str, str]:
    if shutil.which("ss") is None:
        return {}
    result = _run(["ss", "-H", "-ltnp"], timeout=15)
    for line in (result.stdout or "").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        local_address = fields[3]
        if local_address.endswith(":80") or local_address.endswith("]:80"):
            process_match = re.search(r'users:\(\("([^"]+)"', line)
            return {
                "address": local_address,
                "process": process_match.group(1) if process_match else "unknown",
                "raw": line.strip(),
            }
    return {}


def _description_is_reachable() -> bool:
    request = urllib.request.Request(
        "http://127.0.0.1/description.xml",
        headers={"User-Agent": "AlexaOctoPrint-Setup/0.2.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            body = response.read(65536).decode("utf-8", "replace")
    except Exception:
        return False
    return (
        response.status == 200
        and "<modelName>Philips hue bridge 2012</modelName>" in body
    )


def _config_text(path: Path = CONFIG_PATH) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _has_managed_routes(config: str) -> bool:
    return FRONTEND_BEGIN in config and BACKEND_BEGIN in config


def _has_legacy_routes(config: str) -> bool:
    return "alexaoctoprint_hue" in config.lower()


def inspect_status(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    listener = _port_80_listener()
    config = _config_text(config_path)
    haproxy_installed = shutil.which("haproxy") is not None
    listener_process = str(listener.get("process") or "")
    route_reachable = _description_is_reachable() if listener else False
    managed = _has_managed_routes(config)
    legacy = _has_legacy_routes(config) and not managed
    conflict = bool(
        listener
        and listener_process not in ("haproxy", "unknown")
        and not route_reachable
    )

    if managed and route_reachable:
        status = "ready"
        message = "Port 80 and Alexa OctoPrint routes are ready."
    elif legacy:
        status = "legacy_routes"
        message = "Legacy Alexa OctoPrint HAProxy routes were found and can be upgraded."
    elif route_reachable and listener_process != "haproxy":
        status = "external_proxy_ready"
        message = "An existing port 80 service already exposes the Alexa OctoPrint description."
    elif conflict:
        status = "port_conflict"
        message = (
            "Port 80 is owned by {}. It was not changed; configure that service "
            "with equivalent Alexa OctoPrint routes."
        ).format(listener_process)
    elif listener_process == "haproxy":
        status = "routes_required"
        message = "HAProxy owns port 80, but Alexa OctoPrint routes are not ready."
    elif not listener:
        status = "proxy_required"
        message = "Port 80 is free; a local reverse proxy is required for Alexa discovery."
    else:
        status = "inspection_required"
        message = "Port 80 routing requires manual inspection."

    return {
        "ok": not conflict,
        "status": status,
        "message": message,
        "port_80": listener,
        "haproxy_installed": haproxy_installed,
        "haproxy_active": _service_property("ActiveState") == "active" if haproxy_installed else False,
        "managed_routes": managed,
        "legacy_routes": legacy,
        "description_reachable": route_reachable,
        "state_file": str(STATE_PATH),
        "rollback_available": STATE_PATH.exists(),
    }


def _strip_marked_block(lines: Iterable[str], begin: str, end: str) -> List[str]:
    result: List[str] = []
    inside = False
    for line in lines:
        if line.rstrip("\r\n") == begin:
            inside = True
            continue
        if inside and line.rstrip("\r\n") == end:
            inside = False
            continue
        if not inside:
            result.append(line)
    return result


def _strip_legacy_routes(lines: List[str]) -> List[str]:
    result: List[str] = []
    skip_backend = False
    for line in lines:
        stripped = line.strip()
        if LEGACY_BACKEND_PATTERN.match(stripped):
            skip_backend = True
            continue
        if skip_backend:
            if SECTION_PATTERN.match(line):
                skip_backend = False
            else:
                continue
        if "alexaoctoprint_" in line.lower():
            continue
        result.append(line)
    return result


def remove_alexaoctoprint_routes(config: str, include_legacy: bool = True) -> str:
    lines = config.splitlines(keepends=True)
    lines = _strip_marked_block(lines, FRONTEND_BEGIN, FRONTEND_END)
    lines = _strip_marked_block(lines, BACKEND_BEGIN, BACKEND_END)
    if include_legacy:
        lines = _strip_legacy_routes(lines)
    return "".join(lines).rstrip() + "\n"


def _section_ranges(lines: List[str]) -> List[Tuple[int, int, str]]:
    starts: List[Tuple[int, str]] = []
    for index, line in enumerate(lines):
        if SECTION_PATTERN.match(line):
            starts.append((index, line.strip()))
    ranges: List[Tuple[int, int, str]] = []
    for position, (start, name) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        ranges.append((start, end, name))
    return ranges


def _find_port_80_frontend(lines: List[str]) -> Tuple[int, int, str]:
    for start, end, name in _section_ranges(lines):
        if not (name.startswith("frontend ") or name.startswith("listen ")):
            continue
        for line in lines[start + 1 : end]:
            stripped = line.strip()
            if stripped.startswith("bind ") and PORT_80_BIND_PATTERN.search(stripped):
                return start, end, name
    raise RuntimeError("No HAProxy frontend or listen section bound to TCP port 80 was found")


def _managed_frontend_lines() -> List[str]:
    username = MANAGED_USERNAME_PATTERN
    return [
        FRONTEND_BEGIN + "\n",
        "        acl alexaoctoprint_description path -i /description.xml\n",
        "        acl alexaoctoprint_api_root path -i /api\n",
        f"        acl alexaoctoprint_api_user path_reg -i ^/api/{username}/?$\n",
        (
            "        acl alexaoctoprint_lights path_reg -i "
            f"^/api/{username}/lights(/[0-9]+(/state)?)?/?$\n"
        ),
        "        acl alexaoctoprint_get method GET\n",
        "        acl alexaoctoprint_post method POST\n",
        "        acl alexaoctoprint_state_write method PUT POST\n",
        "        use_backend alexaoctoprint_hue if alexaoctoprint_description alexaoctoprint_get\n",
        "        use_backend alexaoctoprint_hue if alexaoctoprint_api_root alexaoctoprint_post\n",
        "        use_backend alexaoctoprint_hue if alexaoctoprint_api_user alexaoctoprint_get\n",
        "        use_backend alexaoctoprint_hue if alexaoctoprint_lights alexaoctoprint_get\n",
        "        use_backend alexaoctoprint_hue if alexaoctoprint_lights alexaoctoprint_state_write\n",
        FRONTEND_END + "\n",
    ]


def _managed_backend_lines(octoprint_port: int) -> List[str]:
    return [
        "\n",
        BACKEND_BEGIN + "\n",
        "backend alexaoctoprint_hue\n",
        "        http-request set-header X-AlexaOctoPrint-Original-Path %[path]\n",
        "        http-request set-path /plugin/alexaoctoprint%[path]\n",
        "        option forwardfor\n",
        f"        server alexaoctoprint 127.0.0.1:{octoprint_port}\n",
        BACKEND_END + "\n",
    ]


def build_managed_config(config: str, octoprint_port: int = 5000) -> str:
    if not 1 <= int(octoprint_port) <= 65535:
        raise ValueError("OctoPrint port must be between 1 and 65535")
    clean = remove_alexaoctoprint_routes(config, include_legacy=True)
    lines = clean.splitlines(keepends=True)
    _start, end, _name = _find_port_80_frontend(lines)
    lines[end:end] = _managed_frontend_lines()
    lines.extend(_managed_backend_lines(int(octoprint_port)))
    return "".join(lines).rstrip() + "\n"


def _detect_octoprint_port() -> int:
    result = _run(
        ["systemctl", "show", "octoprint", "-p", "Environment", "--value"],
        timeout=15,
    )
    match = re.search(r"(?:^|\s)PORT=(\d+)(?:\s|$)", result.stdout or "")
    if match:
        return int(match.group(1))

    if shutil.which("ss"):
        listeners = _run(["ss", "-H", "-ltnp"], timeout=15).stdout or ""
        for line in listeners.splitlines():
            if "octoprint" not in line.lower():
                continue
            match = re.search(r":(\d+)\s", line)
            if match:
                return int(match.group(1))
    return 5000


def _require_root() -> Optional[Dict[str, Any]]:
    if not hasattr(os, "geteuid") or os.geteuid() == 0:
        return None
    return {
        "ok": False,
        "status": "permission_required",
        "error": (
            "Root permission is required. Run this setup through SSH with sudo, "
            "or allow the OctoPrint service account to execute this fixed helper."
        ),
        "ssh_required": True,
    }


def _install_haproxy_package() -> Optional[str]:
    update = _run(["apt-get", "update"], timeout=600)
    if update.returncode != 0:
        return (update.stderr or update.stdout or "apt-get update failed").strip()
    install = _run(
        ["apt-get", "install", "-y", "haproxy"],
        timeout=600,
    )
    if install.returncode != 0:
        return (install.stderr or install.stdout or "HAProxy installation failed").strip()
    return None


def _validate_config(path: Path) -> Optional[str]:
    result = _run(["haproxy", "-c", "-f", str(path)], timeout=30)
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout or "HAProxy validation failed").strip()


def _write_config_atomic(path: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".alexaoctoprint.",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, str(path))
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _write_file_atomic(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".alexaoctoprint.",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, str(path))
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _restart_haproxy() -> Optional[str]:
    result = _run(["systemctl", "restart", "haproxy"], timeout=60)
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout or "Could not restart HAProxy").strip()


def install_routes(
    octoprint_port: Optional[int] = None,
    config_path: Path = CONFIG_PATH,
) -> Dict[str, Any]:
    permission_error = _require_root()
    if permission_error:
        return permission_error

    before = inspect_status(config_path)
    listener = before.get("port_80") or {}
    listener_process = str(listener.get("process") or "")
    if listener and listener_process not in ("haproxy", "unknown"):
        if before.get("description_reachable"):
            return {
                **before,
                "ok": True,
                "changed": False,
                "message": "Existing port 80 routing already exposes Alexa OctoPrint; HAProxy was not changed.",
            }
        return {
            **before,
            "ok": False,
            "changed": False,
            "error": "Port 80 is occupied by {}; no process was stopped.".format(listener_process),
        }

    haproxy_preexisting = shutil.which("haproxy") is not None
    service_active_before = _service_property("ActiveState") == "active" if haproxy_preexisting else False
    service_enabled_before = _service_property("UnitFileState") == "enabled" if haproxy_preexisting else False
    if not haproxy_preexisting:
        package_error = _install_haproxy_package()
        if package_error:
            return {
                "ok": False,
                "status": "package_install_failed",
                "changed": False,
                "error": package_error,
            }

    if not config_path.exists():
        return {
            "ok": False,
            "status": "config_missing",
            "changed": False,
            "error": f"HAProxy configuration was not found at {config_path}",
        }

    port = int(octoprint_port or _detect_octoprint_port())
    if port == 80:
        return {
            "ok": False,
            "status": "octoprint_uses_port_80",
            "changed": False,
            "error": (
                "OctoPrint is configured on port 80. Move OctoPrint to an internal "
                "port such as 5000 before installing the reverse-proxy routes."
            ),
        }

    current_bytes = config_path.read_bytes()
    current_text = current_bytes.decode("utf-8")
    state = _read_json(STATE_PATH)
    if state and Path(str(state.get("backup_path") or "")).exists():
        backup_path = Path(str(state["backup_path"]))
        original_sha256 = str(state.get("original_sha256") or "")
        first_install_time = str(state.get("installed_at") or "")
        original_haproxy_preexisting = bool(state.get("haproxy_preexisting", True))
        original_service_active = bool(state.get("service_active_before", True))
        original_service_enabled = bool(state.get("service_enabled_before", True))
    else:
        clean_original = remove_alexaoctoprint_routes(current_text, include_legacy=True).encode("utf-8")
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(str(STATE_DIR), 0o700)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = STATE_DIR / f"haproxy.cfg.before-alexaoctoprint.{stamp}"
        backup_path.write_bytes(clean_original)
        os.chmod(str(backup_path), 0o600)
        original_sha256 = _sha256(clean_original)
        first_install_time = datetime.now(timezone.utc).isoformat()
        original_haproxy_preexisting = haproxy_preexisting
        original_service_active = service_active_before
        original_service_enabled = service_enabled_before

    try:
        managed_text = build_managed_config(current_text, port)
    except (RuntimeError, ValueError, UnicodeDecodeError) as exc:
        return {
            "ok": False,
            "status": "config_unsupported",
            "changed": False,
            "error": str(exc),
            "backup_path": str(backup_path),
        }

    managed_bytes = managed_text.encode("utf-8")
    descriptor, validation_name = tempfile.mkstemp(
        prefix="haproxy.cfg.validate.",
        dir=str(config_path.parent),
    )
    os.close(descriptor)
    validation_path = Path(validation_name)
    try:
        validation_path.write_bytes(managed_bytes)
        validation_error = _validate_config(validation_path)
    finally:
        _unlink_if_exists(validation_path)
    if validation_error:
        return {
            "ok": False,
            "status": "validation_failed",
            "changed": False,
            "error": validation_error,
            "backup_path": str(backup_path),
        }

    _write_config_atomic(config_path, managed_bytes)
    restart_error = _restart_haproxy()
    if restart_error:
        _write_config_atomic(config_path, current_bytes)
        _restart_haproxy()
        return {
            "ok": False,
            "status": "restart_failed",
            "changed": False,
            "error": restart_error,
            "rolled_back": True,
        }

    _run(["systemctl", "enable", "haproxy"], timeout=30)
    state = {
        "schema": 1,
        "installed_at": first_install_time,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "backup_path": str(backup_path),
        "original_sha256": original_sha256,
        "installed_sha256": _sha256(managed_bytes),
        "haproxy_preexisting": original_haproxy_preexisting,
        "service_active_before": original_service_active,
        "service_enabled_before": original_service_enabled,
        "octoprint_port": port,
    }
    _write_json_atomic(STATE_PATH, state)
    return {
        "ok": True,
        "status": "installed",
        "changed": managed_bytes != current_bytes,
        "message": (
            "Alexa OctoPrint routes were installed and HAProxy passed validation. "
            "Existing non-plugin routes were preserved."
        ),
        "backup_path": str(backup_path),
        "octoprint_port": port,
    }


def remove_routes(
    config_path: Path = CONFIG_PATH,
    purge_installed_package: bool = False,
) -> Dict[str, Any]:
    permission_error = _require_root()
    if permission_error:
        return permission_error
    if not config_path.exists():
        return {
            "ok": False,
            "status": "config_missing",
            "error": f"HAProxy configuration was not found at {config_path}",
        }

    state = _read_json(STATE_PATH)
    current_bytes = config_path.read_bytes()
    current_text = current_bytes.decode("utf-8")
    if not state and not _has_legacy_routes(current_text):
        return {
            "ok": True,
            "status": "not_installed",
            "changed": False,
            "message": "No Alexa OctoPrint HAProxy routes were found.",
        }

    backup_path = Path(str(state.get("backup_path") or "")) if state else None
    exact_restore = bool(
        state
        and backup_path
        and backup_path.exists()
        and _sha256(current_bytes) == str(state.get("installed_sha256") or "")
    )
    if exact_restore:
        restored_bytes = backup_path.read_bytes()
    else:
        restored_bytes = remove_alexaoctoprint_routes(
            current_text,
            include_legacy=True,
        ).encode("utf-8")

    descriptor, validation_name = tempfile.mkstemp(
        prefix="haproxy.cfg.restore.",
        dir=str(config_path.parent),
    )
    os.close(descriptor)
    validation_path = Path(validation_name)
    try:
        validation_path.write_bytes(restored_bytes)
        validation_error = _validate_config(validation_path)
    finally:
        _unlink_if_exists(validation_path)
    if validation_error:
        return {
            "ok": False,
            "status": "restore_validation_failed",
            "changed": False,
            "error": validation_error,
        }

    _write_config_atomic(config_path, restored_bytes)
    restart_error = _restart_haproxy()
    if restart_error:
        _write_config_atomic(config_path, current_bytes)
        _restart_haproxy()
        return {
            "ok": False,
            "status": "restore_restart_failed",
            "changed": False,
            "error": restart_error,
            "rolled_back": True,
        }

    package_removed = False
    if state:
        if not bool(state.get("service_enabled_before", True)):
            _run(["systemctl", "disable", "haproxy"], timeout=30)
        if not bool(state.get("service_active_before", True)):
            _run(["systemctl", "stop", "haproxy"], timeout=30)
        if purge_installed_package and not bool(state.get("haproxy_preexisting", True)):
            purge = _run(["apt-get", "purge", "-y", "haproxy"], timeout=600)
            package_removed = purge.returncode == 0
        _unlink_if_exists(STATE_PATH)

    return {
        "ok": True,
        "status": "removed",
        "changed": restored_bytes != current_bytes,
        "message": (
            "Alexa OctoPrint routes were removed. "
            + ("The exact saved configuration was restored." if exact_restore else "Later HAProxy changes were preserved.")
        ),
        "exact_restore": exact_restore,
        "package_removed": package_removed,
    }


def enable_web_helper(
    service_user: str,
    python_executable: Optional[str] = None,
) -> Dict[str, Any]:
    permission_error = _require_root()
    if permission_error:
        return permission_error
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", service_user or ""):
        return {
            "ok": False,
            "status": "invalid_service_user",
            "error": "The OctoPrint service user name is invalid.",
        }

    default_venv_python = Path("/home") / service_user / "oprint" / "bin" / "python3"
    executable = Path(
        python_executable
        or (str(default_venv_python) if default_venv_python.exists() else sys.executable)
    ).resolve()
    if not executable.is_file():
        return {
            "ok": False,
            "status": "python_missing",
            "error": f"Python executable was not found at {executable}",
        }

    quoted_python = shlex.quote(str(executable))
    helper = (
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  status|install|remove)\n"
        f"    exec {quoted_python} -m octoprint_alexaoctoprint.haproxy_setup \"$1\" --json --yes\n"
        "    ;;\n"
        "  *)\n"
        "    echo '{\"ok\":false,\"status\":\"invalid_command\",\"error\":\"Unsupported command\"}'\n"
        "    exit 2\n"
        "    ;;\n"
        "esac\n"
    ).encode("utf-8")
    sudoers = (
        f"{service_user} ALL=(root) NOPASSWD: {WEB_HELPER_PATH} status\n"
        f"{service_user} ALL=(root) NOPASSWD: {WEB_HELPER_PATH} install\n"
        f"{service_user} ALL=(root) NOPASSWD: {WEB_HELPER_PATH} remove\n"
    ).encode("utf-8")

    _write_file_atomic(WEB_HELPER_PATH, helper, 0o755)
    descriptor, validation_name = tempfile.mkstemp(
        prefix="alexaoctoprint-sudoers.",
        dir=str(SUDOERS_PATH.parent),
    )
    os.close(descriptor)
    validation_path = Path(validation_name)
    try:
        validation_path.write_bytes(sudoers)
        os.chmod(str(validation_path), 0o440)
        validation = _run(["visudo", "-cf", str(validation_path)], timeout=15)
        if validation.returncode != 0:
            _unlink_if_exists(WEB_HELPER_PATH)
            return {
                "ok": False,
                "status": "sudoers_validation_failed",
                "error": (validation.stderr or validation.stdout or "visudo validation failed").strip(),
            }
        os.replace(str(validation_path), str(SUDOERS_PATH))
    finally:
        _unlink_if_exists(validation_path)

    return {
        "ok": True,
        "status": "web_helper_enabled",
        "changed": True,
        "message": (
            "The OctoPrint web panel may now run only the fixed HAProxy "
            "status, install, and remove commands."
        ),
        "helper": str(WEB_HELPER_PATH),
        "service_user": service_user,
        "python": str(executable),
    }


def disable_web_helper() -> Dict[str, Any]:
    permission_error = _require_root()
    if permission_error:
        return permission_error
    changed = WEB_HELPER_PATH.exists() or SUDOERS_PATH.exists()
    _unlink_if_exists(SUDOERS_PATH)
    _unlink_if_exists(WEB_HELPER_PATH)
    return {
        "ok": True,
        "status": "web_helper_disabled",
        "changed": changed,
        "message": "The Alexa OctoPrint HAProxy web helper was removed.",
    }


def _print_result(result: Dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return
    print(result.get("message") or result.get("error") or result.get("status") or "Done")
    print(json.dumps(result, indent=2, sort_keys=True))


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    answer = input(prompt + " [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install, inspect, or remove Alexa OctoPrint HAProxy routes.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("status", "install", "remove", "enable-web", "disable-web"),
    )
    parser.add_argument("--octoprint-port", type=int)
    parser.add_argument("--purge-installed-package", action="store_true")
    parser.add_argument("--service-user", default="pi")
    parser.add_argument("--python-executable")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)

    command = arguments.command
    if command is None:
        _print_result(inspect_status(), False)
        print("\n1. Install or update routes\n2. Remove routes\n3. Exit")
        choice = input("Choose an option: ").strip()
        command = {"1": "install", "2": "remove"}.get(choice, "status")
        if choice not in ("1", "2"):
            return 0

    if command == "status":
        result = inspect_status()
    elif command == "install":
        if not _confirm(
            "Back up HAProxy, add the restricted Alexa OctoPrint routes, validate, and restart the service?",
            arguments.yes,
        ):
            result = {"ok": False, "status": "cancelled", "message": "No changes were made."}
        else:
            result = install_routes(arguments.octoprint_port)
    elif command == "remove":
        if not _confirm(
            "Restore the HAProxy configuration saved before Alexa OctoPrint setup?",
            arguments.yes,
        ):
            result = {"ok": False, "status": "cancelled", "message": "No changes were made."}
        else:
            result = remove_routes(
                purge_installed_package=arguments.purge_installed_package,
            )
    elif command == "enable-web":
        if not _confirm(
            "Install a root-owned helper limited to HAProxy status, install, and remove commands?",
            arguments.yes,
        ):
            result = {"ok": False, "status": "cancelled", "message": "No changes were made."}
        else:
            result = enable_web_helper(
                service_user=arguments.service_user,
                python_executable=arguments.python_executable,
            )
    else:
        result = disable_web_helper()

    _print_result(result, arguments.json)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
