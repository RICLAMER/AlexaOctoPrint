from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

import octoprint.plugin
from flask import Response, jsonify, request
from octoprint.server.util.flask import restricted_access

try:
    from octoprint.events import Events
except Exception:  # pragma: no cover - only used when OctoPrint is unavailable
    Events = None

from .actions import (
    ACTION_DEFINITIONS,
    action_name,
    action_settings,
    action_supports_off,
    build_gcode_for_action,
    enabled_action_keys,
    get_default_settings,
    list_action_metadata,
    migrate_stored_settings,
    merged_settings,
    validate_action_key,
)
from .debug import DebugEventLog
from .device_state import HueDeviceStateStore
from .enclosure import find_output_by_label, hardware_value, list_output_labels
from .hue import (
    build_identity,
    decode_light_key,
    description_xml,
    generate_hue_username,
    hue_base_url,
    lights_payload,
    location_url,
    resolve_advertised_host,
    sanitize_hue_path,
    success_response,
    unauthorized_response,
    username_matches,
    username_response,
    valid_hue_username,
)
from .proxy import run_proxy_command
from .ssdp import SSDPResponder
from .update import build_update_information


ACTION_STATE_HOLD_SECONDS = 5.0
CANCEL_ARM_SECONDS = 15


class AlexaOctoPrintPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    def __init__(self) -> None:
        self._identity = build_identity()
        self._ssdp: Optional[SSDPResponder] = None
        self._events = DebugEventLog()
        self._device_states = HueDeviceStateStore()
        self._cancel_armed_until = 0.0
        self._hue_username = ""
        self._hue_http_lock = threading.Lock()
        self._hue_http: Dict[str, Any] = {
            "total": 0,
            "description": 0,
            "api_root": 0,
            "api_user": 0,
            "lights": 0,
            "light": 0,
            "state": 0,
            "last_at": None,
            "last_stage": "",
            "last_remote": "",
            "last_method": "",
            "last_path": "",
            "last_user_agent": "",
        }

    def get_settings_defaults(self) -> Dict[str, Any]:
        return get_default_settings()

    def get_template_configs(self) -> List[Dict[str, Any]]:
        return [dict(type="settings", custom_bindings=True)]

    def is_template_autoescaped(self) -> bool:
        return True

    def get_assets(self) -> Dict[str, List[str]]:
        return {
            "js": ["js/alexaoctoprint.js"],
            "css": ["css/alexaoctoprint.css"],
        }

    def get_update_information(self) -> Dict[str, Any]:
        return build_update_information(
            identifier=self._identifier,
            display_name=self._plugin_name,
            current_version=self._plugin_version,
        )

    def get_api_commands(self) -> Dict[str, List[str]]:
        return {
            "debug_status": [],
            "list_files": [],
            "list_enclosure_outputs": [],
            "run_action": ["action"],
            "proxy_status": [],
            "proxy_install": [],
            "proxy_remove": [],
        }

    def is_blueprint_protected(self) -> bool:
        # Alexa cannot authenticate against OctoPrint, so Hue-compatible routes
        # must be public on the LAN. The routes below do not expose API keys.
        return False

    def on_after_startup(self) -> None:
        self._migrate_and_initialize_settings()
        self._refresh_runtime()
        self._start_or_stop_ssdp()
        self._record(
            "startup",
            "Alexa OctoPrint plugin started",
            location=self._description_location(),
        )
        self._logger.info("Alexa OctoPrint started. Hue description: %s", self._description_location())

    def on_shutdown(self) -> None:
        self._stop_ssdp()
        self._device_states.close()
        self._record("shutdown", "Alexa OctoPrint plugin stopped")

    def on_settings_save(self, data: Dict[str, Any]) -> None:
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._migrate_and_initialize_settings()
        self._refresh_runtime()
        self._start_or_stop_ssdp(restart=True)
        self._record("settings", "Settings saved", location=self._description_location())

    def on_event(self, event: str, payload: Dict[str, Any]) -> None:
        if not payload:
            return

        selected_event = getattr(Events, "FILE_SELECTED", "FileSelected") if Events else "FileSelected"
        started_event = getattr(Events, "PRINT_STARTED", "PrintStarted") if Events else "PrintStarted"
        if event not in (selected_event, started_event):
            return

        path = payload.get("path") or payload.get("file")
        if not path:
            return

        origin = payload.get("origin") or "local"
        self._settings.set(["runtime", "last_file_path"], path)
        self._settings.set(["runtime", "last_file_origin"], origin)
        self._settings.save()
        self._record("runtime", "Last file updated", path=path, origin=origin, event=event)

    def on_api_get(self):
        return jsonify(self._debug_snapshot())

    def on_api_command(self, command: str, data: Dict[str, Any]):
        if command == "debug_status":
            return jsonify(self._debug_snapshot())

        if command == "list_files":
            return jsonify({"files": self._list_files()})

        if command == "list_enclosure_outputs":
            return jsonify(self._enclosure_outputs_snapshot())

        if command == "run_action":
            action = str(data.get("action") or "")
            requested_on = bool(data.get("on", True))
            result = self._execute_action(
                action,
                source="debug_api",
                requested_on=requested_on,
            )
            return jsonify(result)

        if command in ("proxy_status", "proxy_install", "proxy_remove"):
            proxy_command = command.replace("proxy_", "", 1)
            result = run_proxy_command(proxy_command, logger=self._logger)
            self._record(
                "proxy",
                "HAProxy setup command completed",
                command=proxy_command,
                ok=bool(result.get("ok")),
                status=result.get("status"),
                error=result.get("error"),
            )
            return jsonify(result)

        return jsonify({"ok": False, "error": f"Unknown command: {command}"}), 400

    @octoprint.plugin.BlueprintPlugin.route("/description.xml", methods=["GET"])
    def hue_description(self):
        self._record_hue_request("description")
        return Response(description_xml(self._base_url(), self._identity), content_type="text/xml")

    @octoprint.plugin.BlueprintPlugin.route("/espalexa", methods=["GET"])
    def espalexa_status(self):
        snapshot = self._debug_snapshot(include_events=False)
        lines = [
            "Hello from AlexaOctoPrint!",
            "",
            f"Enabled: {snapshot['enabled']}",
            f"Language: {snapshot['language']}",
            f"Bridge ID: {snapshot['identity']['bridge_id']}",
            f"Description: {snapshot['location']}",
            "",
            "Devices:",
        ]
        for device in snapshot["devices"]:
            lines.append(f"- {device['id']} | {device['key']} | {device['name']}")
        lines.append("")
        lines.append(f"SSDP: {snapshot['ssdp']}")
        return Response("\r\n".join(lines), mimetype="text/plain")

    @octoprint.plugin.BlueprintPlugin.route("/debug/status", methods=["GET"])
    @restricted_access
    def debug_status(self):
        return jsonify(self._debug_snapshot())

    @octoprint.plugin.BlueprintPlugin.route("/api", methods=["GET", "POST"])
    def hue_api_root(self):
        self._record_hue_request("api_root")
        if request.method == "POST":
            return self._hue_json(username_response(self._hue_username))
        return self._hue_json({})

    @octoprint.plugin.BlueprintPlugin.route("/api/<username>", methods=["GET"])
    def hue_api_user(self, username: str):
        authorized = self._is_authorized_hue_username(username)
        self._record_hue_request("api_user", username_valid=authorized)
        if not authorized:
            return self._hue_json(unauthorized_response(request.path))
        return self._hue_json({"lights": lights_payload(self._identity, self._hue_devices())})

    @octoprint.plugin.BlueprintPlugin.route("/api/<username>/lights", methods=["GET"])
    def hue_lights(self, username: str):
        authorized = self._is_authorized_hue_username(username)
        self._record_hue_request("lights", username_valid=authorized)
        if not authorized:
            return self._hue_json(unauthorized_response(request.path))
        return self._hue_json(lights_payload(self._identity, self._hue_devices()))

    @octoprint.plugin.BlueprintPlugin.route("/api/<username>/lights/<light_id>", methods=["GET"])
    def hue_light(self, username: str, light_id: str):
        authorized = self._is_authorized_hue_username(username)
        self._record_hue_request("light", username_valid=authorized, light_id=light_id)
        if not authorized:
            return self._hue_json(unauthorized_response(request.path))
        devices = lights_payload(self._identity, self._hue_devices())
        return self._hue_json(devices.get(light_id, {}))

    @octoprint.plugin.BlueprintPlugin.route(
        "/api/<username>/lights/<light_id>/state",
        methods=["PUT", "POST"],
    )
    def hue_light_state(self, username: str, light_id: str):
        payload = request.get_json(silent=True) or {}
        authorized = self._is_authorized_hue_username(username)
        self._record_hue_request(
            "state",
            username_valid=authorized,
            light_id=light_id,
            payload=payload,
        )
        if not authorized:
            return self._hue_json(unauthorized_response(request.path))
        result = self._execute_light(light_id, source="alexa", payload=payload)
        if result.get("ok"):
            return self._hue_json(success_response(f"/lights/{light_id}/state/", True))
        return self._hue_json(
            [
                {
                    "error": {
                        "type": 901,
                        "address": f"/lights/{light_id}/state/on",
                        "description": str(result.get("error") or "Alexa OctoPrint action failed"),
                    }
                }
            ]
        )

    def _settings_snapshot(self) -> Dict[str, Any]:
        try:
            stored = self._settings.get_all_data(merged=True)
        except Exception:
            stored = {}
        return merged_settings(stored)

    def _migrate_and_initialize_settings(self) -> None:
        try:
            stored = self._settings.get_all_data(merged=False)
        except TypeError:
            stored = self._settings.get_all_data()
        except Exception:
            stored = {}

        original = dict(stored or {})
        migrated = migrate_stored_settings(original)
        network = migrated.setdefault("network", {})
        identity = build_identity(
            bridge_id=network.get("bridge_id"),
            uuid_value=network.get("uuid"),
        )
        network["bridge_id"] = identity.bridge_id
        network["uuid"] = identity.uuid
        if not valid_hue_username(network.get("hue_username")):
            network["hue_username"] = generate_hue_username()

        if migrated == original:
            return

        for key, value in migrated.items():
            self._settings.set([key], value)
        for key in original:
            if key not in migrated:
                try:
                    self._settings.remove([key])
                except Exception:
                    pass
        self._settings.save()
        self._logger.info("Alexa OctoPrint settings migrated to the current schema")

    def _refresh_runtime(self) -> None:
        settings = self._settings_snapshot()
        debug_settings = settings.get("debug") or {}
        self._events.resize(int(debug_settings.get("max_events") or 100))
        network = settings.get("network") or {}
        self._identity = build_identity(
            bridge_id=network.get("bridge_id"),
            uuid_value=network.get("uuid"),
        )
        self._hue_username = str(network.get("hue_username") or "")

    def _start_or_stop_ssdp(self, restart: bool = False) -> None:
        settings = self._settings_snapshot()
        enabled = bool(settings.get("enabled", True))

        if restart:
            self._stop_ssdp()

        if not enabled:
            self._stop_ssdp()
            return

        if self._ssdp and self._ssdp.snapshot().get("running"):
            return

        self._ssdp = SSDPResponder(
            logger=self._logger,
            get_location=self._description_location,
            get_identity=lambda: self._identity,
            bind_ip="0.0.0.0",
            on_response=self._on_ssdp_response,
        )
        self._ssdp.start()

    def _stop_ssdp(self) -> None:
        if self._ssdp:
            self._ssdp.stop()
            self._ssdp = None

    def _base_url(self) -> str:
        return hue_base_url(resolve_advertised_host(""), 80, "/")

    def _description_location(self) -> str:
        return location_url(resolve_advertised_host(""), 80, "/")

    def _hue_devices(self) -> List[Dict[str, Any]]:
        settings = self._settings_snapshot()
        devices: List[Dict[str, Any]] = []
        for key in enabled_action_keys(settings):
            devices.append({"key": key, "name": action_name(settings, key), "on": self._device_states.get(key)})
        return devices

    def _execute_light(self, light_id: str, source: str, payload: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        devices = self._hue_devices()
        index = decode_light_key(self._identity, light_id)
        if index is None or index >= len(devices):
            result = {"ok": False, "error": "Unknown light id", "light_id": light_id}
            self._record("action_error", result["error"], light_id=light_id, source=source)
            return result

        action_key = str(devices[index]["key"])
        requested_on = bool((payload or {}).get("on", True))
        if not requested_on and not action_supports_off(action_key):
            self._device_states.set(action_key, False)
            return self._ok(
                action_key,
                source,
                "Alexa action state reset",
                name=devices[index]["name"],
                on=False,
                executed=False,
            )

        result = self._execute_action(
            action_key,
            source=source,
            payload=payload,
            requested_on=requested_on,
        )
        if result.get("ok"):
            if action_supports_off(action_key):
                self._device_states.set(action_key, requested_on)
                result["on"] = requested_on
            else:
                self._device_states.set(
                    action_key,
                    True,
                    reset_after=ACTION_STATE_HOLD_SECONDS,
                )
                result["on"] = True
                result["state_reset_seconds"] = ACTION_STATE_HOLD_SECONDS
        return result

    def _execute_action(
        self,
        action_key: str,
        source: str,
        payload: Optional[Mapping[str, Any]] = None,
        requested_on: bool = True,
    ) -> Dict[str, Any]:
        try:
            validate_action_key(action_key)
        except KeyError as exc:
            return self._fail(action_key, source, str(exc))

        settings = self._settings_snapshot()
        definition = ACTION_DEFINITIONS[action_key]
        current = action_settings(settings, action_key)
        name = action_name(settings, action_key)

        if not current.get("enabled", False):
            return self._fail(action_key, source, "Action is disabled", name=name)
        if not requested_on and not definition.supports_off:
            return self._fail(
                action_key,
                source,
                "This action does not support an off command",
                name=name,
            )

        printer_state = self._printer_state()
        busy = bool(printer_state.get("printing") or printer_state.get("paused"))
        if busy and not current.get("allow_while_printing", False):
            return self._fail(
                action_key,
                source,
                "Action blocked while printer is printing or paused",
                name=name,
                printer_state=printer_state,
            )

        try:
            if definition.action_type == "pause":
                result = self._pause(action_key, source, name, printer_state)
            elif definition.action_type == "resume":
                result = self._resume(action_key, source, name, printer_state)
            elif definition.action_type == "cancel":
                result = self._cancel(settings, action_key, source, name, printer_state)
            elif definition.action_type == "print_last":
                result = self._print_last(settings, action_key, source, name, printer_state)
            elif definition.action_type == "print_file":
                result = self._print_configured_file(current, action_key, source, name, printer_state)
            elif definition.action_type == "enclosure_output":
                result = self._set_enclosure_output(
                    current,
                    action_key,
                    source,
                    name,
                    requested_on,
                )
            else:
                result = self._send_action_gcode(
                    settings,
                    action_key,
                    source,
                    name,
                    requested_on,
                )
        except Exception as exc:
            self._logger.exception("Alexa action failed: %s", action_key)
            return self._fail(action_key, source, str(exc), name=name)

        result["payload"] = dict(payload or {})
        result["requested_on"] = requested_on
        return result

    def _pause(self, action_key: str, source: str, name: str, printer_state: Mapping[str, Any]) -> Dict[str, Any]:
        if not printer_state.get("printing"):
            return self._fail(action_key, source, "Printer is not printing", name=name, printer_state=printer_state)
        self._printer.pause_print()
        return self._ok(action_key, source, "Print paused", name=name)

    def _resume(self, action_key: str, source: str, name: str, printer_state: Mapping[str, Any]) -> Dict[str, Any]:
        if not printer_state.get("paused"):
            return self._fail(action_key, source, "Printer is not paused", name=name, printer_state=printer_state)
        self._printer.resume_print()
        return self._ok(action_key, source, "Print resumed", name=name)

    def _cancel(
        self,
        settings: Mapping[str, Any],
        action_key: str,
        source: str,
        name: str,
        printer_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        if not (printer_state.get("printing") or printer_state.get("paused")):
            return self._fail(action_key, source, "Printer is not printing or paused", name=name)

        now = time.time()
        if self._cancel_armed_until < now:
            self._cancel_armed_until = now + CANCEL_ARM_SECONDS
            return self._ok(
                action_key,
                source,
                "Cancel armed. Repeat the command before the timeout to cancel.",
                name=name,
                armed_until=self._cancel_armed_until,
            )

        self._cancel_armed_until = 0
        self._printer.cancel_print()
        return self._ok(action_key, source, "Print cancelled", name=name)

    def _print_last(
        self,
        settings: Mapping[str, Any],
        action_key: str,
        source: str,
        name: str,
        printer_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        runtime = settings.get("runtime") or {}
        path = str(runtime.get("last_file_path") or "")
        origin = str(runtime.get("last_file_origin") or "local")
        if not path:
            return self._fail(action_key, source, "No last file is known yet", name=name)
        return self._print_file(path, origin, action_key, source, name, printer_state)

    def _print_configured_file(
        self,
        current: Mapping[str, Any],
        action_key: str,
        source: str,
        name: str,
        printer_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        path = str(current.get("file_path") or "")
        origin = str(current.get("file_origin") or "local")
        if not path:
            return self._fail(action_key, source, "No file configured for this action", name=name)
        return self._print_file(path, origin, action_key, source, name, printer_state)

    def _print_file(
        self,
        path: str,
        origin: str,
        action_key: str,
        source: str,
        name: str,
        printer_state: Mapping[str, Any],
    ) -> Dict[str, Any]:
        if printer_state.get("printing") or printer_state.get("paused"):
            return self._fail(action_key, source, "Printer is busy", name=name, printer_state=printer_state)
        if not printer_state.get("operational", False):
            return self._fail(action_key, source, "Printer is not operational", name=name, printer_state=printer_state)

        sd = origin.lower() in ("sd", "sdcard")
        try:
            self._printer.select_file(path, sd, printAfterSelect=True, user="alexaoctoprint")
        except TypeError:
            self._printer.select_file(path, sd, True)
        return self._ok(action_key, source, "File selected and print started", name=name, path=path, origin=origin)

    def _send_action_gcode(
        self,
        settings: Mapping[str, Any],
        action_key: str,
        source: str,
        name: str,
        requested_on: bool,
    ) -> Dict[str, Any]:
        commands = build_gcode_for_action(
            settings,
            action_key,
            requested_on=requested_on,
        )
        if not commands:
            return self._fail(action_key, source, "No G-code configured", name=name)
        self._printer.commands(commands)
        return self._ok(action_key, source, "G-code sent", name=name, commands=commands)

    def _set_enclosure_output(
        self,
        current: Mapping[str, Any],
        action_key: str,
        source: str,
        name: str,
        status: bool,
    ) -> Dict[str, Any]:
        label = str(current.get("enclosure_label") or "").strip()
        if not label:
            return self._fail(action_key, source, "No Enclosure output label configured", name=name)

        enclosure, enclosure_module, error = self._enclosure_plugin()
        if enclosure is None:
            return self._fail(
                action_key,
                source,
                error or "OctoPrint-Enclosure plugin is not loaded",
                name=name,
                label=label,
            )

        output = self._find_enclosure_output(enclosure, label)
        if output is None:
            return self._fail(action_key, source, "Enclosure output label not found", name=name, label=label)
        output_type = str(output.get("output_type") or "regular").strip().lower()
        if output_type != "regular":
            return self._fail(
                action_key,
                source,
                "Selected Enclosure Label is not a regular on/off output",
                name=name,
                label=label,
                output_type=output_type,
            )

        try:
            active_low = bool(output.get("active_low", False))
            write_value = hardware_value(status, active_low)
            to_int = getattr(enclosure, "to_int", int)
            if output.get("gpio_i2c_enabled", False) and hasattr(enclosure, "gpio_i2c_write"):
                enclosure.gpio_i2c_write(output, write_value)
            elif hasattr(enclosure, "write_gpio"):
                enclosure.write_gpio(to_int(output.get("gpio_pin")), write_value)
            else:
                return self._fail(
                    action_key,
                    source,
                    "Loaded Enclosure plugin does not expose output control helpers",
                    name=name,
                    label=label,
                )

            time.sleep(0.1)
            actual_status = self._read_enclosure_output_status(enclosure_module, enclosure, output)
            if actual_status is not None and actual_status != status:
                return self._fail(
                    action_key,
                    source,
                    "Enclosure output did not reach the requested state",
                    name=name,
                    label=label,
                    requested_status=status,
                    actual_status=actual_status,
                )
        except Exception as exc:
            return self._fail(action_key, source, str(exc), name=name, label=label)

        return self._ok(
            action_key,
            source,
            "Enclosure output changed",
            name=name,
            label=str(output.get("label") or label).strip(),
            output_index=output.get("index_id"),
            gpio_pin=output.get("gpio_pin"),
            status=status,
            actual_status=actual_status,
        )

    def _enclosure_plugin(self):
        manager = getattr(self, "_plugin_manager", None)
        if manager is None:
            return None, None, "OctoPrint plugin manager is unavailable"

        try:
            plugin_info = manager.get_plugin_info("enclosure")
        except Exception as exc:
            return None, None, f"Could not inspect OctoPrint-Enclosure: {exc}"

        if plugin_info is None:
            return None, None, "OctoPrint-Enclosure plugin is not installed"

        enclosure = getattr(plugin_info, "implementation", None)
        enclosure_module = getattr(plugin_info, "instance", None)
        if enclosure is None:
            return None, enclosure_module, "OctoPrint-Enclosure plugin is not enabled or loaded"
        return enclosure, enclosure_module, ""

    def _enclosure_outputs(self, enclosure: Any) -> List[Mapping[str, Any]]:
        outputs = getattr(enclosure, "rpi_outputs", None)
        if outputs is None:
            try:
                outputs = enclosure._settings.get(["rpi_outputs"])
            except Exception:
                outputs = []
        return [
            output
            for output in (outputs or [])
            if isinstance(output, Mapping)
        ]

    def _enclosure_outputs_snapshot(self) -> Dict[str, Any]:
        enclosure, _enclosure_module, error = self._enclosure_plugin()
        if enclosure is None:
            return {
                "available": False,
                "outputs": [],
                "error": error,
            }

        outputs = list_output_labels(self._enclosure_outputs(enclosure))
        return {
            "available": True,
            "outputs": outputs,
            "error": "" if outputs else "No Enclosure output Labels were found",
        }

    def _find_enclosure_output(self, enclosure: Any, label: str) -> Optional[Mapping[str, Any]]:
        return find_output_by_label(self._enclosure_outputs(enclosure), label)

    def _read_enclosure_output_status(
        self,
        enclosure_module: Any,
        enclosure: Any,
        output: Mapping[str, Any],
    ) -> Optional[bool]:
        active_low = bool(output.get("active_low", False))
        if output.get("gpio_i2c_enabled", False) and hasattr(enclosure, "gpio_i2c_input"):
            return bool(enclosure.gpio_i2c_input(output, active_low))

        reader = getattr(enclosure_module, "PinState_Boolean", None)
        if callable(reader):
            to_int = getattr(enclosure, "to_int", int)
            return bool(reader(to_int(output.get("gpio_pin")), active_low))
        return None

    def _printer_state(self) -> Dict[str, Any]:
        printer = getattr(self, "_printer", None)
        state = {
            "available": printer is not None,
            "operational": False,
            "printing": False,
            "paused": False,
            "error": False,
            "closed_or_error": False,
        }
        if printer is None:
            return state

        checks = {
            "operational": "is_operational",
            "printing": "is_printing",
            "paused": "is_paused",
            "error": "is_error",
            "closed_or_error": "is_closed_or_error",
        }
        for key, method_name in checks.items():
            method = getattr(printer, method_name, None)
            if callable(method):
                try:
                    state[key] = bool(method())
                except Exception:
                    state[key] = False
        return state

    def _list_files(self) -> List[Dict[str, Any]]:
        manager = getattr(self, "_file_manager", None)
        if manager is None:
            return []

        try:
            listing = manager.list_files(recursive=True)
        except TypeError:
            listing = manager.list_files()
        except Exception as exc:
            self._record("file_error", "Could not list files", error=str(exc))
            return []

        files: List[Dict[str, Any]] = []
        if isinstance(listing, Mapping):
            for origin, entries in listing.items():
                self._flatten_files(str(origin), entries, files)
        return files

    def _flatten_files(self, origin: str, entries: Any, files: List[Dict[str, Any]], inherited_path: str = "") -> None:
        if isinstance(entries, Mapping):
            for key, value in entries.items():
                if isinstance(value, Mapping):
                    entry = dict(value)
                    entry.setdefault("path", entry.get("name") or key)
                    self._flatten_file_entry(origin, entry, files)
                else:
                    path = f"{inherited_path}/{key}".strip("/")
                    self._flatten_files(origin, value, files, path)
        elif isinstance(entries, Iterable) and not isinstance(entries, (str, bytes)):
            for entry in entries:
                self._flatten_file_entry(origin, entry, files)

    def _flatten_file_entry(self, origin: str, entry: Any, files: List[Dict[str, Any]]) -> None:
        if not isinstance(entry, Mapping):
            return

        entry_type = str(entry.get("type") or "")
        path = str(entry.get("path") or entry.get("name") or "")
        name = str(entry.get("display") or entry.get("name") or path)
        lower_path = path.lower()

        if entry_type in ("machinecode", "gcode") or lower_path.endswith((".gcode", ".gco", ".g")):
            files.append({"origin": origin, "path": path, "name": name})

        children = entry.get("children") or entry.get("files")
        if children:
            self._flatten_files(origin, children, files, path)

    def _on_ssdp_response(self, event: Dict[str, object]) -> None:
        remote = str(event.get("remote") or "")
        location = str(event.get("location") or "")
        self._record("ssdp", "SSDP response sent to Echo", remote=remote, location=location)
        self._logger.info("Alexa SSDP response sent to %s with %s", remote, location)

    def _is_authorized_hue_username(self, username: str) -> bool:
        return username_matches(self._hue_username, username)

    def _hue_json(self, payload: Any):
        response = jsonify(payload)
        response.headers["Connection"] = "close"
        return response

    def _record_hue_request(self, stage: str, **data: Any) -> None:
        forwarded = str(request.headers.get("X-Forwarded-For") or request.remote_addr or "")
        remote = forwarded.split(",", 1)[0].strip()
        raw_path = str(request.headers.get("X-AlexaOctoPrint-Original-Path") or request.path)
        path = sanitize_hue_path(raw_path)
        method = str(request.method or "")
        user_agent = str(request.headers.get("User-Agent") or "")
        now = datetime.now(timezone.utc).isoformat()

        with self._hue_http_lock:
            self._hue_http["total"] = int(self._hue_http.get("total", 0)) + 1
            self._hue_http[stage] = int(self._hue_http.get(stage, 0)) + 1
            self._hue_http.update(
                {
                    "last_at": now,
                    "last_stage": stage,
                    "last_remote": remote,
                    "last_method": method,
                    "last_path": path,
                    "last_user_agent": user_agent,
                }
            )

        event_data = {
            "stage": stage,
            "remote": remote,
            "method": method,
            "path": path,
            "user_agent": user_agent,
        }
        event_data.update(data)
        self._record("hue_http", "Hue HTTP request received", **event_data)
        self._logger.info("Alexa Hue HTTP %s from %s: %s %s", stage, remote, method, path)

    def _hue_http_snapshot(self) -> Dict[str, Any]:
        with self._hue_http_lock:
            return dict(self._hue_http)

    def _debug_snapshot(self, include_events: bool = True) -> Dict[str, Any]:
        settings = self._settings_snapshot()
        devices = self._hue_devices()
        lights = []
        light_payload = lights_payload(self._identity, devices)
        for light_id, device in zip(light_payload.keys(), devices):
            lights.append({"id": light_id, **device})

        snapshot: Dict[str, Any] = {
            "enabled": bool(settings.get("enabled", True)),
            "language": settings.get("language"),
            "location": self._description_location(),
            "base_url": self._base_url(),
            "identity": {
                "bridge_id": self._identity.bridge_id,
                "uuid": self._identity.uuid,
                "hue_username_suffix": self._hue_username[-6:],
            },
            "printer": self._printer_state(),
            "ssdp": self._ssdp_snapshot(),
            "hue_http": self._hue_http_snapshot(),
            "enclosure": self._enclosure_outputs_snapshot(),
            "devices": lights,
            "actions": list_action_metadata(settings),
            "cancel_armed_until": self._cancel_armed_until,
        }
        if include_events:
            snapshot["events"] = self._events.snapshot()
        return snapshot

    def _ssdp_snapshot(self) -> Dict[str, Any]:
        if not self._ssdp:
            return {"running": False}
        return self._ssdp.snapshot()

    def _ok(self, action_key: str, source: str, message: str, **data: Any) -> Dict[str, Any]:
        payload = {"ok": True, "action": action_key, "source": source, "message": message, **data}
        event_payload = dict(payload)
        event_payload.pop("message", None)
        self._record("action", message, **event_payload)
        self._logger.info("Alexa action ok: %s (%s)", action_key, message)
        return payload

    def _fail(self, action_key: str, source: str, error: str, **data: Any) -> Dict[str, Any]:
        payload = {"ok": False, "action": action_key, "source": source, "error": error, **data}
        self._record("action_error", error, **payload)
        self._logger.warning("Alexa action failed: %s (%s)", action_key, error)
        return payload

    def _record(self, event_type: str, message: str, **data: Any) -> None:
        settings = self._settings_snapshot()
        debug = settings.get("debug") or {}
        if debug.get("enabled", True):
            self._events.record(event_type, message, **data)


__plugin_name__ = "Alexa OctoPrint"
__plugin_version__ = "0.2.0"
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = AlexaOctoPrintPlugin()
__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
}
