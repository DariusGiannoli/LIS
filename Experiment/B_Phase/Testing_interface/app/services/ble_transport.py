# services/ble_transport.py
from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

# We use the user-provided python_ble_api.py
# It exposes: python_ble_api().get_ble_devices(), .connect_ble_device(name),
#             .disconnect_ble_device(), .send_command_list(commands)
try:
    from core.io.python_ble_api import python_ble_api
except Exception as e:
    python_ble_api = None  # type: ignore

class BLETransport:
    """
    Thin wrapper around python_ble_api with defensive fallbacks and clear errors.
    Provides:
      - scan_devices() -> list[str]
      - connect(name) -> (ok, msg)
      - disconnect() -> (ok, msg)
      - play_pattern(pattern_dict) -> (ok, msg)
    """
    def __init__(self) -> None:
        self.api = python_ble_api() if python_ble_api else None
        self._connected: bool = False

    # ---------- Public API ----------
    def scan_devices(self) -> List[str]:
        if not self.api:
            raise RuntimeError("BLE API not available (python_ble_api import failed).")
        # canonical method in your file
        if hasattr(self.api, "get_ble_devices"):
            return list(self.api.get_ble_devices() or [])
        # fallback names if a different API is used in the future
        for name in ("scan_devices", "scan", "discover"):
            if hasattr(self.api, name):
                fn = getattr(self.api, name)
                res = fn()
                # normalize to list[str]
                if isinstance(res, list):
                    return [str(x) for x in res]
        raise RuntimeError("BLE API does not expose a scan method (get_ble_devices/scan/scan_devices/discover).")

    def connect(self, device_name: str) -> tuple[bool, str]:
        if not self.api:
            return False, "BLE API not available."
        if hasattr(self.api, "connect_ble_device"):
            try:
                ok = bool(self.api.connect_ble_device(device_name))
                self._connected = ok
                return ok, "" if ok else "connect_ble_device returned False."
            except Exception as e:
                return False, str(e)
        # fallback names
        for name in ("connect", "connect_device"):
            if hasattr(self.api, name):
                try:
                    ok = bool(getattr(self.api, name)(device_name))
                    self._connected = ok
                    return ok, "" if ok else f"{name} returned False."
                except Exception as e:
                    return False, str(e)
        return False, "BLE API does not expose a connect method."

    def disconnect(self) -> tuple[bool, str]:
        if not self.api:
            return False, "BLE API not available."
        if hasattr(self.api, "disconnect_ble_device"):
            try:
                ok = bool(self.api.disconnect_ble_device())
                self._connected = False
                return ok, "" if ok else "disconnect_ble_device returned False."
            except Exception as e:
                return False, str(e)
        for name in ("disconnect", "close"):
            if hasattr(self.api, name):
                try:
                    ok = bool(getattr(self.api, name)())
                    self._connected = False
                    return ok, "" if ok else f"{name} returned False."
                except Exception as e:
                    return False, str(e)
        return False, "BLE API does not expose a disconnect method."

    def is_connected(self) -> bool:
        return self._connected

    def play_pattern(self, pattern: Dict[str, Any]) -> tuple[bool, str]:
        """
        Streams the pattern to the BLE device step-by-step:
          - send_command_list for each step
          - sleep delay_after_ms between steps
        """
        if not self.api:
            return False, "BLE API not available."
        if not self._connected:
            return False, "Not connected."

        steps = pattern.get("steps", [])
        try:
            for step in steps:
                cmds = step.get("commands", [])
                if cmds:
                    if hasattr(self.api, "send_command_list"):
                        ok = bool(self.api.send_command_list(cmds))
                        if not ok:
                            return False, "send_command_list returned False."
                    else:
                        return False, "BLE API does not expose send_command_list."

                delay_ms = int(step.get("delay_after_ms", 0) or 0)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
            return True, ""
        except Exception as e:
            return False, str(e)
