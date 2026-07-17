# Three-byte command protocol

The Python APIs send one three-byte frame for each actuator command. Both the
USB serial and BLE controllers accept the same format.

## PC to ESP32-S3

### Byte 1 — waveform, group, and mode

```text
bit:   7   6   5   4   3   2   1   0
       W   0  G3  G2  G1  G0  M1  M0
```

- `W`: waveform (`0` = square, `1` = sine).
- `G`: UART subchain (`0` to `3`).
- `M`: mode (`00` = stop, `01` = start, `10` = soft stop).

### Byte 2 — local actuator address

```text
bit:   7   6   5   4   3   2   1   0
       0   0  A5  A4  A3  A2  A1  A0
```

The current hardware uses local addresses `0` to `7`. A global actuator address
is converted with:

```text
group = address // 8
local address = address % 8
```

### Byte 3 — intensity and frequency

```text
bit:   7   6   5   4   3   2   1   0
      D4  D3  D2  D1  D0  F2  F1  F0
```

- `D`: intensity (`0` to `31`).
- `F`: frequency index (`0` to `7`).

## ESP32-S3 to PIC16F18313

A STOP command is forwarded as one address byte:

```text
[local_address << 1 | 0]
```

A START command is forwarded as three bytes:

```text
[local_address << 1 | 1]
[1 | intensity on five bits]
[1 | waveform | frequency on three bits]
```

## Frequency indices

| Index | Approximate frequency |
| ---: | ---: |
| 0 | 123 Hz |
| 1 | 145 Hz |
| 2 | 170 Hz |
| 3 | 200 Hz |
| 4 | 235 Hz |
| 5 | 275 Hz |
| 6 | 322 Hz |
| 7 | 384 Hz |

The PIC firmware applies separate calibrated intensity lookup tables for sine
and square output.
