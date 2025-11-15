# Random for Gabriel

## Overview

Main changes include moving from 4 to 5 bits for duty, keeping a 3-byte structure but adding a wave parameter in the first byte to switch between sine and square wave.

---

## Bit structure

**Byte 1:** `[W][0][G3][G2][G1][G0][M1][M0]`  
- **W**: waveform (0 = square, 1 = sine)  
- **G**: group (4 bits, 0–15)  
- **M**: mode (00 = STOP, 01 = START, 10 = SOFTSTOP)

**Byte 2:** `[0][0][A5][A4][A3][A2][A1][A0]`  
- **A**: local address (6 bits, 0–63, currently 0–7 used)

**Byte 3:** `[D4][D3][D2][D1][D0][F2][F1][F0]`  
- **D**: duty code (5 bits, 0–31)  
- **F**: frequency index (3 bits, 0–7)

The waveform bit **W** is in Byte 1 so that all high-level control flags (waveform, group, mode) are decoded immediately from the first byte.

---

## `main.c`

### Duty mapping (no LUT)

The duty code `duty5 ∈ [0..31]` is mapped to an approximate percentage in `[0..100)` using a simple linear formula:

$$
\text{duty\_pct} \approx \frac{\text{duty5}}{32} \times 100
$$

In firmware this is implemented with integer arithmetic as:

```c
// duty5_raw in [0..31]
duty_pct = (uint8_t)(((uint16_t)duty5_raw * 100u) / 32u);
```

So:

- duty5 = 0   → duty_pct ≈ 0%
- duty5 = 31  → duty_pct ≈ 96%

This `duty_pct` (0–100) is then used to set the effective PWM amplitude in `lra_set_amp()` for both sine and square wave modes.

---

### Sine waveform (`wave = 1`)

The sine mode uses a signed 64-sample LUT:

```c
#define SINE_LEN 64u
static const int8_t SINE64_8[SINE_LEN] = {
   0,  12,  25,  37,  49,  60,  71,  81,
  90,  99, 106, 113, 118, 122, 125, 127,
 127, 127, 125, 122, 118, 113, 106,  99,
  90,  81,  71,  60,  49,  37,  25,  12,
   0, -12, -25, -37, -49, -60, -71, -81,
 -90, -99,-106,-113,-118,-122,-125,-127,
-127,-127,-125,-122,-118,-113,-106, -99,
 -90, -81, -71, -60, -49, -37, -25, -12
};
```

Mathematically this approximates:

$$
s[k] \approx 127 \cdot \sin\left(2\pi \frac{k}{64}\right), \quad k = 0,\dots,63
$$

Timer1 advances $k$ at a fixed step $\Delta t$, so the output is a discrete-time sinusoid of frequency:

$$
f = \frac{1}{T}, \quad T = 64 \cdot \Delta t
$$

The motor drive amplitude is scaled using `duty_pct` and the instantaneous magnitude of the sine sample:

$$
A_\text{eff}(k) \propto \text{duty\_pct} \cdot \frac{|s[k]|}{127}
$$

In code, this is implemented by:

1. Converting `duty_pct` to a global 10-bit scale factor `scale` via `lra_set_amp(duty_pct)`.
2. Multiplying `scale` by $|s[k]|$ and normalizing to the PWM top value before loading the CCP1 duty.

---

### Square waveform (`wave = 0`)

The square mode uses Timer2 + CWG with a 200-step window per period (0–199) and an H-bridge polarity flip at half-period:

- For `index200 ∈ [0..199]`, the output is "on" for a span proportional to `duty_pct` in each half-period.
- The H-bridge polarity is flipped between the first and second halves of the cycle, so the motor sees a bipolar square wave.

Mathematically, for an ideal 50% square wave (same peak amplitude $A$):

$$
x_\text{square}(t) =
\begin{cases}
+A, & 0 \le t < T/2 \\
-A, & T/2 \le t < T
\end{cases}
\quad \text{with } f = \frac{1}{T}
$$

Here the effective amplitude $A$ is proportional to `duty_pct` (through the same PWM scaling logic as in sine mode).

---

## `serial_api.py`

### Basic usage (single device, sine then square on the same actuator)

```python
if __name__ == '__main__':
    api = SERIAL_API()
    devs = api.get_serial_devices()
    print(devs)

    if devs and api.connect_serial_device(devs[2]):
        addr = 0

        # START sine (wave=1) with duty5≈20, freq=3
        api.send_command(addr, duty=20, freq=3, start_or_stop=1, wave=1)
        time.sleep(1.2)
        # STOP
        api.send_command(addr, duty=0, freq=3, start_or_stop=0, wave=1)

        # START square (wave=0) with duty5≈20, freq=3
        api.send_command(addr, duty=20, freq=3, start_or_stop=1, wave=0)
        time.sleep(1.0)
        # STOP
        api.send_command(addr, duty=0, freq=3, start_or_stop=0, wave=0)

        api.disconnect_serial_device()
```

### Example with two actuators at once (one sine, one square)

```python
if devs and api.connect_serial_device(devs[2]):
    commands = [
        {'addr': 0, 'duty': 20, 'freq': 3, 'start_or_stop': 1, 'wave': 1},  # sine
        {'addr': 1, 'duty': 20, 'freq': 3, 'start_or_stop': 1, 'wave': 0}   # square
    ]
    api.send_command_list(commands)
    time.sleep(1.5)

    commands_stop = [
        {'addr': 0, 'duty': 0, 'freq': 3, 'start_or_stop': 0, 'wave': 1},
        {'addr': 1, 'duty': 0, 'freq': 3, 'start_or_stop': 0, 'wave': 0}
    ]
    api.send_command_list(commands_stop)
```

---

## Mathematical comparison: square vs sine

| Quantity | Sine wave | Square wave (50% duty, ±A) |
|----------|-----------|----------------------------|
| Signal | $x_\text{sine}(t) = A \sin(2\pi f t)$ | $x_\text{square}(t) = A \cdot \text{sgn}(\sin(2\pi f t))$ |
| RMS | $x_{\text{RMS,sine}} = \frac{A}{\sqrt{2}}$ | $x_{\text{RMS,square}} = A$ |
| Avg. power | $P_\text{sine} \propto \frac{A^2}{2}$ | $P_\text{square} \propto A^2$ |
| Power relation | For the same peak $A$: $P_\text{square} = 2 \cdot P_\text{sine}$ | |
| Frequency | $f = \frac{1}{T}$ with $T$ the waveform period | |
| Amplitude/offset | $A = \frac{x_{\max} - x_{\min}}{2}$, offset $= \frac{x_{\max} + x_{\min}}{2}$ | |

---

## Note

- **Square mode**: higher RMS for the same peak → stronger mechanical impact, clearer "tap" sensations, good for alerts and strong cues.
- **Sine mode**: smoother envelope, lower harmonic content → more comfortable continuous feedback and less audible noise.