# Haptic Waveform Control Strategy: SINE vs. SQUARE

## Overview

This document details the technical implementation of the vibration control logic within the `main.c` firmware. It explains how the **Intensity Index (0-31)** input is mapped to the physical actuator output differently depending on the selected waveform mode (SINE or SQUARE).

---

## 1. Perceptual Mapping (The "Duty" Input)

Unlike standard linear drivers, the input parameter (0-31) is **not** applied directly to the hardware. Instead, it acts as an index pointing to a **Perceptual Look-Up Table (LUT)**.

This creates a non-linear response curve designed to match the human psychophysical perception of vibration ([Steven's Power Law](https://en.wikipedia.org/wiki/Stevens%27s_power_law)), ensuring that "Step 16" feels exactly like "50% intensity" regardless of the waveform physics.

| Stage | Description |
|-------|-------------|
| **Input** | Index 0-31 (User Command) |
| **Transformation** | `Physical_Output_% = LUT[Index]` |
| **Output** | 0-100% (Sent to PWM/Timer logic) |

---

## 2. SQUARE Mode: Time-Domain Modulation

In this mode, the mapped percentage controls the **duration (width)** of the actuation pulse (*Windowing*).

### Curve Profile (Multi-Slope)

The LUT applies a specific 3-stage curve to tame the aggressive nature of square waves:

1. **Precision Zone (0-50% input):** Slow rise (6% → 20%) for fine control of weak effects.
2. **Attack Zone (50-75% input):** Sharp rise (20% → 65%) to create a strong "kick".
3. **Saturation Zone (75-100% input):** Linear finish.

### Physical Mechanism

**Time-based Windowing** — The H-Bridge operates in a binary state (Max Power or Coast) based on a counter compared against the LUT value.

```c
uint8_t target_width = LUT_SQUARE[input_index]; // e.g., input 16 -> 20% width

if (counter < target_width) { OUTPUT = MAX; } 
else                        { OUTPUT = 0;   }
```

### Haptic Characteristic

Sharp, aggressive "kick". Ideal for **alerts** and **strong feedback**.

---

## 3. SINE Mode: Amplitude Modulation (SPWM)

In this mode, the mapped percentage controls the **peak amplitude (height)** of the synthesized wave.

### Curve Profile (Gamma Correction)

The LUT applies a smooth **Gamma curve (γ ≈ 1.3)** where the mid-point (Index 16) maps to ~42% physical power. This provides a "creamy" and progressive feel.

### Physical Mechanism

**Sinusoidal Pulse Width Modulation (SPWM)** via Direct Digital Synthesis.

### Technical Construction

1. **Look-Up Table (Sine):** Stores 64 signed samples of a perfect sine wave.
2. **Amplitude Scaling:** The value from the perceptual LUT acts as a gain coefficient (*A*).

$$
PWM_{output}(t) = 128 \cdot |SineSample[t]| \times A_{LUT}
$$

3. **Reconstruction:** The H-Bridge switches at high frequency (~40kHz) to create an average analog voltage proportional to the scaled sine wave.

### Haptic Characteristic

Smooth, precise texture. Ideal for **UI navigation** and **subtle effects**.

---

## Summary Table

| Feature | SQUARE Mode | SINE Mode |
|---------|-------------|-----------|
| **Control Domain** | Time (Pulse Width) | Amplitude (Signal Height) |
| **Mapping Strategy** | Multi-Slope (Precision low-end, aggressive mid-range) | Gamma Corrected (Smooth, progressive curve) |
| **Mid-Point (Input 16)** | 20% Physical Width (Feels like 50% strength) | 42% Physical Amplitude (Feels like 50% strength) |
| **Primary Use Case** | Impact / Notification | Texture / Immersion |

---

## Conclusion

By combining distinct physical modulation strategies (Time vs. Amplitude) with tailored psychophysical LUTs, the system provides a calibrated haptic range:

1. **SINE:** High-fidelity feel with linear perceived progression.
2. **SQUARE:** Maximum physical energy transfer with manageable low-intensity control.
