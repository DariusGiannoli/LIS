import csv, time
import serial, serial.tools.list_ports

# ---------- util ----------
PR_VAL = [85, 72, 60, 52, 44, 37, 32, 27]  # doit matcher le PIC
def freq_idx_to_hz(idx: int) -> float:
    # f_pwm = 2 MHz / (PR2+1), f_mech = f_pwm / 200
    pr = PR_VAL[idx]
    f_pwm = 2_000_000.0 / (pr + 1)
    return f_pwm / 200.0

# ---------- tests ----------
def sweep_duty(api, addr=0, freq_idx=3, duty_steps=(0, 20, 40, 60, 80, 99),
               dwell_s=1.0, csv_name="results_duty.csv"):
    with open(csv_name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "test", "addr", "duty", "freq_idx", "freq_hz", "action"])
        # start once at duty=0 to arm the chain cleanly
        api.send_command(addr, 0, freq_idx, 1)
        time.sleep(0.5)
        for d in duty_steps:
            api.send_command(addr, int(d), freq_idx, 1)
            w.writerow([time.time(), "sweep_duty", addr, d, freq_idx, f"{freq_idx_to_hz(freq_idx):.2f}", "START"])
            time.sleep(dwell_s)
        api.send_command(addr, 0, freq_idx, 0)
        w.writerow([time.time(), "sweep_duty", addr, 0, freq_idx, f"{freq_idx_to_hz(freq_idx):.2f}", "STOP"])

def sweep_freq(api, addr=0, duty=60, freq_indices=tuple(range(8)),
               dwell_s=1.0, csv_name="results_freq.csv"):
    with open(csv_name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "test", "addr", "duty", "freq_idx", "freq_hz", "action"])
        for fi in freq_indices:
            api.send_command(addr, duty, fi, 1)
            w.writerow([time.time(), "sweep_freq", addr, duty, fi, f"{freq_idx_to_hz(fi):.2f}", "START"])
            time.sleep(dwell_s)
        api.send_command(addr, 0, freq_indices[-1], 0)
        w.writerow([time.time(), "sweep_freq", addr, 0, freq_indices[-1],
                    f"{freq_idx_to_hz(freq_indices[-1]):.2f}", "STOP"])

def burst_test(api, addr=0, duty=70, freq_idx=3,
               on_ms=100, off_ms=200, repeats=20,
               csv_name="results_burst.csv"):
    with open(csv_name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "test", "addr", "duty", "freq_idx", "freq_hz", "action"])
        for k in range(repeats):
            api.send_command(addr, duty, freq_idx, 1)
            w.writerow([time.time(), "burst", addr, duty, freq_idx, f"{freq_idx_to_hz(freq_idx):.2f}", f"START_{k}"])
            time.sleep(on_ms / 1000.0)
            api.send_command(addr, duty, freq_idx, 0)
            w.writerow([time.time(), "burst", addr, duty, freq_idx, f"{freq_idx_to_hz(freq_idx):.2f}", f"STOP_{k}"])
            time.sleep(off_ms / 1000.0)

def stress_stop_start(api, addr=0, duty=50, freq_idx=3,
                      repeats=200, delay_ms=20, csv_name="results_stress.csv"):
    """Envoie START/STOP rapides pour tester la fiabilité du STOP."""
    ok = 0
    with open(csv_name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "test", "i", "action", "ok"])
        for i in range(repeats):
            ok &= api.send_command(addr, duty, freq_idx, 1)
            w.writerow([time.time(), "stress", i, "START", 1])
            time.sleep(delay_ms / 1000.0)
            ok &= api.send_command(addr, duty, freq_idx, 0)
            w.writerow([time.time(), "stress", i, "STOP", 1])
            time.sleep(delay_ms / 1000.0)
    return ok

# ---------- exécution ----------
if __name__ == "__main__":
    from archives.serial_api import SERIAL_API  # ou adapte si dans le même fichier
    api = SERIAL_API()
    devs = api.get_serial_devices()
    print("Ports:", devs)
    if not devs:
        raise SystemExit("No serial devices.")

    # ⚠️ choisis le bon index de port !
    if api.connect_serial_device(devs[2]):  # adapte l’index à ta machine
        addr = 0

        # 1) Sweep duty (plus de pas si tu veux)
        sweep_duty(api, addr=addr, freq_idx=3,
                   duty_steps=list(range(0, 100, 10)) + [99],
                   dwell_s=1.0, csv_name="results_duty.csv")

        # 2) Sweep fréquence
        sweep_freq(api, addr=addr, duty=60,
                   freq_indices=tuple(range(8)),
                   dwell_s=1.0, csv_name="results_freq.csv")

        # 3) Bursts courts (attaque)
        burst_test(api, addr=addr, duty=70, freq_idx=3,
                   on_ms=100, off_ms=200, repeats=30,
                   csv_name="results_burst.csv")

        # 4) Stress STOP/START
        stress_stop_start(api, addr=addr, duty=50, freq_idx=3,
                          repeats=200, delay_ms=20, csv_name="results_stress.csv")

        api.disconnect_serial_device()
    else:
        print("Failed to connect.")