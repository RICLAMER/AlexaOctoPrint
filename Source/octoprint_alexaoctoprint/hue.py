from __future__ import annotations

import hmac
import re
import secrets
import socket
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urljoin, urlparse
from xml.sax.saxutils import escape


PLUGIN_SWVERSION = "espalexa-2.7.0"
HUE_USERNAME_BYTES = 20
HUE_USERNAME_PATTERN = re.compile(r"^[0-9a-f]{40}$")
HUE_PATH_USERNAME_PATTERN = re.compile(r"(?i)(/api/)[^/]+")


@dataclass(frozen=True)
class BridgeIdentity:
    bridge_id: str
    uuid: str
    friendly_name: str = "AlexaOctoPrint"


def compact_mac_from_uuidnode() -> str:
    node = uuid.getnode()
    return f"{node:012x}"[-12:]


def normalize_bridge_id(value: Optional[str] = None) -> str:
    raw = "".join(ch for ch in str(value or "") if ch.isalnum()).lower()
    if len(raw) >= 12:
        raw = raw[-12:]
    if len(raw) != 12:
        raw = compact_mac_from_uuidnode()
    return raw


def build_identity(bridge_id: Optional[str] = None, uuid_value: Optional[str] = None) -> BridgeIdentity:
    normalized_bridge_id = normalize_bridge_id(bridge_id)
    normalized_uuid = str(uuid_value or "").strip()
    if not normalized_uuid:
        normalized_uuid = f"2f402f80-da50-11e1-9b23-{normalized_bridge_id}"
    return BridgeIdentity(bridge_id=normalized_bridge_id, uuid=normalized_uuid)


def encode_light_key(identity: BridgeIdentity, index: int) -> str:
    mac24 = int(identity.bridge_id[-6:], 16)
    return str((mac24 << 7) | int(index))


def decode_light_key(identity: BridgeIdentity, light_id: str) -> Optional[int]:
    try:
        numeric = int(light_id)
    except (TypeError, ValueError):
        return None

    mac24 = int(identity.bridge_id[-6:], 16)
    if numeric >> 7 != mac24:
        return None
    return numeric & 127


def unique_light_id(identity: BridgeIdentity, index: int) -> str:
    mac = identity.bridge_id.upper()
    pairs = [mac[i : i + 2] for i in range(0, 12, 2)]
    return "{}-{:02X}-00:11".format(":".join(pairs), int(index) + 1)


def device_json(identity: BridgeIdentity, light_id: str, name: str, on: bool = False) -> Dict[str, Any]:
    index = decode_light_key(identity, light_id)
    if index is None:
        index = 0
    return {
        "state": {
            "on": bool(on),
            "alert": "none",
            "reachable": True,
        },
        "type": "On/off light",
        "name": name,
        "modelid": "HASS321",
        "manufacturername": "Philips",
        "uniqueid": unique_light_id(identity, index),
        "swversion": PLUGIN_SWVERSION,
    }


def lights_payload(identity: BridgeIdentity, devices: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for index, device in enumerate(devices):
        light_id = encode_light_key(identity, index)
        payload[light_id] = device_json(
            identity=identity,
            light_id=light_id,
            name=str(device.get("name") or f"Alexa OctoPrint {index + 1}"),
            on=bool(device.get("on", False)),
        )
    return payload


def success_response(path: str, value: Any = True) -> List[Dict[str, Any]]:
    return [{"success": {path: value}}]


def generate_hue_username() -> str:
    return secrets.token_hex(HUE_USERNAME_BYTES)


def valid_hue_username(value: Any) -> bool:
    return bool(HUE_USERNAME_PATTERN.fullmatch(str(value or "")))


def username_matches(expected: str, provided: str) -> bool:
    if not valid_hue_username(expected) or not valid_hue_username(provided):
        return False
    return hmac.compare_digest(expected, provided)


def username_response(username: str) -> List[Dict[str, Any]]:
    return [{"success": {"username": username}}]


def unauthorized_response(path: str = "/") -> List[Dict[str, Any]]:
    return [
        {
            "error": {
                "type": 1,
                "address": sanitize_hue_path(path),
                "description": "unauthorized user",
            }
        }
    ]


def sanitize_hue_path(path: str) -> str:
    return HUE_PATH_USERNAME_PATTERN.sub(r"\1<redacted>", str(path or ""))


def hue_base_url(host: str, port: int, path: str) -> str:
    clean_path = "/" + str(path or "").strip("/")
    if clean_path == "/":
        clean_path = ""
    if port <= 0:
        port = 80
    return f"http://{host}:{port}{clean_path}/"


def description_xml(base_url: str, identity: BridgeIdentity) -> str:
    safe_base = escape(base_url)
    parsed = urlparse(base_url)
    host = parsed.hostname or "0.0.0.0"
    port = parsed.port or 80
    safe_name = escape(f"Espalexa ({host}:{port})")
    safe_bridge_id = escape(identity.bridge_id)
    safe_uuid = escape(identity.uuid)
    return (
        '<?xml version="1.0" ?>'
        '<root xmlns="urn:schemas-upnp-org:device-1-0">'
        "<specVersion><major>1</major><minor>0</minor></specVersion>"
        f"<URLBase>{safe_base}</URLBase>"
        "<device>"
        "<deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>"
        f"<friendlyName>{safe_name}</friendlyName>"
        "<manufacturer>Royal Philips Electronics</manufacturer>"
        "<manufacturerURL>http://www.philips.com</manufacturerURL>"
        "<modelDescription>Philips hue Personal Wireless Lighting</modelDescription>"
        "<modelName>Philips hue bridge 2012</modelName>"
        "<modelNumber>929000226503</modelNumber>"
        "<modelURL>http://www.meethue.com</modelURL>"
        f"<serialNumber>{safe_bridge_id}</serialNumber>"
        f"<UDN>uuid:{safe_uuid}</UDN>"
        "<presentationURL>index.html</presentationURL>"
        "</device>"
        "</root>"
    )


def local_ip_for_target(target: str = "8.8.8.8") -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((target, 80))
        return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()


def resolve_advertised_host(configured_host: str) -> str:
    configured_host = str(configured_host or "").strip()
    if configured_host:
        return configured_host
    return local_ip_for_target()


def location_url(host: str, port: int, path: str) -> str:
    return urljoin(hue_base_url(host, port, path), "description.xml")
