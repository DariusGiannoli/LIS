# LIS Haptic System

Firmware and Python APIs for controlling a 32-actuator haptic system over USB
serial or Bluetooth Low Energy (BLE).

The final implementation uses a three-byte command protocol, 32 intensity
levels, eight frequency levels, and sine or square waveforms.

## Architecture

```text
PC application
    |
    | USB serial or BLE
    v
ESP32-S3 controller
    |
    | 4 UART subchains, 8 actuators per subchain
    v
PIC16F18313 vibration units
```

## Repository structure

- `firmware/pic/` — PIC16F18313 actuator firmware and NeoPixel driver.
- `firmware/serial/` — ESP32-S3 USB serial controller.
- `firmware/ble/` — ESP32-S3 BLE controller.
- `python/` — Serial and BLE Python APIs.
- `3D/` — Final left and right enclosure models.
- `docs/` — Protocol and waveform documentation.

## Capabilities

- 32 individually addressable actuators (`0` to `31`).
- 32 intensity levels (`0` to `31`, encoded on five bits).
- Eight frequency levels (`0` to `7`, encoded on three bits).
- Sine and square waveforms.
- Individual and batched start/stop commands.
- USB serial and BLE transports.

## Requirements

### Python

- Python 3.9 or newer.
- `pyserial` for USB serial control.
- `bleak` for BLE control.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ESP32-S3

- Arduino IDE or Arduino CLI with the ESP32 board package.
- Adafruit NeoPixel library.
- EspSoftwareSerial library.

### PIC16F18313

- MPLAB X IDE.
- MPLAB XC8 compiler.

Create an XC8 project containing all files from `firmware/pic/`, then flash the
same firmware to each vibration unit.

## Flashing the controller

Choose one ESP32-S3 controller firmware:

- USB serial: `firmware/serial/controller.ino`
- Bluetooth LE: `firmware/ble/controller.ino`

Both controllers translate the same PC-side three-byte frames into commands for
the four PIC UART subchains.

## Serial example

```python
from python.serial_api import SERIAL_API

api = SERIAL_API()
devices = api.get_serial_devices()

if not devices:
    raise RuntimeError("No serial controller found")

api.connect_serial_device(devices[0])

# Start actuator 0: sine wave, intensity 16/31, frequency index 3.
api.send_command(addr=0, duty=16, freq=3, start_or_stop=1, wave=1)

# Stop actuator 0.
api.send_command(addr=0, duty=0, freq=3, start_or_stop=0, wave=1)

api.disconnect_serial_device()
```

## BLE example

Flash `firmware/ble/controller.ino`. The controller advertises as
`VibraForge-BLE`.

```python
from python.ble_api import BLE_API

api = BLE_API()

if not api.connect_ble_device():
    raise RuntimeError("VibraForge-BLE not found")

api.send_command(addr=0, duty=16, freq=3, start_or_stop=1, wave=1)
api.send_command(addr=0, duty=0, freq=3, start_or_stop=0, wave=1)
api.disconnect_ble_device()
```

## Protocol

Commands sent from the PC contain three bytes:

| Byte | Content |
| --- | --- |
| 1 | Waveform, UART group, and start/stop mode |
| 2 | Actuator address inside the group |
| 3 | Five-bit intensity and three-bit frequency |

See [docs/protocol.md](docs/protocol.md) for the complete bit layout and
frequency table. See [docs/waveforms.md](docs/waveforms.md) for the sine and
square control strategies.

## Safety

- Always send a STOP command after a test.
- Avoid leaving actuators at high intensity for extended periods.
- Verify the motor supply and UART wiring before flashing or testing.
- Start new hardware tests at a low intensity.

## Legacy code

Previous experiments, ESP-NOW prototypes, and development versions are
preserved on the `legacy` branch and in the Git history. `main` contains only
the consolidated pre-hackathon implementation.

## Contact

Darius Giannoli — darius.giannoli(at)epfl.ch

### Acknowledgments

Grateful for Dr. Yang Chen's supervision and for Gabriel Taieb for his contributions to this work
