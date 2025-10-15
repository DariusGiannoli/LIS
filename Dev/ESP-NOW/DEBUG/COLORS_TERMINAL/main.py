import serial
import time

# --- CONFIGURATION ---
# IMPORTANT: Replace "COM3" with the correct serial port for your Master ESP32.
#
# How to find your serial port:
#   - Windows: Open Device Manager, look under "Ports (COM & LPT)". It will likely be a "USB-SERIAL CH340" or similar.
#   - macOS: Open Terminal and run: ls /dev/tty.*
#            Look for something like /dev/tty.usbserial-XXXXXXXX or /dev/tty.SLAB_USBtoUART
#   - Linux: Open a terminal and run: ls /dev/ttyUSB* or ls /dev/ttyACM*
#
SERIAL_PORT = '/dev/tty.usbmodem101' # <-- CHANGE THIS
BAUD_RATE = 9600
# ---------------------

def run_controller():
    """
    Connects to the ESP32 Master board over serial and sends commands.
    """
    print("--- ESP32 NeoPixel Controller ---")
    print(f"Connecting to port {SERIAL_PORT} at {BAUD_RATE} baud...")

    try:
        # Establish a serial connection
        esp_serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        # Wait a moment for the connection to establish and for the ESP32 to reset
        time.sleep(2)
        print("Connection successful!")
    except serial.SerialException as e:
        print(f"Error: Could not open serial port '{SERIAL_PORT}'.")
        print(f"Details: {e}")
        print("Please check the port name and ensure the device is connected.")
        return

    print("\nEnter a command to control the Slave's LED.")
    print("Commands: r (Red), g (Green), b (Blue), w (White), o (Off)")
    print("Type 'q' or 'quit' to exit.")
    print("-" * 35)

    while True:
        # Get user input from the terminal
        command = input("Enter command > ").strip().lower()

        if command in ['q', 'quit']:
            print("Exiting program.")
            break
        
        # Check if the command is one of the valid options
        if command in ['r', 'g', 'b', 'w', 'o']:
            # Send the command character to the ESP32, encoded as bytes
            esp_serial.write(command.encode('utf-8'))
            print(f"Sent command: '{command}'")
        else:
            print("Invalid command. Please use 'r', 'g', 'b', 'w', or 'o'.")

    # Close the serial connection when done
    esp_serial.close()
    print("Serial port closed.")


if __name__ == "__main__":
    run_controller()
