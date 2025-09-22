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
        return bool(getattr(self.api, "connected", False))

    # ----------------------- primitives -----------------------
    def _send(self, addr: int, duty: int, freq_idx: int, start: bool) -> bool:
        start_or_stop = 1 if start else 0
        with self._lock:
            try:
                return bool(self.api.send_command(addr, duty, freq_idx, start_or_stop))
            except Exception as e:
                print(f"[ERR] send_command({addr=}, {duty=}, {freq_idx=}, {start_or_stop=}) → {e}")
                return False

    def stop_actuators(self, actuators: Iterable[int]) -> None:
        for a in set(actuators):
            self._send(a, 0, 0, False)

    # ----------------------- patterns -----------------------
    def play_buzz(self, actuators: Iterable[int], duty: int, freq_idx: int, duration_ms: int) -> None:
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
        if not schedule:
            return
        step_s = max(0.001, int(step_ms) / 1000.0)

        def _worker(stop_evt):
            prev: set[int] = set()
            used: set[int] = set()
            try:
                for frame in schedule:
                    if stop_evt.is_set():
                        break
                    current = {addr for (addr, duty) in frame if duty > 0}
                    # start/update current frame
                    for addr, duty in frame:
                        if duty > 0:
                            self._send(addr, duty, freq_idx, True)
                            used.add(addr)
                    # stop those not in current frame
                    for addr in (prev - current):
                        self._send(addr, 0, freq_idx, False)
                    prev = current
                    t_end = time.time() + step_s
                    while time.time() < t_end:
                        if stop_evt.is_set():
                            break
                        time.sleep(0.002)
            finally:
                # all off
                for addr in used:
                    self._send(addr, 0, freq_idx, False)

        runner = _Runner(_worker)
        self._runners.append(runner)
        runner.start()
    
    def play_motion(
    self,
    path: Iterable[int],
    duty: int,
    freq_idx: int,
    step_ms: int,
    steps_per_hop: int,
    loops: int,
) -> None:
        pts = [int(x) for x in path]
        if len(pts) < 2 or steps_per_hop <= 0 or loops <= 0:
            return

        duty = max(0, min(15, int(duty)))
        step_s = max(1, int(step_ms)) / 1000.0
        steps_per_hop = max(1, int(steps_per_hop))
        loops = max(1, int(loops))

        # Build overlapping triplets using quadratic Bernstein weights (3-act phantom).
        # We pad the path at both ends so every step uses exactly 3 actuators.
        ext = [pts[0]] + pts + [pts[-1]]

        def _worker(stop_evt):
            prev_set = set()
            try:
                for _ in range(loops):
                    for i in range(len(ext) - 2):
                        a, b, c = ext[i], ext[i + 1], ext[i + 2]
                        for k in range(steps_per_hop):
                            if stop_evt.is_set():
                                raise SystemExit
                            u = k / float(steps_per_hop)  # [0,1)
                            wa = (1 - u) * (1 - u)
                            wb = 2 * u * (1 - u)
                            wc = u * u
                            cmds = [
                                (a, int(round(duty * wa))),
                                (b, int(round(duty * wb))),
                                (c, int(round(duty * wc))),
                            ]
                            current = {a, b, c}

                            # Start/update current triad
                            for addr, d in cmds:
                                d = max(0, min(15, d))
                                if d > 0:
                                    self._send(addr, d, freq_idx, True)
                                else:
                                    self._send(addr, 0, freq_idx, False)

                            # Stop any actuator that left the triad
                            for addr in (prev_set - current):
                                self._send(addr, 0, freq_idx, False)
                            prev_set = current

                            # Timing
                            t_end = time.time() + step_s
                            while time.time() < t_end:
                                if stop_evt.is_set():
                                    raise SystemExit
                                time.sleep(0.004)

                    # Final step at u=1 for the last triplet
                    a, b, c = ext[-3], ext[-2], ext[-1]
                    self._send(a, 0, freq_idx, False)
                    self._send(b, 0, freq_idx, False)
                    self._send(c, duty, freq_idx, True)
                    t_end = time.time() + step_s
                    while time.time() < t_end:
                        if stop_evt.is_set():
                            break
                        time.sleep(0.004)
            finally:
                # Ensure all off
                for addr in set(ext):
                    self._send(addr, 0, freq_idx, False)

        runner = _Runner(_worker)
        self._runners.append(runner)
        runner.start()

    def stop_all(self) -> None:
        # Signal and join runners
        for r in self._runners:
            r.stop()
        for r in self._runners:
            r.join(0.2)
        self._runners.clear()
        # Issue stop to every possible address (0..15)
        for a in range(16):
            self._send(a, 0, 0, False)


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
    
    def play_motion(
        self,
        path: Iterable[int],
        duty: int,
        freq_idx: int,
        step_ms: int,
        steps_per_hop: int,
        loops: int,
    ) -> None:
        print(
            f"[MOCK] play_motion(path={list(path)}, duty={duty}, "
            f"freq={freq_idx}, step_ms={step_ms}, steps_per_hop={steps_per_hop}, loops={loops})"
        )

    def stop_all(self) -> None:
        print("[MOCK] stop_all()")