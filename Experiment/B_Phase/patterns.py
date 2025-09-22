"""Pattern models + JSON persistence for the library."""
from __future__ import annotations
from dataclasses import dataclass, asdict, fields
from typing import Dict, List, Literal, Optional
import json
import os

Mode = Literal["buzz", "pulse", "motion"]

def _filter_fields(cls, data: Dict) -> Dict:
    """Keep only keys that exist on the target dataclass 'cls'."""
    if not isinstance(data, dict):
        return {}
    allowed = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in allowed}


@dataclass
class BuzzPattern:
    actuators: List[int]
    duty: int  # 0..15
    freq_idx: int  # 0..7
    duration_ms: int

    def to_dict(self):
        d = asdict(self)
        d.update({"mode": "buzz"})
        return d


@dataclass
class PulsePattern:
    actuators: List[int]
    duty: int
    freq_idx: int
    on_ms: int
    off_ms: int
    repetitions: int

    def to_dict(self):
        d = asdict(self)
        d.update({"mode": "pulse"})
        return d

@dataclass
class MotionPattern:
    # Drawn path stored normalized to the grid canvas rect [0..1]×[0..1]
    path_norm: List[List[float]]  # [[x,y], ...]
    intensity: int                # 0..15
    freq_idx: int                 # 0..7
    total_ms: int                 # total animation time
    step_ms: int                  # per-step duration (will be clamped ≤ 69 at runtime)
    max_phantom: int              # number of concurrent phantoms
    sampling_hz: int              # resampling frequency of the polyline

    def to_dict(self):
        d = asdict(self)
        d.update({"mode": "motion"})
        return d


@dataclass
class MultiPattern:
    name: str
    buzz: Optional[BuzzPattern] = None
    pulse: Optional[PulsePattern] = None
    motion: Optional[MotionPattern] = None  # NEW

    def summary(self) -> str:
        parts = []
        if self.buzz and self.buzz.actuators:
            parts.append(f"Buzz({len(self.buzz.actuators)})")
        if self.pulse and self.pulse.actuators:
            parts.append(f"Pulse({len(self.pulse.actuators)})")
        if self.motion and getattr(self.motion, "path_norm", None):
            try:
                npts = len(self.motion.path_norm)
            except Exception:
                npts = 0
            parts.append(f"Motion({npts} pts)")
        return ", ".join(parts) or "(empty)"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "buzz": self.buzz.to_dict() if self.buzz else None,
            "pulse": self.pulse.to_dict() if self.pulse else None,
            "motion": self.motion.to_dict() if self.motion else None,  # NEW
        }

    @staticmethod
    def from_dict(d: Dict) -> "MultiPattern":
        b = d.get("buzz")
        p = d.get("pulse")
        m = d.get("motion")

        # Filter unknown keys (e.g., legacy "mode") before constructing dataclasses
        buzz_obj = BuzzPattern(**_filter_fields(BuzzPattern, b)) if b else None
        pulse_obj = PulsePattern(**_filter_fields(PulsePattern, p)) if p else None
        motion_obj = None

        if m:
            if "path_norm" in m:
                # New schema: just filter to the MotionPattern fields
                motion_obj = MotionPattern(**_filter_fields(MotionPattern, m))

            elif "path" in m:
                # Legacy schema → convert addresses (0..15) to normalized grid centers
                legacy_path = m.get("path") or []
                if isinstance(legacy_path, list) and all(isinstance(a, int) for a in legacy_path):
                    path_norm: List[List[float]] = []
                    for addr in legacy_path:
                        addr = int(addr)
                        row, col = addr // 4, addr % 4  # 4x4 grid
                        x = (col + 0.5) / 4.0
                        y = (row + 0.5) / 4.0
                        path_norm.append([x, y])
                else:
                    path_norm = []

                # Map old fields to new ones with sensible defaults
                intensity = int(m.get("duty", 10))
                freq_idx = int(m.get("freq_idx", 3))
                step_ms_old = int(m.get("step_ms", 40))
                steps_per_hop = int(m.get("steps_per_hop", 6))
                loops = int(m.get("loops", 1))

                # Rough total time estimate for legacy patterns
                hops = max(1, len(legacy_path))
                total_ms = max(step_ms_old * steps_per_hop * hops * loops, step_ms_old)

                motion_obj = MotionPattern(
                    path_norm=path_norm,
                    intensity=intensity,
                    freq_idx=freq_idx,
                    total_ms=total_ms,
                    step_ms=min(69, step_ms_old),
                    max_phantom=1,        # legacy had no multi-phantom notion
                    sampling_hz=60,       # reasonable default
                )
            else:
                # Unknown shape → ignore safely
                motion_obj = None

        return MultiPattern(
            name=d.get("name", "Unnamed"),
            buzz=buzz_obj,
            pulse=pulse_obj,
            motion=motion_obj,
        )


# ---------------- persistence ----------------

LIB_FILE = "patterns.json"


def load_library(path: str = LIB_FILE) -> List[MultiPattern]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [MultiPattern.from_dict(x) for x in data]


def save_library(items: List[MultiPattern], path: str = LIB_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([x.to_dict() for x in items], f, indent=2)