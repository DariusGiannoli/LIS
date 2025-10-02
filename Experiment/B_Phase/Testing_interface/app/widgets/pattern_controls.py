# widgets/pattern_controls.py
from __future__ import annotations
from typing import Dict, Any, Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSpinBox,
    QDoubleSpinBox, QPushButton, QGroupBox, QListWidget, QListWidgetItem,
    QInputDialog, QButtonGroup
)

class PatternControls(QWidget):
    """
    Left panel: pattern buttons + parameters, Preview/Send/Clear, Library.
    (BLE is in the menu bar.)
    """
    sigPreview = pyqtSignal()       # preview the merged timeline
    sigSend = pyqtSignal()          # auto-generate + send
    sigSave = pyqtSignal()
    sigDelete = pyqtSignal()
    sigLoadRequest = pyqtSignal(str)
    sigTypeChanged = pyqtSignal(str)
    sigClearAll = pyqtSignal()      # <-- NEW: clear selections for ALL patterns

    def __init__(self, defaults: Dict[str, Dict[str, Any]]) -> None:
        super().__init__()
        self._defaults = defaults
        self._last_payload: Optional[Dict[str, Any]] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # --- Pattern type as 3 buttons + Clear All ---
        self.grpType = QGroupBox("Pattern Type")
        typeLay = QHBoxLayout(self.grpType)
        self.btnBuzz = QPushButton("Buzz"); self.btnBuzz.setCheckable(True)
        self.btnPulse = QPushButton("Pulse"); self.btnPulse.setCheckable(True)
        self.btnMotion = QPushButton("Motion"); self.btnMotion.setCheckable(True)
        self.btnClear = QPushButton("Clear All")  # clears ALL patterns

        self.btnGroup = QButtonGroup(self)
        self.btnGroup.setExclusive(True)
        self.btnGroup.addButton(self.btnBuzz)
        self.btnGroup.addButton(self.btnPulse)
        self.btnGroup.addButton(self.btnMotion)
        self.btnBuzz.setChecked(True)

        typeLay.addWidget(self.btnBuzz)
        typeLay.addWidget(self.btnPulse)
        typeLay.addWidget(self.btnMotion)
        typeLay.addStretch(1)
        typeLay.addWidget(self.btnClear)
        root.addWidget(self.grpType)

        # --- Parameters (stack by type) ---
        self.grpParams = QGroupBox("Pattern Parameters")
        paramsLay = QVBoxLayout(self.grpParams)

        # Buzz
        self.spBuzzDuty = QSpinBox(); self.spBuzzDuty.setRange(0, 15)
        self.spBuzzFreq = QSpinBox(); self.spBuzzFreq.setRange(0, 7)
        self.spBuzzDur  = QSpinBox(); self.spBuzzDur.setRange(1, 100000); self.spBuzzDur.setSuffix(" ms")
        formBuzz = QFormLayout()
        formBuzz.addRow("Duty (0–15):", self.spBuzzDuty)
        formBuzz.addRow("Frequency (0–7):", self.spBuzzFreq)
        formBuzz.addRow("Duration (ms):", self.spBuzzDur)
        self.boxBuzz = QGroupBox("Buzz"); self.boxBuzz.setLayout(formBuzz)

        # Pulse
        self.spPulseDuty = QSpinBox(); self.spPulseDuty.setRange(0, 15)
        self.spPulseFreq = QSpinBox(); self.spPulseFreq.setRange(0, 7)
        self.spPulseDur  = QSpinBox(); self.spPulseDur.setRange(1, 100000); self.spPulseDur.setSuffix(" ms")
        self.spPauseDur  = QSpinBox(); self.spPauseDur.setRange(0, 100000); self.spPauseDur.setSuffix(" ms")
        self.spNumPulses = QSpinBox(); self.spNumPulses.setRange(1, 1000)
        formPulse = QFormLayout()
        formPulse.addRow("Duty (0–15):", self.spPulseDuty)
        formPulse.addRow("Frequency (0–7):", self.spPulseFreq)
        formPulse.addRow("Pulse duration (ms):", self.spPulseDur)
        formPulse.addRow("Pause duration (ms):", self.spPauseDur)
        formPulse.addRow("Num pulses:", self.spNumPulses)
        self.boxPulse = QGroupBox("Pulse"); self.boxPulse.setLayout(formPulse)

        # Motion
        self.spMotionDuty = QSpinBox(); self.spMotionDuty.setRange(0, 15)
        self.spMotionFreq = QSpinBox(); self.spMotionFreq.setRange(0, 7)
        self.spMotionDur  = QDoubleSpinBox(); self.spMotionDur.setRange(0.001, 2.0)
        self.spMotionDur.setDecimals(4); self.spMotionDur.setSingleStep(0.005); self.spMotionDur.setSuffix(" s")
        self.spMoveSpeed  = QSpinBox(); self.spMoveSpeed.setRange(10, 20000); self.spMoveSpeed.setSuffix(" px/s")
        formMotion = QFormLayout()
        formMotion.addRow("Duty/Intensity (0–15):", self.spMotionDuty)
        formMotion.addRow("Frequency (0–7):", self.spMotionFreq)
        formMotion.addRow("Motion duration (s):", self.spMotionDur)
        formMotion.addRow("Movement speed (px/s):", self.spMoveSpeed)
        self.boxMotion = QGroupBox("Motion"); self.boxMotion.setLayout(formMotion)

        paramsLay.addWidget(self.boxBuzz)
        paramsLay.addWidget(self.boxPulse)
        paramsLay.addWidget(self.boxMotion)
        root.addWidget(self.grpParams)

        # Actions (no Generate)
        row = QHBoxLayout()
        self.btnPreview = QPushButton("Preview")
        self.btnSend = QPushButton("Send to Device (All)")
        row.addWidget(self.btnPreview); row.addWidget(self.btnSend)
        root.addLayout(row)

        # Library
        self.grpLibrary = QGroupBox("Pattern Library")
        libLay = QVBoxLayout(self.grpLibrary)
        self.listLib = QListWidget()
        libBtns = QHBoxLayout()
        self.btnSave = QPushButton("Save")
        self.btnDelete = QPushButton("Delete")
        libBtns.addWidget(self.btnSave); libBtns.addWidget(self.btnDelete)
        libLay.addWidget(self.listLib)
        libLay.addLayout(libBtns)
        root.addWidget(self.grpLibrary)
        root.addStretch(1)

        # Defaults & visibility
        self._apply_defaults()
        self._on_type_changed(self.current_pattern_type())

        # Signals
        self.btnBuzz.clicked.connect(lambda: self._on_type_changed("buzz"))
        self.btnPulse.clicked.connect(lambda: self._on_type_changed("pulse"))
        self.btnMotion.clicked.connect(lambda: self._on_type_changed("motion"))
        self.btnClear.clicked.connect(self.sigClearAll.emit)          # <-- clear all

        self.btnPreview.clicked.connect(self.sigPreview.emit)
        self.btnSend.clicked.connect(self.sigSend.emit)
        self.btnSave.clicked.connect(self.sigSave.emit)
        self.btnDelete.clicked.connect(self.sigDelete.emit)
        self.listLib.itemDoubleClicked.connect(self._on_load_double_clicked)

    # ---- Public helpers ----
    def current_pattern_type(self) -> str:
        if self.btnPulse.isChecked(): return "pulse"
        if self.btnMotion.isChecked(): return "motion"
        return "buzz"

    def set_pattern_type(self, t: str) -> None:
        {"buzz": self.btnBuzz, "pulse": self.btnPulse, "motion": self.btnMotion}.get(t, self.btnBuzz).setChecked(True)
        self._on_type_changed(t)

    def ask_pattern_name(self) -> tuple[str, bool]:
        name, ok = QInputDialog.getText(self, "Save Pattern", "Name:")
        return name, ok

    def refresh_library_list(self, items: list[dict]) -> None:
        self.listLib.clear()
        for it in items:
            lw = QListWidgetItem(f"{it['name']}  ·  {it['type']}  ·  {it['created_at']}")
            lw.setData(Qt.ItemDataRole.UserRole, it["name"])
            self.listLib.addItem(lw)

    def current_library_item_name(self) -> str | None:
        it = self.listLib.currentItem()
        return None if it is None else it.data(Qt.ItemDataRole.UserRole)

    def _on_load_double_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.sigLoadRequest.emit(name)

    # ---- Params I/O ----
    def _apply_defaults(self) -> None:
        d = self._defaults["buzz"]
        self.spBuzzDuty.setValue(d["duty"]); self.spBuzzFreq.setValue(d["freq"]); self.spBuzzDur.setValue(d["duration"])
        d = self._defaults["pulse"]
        self.spPulseDuty.setValue(d["duty"]); self.spPulseFreq.setValue(d["freq"])
        self.spPulseDur.setValue(d["pulse_duration"]); self.spPauseDur.setValue(d["pause_duration"])
        self.spNumPulses.setValue(d["num_pulses"])
        d = self._defaults["motion"]
        self.spMotionDuty.setValue(d["duty"]); self.spMotionFreq.setValue(d["freq"])
        self.spMotionDur.setValue(float(d["motion_duration"])); self.spMoveSpeed.setValue(d["movement_speed"])

    def set_params(self, ptype: str, params: Dict[str, Any]) -> None:
        if ptype == "buzz":
            self.spBuzzDuty.setValue(params.get("duty", self.spBuzzDuty.value()))
            self.spBuzzFreq.setValue(params.get("freq", self.spBuzzFreq.value()))
            self.spBuzzDur.setValue(params.get("duration", self.spBuzzDur.value()))
        elif ptype == "pulse":
            self.spPulseDuty.setValue(params.get("duty", self.spPulseDuty.value()))
            self.spPulseFreq.setValue(params.get("freq", self.spPulseFreq.value()))
            self.spPulseDur.setValue(params.get("pulse_duration", self.spPulseDur.value()))
            self.spPauseDur.setValue(params.get("pause_duration", self.spPauseDur.value()))
            self.spNumPulses.setValue(params.get("num_pulses", self.spNumPulses.value()))
        elif ptype == "motion":
            self.spMotionDuty.setValue(params.get("duty", self.spMotionDuty.value()))
            self.spMotionFreq.setValue(params.get("freq", self.spMotionFreq.value()))
            self.spMotionDur.setValue(float(params.get("motion_duration", self.spMotionDur.value())))
            self.spMoveSpeed.setValue(params.get("movement_speed", self.spMoveSpeed.value()))

    def read_buzz(self) -> Dict[str, int]:
        return dict(duty=self.spBuzzDuty.value(), freq=self.spBuzzFreq.value(), duration=self.spBuzzDur.value())

    def read_pulse(self) -> Dict[str, int]:
        return dict(
            duty=self.spPulseDuty.value(), freq=self.spPulseFreq.value(),
            pulse_duration=self.spPulseDur.value(), pause_duration=self.spPauseDur.value(),
            num_pulses=self.spNumPulses.value()
        )

    def read_motion(self) -> Dict[str, float | int]:
        return dict(
            duty=self.spMotionDuty.value(), freq=self.spMotionFreq.value(),
            motion_duration=float(self.spMotionDur.value()), movement_speed=self.spMoveSpeed.value()
        )

    def _on_type_changed(self, t: str) -> None:
        self.boxBuzz.setVisible(t == "buzz")
        self.boxPulse.setVisible(t == "pulse")
        self.boxMotion.setVisible(t == "motion")
        self.sigTypeChanged.emit(t)

    # For library payload caching
    def set_last_payload(self, payload: Dict[str, Any]) -> None:
        self._last_payload = payload
    def last_payload(self) -> Optional[Dict[str, Any]]:
        return self._last_payload
