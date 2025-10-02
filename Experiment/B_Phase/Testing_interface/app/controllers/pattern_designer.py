# controllers/pattern_designer.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QMainWindow, QSplitter, QMessageBox, QVBoxLayout, QInputDialog, QMenuBar
)

from app.widgets.actuator_grid import ActuatorGridWidget
from app.widgets.pattern_controls import PatternControls
from app.services.pattern_library import PatternLibrary
from app.services.ble_transport import BLETransport

from core import study_params as sp
from core.patterns.generators import (
    generate_static_pattern,
    generate_pulse_pattern,
    generate_motion_pattern,
)

class PatternPlayerThread(QThread):
    finished_with_status = pyqtSignal(bool, str)
    def __init__(self, ble: BLETransport, pattern: Dict[str, Any]) -> None:
        super().__init__()
        self.ble = ble
        self.pattern = pattern
    def run(self) -> None:
        ok, msg = self.ble.play_pattern(self.pattern)
        self.finished_with_status.emit(ok, msg or "")

class PatternDesignerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Pattern Designer — Buzz / Pulse / Motion")
        self.resize(1200, 780)

        self.grid = ActuatorGridWidget()
        self.controls = PatternControls(
            defaults={
                "buzz": dict(duty=sp.DUTY, freq=sp.FREQ, duration=sp.DURATION),
                "pulse": dict(duty=sp.DUTY, freq=sp.FREQ,
                              pulse_duration=sp.PULSE_DURATION,
                              pause_duration=sp.PAUSE_DURATION,
                              num_pulses=sp.NUM_PULSES),
                "motion": dict(duty=sp.DUTY, freq=sp.FREQ,
                               motion_duration=getattr(sp, "MOTION_DURATION", 0.04),
                               movement_speed=getattr(sp, "MOVEMENT_SPEED", 2000)),
            }
        )

        self.library = PatternLibrary()
        self.ble = BLETransport()
        self._last_scan: List[str] = []
        self._player: PatternPlayerThread | None = None

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.controls)
        splitter.addWidget(self.grid)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.addWidget(splitter)
        self.setCentralWidget(root)

        # ---- Menu bar (Bluetooth + Edit) ----
        mb: QMenuBar = self.menuBar()
        m_ble = mb.addMenu("Bluetooth")
        self.act_ble_scan = m_ble.addAction("Scan Devices")
        self.act_ble_connect = m_ble.addAction("Connect…")
        self.act_ble_disconnect = m_ble.addAction("Disconnect")

        m_edit = mb.addMenu("Edit")
        self.act_clear_all = m_edit.addAction("Clear All Selections")

        # ---- Signals ----
        self.controls.sigTypeChanged.connect(self.grid.set_active_mode)
        self.controls.sigPreview.connect(self.on_preview)
        self.controls.sigSend.connect(self.on_send)
        self.controls.sigClearAll.connect(self.on_clear_all)  # <-- hook Clear All

        self.controls.sigSave.connect(self.on_save)
        self.controls.sigDelete.connect(self.on_delete)
        self.controls.sigLoadRequest.connect(self.on_load_request)

        self.act_ble_scan.triggered.connect(self.on_scan_ble)
        self.act_ble_connect.triggered.connect(self.on_connect_ble)
        self.act_ble_disconnect.triggered.connect(self.on_disconnect_ble)
        self.act_clear_all.triggered.connect(self.on_clear_all)

        self.refresh_library()

    # ---------- Build per-type patterns ----------
    def build_patterns_by_type(self) -> Dict[str, Dict[str, Any]]:
        selected = self.grid.all_selected_by_type()

        out: Dict[str, Dict[str, Any]] = {}
        if selected["buzz"]:
            p = self.controls.read_buzz()
            out["buzz"] = dict(
                type="buzz", devices=selected["buzz"], params=p,
                data=generate_static_pattern(devices=selected["buzz"], duty=p["duty"], freq=p["freq"], duration=p["duration"]),
            )
        if selected["pulse"]:
            p = self.controls.read_pulse()
            out["pulse"] = dict(
                type="pulse", devices=selected["pulse"], params=p,
                data=generate_pulse_pattern(
                    devices=selected["pulse"], duty=p["duty"], freq=p["freq"],
                    pulse_duration=p["pulse_duration"], pause_duration=p["pause_duration"], num_pulses=p["num_pulses"]),
            )
        if selected["motion"]:
            p = self.controls.read_motion()
            out["motion"] = dict(
                type="motion", devices=selected["motion"], params=p,
                data=generate_motion_pattern(
                    devices=selected["motion"], intensity=p["duty"], freq=p["freq"],
                    duration=p["motion_duration"], movement_speed=p["movement_speed"]),
            )

        if not out:
            raise ValueError("Select at least one actuator in any pattern (Buzz/Pulse/Motion).")
        for k, v in out.items():
            if "steps" not in v["data"]:
                raise RuntimeError(f"Generator for '{k}' did not return pattern with 'steps'.")
        return out

    # ---------- Merge utilities ----------
    @staticmethod
    def _flatten_to_events(pattern_dict: Dict[str, Any]) -> List[tuple[int, list]]:
        events = []
        t = 0
        for step in pattern_dict.get("steps", []):
            cmds = step.get("commands", []) or []
            if cmds:
                events.append((t, cmds))
            t += int(step.get("delay_after_ms", 0) or 0)
        return events

    @classmethod
    def _merge_patterns(cls, patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        from collections import defaultdict
        time_to_cmds: dict[int, list] = defaultdict(list)
        for pat in patterns:
            for t, cmds in cls._flatten_to_events(pat):
                time_to_cmds[t].extend(cmds)
        times = sorted(time_to_cmds.keys())
        if not times:
            return {"steps": []}
        steps = [{"commands": time_to_cmds[t], "delay_after_ms": 0} for t in times]
        for i in range(len(steps) - 1):
            steps[i]["delay_after_ms"] = max(0, times[i + 1] - times[i])
        return {"steps": steps}

    def _build_merged_payload(self) -> Dict[str, Any]:
        per_type = self.build_patterns_by_type()
        merged = self._merge_patterns([v["data"] for v in per_type.values()])
        payload = dict(
            type="multi",
            devices_by_type={k: v["devices"] for k, v in per_type.items()},
            params_by_type={k: v["params"] for k, v in per_type.items()},
            data_by_type={k: v["data"] for k, v in per_type.items()},
            merged=merged,
        )
        self.controls.set_last_payload(payload)
        return payload
    
    def on_save(self) -> None:
        payload = self.controls.last_payload()
        if not payload:
            try:
                payload = self._build_merged_payload()
            except Exception as e:
                QMessageBox.critical(self, "Save error", f"No payload to save.\n{e}")
                return

        name, ok = QInputDialog.getText(self, "Save Pattern", "Name:")
        if not ok or not name:
            return

        try:
            self.library.save_item(
                name=name,
                ptype="multi",
                devices=payload["devices_by_type"],         # dict per type
                params=payload["params_by_type"],           # dict per type
                data_merged=payload["merged"],              # merged
                data_by_type=payload["data_by_type"],       # <-- NEW: keep all three
            )
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))
            return

        self.refresh_library()
        QMessageBox.information(self, "Library", f"Saved '{name}'.")

    def on_load_request(self, name: str) -> None:
        item = self.library.load_item(name)
        if not item:
            QMessageBox.critical(self, "Load error", "Item not found or invalid file.")
            return

        ptype = item.get("type")
        if ptype == "multi" or "data_by_type" in item:
            devices_by_type = item.get("devices", {}) or {}
            params_by_type  = item.get("params", {}) or {}
            data_by_type    = item.get("data_by_type", {}) or {}
            merged          = item.get("data_merged", item.get("data", {"steps": []}))

            # restore params + selections
            if "buzz" in params_by_type:  self.controls.set_params("buzz",  params_by_type["buzz"])
            if "pulse" in params_by_type: self.controls.set_params("pulse", params_by_type["pulse"])
            if "motion" in params_by_type:self.controls.set_params("motion",params_by_type["motion"])
            self.grid.set_selected_ids_by_type(
                devices_by_type.get("buzz", []),
                devices_by_type.get("pulse", []),
                devices_by_type.get("motion", []),
            )

            # cache for quick Send/Preview
            self.controls.set_last_payload(dict(
                type="multi",
                devices_by_type=devices_by_type,
                params_by_type=params_by_type,
                data_by_type=data_by_type,      # <-- keep per-type data in memory
                merged=merged,
            ))
        else:
            # Backward-compat: single-type entries
            devs = item.get("devices", [])
            params = item.get("params", {})
            t = item.get("type", "buzz")
            b = devs if t == "buzz" else []
            p = devs if t == "pulse" else []
            m = devs if t == "motion" else []
            self.grid.set_selected_ids_by_type(b, p, m)
            self.controls.set_params(t, params)
            self.controls.set_pattern_type(t)
            self.controls.set_last_payload(dict(
                type="multi",
                devices_by_type={"buzz": b, "pulse": p, "motion": m},
                params_by_type={t: params},
                data_by_type={t: item.get("data", {"steps": []})},  # best effort
                merged=item.get("data", {"steps": []}),
            ))

        QMessageBox.information(self, "Library", f"Loaded '{name}'.")
    # ---------- Preview ----------
    def on_preview(self) -> None:
        try:
            payload = self._build_merged_payload()
        except Exception as e:
            QMessageBox.critical(self, "Preview error", str(e))
            return
        self.grid.start_preview(payload["merged"])

    # ---------- Send (auto-generate + preview while playing) ----------
    def on_send(self) -> None:
        try:
            payload = self._build_merged_payload()
        except Exception as e:
            QMessageBox.critical(self, "Send error", str(e))
            return

        if not self.ble.is_connected():
            QMessageBox.warning(self, "Bluetooth", "Not connected. Use Bluetooth → Connect…")
            return

        # Start visual preview in parallel
        self.grid.start_preview(payload["merged"])

        # Launch BLE on a worker thread
        self._player = PatternPlayerThread(self.ble, payload["merged"])
        self._player.finished_with_status.connect(self._on_ble_finished)
        self._player.start()

    def _on_ble_finished(self, ok: bool, msg: str) -> None:
        self.grid.stop_preview()
        if ok:
            QMessageBox.information(self, "Bluetooth", "Pattern sent successfully.")
        else:
            QMessageBox.critical(self, "Bluetooth", msg or "Unknown error")
        self._player = None

    # ---------- Clear ----------
    def on_clear_all(self) -> None:
        self.grid.clear_all()

    # ---------- Library ----------
    def refresh_library(self) -> None:
        self.controls.refresh_library_list(self.library.list_items())


    def on_delete(self) -> None:
        name = self.controls.current_library_item_name()
        if not name:
            QMessageBox.warning(self, "Delete", "Select an item to delete.")
            return
        if not self.library.delete_item(name):
            QMessageBox.critical(self, "Delete error", "Could not delete this item.")
            return
        self.refresh_library()


    # ---------- Bluetooth ----------
    def on_scan_ble(self) -> None:
        try:
            self._last_scan = self.ble.scan_devices()
        except Exception as e:
            QMessageBox.critical(self, "Bluetooth", f"Scan error: {e}")
            return
        if not self._last_scan:
            QMessageBox.information(self, "Bluetooth", "No devices found.")
        else:
            QMessageBox.information(self, "Bluetooth", f"Found {len(self._last_scan)} device(s).")

    def on_connect_ble(self) -> None:
        if not self._last_scan:
            self.on_scan_ble()
        items = self._last_scan or []
        if not items:
            return
        name, ok = QInputDialog.getItem(self, "Connect Bluetooth", "Choose device:", items, 0, False)
        if not ok or not name:
            return
        ok2, msg = self.ble.connect(name)
        if ok2:
            QMessageBox.information(self, "Bluetooth", f"Connected to {name}.")
        else:
            QMessageBox.critical(self, "Bluetooth", msg or "Connect failed.")

    def on_disconnect_ble(self) -> None:
        ok, msg = self.ble.disconnect()
        if ok:
            QMessageBox.information(self, "Bluetooth", "Disconnected.")
        else:
            QMessageBox.critical(self, "Bluetooth", msg or "Disconnect failed.")
