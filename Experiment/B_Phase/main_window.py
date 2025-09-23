from __future__ import annotations

from typing import List
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QGroupBox,
    QLabel,
    QSpinBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QMenu,
    QButtonGroup, 
)

from widgets.actuator_grid import ActuatorGrid
from serial_backend import BaseBackend
from patterns import (
    BuzzPattern, PulsePattern, MotionPattern,
    MultiPattern, load_library, save_library
)

from generators import generate_static_pattern, generate_pulse_pattern, generate_motion_pattern


class MainWindow(QMainWindow):
    def __init__(self, backend: BaseBackend):
        super().__init__()
        self.setWindowTitle("Haptic Controller 4×4")
        self.backend = backend
        self.library: List[MultiPattern] = load_library()

        # -------- Layout skeleton --------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)   # left 1/4
        splitter.setStretchFactor(1, 3)   # right 3/4
        self.setCentralWidget(splitter)
        self.grid = ActuatorGrid()

        # --- Menu bar: Connection ---
        self.selected_port: str | None = None

        self.m_connection = self.menuBar().addMenu("Connection")
        self.action_scan = self.m_connection.addAction("Scan Ports")
        self.ports_menu = self.m_connection.addMenu("Ports")
        self.action_connect = self.m_connection.addAction("Connect")

        # one-time wiring
        self.port_group = QActionGroup(self)
        self.port_group.setExclusive(True)
        self.port_group.triggered.connect(self._on_port_chosen)
        self.action_scan.triggered.connect(self._scan_ports)
        self.action_connect.triggered.connect(self._toggle_connect)


        # -------- Buzz controls --------
        buzz = QGroupBox("Buzz")
        bl = QVBoxLayout(buzz)
        self.buzz_intensity = self._spin("Intensity (0..15)", 0, 15, 8)
        self.buzz_freq = self._spin("Frequency index (0..7)", 0, 7, 3)
        self.buzz_duration = self._spin("Duration (ms)", 0, 20000, 500)
        bl.addLayout(self.buzz_intensity.l)
        bl.addLayout(self.buzz_freq.l)
        bl.addLayout(self.buzz_duration.l)
        left_layout.addWidget(buzz)

        # -------- Pulse controls --------
        pulse = QGroupBox("Pulse")
        pl = QVBoxLayout(pulse)
        self.pulse_intensity = self._spin("Intensity (0..15)", 0, 15, 8)
        self.pulse_freq = self._spin("Frequency index (0..7)", 0, 7, 3)
        self.pulse_on = self._spin("On (ms)", 0, 5000, 100)
        self.pulse_off = self._spin("Off (ms)", 0, 5000, 100)
        self.pulse_rep = self._spin("Repetition", 1, 1000, 10)
        pl.addLayout(self.pulse_intensity.l)
        pl.addLayout(self.pulse_freq.l)
        pl.addLayout(self.pulse_on.l)
        pl.addLayout(self.pulse_off.l)
        pl.addLayout(self.pulse_rep.l)
        left_layout.addWidget(pulse)

        # -------- Motion (Drawn 3-act phantom) --------
        motion = QGroupBox("Motion (drawn phantom)")
        ml = QVBoxLayout(motion)

        self.motion_intensity = self._spin("Intensity (0..15)", 0, 15, 10)
        self.motion_freq = self._spin("Frequency index (0..7)", 0, 7, 3)
        self.motion_total = self._spin("Total time (ms)", 1, 120000, 500)
        self.motion_step = self._spin("Step duration (ms, ≤69)", 1, 69, 40)
        self.motion_max_ph = self._spin("Max phantom", 1, 100, 1)
        self.motion_sampling = self._spin("Sampling rate (Hz)", 1, 240, 60)

        ml.addLayout(self.motion_intensity.l)
        ml.addLayout(self.motion_freq.l)
        ml.addLayout(self.motion_total.l)
        ml.addLayout(self.motion_step.l)
        ml.addLayout(self.motion_max_ph.l)
        ml.addLayout(self.motion_sampling.l)


        left_layout.addWidget(motion)

        # -------- Actuator selection helpers --------
        tools = QGroupBox("Actuator Selection (affects current mode)")
        tl = QHBoxLayout(tools)

        tl.addWidget(QLabel("Mode:"))

        # Segmented buttons: Buzz | Pulse | Motion
        self.mode_group = QButtonGroup(self)
        self.mode_buzz_btn = QPushButton("Buzz")
        self.mode_pulse_btn = QPushButton("Pulse")
        self.mode_motion_btn = QPushButton("Motion")

        for btn, mode in [
            (self.mode_buzz_btn, "buzz"),
            (self.mode_pulse_btn, "pulse"),
            (self.mode_motion_btn, "motion"),
        ]:
            btn.setCheckable(True)
            btn.setProperty("mode", mode)          # we read this in the handler
            self.mode_group.addButton(btn)
            tl.addWidget(btn)

        # Default mode
        self.mode_buzz_btn.setChecked(True)
        self.grid.setMode("buzz")

        # When a button is clicked, switch mode
        self.mode_group.buttonClicked.connect(self._on_mode_button_clicked)

        tl.addStretch(1)

        self.sel_all_btn = QPushButton("Select All")
        self.clear_btn   = QPushButton("Clear")

        self.sel_all_btn.clicked.connect(lambda: self.grid.selectAllCurrent())
        self.clear_btn.clicked.connect(self._clear_all_modes)   # ← clear ALL modes

        tl.addWidget(self.sel_all_btn)
        tl.addWidget(self.clear_btn)
        left_layout.addWidget(tools)

        # -------- Play / Save --------
        playbox = QGroupBox("Controls")
        pbl = QHBoxLayout(playbox)
        self.play_all_btn = QPushButton("Play Selected Modes")
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self._preview_selected_modes)
        self.stop_all_btn = QPushButton("Stop All")
        self.save_btn = QPushButton("Save Pattern…")
        self.play_all_btn.clicked.connect(self._play_selected_modes)
        self.stop_all_btn.clicked.connect(lambda: self.backend.stop_all())
        self.save_btn.clicked.connect(self._save_pattern)
        pbl.addWidget(self.play_all_btn)
        pbl.addWidget(self.preview_btn)
        pbl.addWidget(self.stop_all_btn)
        pbl.addWidget(self.save_btn)
        left_layout.addWidget(playbox)

        # -------- Pattern library --------
        lib = QGroupBox("Pattern Library")
        ll = QVBoxLayout(lib)
        self.lib_list = QListWidget()
        self.play_lib_btn = QPushButton("Play From Library")
        self.play_lib_btn.clicked.connect(self._play_from_library)

        ll.addWidget(self.lib_list, 1)
        ll.addWidget(self.play_lib_btn)

        # Interactions: double-click = load; right-click = context menu (Delete)
        self.lib_list.itemDoubleClicked.connect(self._load_from_library_doubleclick)
        self.lib_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lib_list.customContextMenuRequested.connect(self._on_lib_context_menu)
        self.lib_list.setToolTip("Double-click to load. Right-click for delete.")

        left_layout.addWidget(lib, 1)

        # -------- Right: the 4×4 grid --------
        guide = QLabel("Click circles to select actuators for the current mode.")
        guide.setStyleSheet("color:#334155; margin:4px;")
        self.grid.selectionChanged.connect(lambda _m, _s: self._update_status())
        right_layout.addWidget(guide)
        right_layout.addWidget(self.grid, 1)
        self.status = QLabel("")
        right_layout.addWidget(self.status)

        # Final tweaks
        self._scan_ports()
        self._refresh_library_view()
        self._update_status()

    # ---------------- helpers ----------------
    class _LabeledSpin:
        def __init__(self, label: str, spin: QSpinBox, layout: QHBoxLayout):
            self.label = label
            self.spin = spin
            self.l = layout

    def _spin(self, label: str, mn: int, mx: int, val: int) -> "MainWindow._LabeledSpin":
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        s = QSpinBox()
        s.setRange(mn, mx)
        s.setValue(val)
        s.setSingleStep(10)   # or 1 if you want super fine control
        s.setMaximumWidth(120)
        row.addStretch(1)
        row.addWidget(s)
        return MainWindow._LabeledSpin(label, s, row)

    def _mode_changed(self, mode: str):
        self.grid.setMode(mode)
        self._update_status()

    def _scan_ports(self):
        ports = self.backend.scan_ports()
        self._populate_ports_menu(ports)

    def _toggle_connect(self):
        if self.backend.is_connected():
            self.backend.disconnect()
        else:
            port = self.selected_port or ""
            self.backend.connect(port)
        self._update_status()

    def _on_port_chosen(self, action: QAction):
        self.selected_port = action.text()

    def _populate_ports_menu(self, ports: List[str]):
        self.ports_menu.clear()
        # clear old actions from the group
        for a in list(self.port_group.actions()):
            self.port_group.removeAction(a)
        self.selected_port = None
        for i, p in enumerate(ports):
            act = self.ports_menu.addAction(p)
            act.setCheckable(True)
            self.port_group.addAction(act)
            if i == 0:
                act.setChecked(True)
                self.selected_port = p

    def _sel(self, mode: str) -> List[int]:
        return sorted(self.grid.selection(mode))
    
    def _on_mode_button_clicked(self, button):
        """Switch grid mode when a segmented button is clicked."""
        mode = button.property("mode")
        if isinstance(mode, str):
            self.grid.setMode(mode)
            self._update_status()

    def _clear_all_modes(self):
        """Clear ALL selections (Buzz, Pulse, Motion) and the drawn Motion path."""
        # Clear per-mode selections
        self.grid.setSelection("buzz", set())
        self.grid.setSelection("pulse", set())
        self.grid.setSelection("motion", set())

        # Clear the drawn Motion path (no clearMotion anymore)
        self.grid.set_motion_drawn_path_norm([])

        # Refresh preview/labels
        self._update_status()
    
    def _preview_selected_modes(self):
        # Buzz & Pulse come from explicit selections
        buzz_set = set(self._sel("buzz"))
        pulse_set = set(self._sel("pulse"))

        # Motion: build a short schedule and preview the union of addresses
        schedule = self.grid.build_motion_schedule(
            intensity=self.motion_intensity.spin.value(),
            total_ms=self.motion_total.spin.value(),
            step_ms=self.motion_step.spin.value(),
            max_phantom=self.motion_max_ph.spin.value(),
            sampling_hz=self.motion_sampling.spin.value(),
        )
        motion_set = set()
        for frame in schedule:
            for addr, duty in frame:
                if duty > 0:
                    motion_set.add(addr)

        # Show all three at once (dashed border for previewed items)
        self.grid.preview_modes(
            buzz=buzz_set,
            pulse=pulse_set,
            motion=motion_set,
            ms=900,
        )

    def _play_selected_modes(self):    
    # --- BUZZ Pattern ---
        buzz_sel = self._sel("buzz")
        if buzz_sel:
            # Generate buzz pattern using generators.py
            buzz_pattern = generate_static_pattern(
                devices=buzz_sel,
                duty=self.buzz_intensity.spin.value(),
                freq=self.buzz_freq.spin.value(),
                duration=self.buzz_duration.spin.value()
            )
            
            # Execute the generated pattern
            if hasattr(self.backend, 'play_generator_pattern'):
                self.backend.play_generator_pattern(
                    pattern_dict=buzz_pattern,
                    freq_idx=self.buzz_freq.spin.value()
                )
            else:
                # Fallback to old method if bridge not available
                self.backend.play_buzz(
                    buzz_sel,
                    duty=self.buzz_intensity.spin.value(),
                    freq_idx=self.buzz_freq.spin.value(),
                    duration_ms=self.buzz_duration.spin.value(),
                )
        
        # --- PULSE Pattern ---
        pulse_sel = self._sel("pulse")
        if pulse_sel:
            # Generate pulse pattern using generators.py
            pulse_pattern = generate_pulse_pattern(
                devices=pulse_sel,
                duty=self.pulse_intensity.spin.value(),
                freq=self.pulse_freq.spin.value(),
                pulse_duration=self.pulse_on.spin.value(),
                pause_duration=self.pulse_off.spin.value(),
                num_pulses=self.pulse_rep.spin.value()
            )
            
            # Execute the generated pattern
            if hasattr(self.backend, 'play_generator_pattern'):
                self.backend.play_generator_pattern(
                    pattern_dict=pulse_pattern,
                    freq_idx=self.pulse_freq.spin.value()
                )
            else:
                # Fallback to old method if bridge not available
                self.backend.play_pulse(
                    pulse_sel,
                    duty=self.pulse_intensity.spin.value(),
                    freq_idx=self.pulse_freq.spin.value(),
                    on_ms=self.pulse_on.spin.value(),
                    off_ms=self.pulse_off.spin.value(),
                    repetitions=self.pulse_rep.spin.value(),
                )
        
        # --- MOTION Pattern ---
        # Convert the drawn path to coordinates for the generator
        path_norm = self.grid.motion_drawn_path_norm()
        if len(path_norm) >= 2:
            # Convert normalized path to actual coordinates
            coordinates = []
            for x_norm, y_norm in path_norm:
                # These are normalized coordinates [0,1] - the generator can handle them
                coordinates.append((x_norm, y_norm))
            
            if coordinates:
                # Generate motion pattern using generators.py
                motion_pattern = generate_motion_pattern(
                    devices=coordinates,  # Pass the coordinate path
                    intensity=self.motion_intensity.spin.value(),
                    freq=self.motion_freq.spin.value(),
                    duration=self.motion_step.spin.value() / 1000.0  # Convert ms to seconds
                )
                
                # Execute the generated pattern
                if hasattr(self.backend, 'play_generator_pattern'):
                    self.backend.play_generator_pattern(
                        pattern_dict=motion_pattern,
                        freq_idx=self.motion_freq.spin.value()
                    )
                else:
                    # Fallback to old schedule-based method
                    schedule = self.grid.build_motion_schedule(
                        intensity=self.motion_intensity.spin.value(),
                        total_ms=self.motion_total.spin.value(),
                        step_ms=self.motion_step.spin.value(),
                        max_phantom=self.motion_max_ph.spin.value(),
                        sampling_hz=self.motion_sampling.spin.value(),
                    )
                    if schedule and self.backend.is_connected():
                        step_ms = min(self.motion_step.spin.value(), 69)
                        self.backend.play_motion_schedule(
                            schedule=schedule,
                            freq_idx=self.motion_freq.spin.value(),
                            step_ms=step_ms,
                        )
    
        self._update_status()


    def _save_pattern(self):
        # Build a MultiPattern from current selections
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Save Pattern", "Name:")
        if not ok or not name.strip():
            return

        buzz = None
        pulse = None
        bsel = self._sel("buzz")
        if bsel:
            buzz = BuzzPattern(
                actuators=bsel,
                duty=self.buzz_intensity.spin.value(),
                freq_idx=self.buzz_freq.spin.value(),
                duration_ms=self.buzz_duration.spin.value(),
            )
        psel = self._sel("pulse")
        if psel:
            pulse = PulsePattern(
                actuators=psel,
                duty=self.pulse_intensity.spin.value(),
                freq_idx=self.pulse_freq.spin.value(),
                on_ms=self.pulse_on.spin.value(),
                off_ms=self.pulse_off.spin.value(),
                repetitions=self.pulse_rep.spin.value(),
            )
        motion = None
        path_norm = self.grid.motion_drawn_path_norm()
        if len(path_norm) >= 2:
            motion = MotionPattern(
                path_norm=path_norm,
                intensity=self.motion_intensity.spin.value(),
                freq_idx=self.motion_freq.spin.value(),
                total_ms=self.motion_total.spin.value(),
                step_ms=self.motion_step.spin.value(),
                max_phantom=self.motion_max_ph.spin.value(),
                sampling_hz=self.motion_sampling.spin.value(),
            )
        item = MultiPattern(name=name.strip(), buzz=buzz, pulse=pulse, motion=motion)
        self.library.append(item)
        save_library(self.library)
        self._refresh_library_view()

    def _refresh_library_view(self):
        self.lib_list.clear()
        for it in self.library:
            lw = QListWidgetItem(f"{it.name} — {it.summary()}")
            self.lib_list.addItem(lw)
    
    def _load_from_library_doubleclick(self, item: QListWidgetItem):
        """Double-click on a row → load pattern into UI + canvas (no auto-play)."""
        row = self.lib_list.row(item)
        if row < 0 or row >= len(self.library):
            return
        it = self.library[row]
        self._apply_pattern_to_ui(it)  # shows Buzz+Pulse+Motion on canvas

    def _on_lib_context_menu(self, pos):
        """Right-click → context menu with Delete."""
        item = self.lib_list.itemAt(pos)
        if not item:
            return
        row = self.lib_list.row(item)
        if row < 0 or row >= len(self.library):
            return

        menu = QMenu(self)
        act_del = menu.addAction("Delete")
        chosen = menu.exec(self.lib_list.mapToGlobal(pos))
        if chosen == act_del:
            self._delete_from_library_row(row)

    def _delete_from_library_row(self, row: int):
        """Remove a library item by row and refresh UI."""
        if 0 <= row < len(self.library):
            self.library.pop(row)
            save_library(self.library)
            self._refresh_library_view()
            self._update_status()
    
    def _delete_from_library_click(self, item):
        """Left-click on a row deletes that pattern from the library."""
        row = self.lib_list.row(item)
        if row < 0 or row >= len(self.library):
            return
        # Remove from memory and persist to patterns.json
        self.library.pop(row)
        save_library(self.library)
        # Refresh UI
        self._refresh_library_view()
        self._update_status()

    def _play_from_library(self):
        """Pick a pattern by name, load it into the UI & canvas, then play with current backend."""
        if not self.library:
            return
        from PyQt6.QtWidgets import QInputDialog

        names = [it.name for it in self.library]
        name, ok = QInputDialog.getItem(self, "Play From Library", "Select pattern:", names, 0, False)
        if not ok or not name:
            return

        # Find pattern by name
        it = next((x for x in self.library if x.name == name), None)
        if not it:
            return

        # Load into UI + canvas
        self._apply_pattern_to_ui(it)

        # Then play using the currently shown controls
        self._play_selected_modes()

    def _apply_pattern_to_ui(self, it: MultiPattern):
        """Load a library pattern into controls + canvas (Buzz/Pulse selections, Motion path/params)."""
        # --- Buzz ---
        if it.buzz and it.buzz.actuators:
            self.buzz_intensity.spin.setValue(int(it.buzz.duty))
            self.buzz_freq.spin.setValue(int(it.buzz.freq_idx))
            self.buzz_duration.spin.setValue(int(it.buzz.duration_ms))
            self.grid.setSelection("buzz", set(int(a) for a in it.buzz.actuators))
        else:
            self.grid.setSelection("buzz", set())

        # --- Pulse ---
        if it.pulse and it.pulse.actuators:
            self.pulse_intensity.spin.setValue(int(it.pulse.duty))
            self.pulse_freq.spin.setValue(int(it.pulse.freq_idx))
            self.pulse_on.spin.setValue(int(it.pulse.on_ms))
            self.pulse_off.spin.setValue(int(it.pulse.off_ms))
            self.pulse_rep.spin.setValue(int(it.pulse.repetitions))
            self.grid.setSelection("pulse", set(int(a) for a in it.pulse.actuators))
        else:
            self.grid.setSelection("pulse", set())

        # --- Motion (drawn phantom) ---
        if it.motion and getattr(it.motion, "path_norm", None) and len(it.motion.path_norm) >= 2:
            self.motion_intensity.spin.setValue(int(it.motion.intensity))
            self.motion_freq.spin.setValue(int(it.motion.freq_idx))
            self.motion_total.spin.setValue(int(it.motion.total_ms))
            self.motion_step.spin.setValue(min(69, int(it.motion.step_ms)))
            self.motion_max_ph.spin.setValue(min(100, int(it.motion.max_phantom)))
            self.motion_sampling.spin.setValue(int(it.motion.sampling_hz))

            # Put the polyline back on the overlay
            self.grid.set_motion_drawn_path_norm(it.motion.path_norm)

            # Derive which actuators Motion will drive (persistent highlight on canvas)
            sched = self.grid.build_motion_schedule_from_norm_path(
                path_norm=it.motion.path_norm,
                intensity=self.motion_intensity.spin.value(),
                total_ms=self.motion_total.spin.value(),
                step_ms=self.motion_step.spin.value(),
                max_phantom=self.motion_max_ph.spin.value(),
                sampling_hz=self.motion_sampling.spin.value(),
            )
            motion_set = {addr for frame in sched for (addr, duty) in frame if duty > 0}
            self.grid.setSelection("motion", motion_set)
        else:
            self.grid.setSelection("motion", set())
            # also clear overlay path if you want:
            # self.grid.set_motion_drawn_path_norm([])

        # Visual refresh
        self._update_status()
        # Quick, friendly preview overlay of all three modes at once
        try:
            self.grid.preview_modes(
                buzz=self.grid.selection("buzz"),
                pulse=self.grid.selection("pulse"),
                motion=self.grid.selection("motion"),
                ms=900,
            )
        except Exception:
            pass

    def _update_status(self):
        conn = "connected" if self.backend.is_connected() else "disconnected"
        b = len(self._sel("buzz"))
        p = len(self._sel("pulse"))
        m = len(self._sel("motion"))
        self.status.setText(f"Status: {conn} | Buzz:{b} Pulse:{p} Motion:{m}")
        if hasattr(self, "action_connect"):
            self.action_connect.setText("Disconnect" if self.backend.is_connected() else "Connect")