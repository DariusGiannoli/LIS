Random for Gabriel

---

## Duty mapping (PC/ESP → PIC)

- **Transport**: duty5 ∈ {0..31} (5 bits) sent in Byte 3.

- **Gamma Mapping**: for the mapping between 0...31 to 0...99 we use the following formula:

  ```c
  static inline uint8_t map5bit_to_0_99_gamma(uint8_t v){
      if (v>31) v=31;
      uint16_t x=v*8, g=(x*x+127)/255;
      return (uint8_t)((g*99+64)/128);
  }
  ```

---

## How the sine driver works (why it's quieter)

- **Carrier**: fixed ~40 kHz PWM (Timer2 + CCP1).
- **Sine**: Timer1 steps through a LUT (SINE_LEN=64) → true bipolar sine over a full cycle.
- **Zero-cross**: at sign change, outputs are briefly coasted then rerouted (no shoot-through clicks).
- **Result**: only the fundamental is excited; higher harmonics (3f, 5f, …) are strongly reduced → less audible buzz.

---

## Color mapping (32 steps)

- **Index source**: use the raw 5-bit duty (duty_index = duty5, 0–31).
- **Palette**: use the original 16 colors on even indices (0,2,…,30).
- **Odd indices (1,3,…,29)**: color = average of adjacent keys.
- **Index 31**: last key (white) as for 15 in the 4 bits structure.
- **Note (NeoPixel/WS2812)**: disable interrupts during sendColor_SPI(...) to keep LED timing correct.

---

## File layout & compatibility

- **Sine + colors**: flash sinus/optimized_with_colors.c (PIC).
- **Square + colors**: flash square/square_32_colors.c (PIC).
- **ESP/Arduino**: unit/unit.ino unchanged (still forwards 4-byte frames).
- **PC**: use serial_api_5bits.py (sends duty 0–31, not 0–99).

---

## Send a command (python)

```python
serial_api.send_command(addr=0, duty=15, freq=3, start_or_stop=1)  # START @ ~50%
time.sleep(2)
serial_api.send_command(addr=0, duty=15, freq=3, start_or_stop=0)  # STOP
```

**Attention !** Choose the correct serial device index in `connect_serial_device(device_names[...])` and the correct `addr` (0–31) for your board/subchain.
