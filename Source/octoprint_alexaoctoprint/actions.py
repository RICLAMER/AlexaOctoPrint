from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional


SUPPORTED_LANGUAGES = ("pt", "en", "es")
DEFAULT_LANGUAGE = "pt"


@dataclass(frozen=True)
class ActionDefinition:
    key: str
    names: Mapping[str, str]
    category: str
    action_type: str
    enabled: bool = True
    allow_while_printing: bool = False
    supports_off: bool = False
    default_gcode: str = ""
    default_off_gcode: str = ""
    temperature: Optional[int] = None
    extrusion_mm: Optional[float] = None
    distance_mm: Optional[float] = None
    feedrate: Optional[int] = None
    file_slot: Optional[int] = None
    enclosure_label: Optional[str] = None


ACTION_DEFINITIONS: Dict[str, ActionDefinition] = {
    "printer_power": ActionDefinition(
        key="printer_power",
        names={"pt": "Impressora 3D", "en": "3D Printer", "es": "Impresora 3D"},
        category="enclosure",
        action_type="enclosure_output",
        supports_off=True,
        enclosure_label="Power",
    ),
    "printer_light": ActionDefinition(
        key="printer_light",
        names={
            "pt": "Luz da Impressora",
            "en": "Printer Light",
            "es": "Luz de la Impresora",
        },
        category="enclosure",
        action_type="enclosure_output",
        allow_while_printing=True,
        supports_off=True,
        enclosure_label="LIGHT",
    ),
    "pause": ActionDefinition(
        key="pause",
        names={
            "pt": "Pausar Impressão",
            "en": "Pause Print",
            "es": "Pausar Impresión",
        },
        category="print",
        action_type="pause",
        allow_while_printing=True,
    ),
    "resume": ActionDefinition(
        key="resume",
        names={
            "pt": "Retomar Impressão",
            "en": "Resume Print",
            "es": "Reanudar Impresión",
        },
        category="print",
        action_type="resume",
        allow_while_printing=True,
    ),
    "cancel": ActionDefinition(
        key="cancel",
        names={
            "pt": "Cancelar Impressão",
            "en": "Cancel Print",
            "es": "Cancelar Impresión",
        },
        category="print",
        action_type="cancel",
        allow_while_printing=True,
    ),
    "home": ActionDefinition(
        key="home",
        names={
            "pt": "Levar Impressora para Home",
            "en": "Home Printer",
            "es": "Llevar Impresora a Inicio",
        },
        category="movement",
        action_type="gcode",
        default_gcode="G28",
    ),
    "level": ActionDefinition(
        key="level",
        names={"pt": "Nivelar Mesa", "en": "Level Bed", "es": "Nivelar Cama"},
        category="movement",
        action_type="gcode",
        default_gcode="G28 X Y Z",
    ),
    "z_up": ActionDefinition(
        key="z_up",
        names={"pt": "Subir Eixo Z", "en": "Raise Z Axis", "es": "Subir Eje Z"},
        category="movement",
        action_type="z_move",
        distance_mm=2.0,
        feedrate=600,
    ),
    "z_down": ActionDefinition(
        key="z_down",
        names={"pt": "Baixar Eixo Z", "en": "Lower Z Axis", "es": "Bajar Eje Z"},
        category="movement",
        action_type="z_move",
        distance_mm=2.0,
        feedrate=600,
    ),
    "extrude": ActionDefinition(
        key="extrude",
        names={
            "pt": "Extrudar Filamento",
            "en": "Extrude Filament",
            "es": "Extruir Filamento",
        },
        category="extruder",
        action_type="extrude",
        extrusion_mm=5.0,
        feedrate=300,
    ),
    "retract": ActionDefinition(
        key="retract",
        names={
            "pt": "Recolher Filamento",
            "en": "Retract Filament",
            "es": "Retraer Filamento",
        },
        category="extruder",
        action_type="extrude",
        extrusion_mm=5.0,
        feedrate=1800,
    ),
    "bed_heat": ActionDefinition(
        key="bed_heat",
        names={"pt": "Aquecer Mesa", "en": "Heat Bed", "es": "Calentar Cama"},
        category="temperature",
        action_type="bed_temperature",
        allow_while_printing=True,
        temperature=100,
    ),
    "bed_off": ActionDefinition(
        key="bed_off",
        names={"pt": "Desligar Mesa", "en": "Turn Off Bed", "es": "Apagar Cama"},
        category="temperature",
        action_type="gcode",
        allow_while_printing=True,
        default_gcode="M140 S0",
    ),
    "hotend_pla": ActionDefinition(
        key="hotend_pla",
        names={
            "pt": "Aquecer Bico para PLA",
            "en": "Heat Nozzle for PLA",
            "es": "Calentar Boquilla para PLA",
        },
        category="temperature",
        action_type="hotend_temperature",
        allow_while_printing=True,
        temperature=200,
    ),
    "hotend_abs": ActionDefinition(
        key="hotend_abs",
        names={
            "pt": "Aquecer Bico para ABS",
            "en": "Heat Nozzle for ABS",
            "es": "Calentar Boquilla para ABS",
        },
        category="temperature",
        action_type="hotend_temperature",
        allow_while_printing=True,
        temperature=240,
    ),
    "hotend_petg": ActionDefinition(
        key="hotend_petg",
        names={
            "pt": "Aquecer Bico para PETG",
            "en": "Heat Nozzle for PETG",
            "es": "Calentar Boquilla para PETG",
        },
        category="temperature",
        action_type="hotend_temperature",
        allow_while_printing=True,
        temperature=235,
    ),
    "hotend_off": ActionDefinition(
        key="hotend_off",
        names={
            "pt": "Desligar Aquecimento do Bico",
            "en": "Turn Off Nozzle Heating",
            "es": "Apagar Calentamiento de la Boquilla",
        },
        category="temperature",
        action_type="gcode",
        allow_while_printing=True,
        default_gcode="M104 S0",
    ),
    "motors": ActionDefinition(
        key="motors",
        names={
            "pt": "Motores da Impressora",
            "en": "Printer Motors",
            "es": "Motores de la Impresora",
        },
        category="movement",
        action_type="toggle_gcode",
        supports_off=True,
        default_gcode="M17",
        default_off_gcode="M18",
    ),
    "print_last": ActionDefinition(
        key="print_last",
        names={
            "pt": "Imprimir Último Arquivo",
            "en": "Print Last File",
            "es": "Imprimir Último Archivo",
        },
        category="print",
        action_type="print_last",
        enabled=False,
    ),
    "print_piece1": ActionDefinition(
        key="print_piece1",
        names={
            "pt": "Imprimir Peça Um",
            "en": "Print Part One",
            "es": "Imprimir Pieza Uno",
        },
        category="print",
        action_type="print_file",
        enabled=False,
        file_slot=1,
    ),
    "print_piece2": ActionDefinition(
        key="print_piece2",
        names={
            "pt": "Imprimir Peça Dois",
            "en": "Print Part Two",
            "es": "Imprimir Pieza Dos",
        },
        category="print",
        action_type="print_file",
        enabled=False,
        file_slot=2,
    ),
    "print_piece3": ActionDefinition(
        key="print_piece3",
        names={
            "pt": "Imprimir Peça Três",
            "en": "Print Part Three",
            "es": "Imprimir Pieza Tres",
        },
        category="print",
        action_type="print_file",
        enabled=False,
        file_slot=3,
    ),
    "emergency": ActionDefinition(
        key="emergency",
        names={
            "pt": "Emergência da Impressora",
            "en": "Printer Emergency",
            "es": "Emergencia de la Impresora",
        },
        category="safety",
        action_type="gcode",
        enabled=False,
        allow_while_printing=True,
        default_gcode="M112\nM104 S0\nM140 S0",
    ),
}


ACTION_ORDER = list(ACTION_DEFINITIONS.keys())
LEGACY_ACTION_KEYS = (
    "printer_power_on",
    "printer_power_off",
    "light_on",
    "motors_off",
)


def _action_defaults(definition: ActionDefinition) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "enabled": definition.enabled,
        "name": "",
        "allow_while_printing": definition.allow_while_printing,
    }
    if definition.default_gcode:
        data["gcode"] = definition.default_gcode
    if definition.default_off_gcode:
        data["off_gcode"] = definition.default_off_gcode
    if definition.temperature is not None:
        data["temperature"] = definition.temperature
    if definition.extrusion_mm is not None:
        data["extrusion_mm"] = definition.extrusion_mm
    if definition.distance_mm is not None:
        data["distance_mm"] = definition.distance_mm
    if definition.feedrate is not None:
        data["feedrate"] = definition.feedrate
    if definition.file_slot is not None:
        data["file_path"] = ""
        data["file_origin"] = "local"
    if definition.enclosure_label is not None:
        data["enclosure_label"] = definition.enclosure_label
    return data


def get_default_settings() -> Dict[str, Any]:
    return {
        "enabled": True,
        "language": DEFAULT_LANGUAGE,
        "network": {
            "bridge_id": "",
            "uuid": "",
            "hue_username": "",
        },
        "debug": {
            "enabled": True,
            "max_events": 100,
        },
        "runtime": {
            "last_file_path": "",
            "last_file_origin": "local",
        },
        "actions": {
            key: _action_defaults(definition)
            for key, definition in ACTION_DEFINITIONS.items()
        },
    }


def deep_update(base: MutableMapping[str, Any], extra: Mapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), MutableMapping):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _legacy_action_settings(stored_actions: Mapping[str, Any], *keys: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key in keys:
        value = stored_actions.get(key)
        if isinstance(value, Mapping):
            deep_update(result, copy.deepcopy(value))
    return result


def migrate_stored_settings(stored: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    migrated = copy.deepcopy(dict(stored or {}))
    stored_actions = migrated.get("actions")
    if not isinstance(stored_actions, MutableMapping):
        stored_actions = {}
        migrated["actions"] = stored_actions

    if "printer_power" not in stored_actions:
        legacy = _legacy_action_settings(
            stored_actions,
            "printer_power_off",
            "printer_power_on",
        )
        if legacy:
            legacy.pop("enclosure_status", None)
            legacy["allow_while_printing"] = False
            stored_actions["printer_power"] = legacy

    if "printer_light" not in stored_actions:
        legacy = _legacy_action_settings(stored_actions, "light_on")
        if legacy:
            legacy.pop("enclosure_status", None)
            stored_actions["printer_light"] = legacy

    if "motors" not in stored_actions:
        legacy = _legacy_action_settings(stored_actions, "motors_off")
        if legacy:
            legacy_off_gcode = str(legacy.get("gcode") or "M18")
            legacy["gcode"] = "M17"
            legacy["off_gcode"] = legacy_off_gcode
            stored_actions["motors"] = legacy

    for key in LEGACY_ACTION_KEYS:
        stored_actions.pop(key, None)

    migrated.pop("cancel_requires_arm", None)
    migrated.pop("cancel_arm_seconds", None)
    debug = migrated.get("debug")
    if isinstance(debug, MutableMapping):
        debug.pop("test_device_enabled", None)

    network = migrated.get("network")
    if isinstance(network, MutableMapping):
        for key in tuple(network.keys()):
            if key not in ("bridge_id", "uuid", "hue_username"):
                network.pop(key, None)
    return migrated


def merged_settings(stored: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    data = get_default_settings()
    migrated = migrate_stored_settings(stored)
    deep_update(data, migrated)

    actions = data.get("actions") or {}
    data["actions"] = {
        key: actions[key]
        for key in ACTION_ORDER
        if key in actions
    }
    return data


def language_from_settings(settings: Mapping[str, Any]) -> str:
    language = str(settings.get("language") or DEFAULT_LANGUAGE).lower()
    if language not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE
    return language


def action_settings(settings: Mapping[str, Any], action_key: str) -> Dict[str, Any]:
    actions = settings.get("actions") or {}
    merged = _action_defaults(ACTION_DEFINITIONS[action_key])
    if isinstance(actions, Mapping):
        stored = actions.get(action_key) or {}
        if isinstance(stored, Mapping):
            deep_update(merged, stored)
    return merged


def action_name(settings: Mapping[str, Any], action_key: str) -> str:
    definition = ACTION_DEFINITIONS[action_key]
    current = action_settings(settings, action_key)
    custom = str(current.get("name") or "").strip()
    if custom:
        return custom
    language = language_from_settings(settings)
    return definition.names.get(language, definition.names[DEFAULT_LANGUAGE])


def enabled_action_keys(settings: Mapping[str, Any]) -> List[str]:
    if not settings.get("enabled", True):
        return []
    return [
        key
        for key in ACTION_ORDER
        if action_settings(settings, key).get("enabled", False)
    ]


def action_supports_off(action_key: str) -> bool:
    return ACTION_DEFINITIONS[action_key].supports_off


def build_gcode_for_action(
    settings: Mapping[str, Any],
    action_key: str,
    requested_on: bool = True,
) -> List[str]:
    definition = ACTION_DEFINITIONS[action_key]
    current = action_settings(settings, action_key)

    if definition.action_type == "bed_temperature":
        temp = int(current.get("temperature", definition.temperature or 0))
        return [f"M140 S{temp}"]

    if definition.action_type == "hotend_temperature":
        temp = int(current.get("temperature", definition.temperature or 0))
        return [f"M104 S{temp}"]

    if definition.action_type == "extrude":
        extrusion_mm = float(current.get("extrusion_mm", definition.extrusion_mm or 0))
        if action_key == "retract":
            extrusion_mm = -abs(extrusion_mm)
        feedrate = int(current.get("feedrate", definition.feedrate or 300))
        return ["M83", f"G1 E{extrusion_mm:g} F{feedrate}"]

    if definition.action_type == "z_move":
        distance_mm = float(current.get("distance_mm", definition.distance_mm or 0))
        distance_mm = abs(distance_mm) * (-1 if action_key == "z_down" else 1)
        feedrate = int(current.get("feedrate", definition.feedrate or 600))
        return ["G91", f"G1 Z{distance_mm:g} F{feedrate}", "G90"]

    setting_key = "gcode" if requested_on else "off_gcode"
    fallback = definition.default_gcode if requested_on else definition.default_off_gcode
    return split_gcode(str(current.get(setting_key) or fallback or ""))


def split_gcode(raw: str) -> List[str]:
    commands: List[str] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        cleaned = line.strip()
        if cleaned and not cleaned.startswith(";"):
            commands.append(cleaned)
    return commands


def list_action_metadata(settings: Mapping[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for key in ACTION_ORDER:
        definition = ACTION_DEFINITIONS[key]
        current = action_settings(settings, key)
        result.append(
            {
                "key": key,
                "name": action_name(settings, key),
                "category": definition.category,
                "type": definition.action_type,
                "enabled": bool(current.get("enabled", False)),
                "supports_off": definition.supports_off,
                "settings": current,
                "names": dict(definition.names),
            }
        )
    return result


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def validate_action_key(action_key: str) -> str:
    if action_key not in ACTION_DEFINITIONS:
        raise KeyError(f"Unknown Alexa OctoPrint action: {action_key}")
    return action_key


def iter_file_action_keys() -> Iterable[str]:
    for key, definition in ACTION_DEFINITIONS.items():
        if definition.action_type == "print_file":
            yield key
