# test_one.py
import time
from serial_api import SERIAL_API

PORT = "/dev/cu.usbmodem1101"  # adapte si besoin
ADDR = 0                       # choisis 0..15 que tu sais câblé

api = SERIAL_API()
assert api.connect_serial_device(PORT), "Connex. série KO"
print("Connected.")

# START fort pendant 2 s
cmd_on  = [{"addr": ADDR, "duty": 15, "freq": 7, "start_or_stop": 1}]
cmd_off = [{"addr": ADDR, "duty": 0,  "freq": 0, "start_or_stop": 0}]

api.send_command_list(cmd_on)
time.sleep(2.0)
api.send_command_list(cmd_off)

api.disconnect_serial_device()
print("Done.")
