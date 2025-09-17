import serial
import serial.tools.list_ports
import time

class SerialAPI:

    
    def __init__(self):
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop, delay_ms=0, wave=0):
        # Split address into serial group and local address
        serial_group = addr // 8  # 0-7 for addresses 0-127
        serial_addr = addr % 8  # 0-15 within each group
        
        # Byte 1: [serial_group(4)] [reserved(2)] [start_or_stop(1)]
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        
        # Byte 2: 0x40 | [addr(6)]
        byte2 = 0x40 | (serial_addr & 0x3F)
        
        # Byte 3: 0x80 | [duty(4)] [freq(3)] [wave(1)]
        byte3 = 0x80 | ((duty & 0x0F) << 3) | ((freq & 0x07))
        
        # Bytes 4-5: 16-bit delay in milliseconds (little-endian)
        delay_low = delay_ms & 0xFF
        delay_high = (delay_ms >> 8) & 0xFF
        
        return bytearray([byte1, byte2, byte3, delay_low, delay_high])

    def send_timed_batch(self, commands) -> bool:
        """Send batch of commands with individual timing delays"""
        if not self.connected or self.serial_connection is None:
            print("❌ Error: Not connected to serial device")
            return False
            
        print(f"🚀 Preparing to send {len(commands)} commands...")
        
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
            # Clear buffers before sending new commands
            print("🧹 Clearing serial buffers...")
            self.clear_buffers()
            
            # Wait a moment for buffers to clear
            import time
            time.sleep(0.05)
            
            print(f"📤 Sending {len(command_bytes)} bytes...")
            bytes_written = self.serial_connection.write(command_bytes)
            
            # Ensure all data is sent immediately
            self.serial_connection.flush()
            
            # Verify all bytes were written
            if bytes_written != len(command_bytes):
                print(f"⚠️ Warning: Expected to write {len(command_bytes)} bytes, only wrote {bytes_written}")
                return False
            
            print(f"✅ Successfully sent batch: {len(commands)} commands ({bytes_written} bytes)")
            return True
        except Exception as e:
            print(f"❌ Failed to send batch: {e}")
            return False

    def clear_buffers(self):
        """Clear input and output buffers to prevent command interference"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                # Clear input buffer (remove any pending data from device)
                self.serial_connection.reset_input_buffer()
                # Clear output buffer (ensure previous commands are sent)
                self.serial_connection.reset_output_buffer()
                print("🧹 Cleared serial buffers")
        except Exception as e:
            print(f"⚠️ Could not clear buffers: {e}")

    def send_stop_all_command(self):
        """Send stop command to all actuators to ensure clean state"""
        try:
            if not self.connected:
                print("⚠️ Not connected - cannot send stop all")
                return False
                
            print("🛑 Sending stop commands to all actuators...")
            
            # Send stop commands to all 16 actuators
            stop_commands = []
            for addr in range(16):
                stop_commands.append({
                    'addr': addr,
                    'duty': 0,
                    'freq': 0,
                    'start_or_stop': 0,  # Stop
                    'delay_ms': 0,
                    'wave': 0
                })
            
            # Use the regular send method but with extra reliability
            result = self.send_timed_batch(stop_commands)
            if result:
                print("✅ Stop all commands sent successfully")
                # Give extra time for stop commands to be processed
                import time
                time.sleep(0.1)
            else:
                print("❌ Failed to send stop all commands")
            
            return result
        except Exception as e:
            print(f"❌ Failed to send stop all: {e}")
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