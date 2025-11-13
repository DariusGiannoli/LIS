# Random for Gabriel

## Overview

Main changes include 4 to 5 bits for duty, keeping a 3-byte structure but adding a wave parameter in the first byte to switch between sine and square wave.

---

## Bit structure

**Byte 1:** `[W][0][G3][G2][G1][G0][M1][M0]`
- W: waveform (0 = square, 1 = sine)
- G: group (4 bits, 0–15)
- M: mode (00 = STOP, 01 = START, 10 = SOFTSTOP)

**Byte 2:** `[0][0][A5][A4][A3][A2][A1][A0]`
- A: local address (6 bits, 0–63, currently 0–7 used)

**Byte 3:** `[D4][D3][D2][D1][D0][F2][F1][F0]`
- D: duty code (5 bits, 0–31)
- F: frequency index (3 bits, 0–7)

The waveform bit W is in Byte 1 so that all high-level control flags (waveform, group, mode) are decoded immediately from the first byte.

---

## main.c

### Duty LUT

The duty code duty5 ∈ [0..31] is mapped to a perceptual 0–99% using a LUT derived from measured 4-bit data (16 points).
A gamma+offset model was fitted on the 4-bit measurements, then used to generate this 32-step table:

```c
static const uint8_t DUTY5_TO_PCT[32] = {
  0,  0,  1,  1,  1,  2,  3,  4,
  5,  6,  7,  9, 11, 13, 15, 18,
 20, 24, 27, 30, 34, 38, 43, 48,
 53, 58, 64, 70, 77, 84, 91, 99
};
```

So the effective duty percent is:

$$\text{duty\_pct} = \text{DUTY5\_TO\_PCT}[\text{duty5\_}] \in [0,99]$$

### Sine waveform (wave = 1)

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

$$s[k] \approx 127 \cdot \sin\!\Big(2\pi \frac{k}{64}\Big), \quad k=0,\dots,63$$

Timer1 advances k at a fixed step $\Delta t$, so the output is a discrete-time sinusoid of frequency:

$$f = \frac{1}{T}, \quad T = 64 \cdot \Delta t$$

The motor drive amplitude is then scaled by the duty mapping:

$$A_\text{eff}(k) \propto \text{DUTY5\_TO\_PCT}[\text{duty5\_}] \cdot \frac{|s[k]|}{127}$$

### Square waveform (wave = 0)

The square mode uses a 50% duty "on/off" gating around a center value with sign flips (H-bridge polarity), giving:

$$x_\text{square}(t) = \begin{cases} +A, & 0 \le t < T/2 \\ -A, & T/2 \le t < T \end{cases} \quad\text{with } f = \frac{1}{T}$$

and A proportional to the mapped duty.

---

## serial_api.py

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
| Signal | $x_{\text{sine}}(t) = A \sin(2\pi f t)$ | $x_{\text{square}}(t) = A \cdot \mathrm{sgn}(\sin(2\pi f t)) \in \\{-A,+A\\}$ |
| RMS | $x_{\text{RMS,sine}} = \dfrac{A}{\sqrt{2}}$ | $x_{\text{RMS,square}} = A$ |
| Average power | $P_{\text{sine}} \propto \dfrac{A^2}{2}$ | $P_{\text{square}} \propto A^2$ |
| Power ratio | colspan=2 | $P_{\text{square}} = 2 \cdot P_{\text{sine}}$ (for same $A$) |
| Frequency | colspan=2 | $f = \dfrac{1}{T}$, with $T$ the waveform period |
| Amplitude / offset | colspan=2 | $A = \dfrac{x_{\max} - x_{\min}}{2},\quad \text{offset} = \dfrac{x_{\max} + x_{\min}}{2}$ |

---

## Note

- **Square mode:** higher RMS for the same peak → stronger mechanical impact, clearer "tap" sensations, good for alerts and strong cues.
- **Sine mode:** smoother envelope, lower harmonic content → more comfortable continuous feedback and less audible noise.