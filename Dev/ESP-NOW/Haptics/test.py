import serial, time
PORT = "/dev/tty.usbmodem1101"  # master’s port
ser = serial.Serial(PORT, 115200)

# START: group=0, addr=0, duty=8, freq=3, wave=0  => 01 40 C6
ser.write(bytes([0x01, 0x40, 0xC6]))
time.sleep(2.0)

# STOP: group=0, addr=0  => 00 40
ser.write(bytes([0x00, 0x40]))

ser.close()
