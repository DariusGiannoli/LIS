"""
Event Data Model for Universal Haptic Event Designer (with ADSR Implementation)
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import numpy as np
from scipy import signal   # ← NEW

# ---------------------------------------------------------------------------
#  Helper constants for the oscillator factory
# ---------------------------------------------------------------------------
_DEFAULT_SR   = 1000.0   # Hz
_DEFAULT_DUR  = 1.0      # seconds
_DEFAULT_FREQ = 100.0    # Hz
_DEFAULT_AMP  = 1.0


# ---------------------------------------------------------------------------
#  Enums
# ---------------------------------------------------------------------------
class EventCategory(Enum):
    CRASH       = "crash"
    ISOLATION   = "isolation"
    EMBODIMENT  = "embodiment"
    ALERT       = "alert"
    CUSTOM      = "custom"

class ActuatorPattern(Enum):
    SIMULTANEOUS = "simultaneous"
    SEQUENTIAL   = "sequential"
    WAVE         = "wave"
    RADIAL       = "radial"
    CUSTOM       = "custom"


# ---------------------------------------------------------------------------
#  Data containers
# ---------------------------------------------------------------------------
@dataclass
class WaveformData:
    """Container for haptic waveform data"""
    amplitude: List[Dict[str, float]]            # [{"time": float, "amplitude": float}, ...]
    frequency: List[Dict[str, float]]            # [{"time": float, "frequency": float}, ...]
    duration: float
    sample_rate: float = _DEFAULT_SR

    # ---------- helpers for widgets ------------------------------------
    def get_amplitude_array(self) -> np.ndarray:
        if not self.amplitude:
            return np.array([])
        return np.array([p["amplitude"] for p in self.amplitude])

    def get_frequency_array(self) -> np.ndarray:
        if not self.frequency:
            return np.array([])
        return np.array([p["frequency"] for p in self.frequency])

    def get_time_array(self) -> np.ndarray:
        num_samples = int(self.duration * self.sample_rate)
        return np.linspace(0, self.duration, num_samples)


@dataclass
class ParameterModifications:
    """Container for waveform parameter modifications"""
    intensity_multiplier: float = 1.0
    frequency_shift:     float = 0.0
    duration_scale:      float = 1.0
    amplitude_offset:    float = 0.0
    custom_envelope: Optional[List[float]] = None
    attack_time:   float = 0.0
    decay_time:    float = 0.0
    sustain_level: float = 1.0
    release_time:  float = 0.0


@dataclass
class ActuatorMapping:
    """Container for actuator mapping configuration"""
    active_actuators: List[str]                       # ["A.1", "A.2", ...]
    pattern_type: ActuatorPattern = ActuatorPattern.SIMULTANEOUS
    timing_offsets:    Dict[str, float] = None
    intensity_scaling: Dict[str, float] = None
    zones: List[str] = None

    def __post_init__(self):
        self.timing_offsets    = self.timing_offsets or {}
        self.intensity_scaling = self.intensity_scaling or {}
        self.zones             = self.zones or []


@dataclass
class EventMetadata:
    """Container for event metadata"""
    name:        str
    category:    EventCategory
    description: str = ""
    tags:        List[str] = None
    author:      str = ""
    version:     str = "1.0"
    created_date:  str = ""
    modified_date: str = ""

    def __post_init__(self):
        self.tags = self.tags or []
        timestamp = datetime.now().isoformat()
        if not self.created_date:
            self.created_date = timestamp
        if not self.modified_date:
            self.modified_date = self.created_date


# ---------------------------------------------------------------------------
#  Main class
# ---------------------------------------------------------------------------
class HapticEvent:
    """Main event container"""

    # ------------- construction & persistence --------------------------
    def __init__(self,
                 name: str = "New Event",
                 category: EventCategory = EventCategory.CUSTOM) -> None:
        self.metadata             = EventMetadata(name=name, category=category)
        self.waveform_data: Optional[WaveformData] = None
        self.parameter_modifications = ParameterModifications()
        self.actuator_mapping     = ActuatorMapping(active_actuators=[])
        self.original_haptic_file: Optional[str] = None

    # -------------------------------------------------------------------
    #  Factory for built-in oscillators (GUI "Oscillators" library)
    # -------------------------------------------------------------------
    @classmethod
    def new_basic_oscillator(
            cls,
            osc_type: str,
            *,
            frequency: float  = _DEFAULT_FREQ,
            amplitude: float  = _DEFAULT_AMP,
            duration:  float  = _DEFAULT_DUR,
            sample_rate: float = _DEFAULT_SR
    ) -> "HapticEvent":
        """
        Quickly build a HapticEvent containing one of the eight standard
        oscillators: Sine, Square, Saw, Triangle, Chirp, FM, PWM, Noise.
        """
        t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)

        if   osc_type == "Sine":
            y = np.sin(2 * np.pi * frequency * t)
        elif osc_type == "Square":
            y = np.sign(np.sin(2 * np.pi * frequency * t))
        elif osc_type == "Saw":
            y = signal.sawtooth(2 * np.pi * frequency * t, 1.0)
        elif osc_type == "Triangle":
            y = signal.sawtooth(2 * np.pi * frequency * t, 0.5)
        elif osc_type == "Chirp":
            y = signal.chirp(t, f0=frequency, t1=duration,
                             f1=frequency * 4, method="linear")
        elif osc_type == "FM":          # carrier + simple sinusoidal modulator
            carr = 2 * np.pi * frequency * t
            mod  = np.sin(2 * np.pi * frequency * 0.25 * t)
            y = np.sin(carr + 2 * mod)
        elif osc_type == "PWM":
            y = signal.square(2 * np.pi * frequency * t, duty=0.5)
        elif osc_type == "Noise":
            rng = np.random.default_rng()
            y   = rng.uniform(-1.0, 1.0, size=t.shape)
        else:
            raise ValueError(f"Unsupported oscillator type: {osc_type}")

        # Scale amplitude and clamp
        y = np.clip(amplitude * y, -1.0, 1.0)

        event = cls(name=f"{osc_type} Oscillator", category=EventCategory.CUSTOM)

        # Amplitude envelope: one point per sample so the editor can plot it
        event.waveform_data = WaveformData(
            amplitude=_build_envelope_points(t, y),
            frequency=[
                {"time": 0.0,      "frequency": frequency},
                {"time": duration, "frequency": frequency}
            ],
            duration=duration,
            sample_rate=sample_rate
        )
        return event

    # -------------------------------------------------------------------
    #  ADSR Envelope Application (NEW)
    # -------------------------------------------------------------------
    def _apply_adsr_envelope(self, signal: np.ndarray, time_array: np.ndarray) -> np.ndarray:
        """Apply ADSR envelope to the signal"""
        p = self.parameter_modifications
        duration = time_array[-1] if len(time_array) > 0 else 1.0
        
        # If no ADSR parameters set, return original signal
        if (p.attack_time == 0 and p.decay_time == 0 and 
            p.sustain_level == 1.0 and p.release_time == 0):
            return signal
            
        envelope = np.ones_like(time_array)
        
        # Attack phase
        if p.attack_time > 0:
            attack_samples = int(p.attack_time * self.waveform_data.sample_rate)
            attack_samples = min(attack_samples, len(envelope))
            if attack_samples > 0:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
        
        # Decay phase
        if p.decay_time > 0:
            attack_samples = int(p.attack_time * self.waveform_data.sample_rate)
            decay_samples = int(p.decay_time * self.waveform_data.sample_rate)
            decay_start = min(attack_samples, len(envelope))
            decay_end = min(decay_start + decay_samples, len(envelope))
            if decay_end > decay_start:
                envelope[decay_start:decay_end] = np.linspace(1, p.sustain_level, decay_end - decay_start)
        
        # Sustain phase
        attack_samples = int(p.attack_time * self.waveform_data.sample_rate)
        decay_samples = int(p.decay_time * self.waveform_data.sample_rate)
        release_samples = int(p.release_time * self.waveform_data.sample_rate)
        
        sustain_start = min(attack_samples + decay_samples, len(envelope))
        sustain_end = max(0, len(envelope) - release_samples)
        
        if sustain_end > sustain_start:
            envelope[sustain_start:sustain_end] = p.sustain_level
        
        # Release phase
        if p.release_time > 0 and release_samples > 0:
            release_start = max(0, len(envelope) - release_samples)
            if release_start < len(envelope):
                current_level = envelope[release_start] if release_start > 0 else p.sustain_level
                envelope[release_start:] = np.linspace(current_level, 0, len(envelope) - release_start)
        
        return signal * envelope

    # -------------------------------------------------------------------
    #  File I/O helpers  (unchanged code below)
    # -------------------------------------------------------------------
    def load_from_haptic_file(self, file_path: str) -> bool:
        """Load waveform data from .haptic file"""
        try:
            with open(file_path, "r") as f:
                haptic_data = json.load(f)

            signals    = haptic_data.get("signals", {})
            continuous = signals.get("continuous", {})
            envelopes  = continuous.get("envelopes", {})

            amp_data  = envelopes.get("amplitude", [])
            freq_data = envelopes.get("frequency", [])

            duration = 0.0
            if amp_data:
                duration = max(duration, max(p["time"] for p in amp_data))
            if freq_data:
                duration = max(duration, max(p["time"] for p in freq_data))

            self.waveform_data = WaveformData(
                amplitude=amp_data,
                frequency=freq_data,
                duration=duration
            )
            self.original_haptic_file = file_path
            return True

        except Exception as e:
            print(f"Error loading haptic file: {e}")
            return False

    def get_modified_waveform(self) -> Optional[np.ndarray]:
        """Get amplitude array after user modifications including ADSR"""
        if not self.waveform_data:
            return None

        amp = self.waveform_data.get_amplitude_array()
        if amp.size == 0:
            return None

        # Get time array for ADSR application
        time_array = np.array([pt["time"] for pt in self.waveform_data.amplitude])

        mod = amp.copy()
        p   = self.parameter_modifications

        # Apply intensity and offset first
        mod *= p.intensity_multiplier
        mod += p.amplitude_offset

        # Apply custom envelope if present
        if p.custom_envelope and len(p.custom_envelope) == len(mod):
            mod *= np.array(p.custom_envelope)

        # Apply ADSR envelope
        mod = self._apply_adsr_envelope(mod, time_array)

        return np.clip(mod, -1.0, 1.0)

    def get_modified_frequency(self) -> Optional[np.ndarray]:
        """Get frequency array after user modifications"""
        if not self.waveform_data or not self.waveform_data.frequency:
            return None

        freq = self.waveform_data.get_frequency_array()
        if freq.size == 0:
            return None

        p = self.parameter_modifications
        return freq + p.frequency_shift

    # ---------- (de)serialisation --------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serialisable dict (Enum → value)"""
        md   = asdict(self.metadata);  md["category"]      = self.metadata.category.value
        act  = asdict(self.actuator_mapping); act["pattern_type"] = self.actuator_mapping.pattern_type.value
        return {
            "metadata":               md,
            "waveform_data":          asdict(self.waveform_data) if self.waveform_data else None,
            "parameter_modifications":asdict(self.parameter_modifications),
            "actuator_mapping":       act,
            "original_haptic_file":   self.original_haptic_file
        }

    def save_to_file(self, file_path: str) -> bool:
        try:
            self.metadata.modified_date = datetime.now().isoformat()
            with open(file_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving event: {e}")
            return False

    @classmethod
    def load_from_file(cls, file_path: str) -> Optional["HapticEvent"]:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            event = cls()
            # -------- metadata ------------------------------------------
            md = data.get("metadata", {})
            if "category" in md:
                md["category"] = EventCategory(md["category"])
            event.metadata = EventMetadata(**md)

            # -------- waveform ------------------------------------------
            wf = data.get("waveform_data")
            if wf:
                event.waveform_data = WaveformData(**wf)

            # -------- mods ----------------------------------------------
            pm = data.get("parameter_modifications", {})
            event.parameter_modifications = ParameterModifications(**pm)

            # -------- actuators -----------------------------------------
            act = data.get("actuator_mapping", {})
            if "pattern_type" in act:
                act["pattern_type"] = ActuatorPattern(act["pattern_type"])
            event.actuator_mapping = ActuatorMapping(**act)

            event.original_haptic_file = data.get("original_haptic_file")
            return event

        except Exception as e:
            print(f"Error loading event: {e}")
            return None


# ---------------------------------------------------------------------------
#  Local utility
# ---------------------------------------------------------------------------
def _build_envelope_points(t: np.ndarray, y: np.ndarray) -> List[Dict[str, float]]:
    """Convert two equal-length arrays into list-of-dicts for WaveformData."""
    return [{"time": float(tt), "amplitude": float(yy)} for tt, yy in zip(t, y)]