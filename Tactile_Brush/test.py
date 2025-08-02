from python_serial_api import python_serial_api
import time 
# ──‑‑‑‑‑‑‑‑‑ 1.  EDIT THESE FOUR CONSTANTS ONLY ‑‑‑‑‑‑‑‑‑──────────
SERIAL_PORT = "/dev/tty.usbmodem2101"   # Windows? -> "COM3" (just guess & adjust)
CHAIN       = 0# 0‑3 on your unit
#DEVICE      = 0# 0‑15 on that chain
DUTY        = 8                # 0‑15 (higher = stronger)
FREQ        = 6               # 0‑7  (higher = higher freq) 
# ─────────────────────────────────────────────────────────────────

def make_addr(chain: int, device: int) -> int:
    if not (0 <= chain <= 3 and 0 <= device <= 15):
        raise ValueError("chain must be 0‑3 and device 0‑15")
    return chain * 16 + device

if __name__ == "__main__":
    api = python_serial_api()                
    ok = api.connect_serial_device(SERIAL_PORT)       

    if not ok:
        raise SystemExit("❌  Could not open the serial port")


# api.send_command(9, DUTY, FREQ, start_or_stop=1)
# api.send_command(10, DUTY, FREQ, start_or_stop=1)
# api.send_command(14, DUTY, FREQ, start_or_stop=1)
# api.send_command(15, DUTY, FREQ, start_or_stop=1)

# time.sleep(3)
# api.send_command(9, DUTY, FREQ, start_or_stop=0)
# api.send_command(10, DUTY, FREQ, start_or_stop=0)
# api.send_command(14, DUTY, FREQ, start_or_stop=0)

for i in range(17):
    addr = make_addr(CHAIN, i)
    api.send_command(addr, DUTY, FREQ, start_or_stop=1)
    time.sleep(1.5)
    api.send_command(addr, DUTY, FREQ, start_or_stop=0) 
    print(f"✅  Sent START to chain {CHAIN}, device {i} (addr={addr})")
api.disconnect_serial_device()
