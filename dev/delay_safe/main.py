from serial_api import SerialAPI
from patterns import generate_static_pattern, generate_pulse_pattern
import time

# Connect to device
api = SerialAPI()
ports = api.get_serial_ports()
print("Available ports:", ports)
api.connect(ports[2])  
# Create your batch
time.sleep(2)  # Allow connection to establish
static = generate_static_pattern(
    devices=[0, 1, 2, 3],
    duty=8,
    freq=6,
    duration=2000
)

pulse = generate_pulse_pattern(
    devices=[0, 1, 2, 3],
    duty=8,
    freq=3,
    pulse_duration=500,
    pause_duration=200,
    num_pulses=2
)


# api.send_timed_batch(static)
# time.sleep(3)   

api.send_timed_batch(pulse)
time.sleep(3)
# api.send_timed_batch(motion)

# Disconnect
api.disconnect()