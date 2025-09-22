"""Serial backend that wraps your local serial_api.SERIAL_API class.

Assumptions based on your file:
- `SERIAL_API.create_command(addr, duty, freq, start_or_stop)` exists
- `SERIAL_API.send_command(addr, duty, freq, start_or_stop) -> bool` exists
- We can set `api.serial_connection` to a `serial.Serial` and mark `api.connected = True`

If import fails, we expose a MockBackend so the UI still runs.
"""
from __future__ import annotations

import threading
import time
from typing import Iterable, List, Optional

try:
    # Your local file placed next to this project
    from serial_api import SERIAL_API  # type: ignore
except Exception as e:  # pragma: no cover
    SERIAL_API = None  # will trigger MockBackend in main

try:
    import serial  # pyserial
    from serial.tools import list_ports
except Exception as e:  # pragma: no cover
    serial = None
    list_ports = None


class _Runner:
    """Small helper to run timed patterns in a background thread.

    Each runner owns a stop Event so Stop All can interrupt cleanly.
    """

    def __init__(self, target, *args, **kwargs):
        self._stop = threading.Event()
        self._thread = threading.Thread(target=target, args=(*args, self._stop), kwargs=kwargs, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def join(self, timeout: Optional[float] = None):
        self._thread.join(timeout)


class BaseBackend:
    def scan_ports(self) -> List[str]:
        raise NotImplementedError

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError

    def play_buzz(self, actuators: Iterable[int], duty: int, freq_idx: int, duration_ms: int) -> None:
        raise NotImplementedError

    def play_pulse(self, actuators: Iterable[int], duty: int, freq_idx: int, on_ms: int, off_ms: int, repetitions: int) -> None:
        raise NotImplementedError
    
    def play_motion_schedule(
        self,
        schedule: list[list[tuple[int, int]]],  # per-step [(addr, duty), ...]
        freq_idx: int,
        step_ms: int,
    ) -> None:
        raise NotImplementedError

    def stop_actuators(self, actuators: Iterable[int]) -> None:
        raise NotImplementedError

    def stop_all(self) -> None:
        raise NotImplementedError


class SerialBackend(BaseBackend):
    """Real backend using your `serial_api.SERIAL_API` implementation."""

    def __init__(self):
        if SERIAL_API is None:
            raise RuntimeError("serial_api.py not found or failed to import")
        self.api = SERIAL_API()
        self._lock = threading.Lock()
        self._runners: List[_Runner] = []
        self._warned_not_conn = False

    # ----------------------- connection -----------------------
    def scan_ports(self) -> List[str]:
        if list_ports is None:
            return []
        return [p.device for p in list_ports.comports()]

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        if serial is None:
            return False
        try:
            ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.01)
            # Adopt into your API instance
            setattr(self.api, "serial_connection", ser)
            setattr(self.api, "connected", True)
            return True
        except Exception as e:
            print(f"[ERR] connect failed: {e}")
            return False

    def disconnect(self) -> None:
        try:
            ser = getattr(self.api, "serial_connection", None)
            if ser:
                ser.close()
            setattr(self.api, "connected", False)
        except Exception:
            pass

    def is_connected(self) -> bool:
        ser = getattr(self.api, "serial_connection", None)
        try:
            return bool(getattr(self.api, "connected", False) and ser and getattr(ser, "is_open", True))
        except Exception:
            return False

    # ----------------------- primitives -----------------------
    def _send(self, addr: int, duty: int, freq_idx: int, start: bool) -> bool:
        if not self.is_connected():
            # Warn only once to avoid console spam
            if not self._warned_not_conn:
                print("[WARN] Serial not connected; dropping outgoing commands.")
                self._warned_not_conn = True
            return False

        start_or_stop = 1 if start else 0
        with self._lock:
            try:
                ok = bool(self.api.send_command(addr, duty, freq_idx, start_or_stop))
                return ok
            except Exception as e:
                print(f"[ERR] send_command(addr={addr}, duty={duty}, freq={freq_idx}, start={start_or_stop}) → {e}")
                return False


    def stop_actuators(self, actuators: Iterable[int]) -> None:
        for a in set(actuators):
            self._send(a, 0, 0, False)
    
    def stop_all(self) -> None:
        # Stop and join any running pattern threads
        try:
            runners = getattr(self, "_runners", [])
            for r in list(runners):
                try:
                    r.stop()
                except Exception:
                    pass
            for r in list(runners):
                try:
                    r.join(0.2)
                except Exception:
                    pass
            if hasattr(self, "_runners"):
                self._runners.clear()
        except Exception:
            pass
        # Send explicit STOPs only if hardware is connected
        if not self.is_connected():
            return

        for addr in range(16):  # 0..15
            try:
                self._send(addr, 0, 0, False)
            except Exception:
                continue



    # ----------------------- patterns -----------------------
    def play_buzz(self, actuators: Iterable[int], duty: int, freq_idx: int, duration_ms: int) -> None:
        if not self.is_connected():
            return
        acts = list(set(int(x) for x in actuators))
        if not acts:
            return

        def _worker(stop_evt: threading.Event):
            # Start all
            for a in acts:
                self._send(a, duty, freq_idx, True)
            # Hold
            t_end = time.time() + max(0, duration_ms) / 1000.0
            while time.time() < t_end:
                if stop_evt.is_set():
                    break
                time.sleep(0.01)
            # Stop all
            for a in acts:
                self._send(a, duty, freq_idx, False)

        runner = _Runner(_worker)
        self._runners.append(runner)
        runner.start()

    def play_pulse(self, actuators: Iterable[int], duty: int, freq_idx: int, on_ms: int, off_ms: int, repetitions: int) -> None:
        if not self.is_connected():
            return
        acts = list(set(int(x) for x in actuators))
        if not acts or repetitions <= 0:
            return

        on_s = max(0, on_ms) / 1000.0
        off_s = max(0, off_ms) / 1000.0

        def _worker(stop_evt: threading.Event):
            for _ in range(repetitions):
                if stop_evt.is_set():
                    break
                for a in acts:
                    self._send(a, duty, freq_idx, True)
                t_end = time.time() + on_s
                while time.time() < t_end:
                    if stop_evt.is_set():
                        break
                    time.sleep(0.005)
                for a in acts:
                    self._send(a, duty, freq_idx, False)
                t_end = time.time() + off_s
                while time.time() < t_end:
                    if stop_evt.is_set():
                        break
                    time.sleep(0.005)

        runner = _Runner(_worker)
        self._runners.append(runner)
        runner.start()
    
    def play_motion_schedule(
    self,
    schedule: list[list[tuple[int, int]]],
    freq_idx: int,
    step_ms: int,
) -> None:
        if not self.is_connected():
            return
        if not schedule:
            return
        step_s = max(0.001, int(step_ms) / 1000.0)

    def play_motion_schedule(
        self,
        schedule: list[list[tuple[int, int]]],
        freq_idx: int,
        step_ms: int,
    ) -> None:
        if not schedule:
            return

        # Treat SOA as the step period
        SOA_s = max(0.001, int(step_ms) / 1000.0)

        # From Eq. (11): SOA = 0.32*duration + 0.0473  => duration = (SOA - 0.0473) / 0.32
        # Clamp so duration <= SOA and never negative.
        dur_s = max(0.0, (SOA_s - 0.0473) / 0.32)
        dur_s = min(dur_s, SOA_s)          # enforce duration ≤ SOA
        # Keep a tiny guard so we have some off-time even at small SOA.
        dur_s = max(0.0, min(dur_s, SOA_s - 0.002))
        off_s = max(0.0, SOA_s - dur_s)

        def _worker(stop_evt):
            prev_on: set[int] = set()
            used: set[int] = set()
            try:
                for frame in schedule:
                    if stop_evt.is_set():
                        break

                    # Turn ON current frame
                    current_on = {addr for (addr, duty) in frame if duty > 0}
                    for addr, duty in frame:
                        if duty > 0:
                            self._send(addr, duty, freq_idx, True)
                            used.add(addr)

                    # Hold for 'duration' (per Park et al.)
                    t_end = time.time() + dur_s
                    while time.time() < t_end:
                        if stop_evt.is_set():
                            break
                        time.sleep(0.001)

                    # Turn OFF anything that is not supposed to overlap into next SOA
                    for addr in current_on:
                        self._send(addr, 0, freq_idx, False)

                    # Idle for the remainder of SOA
                    t_end = time.time() + off_s
                    while time.time() < t_end:
                        if stop_evt.is_set():
                            break
                        time.sleep(0.001)

                    prev_on = current_on

            finally:
                for addr in used:
                    self._send(addr, 0, freq_idx, False)

        runner = _Runner(_worker)
        self._runners.append(runner)
        runner.start()

    


class MockBackend(BaseBackend):
    """No‑hardware backend; prints to console so you can test the UI."""

    def __init__(self):
        self._connected = True
        self._runners: List[_Runner] = []

    def scan_ports(self) -> List[str]:
        return ["MOCK"]

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        print(f"[MOCK] connect({port=}, {baudrate=})")
        self._connected = True
        return True

    def disconnect(self) -> None:
        print("[MOCK] disconnect()")
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def _send(self, addr: int, duty: int, freq_idx: int, start: bool) -> bool:
        print(f"[MOCK] send addr={addr} duty={duty} freq={freq_idx} start={start}")
        return True

    def stop_actuators(self, actuators: Iterable[int]) -> None:
        for a in set(actuators):
            self._send(a, 0, 0, False)

    def play_buzz(self, actuators: Iterable[int], duty: int, freq_idx: int, duration_ms: int) -> None:
        print(f"[MOCK] play_buzz({list(actuators)}, duty={duty}, freq={freq_idx}, duration_ms={duration_ms})")

    def play_pulse(self, actuators: Iterable[int], duty: int, freq_idx: int, on_ms: int, off_ms: int, repetitions: int) -> None:
        print(f"[MOCK] play_pulse({list(actuators)}, duty={duty}, freq={freq_idx}, on={on_ms}, off={off_ms}, rep={repetitions})")
    
    def play_motion_schedule(
        self,
        schedule: list[list[tuple[int, int]]],
        freq_idx: int,
        step_ms: int,
    ) -> None:
        print(f"[MOCK] play_motion_schedule(len_steps={len(schedule)}, freq={freq_idx}, step_ms={step_ms})")
        if schedule[:1]:
            print(f"[MOCK] first frame: {schedule[0][:6]}")


    def stop_all(self) -> None:
        print("[MOCK] stop_all()")