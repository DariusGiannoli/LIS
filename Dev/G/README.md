# Haptic Waveform Control Strategy: SINE vs. SQUARE

## Overview
This document details the technical implementation of the vibration control logic within the `main_linear.c` firmware. It explains how the **Duty Cycle (0-31)** parameter physically modulates the actuator output differently depending on the selected waveform mode (SINE or SQUARE).

## Visual Comparison
The following graph illustrates the fundamental difference between the two modes:

![Duty Cycle Comparison](sine_square.png)

---

## 1. SQUARE Mode: Time-Domain Modulation
In this mode, the Duty Cycle controls the **duration (width)** of the actuation pulse.

* **Mechanism:** Time-based Windowing.
* **Logic:** The H-Bridge operates in a binary state.
    * **ON:** Full Voltage (Max Power).
    * **OFF:** 0V (Coast).
* **Implementation:** The code compares a counter against the `duty_pct`.
    ```c
    if (counter < duty_pct) { OUTPUT = MAX; } 
    else                    { OUTPUT = 0;   }
    ```
* **Physical Result:** Increasing the Duty Cycle widens the energy block (ON-time) without changing the instantaneous voltage level.
* **Haptic Characteristic:** Sharp, aggressive "kick". Ideal for alerts and strong feedback.

## 2. SINE Mode: Amplitude Modulation (SPWM)
In this mode, the Duty Cycle controls the **peak amplitude (height)** of the wave.

* **Mechanism:** Sinusoidal Pulse Width Modulation (SPWM) via Look-Up Table (LUT).
* **Logic:** The H-Bridge switches at high frequency (~40kHz) to create an average analog voltage.
* **Implementation:** The Duty Cycle acts as a scaling factor on the LUT values.
    ```c
    Output_Value = (LUT_Sample * duty_pct) / 100;
    ```
* **Physical Result:** Increasing the Duty Cycle increases the voltage peak. The shape remains a pure sine wave; only its intensity (height) changes.
* **Haptic Characteristic:** Smooth, precise texture. Ideal for UI navigation and subtle effects.

---

## Summary Table

| Feature | **SQUARE Mode** | **SINE Mode** |
| :--- | :--- | :--- |
| **Control Domain** | **Time** (Pulse Width) | **Amplitude** (Signal Height) |
| **Voltage State** | Binary (0V or Max) | Analog-like (Progressive) |
| **Energy Profile** | High (100% Fill during ON state) | Moderate (Rounded shape) |
| **Primary Use Case** | Impact / Notification | Texture / Immersion |

---

## Conclusion
By implementing these two distinct modulation strategies, the system provides a versatile haptic range:
1.  **SINE** allows for high-fidelity, "premium" feel control.
2.  **SQUARE** maximizes the physical energy transfer for maximum alert perceptibility.
