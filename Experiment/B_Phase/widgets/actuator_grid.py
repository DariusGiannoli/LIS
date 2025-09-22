from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import QWidget, QGridLayout, QToolButton
import math

MODE_COLORS = {
    "buzz": "#2563eb",   # blue
    "pulse": "#16a34a",  # green
    "motion": "#f59e0b", # amber (reserved)
}

class _MotionOverlay(QWidget):
    def __init__(self, host: "ActuatorGrid"):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self._host = host
        self._drawing = False
        self._points: list[QPointF] = []

    # Mouse → collect polyline when Motion mode is active
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self._host.mode() == "motion":
            self._drawing = True
            self._points = [ev.position()]
            self.update()

    def mouseMoveEvent(self, ev):
        if self._drawing and self._host.mode() == "motion":
            p = ev.position()
            if not self._points or (p - self._points[-1]).manhattanLength() >= 3:
                self._points.append(p)
                self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            self.update()

    def clear(self):
        self._points.clear()
        self.update()

    def path_points(self) -> list[QPointF]:
        return list(self._points)

    def set_path_norm(self, pts: list[list[float]]):
        r = self.rect()
        self._points = [QPointF(r.x() + x * r.width(), r.y() + y * r.height()) for (x, y) in pts]
        self.update()

    def path_norm(self) -> list[list[float]]:
        r = self.rect()
        W = max(1.0, float(r.width()))
        H = max(1.0, float(r.height()))
        return [[(p.x() - r.x()) / W, (p.y() - r.y()) / H] for p in self._points]

    def paintEvent(self, _):
        if not self._points:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen()
        pen.setWidth(3)
        painter.setPen(pen)
        path = QPainterPath(self._points[0])
        for p in self._points[1:]:
            path.lineTo(p)
        painter.drawPath(path)

class ActuatorGrid(QWidget):
    """4×4 selectable grid of circular buttons.

    Selection is tracked per mode. The grid highlights the *current* mode.
    """

    selectionChanged = pyqtSignal(str, set)  # (mode, current_selection)

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Initialize state BEFORE any styling ---
        self._mode = "buzz"                             # current mode
        self._selections = {"buzz": set(), "pulse": set(), "motion": set()}
        self._motion_order: list[int] = []              # ordered path for Motion
        self._preview: set[int] = set()                 # preview highlight set
        # Per-mode preview sets used to show "Preview" overlays cumulatively
        self._preview_by_mode = {"buzz": set(), "pulse": set(), "motion": set()}
        self._buttons: list[QToolButton] = []

        # --- UI: 4x4 grid of circular buttons ---
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(14)

        idx = 0
        for r in range(4):
            for c in range(4):
                idx += 1  # label 1..16; address is (idx-1)
                b = QToolButton()
                b.setText(str(idx))
                b.setCheckable(False)
                b.setFixedSize(56, 56)
                b.clicked.connect(lambda _=False, k=idx-1: self._toggle(k))
                self._buttons.append(b)
                grid.addWidget(b, r, c)
                # Transparent overlay for Motion drawing, sits above the buttons
        self._overlay = _MotionOverlay(self)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()

        # Now that state + buttons exist, styling is safe
        self._refresh_styles()
    
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "_overlay"):
            self._overlay.setGeometry(self.rect())
    
    def mode(self) -> str:
        return self._mode
    # ---------------- API ----------------
    def setMode(self, mode: str):
        if mode not in self._selections:
            return
        self._mode = mode
        is_motion = (mode == "motion")
        # Overlay captures mouse only in Motion mode; otherwise let clicks through to buttons
        if hasattr(self, "_overlay"):
            self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not is_motion)
            self._overlay.setVisible(True)
        for b in self._buttons:
            b.setEnabled(not is_motion)  # prevent accidental button toggles while drawing
        self._refresh_styles()

    def selection(self, mode: str | None = None) -> set:
        return set(self._selections[self._mode if mode is None else mode])

    def setSelection(self, mode: str, values: set[int]):
        if mode in self._selections:
            self._selections[mode] = set(int(v) for v in values)
            self._refresh_styles()

    def clearCurrent(self):
        self._selections[self._mode].clear()
        self._refresh_styles()
        self.selectionChanged.emit(self._mode, self.selection())

    def selectAllCurrent(self):
        self._selections[self._mode] = set(range(16))
        self._refresh_styles()
        self.selectionChanged.emit(self._mode, self.selection())
    
    def motionPath(self) -> list[int]:
        return list(self._motion_order)

    def clearMotion(self):
        self._motion_order.clear()
        self._selections["motion"].clear()
        self._overlay.clear()
        self._refresh_styles()
        self.selectionChanged.emit("motion", set())

    def motion_drawn_path(self) -> list[QPointF]:
        return self._overlay.path_points()

    def motion_drawn_path_norm(self) -> list[list[float]]:
        return self._overlay.path_norm()

    def set_motion_drawn_path_norm(self, pts: list[list[float]]):
        self._overlay.set_path_norm(pts)
        self._refresh_styles()
    
    def preview(self, addresses: set[int], ms: int = 600):
        """Backward-compat: preview current mode only."""
        self._preview_by_mode[self._mode] = set(int(a) for a in addresses)
        self._refresh_styles()
        QTimer.singleShot(ms, self._clear_preview_modes)
    
    def preview_modes(self, buzz: set[int], pulse: set[int], motion: set[int], ms: int = 600):
        """Preview all modes at once (Buzz + Pulse + Motion)."""
        self._preview_by_mode = {
            "buzz": set(int(a) for a in buzz),
            "pulse": set(int(a) for a in pulse),
            "motion": set(int(a) for a in motion),
        }
        self._refresh_styles()
        QTimer.singleShot(ms, self._clear_preview_modes)

    def _clear_preview(self):
        self._preview.clear()
        self._refresh_styles()
    
    def _clear_preview_modes(self):
        self._preview_by_mode = {"buzz": set(), "pulse": set(), "motion": set()}
        self._refresh_styles()

    # ---------------- internals ----------------
    def _toggle(self, addr: int):
        if self._mode == "motion":
            s = self._selections["motion"]
            if addr in s:
                s.remove(addr)
                if addr in self._motion_order:
                    self._motion_order.remove(addr)
            else:
                s.add(addr)
                self._motion_order.append(addr)
            self._refresh_styles()
            self.selectionChanged.emit("motion", set(s))
            return

        # Buzz / Pulse (unordered set)
        s = self._selections[self._mode]
        if addr in s:
            s.remove(addr)
        else:
            s.add(addr)
        self._refresh_styles()
        self.selectionChanged.emit(self._mode, set(s))

    def _refresh_styles(self):
        # Guards in case construction order changes
        if not hasattr(self, "_selections"):
            self._selections = {"buzz": set(), "pulse": set(), "motion": set()}
        if not hasattr(self, "_preview_by_mode"):
            self._preview_by_mode = {"buzz": set(), "pulse": set(), "motion": set()}

        col_buzz = MODE_COLORS.get("buzz", "#2563eb")
        col_pulse = MODE_COLORS.get("pulse", "#16a34a")
        col_motion = MODE_COLORS.get("motion", "#f59e0b")

        # Show persistent selections for Buzz/Pulse, plus any preview overlays.
        sel_buzz = set(self._selections.get("buzz", set())) | set(self._preview_by_mode.get("buzz", set()))
        sel_pulse = set(self._selections.get("pulse", set())) | set(self._preview_by_mode.get("pulse", set()))
        # For Motion, persistent set is typically empty (drawn path). We rely on preview to show actuators.
        sel_motion = set(self._selections.get("motion", set())) | set(self._preview_by_mode.get("motion", set()))

        for i, b in enumerate(self._buttons):
            in_b = i in sel_buzz
            in_p = i in sel_pulse
            in_m = i in sel_motion

            # Count how many modes reference this actuator
            count = int(in_b) + int(in_p) + int(in_m)

            # Priority color if overlaps: motion > pulse > buzz
            if in_m:
                border_col = col_motion
            elif in_p:
                border_col = col_pulse
            elif in_b:
                border_col = col_buzz
            else:
                border_col = "#cbd5e1"

            # Thicker border when part of multiple modes
            width = 2 + max(0, count - 1)   # 2, 3, 4 for 1,2,3 modes

            # Dashed border when this actuator is in any *preview* set (helps read Preview)
            in_any_preview = (
                i in self._preview_by_mode.get("buzz", set())
                or i in self._preview_by_mode.get("pulse", set())
                or i in self._preview_by_mode.get("motion", set())
            )
            style = "dashed" if in_any_preview else "solid"

            b.setStyleSheet(
                f"border: {width}px {style} {border_col}; "
                f"border-radius: 28px; font-weight: 600;"
            )
    
    def _actuator_centers(self) -> list[tuple[int, QPointF]]:
        # centers in this widget's coordinates
        centers: list[tuple[int, QPointF]] = []
        for i, b in enumerate(self._buttons):
            c = b.geometry().center()
            centers.append((i, QPointF(float(c.x()), float(c.y()))))
        return centers

    @staticmethod
    def _polyline_length(pts: list[QPointF]) -> float:
        if len(pts) < 2:
            return 0.0
        L = 0.0
        for i in range(len(pts) - 1):
            L += (pts[i+1] - pts[i]).manhattanLength() if False else (pts[i+1] - pts[i]).toPoint().manhattanLength()
        # Use Euclidean distance (faster approximation using .manhattanLength() commented out)
        L = 0.0
        for i in range(len(pts) - 1):
            dv = pts[i+1] - pts[i]
            L += math.hypot(dv.x(), dv.y())
        return L

    @staticmethod
    def _resample_by_length(pts: list[QPointF], count: int) -> list[QPointF]:
        if count <= 1 or len(pts) < 2:
            return pts[:1] * count
        # cumulative lengths
        segL = [0.0]
        for i in range(1, len(pts)):
            dv = pts[i] - pts[i-1]
            segL.append(segL[-1] + math.hypot(dv.x(), dv.y()))
        total = segL[-1]
        if total <= 1e-9:
            return [pts[0]] * count
        out: list[QPointF] = []
        j = 1
        for k in range(count):
            target = (k / (count - 1)) * total
            while j < len(segL) - 1 and segL[j] < target:
                j += 1
            # interpolate between pts[j-1], pts[j]
            tnum = target - segL[j-1]
            tden = max(1e-9, segL[j] - segL[j-1])
            u = tnum / tden
            a, b = pts[j-1], pts[j]
            out.append(QPointF(a.x() * (1 - u) + b.x() * u, a.y() * (1 - u) + b.y() * u))
        return out

    def _top3_weights(self, p: QPointF, centers: list[tuple[int, QPointF]]) -> list[tuple[int, float]]:
        # pick 3 closest actuators, weight by inverse squared distance
        best = []
        for addr, c in centers:
            dx, dy = p.x() - c.x(), p.y() - c.y()
            d2 = dx*dx + dy*dy
            best.append((d2, addr))
        best.sort(key=lambda x: x[0])
        picks = best[:3]
        eps = 1e-6
        ws = []
        denom = 0.0
        for d2, addr in picks:
            w = 1.0 / ((d2 + eps) ** 1.0)  # inverse distance (power 1). Use 2.0 for sharper focus.
            ws.append([addr, w])
            denom += w
        if denom <= 0:
            return [(addr, 0.0) for addr, _ in ws]
        return [(addr, w/denom) for addr, w in ws]

    def build_motion_schedule(
        self,
        intensity: int,
        total_ms: int,
        step_ms: int,
        max_phantom: int,
        sampling_hz: int,
    ) -> list[list[tuple[int, int]]]:
        # Clamp / sanitize
        step_ms = max(1, min(69, int(step_ms)))     # hard clamp ≤ 69ms
        total_ms = max(step_ms, int(total_ms))
        sampling_hz = max(1, int(sampling_hz))
        max_phantom = max(1, int(max_phantom))
        intensity = max(0, min(15, int(intensity)))

        pts = self.motion_drawn_path()
        if len(pts) < 2:
            return []

        # Number of time steps driven by Step Duration and total time
        steps_time = math.ceil(total_ms / step_ms)

        # Optional extra resampling density from sampling rate
        steps_geom = max(2, int((total_ms / 1000.0) * sampling_hz))
        steps = max(steps_time, steps_geom)

        samples = self._resample_by_length(pts, steps)
        centers = self._actuator_centers()

        # spacing between phantom heads in steps
        spacing = max(1, steps // max_phantom)

        schedule: list[list[tuple[int, int]]] = []
        prev_set: set[int] = set()

        for j in range(steps):
            # active phantom heads at this step (lead + trailing heads)
            heads_idx = [j - m*spacing for m in range(max_phantom)]
            heads_idx = [h for h in heads_idx if 0 <= h < steps]
            accum: dict[int, float] = {}
            for h in heads_idx:
                p = samples[h]
                for addr, w in self._top3_weights(p, centers):
                    accum[addr] = accum.get(addr, 0.0) + w

            # normalize and convert to 0..15 duty per actuator (sum phantoms, clamp)
            frame: list[tuple[int, int]] = []
            if accum:
                # normalize by max weight (preserve relative sum)
                mval = max(accum.values())
                for addr, val in accum.items():
                    duty = int(round(intensity * (val / mval)))
                    if duty > 0:
                        frame.append((addr, min(15, duty)))
            schedule.append(frame)

        return schedule

    def build_motion_schedule_from_norm_path(
        self,
        path_norm: list[list[float]],
        intensity: int,
        total_ms: int,
        step_ms: int,
        max_phantom: int,
        sampling_hz: int,
    ) -> list[list[tuple[int, int]]]:
        """
        Build a motion schedule from a normalized path (values in [0,1]×[0,1])
        without permanently mutating the current drawn path on the overlay.

        Returns:
            schedule: list of frames; each frame is a list of (addr, duty) pairs.
        """
        # Snapshot current overlay path (normalized), then restore no matter what.
        prev_norm = self.motion_drawn_path_norm()
        try:
            self.set_motion_drawn_path_norm(path_norm)
            return self.build_motion_schedule(
                intensity=intensity,
                total_ms=total_ms,
                step_ms=step_ms,
                max_phantom=max_phantom,
                sampling_hz=sampling_hz,
            )
        finally:
            # Restore original path to avoid any visual/state side-effects.
            self.set_motion_drawn_path_norm(prev_norm)

