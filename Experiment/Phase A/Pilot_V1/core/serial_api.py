import serial
import serial.tools.list_ports
import time

class SerialAPI:

    
    def __init__(self):
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop, delay_ms=0, wave=0):
        # Split address into serial group and local address
        serial_group = addr // 16  # 0-7 for addresses 0-127
        serial_addr = addr % 16  # 0-15 within each group
        
        # Byte 1: [serial_group(4)] [reserved(2)] [start_or_stop(1)]
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        
        # Byte 2: 0x40 | [addr(6)]
        byte2 = 0x40 | (serial_addr & 0x3F)
        
        # Byte 3: 0x80 | [duty(4)] [freq(3)] [wave(1)]
        byte3 = 0x80 | ((duty & 0x0F) << 3) | ((freq & 0x07) << 0) | (wave & 0x01)
        
        # Bytes 4-5: 16-bit delay in milliseconds (little-endian)
        delay_low = delay_ms & 0xFF
        delay_high = (delay_ms >> 8) & 0xFF
        
        return bytearray([byte1, byte2, byte3, delay_low, delay_high])

    def send_timed_batch(self, commands) -> bool:
        """Send batch of commands with individual timing delays"""
        if not self.connected or self.serial_connection is None:
            print("❌ Error: Not connected to serial device")
            return False
            
        # Validate and build command batch
        command_bytes = bytearray()
        for i, cmd in enumerate(commands):
            addr = cmd.get('addr', -1)
            duty = cmd.get('duty', -1)
            freq = cmd.get('freq', -1)
            start_or_stop = cmd.get('start_or_stop', -1)
            delay_ms = cmd.get('delay_ms', 0)
            wave = cmd.get('wave', 0)  # Optional wave parameter
            
            # Validate parameters
            if not (0 <= addr <= 127 and 0 <= duty <= 15 and 0 <= freq <= 7 
                    and start_or_stop in [0, 1] and 0 <= delay_ms <= 65535 and 0 <= wave <= 1):
                print(f"❌ Error: Invalid parameters in command {i+1}")
                print(f"   addr={addr} (0-127), duty={duty} (0-15), freq={freq} (0-7)")
                print(f"   start_or_stop={start_or_stop} (0-1), delay_ms={delay_ms} (0-65535), wave={wave} (0-1)")
                return False
                
            command_bytes += self.create_command(addr, duty, freq, start_or_stop, delay_ms, wave)
        
        try:
            bytes_written = self.serial_connection.write(command_bytes)
            print(f"✅ Sent batch: {len(commands)} commands ({bytes_written} bytes)")
            return True
        except Exception as e:
            print(f"❌ Failed to send batch: {e}")
            return False

    def get_serial_ports(self):
        """Get list of available serial ports"""
        try:
            ports = serial.tools.list_ports.comports()
            return [f"{port.device} - {port.description}" for port in ports]
        except Exception as e:
            print(f"❌ Error getting ports: {e}")
            return []

    def connect(self, port_info, baudrate=115200) -> bool:
        """Connect to serial device"""
        try:
            port_name = port_info.split(' - ')[0]
            print(f"🔄 Connecting to {port_name} at {baudrate} baud...")
            
            self.serial_connection = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                timeout=1,
                write_timeout=1
            )
            
            time.sleep(0.1)  # Allow connection to establish
            
            if self.serial_connection.is_open:
                self.connected = True
                print(f"✅ Connected to {port_name}")
                return True
            else:
                print(f"❌ Failed to open {port_name}")
                return False
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.serial_connection = None
            self.connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect from serial device"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.connected = False
                self.serial_connection = None
                print("✅ Disconnected")
                return True
        except Exception as e:
            print(f"❌ Disconnect failed: {e}")
        return False

    def is_connected(self) -> bool:
        """Check connection status"""
        return self.connected and self.serial_connection and self.serial_connection.is_open


if __name__ == '__main__':
    api = SerialAPI()
    
    # Test protocol first
    
    # Find available ports
    ports = api.get_serial_ports()
    print(f"\n📡 Available ports: {ports}")
    
    if not ports:
        print("❌ No serial ports found")
        exit(1)
    
    # Find ESP32 port automatically
    esp32_port = None
    for i, port in enumerate(ports):
        if 'usbmodem' in port or 'ESP32' in port:
            esp32_port = port
            print(f"🎯 Found ESP32 at index {i}: {port}")
            break
    
    if esp32_port:
        # Connect to ESP32
        if api.connect(esp32_port):
            # Test batch: activate device 0, then stop it
            test_commands = [
                {"addr": 0, "duty": 3, "freq": 3, "start_or_stop": 1, "delay_ms": 0, "wave": 0},
                {"addr": 0, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 2000, "wave": 0},
                {"addr": 1, "duty": 3, "freq": 3, "start_or_stop": 1, "delay_ms": 0, "wave": 0},
                {"addr": 1, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 2000, "wave": 0},
                {"addr": 2, "duty": 3, "freq": 3, "start_or_stop": 1, "delay_ms": 0, "wave": 0},
                {"addr": 2, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 2000, "wave": 0},
                {"addr": 3, "duty": 3, "freq": 3, "start_or_stop": 1, "delay_ms": 0, "wave": 0},
                {"addr": 3, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 2000, "wave": 0},
                {"addr": 4, "duty": 3, "freq": 3, "start_or_stop": 1, "delay_ms": 0, "wave": 0},
                {"addr": 4, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 2000, "wave": 0},
            ]
            
            print("📤 Sending test batch...")
            success = api.send_timed_batch(test_commands)
            
            if success:
                print("🎉 Test successful!")
                print("⏳ Waiting for commands to execute...")
                time.sleep(3)
            else:
                print("❌ Test failed!")
            
            api.disconnect()
        else:
            print("❌ Failed to connect to ESP32")
    else:
        print("⚠️  ESP32 device not found")
        print("Available ports:")
        for i, port in enumerate(ports):
            print(f"  {i}: {port}")