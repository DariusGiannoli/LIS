# widgets/actuator_grid.py
from __future__ import annotations
from typing import Dict, Tuple, List, Set
import math, re

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush
from PyQt6.QtWidgets import QWidget

from core.hardware.actuator_layout import LAYOUT_POSITIONS

COLORS = {
    "buzz": Qt.GlobalColor.cyan,
    "pulse": Qt.GlobalColor.magenta,
    "motion": Qt.GlobalColor.yellow,
}

PREVIEW_MIN_DELAY_MS = 40  # min dwell per step so humans can see it

class ActuatorGridWidget(QWidget):
    """
    - Per-pattern selections (buzz/pulse/motion).
    - Centered drawing in its viewport.
    - Preview overlay: shows currently 'active' devices during timeline playback.
    """
    def __init__(self) -> None:
        super().__init__()
        self._outer_margin = 16
        self.active_mode: str = "buzz"
        self.sel: Dict[str, Set[int]] = {"buzz": set(), "pulse": set(), "motion": set()}

        # layout bounds
        xs = [p[0] for p in LAYOUT_POSITIONS.values()]
        ys = [p[1] for p in LAYOUT_POSITIONS.values()]
        self._minx, self._maxx = (min(xs), max(xs)) if xs else (0.0, 1.0)
        self._miny, self._maxy = (min(ys), max(ys)) if ys else (0.0, 1.0)
        self._min_spacing = self._compute_min_spacing()

        # cached draw params
        self._scale = 1.0
        self._r = 12.0
        self._xoff = 0.0
        self._yoff = 0.0

        # preview state
        self._preview_steps: List[Tuple[Set[int], int]] = []  # [(active_devices, delay_ms), ...]
        self._preview_idx: int = -1
        self._preview_active: Set[int] = set()
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._advance_preview)

        # cache valid ids for string parsing
        self._valid_ids: Set[int] = set(LAYOUT_POSITIONS.keys())

    # ---- Selection API ----
    def set_active_mode(self, mode: str) -> None:
        if mode in self.sel:
            self.active_mode = mode
            self.update()

    def selected_ids(self, mode: str | None = None) -> List[int]:
        mode = mode or self.active_mode
        return sorted(self.sel[mode])

    def all_selected_by_type(self) -> Dict[str, List[int]]:
        return {k: sorted(v) for k, v in self.sel.items()}

    def set_selected_ids_by_type(self, buzz: List[int], pulse: List[int], motion: List[int]) -> None:
        self.sel["buzz"] = set(buzz or [])
        self.sel["pulse"] = set(pulse or [])
        self.sel["motion"] = set(motion or [])
        self.update()

    def clear_all(self) -> None:
        for k in self.sel:
            self.sel[k].clear()
        self.update()

    # ---- Preview API ----
    def start_preview(self, merged_pattern: Dict) -> None:
        """Accepts a pattern dict: {'steps': [{'commands': [...], 'delay_after_ms': int}, ...]}"""
        self.stop_preview()
        steps = merged_pattern.get("steps", []) or []

        def ids_from_any(obj) -> Set[int]:
            """Extract actuator ids from dict/list/tuple/string forms."""
            out: Set[int] = set()
            if obj is None:
                return out
            # dict cases
            if isinstance(obj, dict):
                for k in ("device", "id", "actuator", "address", "addr"):
                    v = obj.get(k)
                    if isinstance(v, int) and v in self._valid_ids:
                        out.add(v)
                for k in ("devices", "ids", "actuators"):
                    arr = obj.get(k)
                    if isinstance(arr, (list, tuple, set)):
                        for v in arr:
                            if isinstance(v, int) and v in self._valid_ids:
                                out.add(v)
                return out
            # sequence cases
            if isinstance(obj, (list, tuple, set)):
                for v in obj:
                    if isinstance(v, int) and v in self._valid_ids:
                        out.add(v)
                    elif isinstance(v, (list, tuple)):  # nested pairs like [id, duty]
                        for vv in v:
                            if isinstance(vv, int) and vv in self._valid_ids:
                                out.add(vv)
                return out
            # string cases
            if isinstance(obj, str):
                # grab all integers and keep those that are valid device ids
                for s in re.findall(r"-?\d+", obj):
                    try:
                        iv = int(s)
                        if iv in self._valid_ids:
                            out.add(iv)
                    except Exception:
                        pass
                return out
            # fallback: single int
            if isinstance(obj, int) and obj in self._valid_ids:
                out.add(obj)
            return out

        def extract_devices(cmds) -> Set[int]:
            devs: Set[int] = set()
            for c in cmds or []:
                devs |= ids_from_any(c)
            return devs

        self._preview_steps = [(extract_devices(s.get("commands", [])), int(s.get("delay_after_ms", 0) or 0))
                               for s in steps]
        if not self._preview_steps:
            return
        self._preview_idx = -1
        self._advance_preview()

    def stop_preview(self) -> None:
        self._preview_timer.stop()
        self._preview_idx = -1
        self._preview_active.clear()
        self.update()

    def is_previewing(self) -> bool:
        return self._preview_timer.isActive()

    def _advance_preview(self) -> None:
        self._preview_idx += 1
        if self._preview_idx >= len(self._preview_steps):
            self.stop_preview()
            return
        active, delay = self._preview_steps[self._preview_idx]
        self._preview_active = set(active)
        self.update()
        self._preview_timer.start(max(PREVIEW_MIN_DELAY_MS, int(delay)))

    # ---- Internal geometry ----
    def _compute_min_spacing(self) -> float:
        ids = list(LAYOUT_POSITIONS.keys())
        if len(ids) <= 1:
            return 1.0
        mind = float("inf")
        pts = [LAYOUT_POSITIONS[i] for i in ids]
        for i in range(len(pts)):
            x1, y1 = pts[i]
            for j in range(i + 1, len(pts)):
                x2, y2 = pts[j]
                d = math.hypot(x2 - x1, y2 - y1)
                if d > 0:
                    mind = min(mind, d)
        return mind if math.isfinite(mind) else 1.0

    def _compute_geometry(self, w: int, h: int) -> None:
        dx = max(self._maxx - self._minx, 1e-6)
        dy = max(self._maxy - self._miny, 1e-6)
        avail_w = max(0.0, w - 2 * self._outer_margin)
        avail_h = max(0.0, h - 2 * self._outer_margin)

        # initial scale ignoring radius
        scale0 = min(avail_w / dx, avail_h / dy) if (avail_w > 0 and avail_h > 0) else 1.0

        # radius from spacing
        r0 = 0.42 * self._min_spacing * scale0
        r0 = max(10.0, min(r0, 38.0))

        # refine scale to fit circles
        scale = min(
            (avail_w - 2 * r0) / dx if (avail_w - 2 * r0) > 0 else scale0,
            (avail_h - 2 * r0) / dy if (avail_h - 2 * r0) > 0 else scale0,
        )
        scale = max(scale, 1e-3)
        radius = 0.42 * self._min_spacing * scale
        radius = max(10.0, min(radius, 38.0))

        # --- CENTER the layout within the widget (not left-aligned) ---
        width_px  = dx * scale + 2 * radius
        height_px = dy * scale + 2 * radius
        # centers ensure >= outer_margin because width_px <= w - 2*outer_margin
        xoff = (w - width_px) / 2 - self._minx * scale + radius
        yoff = (h - height_px) / 2 - self._miny * scale + radius

        self._scale, self._r, self._xoff, self._yoff = scale, radius, xoff, yoff

    def _center_px(self, ax: float, ay: float) -> tuple[float, float]:
        return (self._xoff + ax * self._scale, self._yoff + ay * self._scale)

    # ---- Qt events ----
    def paintEvent(self, e) -> None:
        self._compute_geometry(self.width(), self.height())

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QBrush(Qt.GlobalColor.darkGray))
        base_pen = QPen(Qt.GlobalColor.black, 2)
        p.setPen(base_pen)

        r = self._r
        dot_r = max(4.0, r * 0.18)
        s = r * 0.52  # badge offset
        for aid, (ax, ay) in LAYOUT_POSITIONS.items():
            cx, cy = self._center_px(ax, ay)
            rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)

            in_active = aid in self.sel[self.active_mode]
            p.setBrush(QBrush(COLORS[self.active_mode] if in_active else Qt.GlobalColor.lightGray))
            p.drawEllipse(rect)

            # Preview highlight (thick ring if currently active)
            if aid in self._preview_active:
                ring = QPen(Qt.GlobalColor.green, 5)
                p.setPen(ring)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(rect.adjusted(2, 2, -2, -2))
                p.setPen(base_pen)

            # Membership badges: left=buzz, mid=pulse, right=motion
            for name, dx in (("buzz", -s), ("pulse", 0.0), ("motion", s)):
                if aid in self.sel[name]:
                    p.setBrush(QBrush(COLORS[name]))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QRectF(cx + dx - dot_r/2, cy - s - dot_r/2, dot_r, dot_r))
                    p.setPen(base_pen)

            # ID label
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(aid))

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.MouseButton.LeftButton:
            return
        aid = self._hit_test(e.position())
        if aid is None:
            return
        s = self.sel[self.active_mode]
        if aid in s: s.remove(aid)
        else: s.add(aid)
        self.update()

    def _hit_test(self, pos: QPointF) -> int | None:
        r2 = self._r * self._r
        for aid, (ax, ay) in LAYOUT_POSITIONS.items():
            cx, cy = self._center_px(ax, ay)
            if (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2 <= r2:
                return aid
        return None
