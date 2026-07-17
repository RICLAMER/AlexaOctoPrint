from __future__ import annotations

import socket
import struct
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple

from .hue import BridgeIdentity


SSDP_GROUP = "239.255.255.250"
SSDP_PORT = 1900


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SSDPResponder:
    def __init__(
        self,
        logger,
        get_location: Callable[[], str],
        get_identity: Callable[[], BridgeIdentity],
        bind_ip: str = "0.0.0.0",
        on_response: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> None:
        self._logger = logger
        self._get_location = get_location
        self._get_identity = get_identity
        self._bind_ip = bind_ip or "0.0.0.0"
        self._on_response = on_response
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._stats: Dict[str, object] = {
            "running": False,
            "started_at": None,
            "stopped_at": None,
            "packets_received": 0,
            "search_requests": 0,
            "responses_sent": 0,
            "errors": 0,
            "last_error": "",
            "last_search_at": None,
            "last_search_from": "",
            "last_location": "",
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="AlexaOctoPrintSSDP", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
        with self._lock:
            self._stats["running"] = False
            self._stats["stopped_at"] = utc_now_iso()

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return dict(self._stats)

    def _set_stat(self, **values: object) -> None:
        with self._lock:
            self._stats.update(values)

    def _inc_stat(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._stats[key] = int(self._stats.get(key, 0)) + amount

    def _run(self) -> None:
        self._set_stat(running=True, started_at=utc_now_iso(), stopped_at=None)
        sock: Optional[socket.socket] = None
        try:
            sock = self._open_socket()
            while not self._stop.is_set():
                try:
                    data, address = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                except OSError as exc:
                    if not self._stop.is_set():
                        self._record_error(exc)
                    break

                self._inc_stat("packets_received")
                if self._is_search_request(data):
                    self._handle_search(sock, address)
        except OSError as exc:
            self._record_error(exc)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
            self._set_stat(running=False, stopped_at=utc_now_iso())

    def _open_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

        bind_address = "" if self._bind_ip in ("", "0.0.0.0") else self._bind_ip
        sock.bind((bind_address, SSDP_PORT))
        membership_interface = self._bind_ip if self._bind_ip not in ("", "0.0.0.0") else "0.0.0.0"
        mreq = struct.pack("4s4s", socket.inet_aton(SSDP_GROUP), socket.inet_aton(membership_interface))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)
        return sock

    def _is_search_request(self, data: bytes) -> bool:
        text = data.decode("utf-8", errors="ignore").upper()
        if "M-SEARCH" not in text:
            return False
        if "SSDP:DISC" not in text:
            return False
        return (
            "UPNP:ROOTD" in text
            or "SSDP:ALL" in text
            or "DEVICE:BASIC:1" in text
            or "ASIC:1" in text
        )

    def _handle_search(self, sock: socket.socket, address: Tuple[str, int]) -> None:
        identity = self._get_identity()
        location = self._get_location()
        response = self._build_response(location, identity)
        try:
            sock.sendto(response.encode("utf-8"), address)
            self._inc_stat("responses_sent")
            self._set_stat(
                last_search_at=utc_now_iso(),
                last_search_from=f"{address[0]}:{address[1]}",
                last_location=location,
            )
            if self._on_response:
                try:
                    self._on_response(
                        {
                            "remote": f"{address[0]}:{address[1]}",
                            "location": location,
                            "time": utc_now_iso(),
                        }
                    )
                except Exception:
                    self._logger.exception("Alexa OctoPrint SSDP callback failed")
        except OSError as exc:
            self._record_error(exc)
        finally:
            self._inc_stat("search_requests")

    def _build_response(self, location: str, identity: BridgeIdentity) -> str:
        return (
            "HTTP/1.1 200 OK\r\n"
            "EXT:\r\n"
            "CACHE-CONTROL: max-age=100\r\n"
            f"LOCATION: {location}\r\n"
            "SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/1.17.0\r\n"
            f"hue-bridgeid: {identity.bridge_id}\r\n"
            "ST: urn:schemas-upnp-org:device:basic:1\r\n"
            f"USN: uuid:{identity.uuid}::upnp:rootdevice\r\n"
            "\r\n"
        )

    def _record_error(self, exc: BaseException) -> None:
        message = str(exc)
        self._inc_stat("errors")
        self._set_stat(last_error=message)
        try:
            self._logger.exception("Alexa OctoPrint SSDP error: %s", message)
        except Exception:
            pass
        time.sleep(1.0)
