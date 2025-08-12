#!/usr/bin/env python3
"""
ESP32 Color Controller
Sends color commands to ESP32 master via serial, which forwards to slave via ESP-NOW
"""

import serial
import serial.tools.list_ports
import time
import sys
import os

class ESP32ColorController:
    def __init__(self):
        self.ser = None
        self.connected = False
        
        # Color command mapping
        self.colors = {
            '1': ('r', 'Red'),
            '2': ('g', 'Green'), 
            '3': ('b', 'Blue'),
            '4': ('y', 'Yellow'),
            '5': ('p', 'Purple'),
            '6': ('c', 'Cyan'),
            '7': ('w', 'White'),
            '8': ('o', 'Off'),
            'r': ('r', 'Red'),
            'g': ('g', 'Green'),
            'b': ('b', 'Blue'),
            'y': ('y', 'Yellow'),
            'p': ('p', 'Purple'),
            'c': ('c', 'Cyan'),
            'w': ('w', 'White'),
            'o': ('o', 'Off'),
            'off': ('o', 'Off')
        }
    
    def find_esp32_port(self):
        """Automatically find ESP32 port"""
        ports = serial.tools.list_ports.comports()
        esp32_keywords = ['CP210', 'CH340', 'FTDI', 'USB-SERIAL', 'ttyUSB', 'ttyACM']
        
        print("Available serial ports:")
        for i, port in enumerate(ports):
            print(f"  {i+1}. {port.device} - {port.description}")
        
        # Try to auto-detect ESP32
        for port in ports:
            for keyword in esp32_keywords:
                if keyword.lower() in port.description.lower():
                    print(f"\n🔍 Found potential ESP32 at: {port.device}")
                    return port.device
        
        return None
    
    def connect(self, port=None, baudrate=115200):
        """Connect to ESP32"""
        if port is None:
            port = self.find_esp32_port()
            
        if port is None:
            print("\n❌ No ESP32 found automatically.")
            ports = serial.tools.list_ports.comports()
            if ports:
                print("Please select a port manually:")
                for i, p in enumerate(ports):
                    print(f"  {i+1}. {p.device}")
                
                try:
                    choice = int(input("Enter port number: ")) - 1
                    if 0 <= choice < len(ports):
                        port = ports[choice].device
                    else:
                        print("Invalid selection")
                        return False
                except ValueError:
                    print("Invalid input")
                    return False
            else:
                print("No serial ports found!")
                return False
        
        try:
            print(f"\n🔌 Connecting to {port} at {baudrate} baud...")
            self.ser = serial.Serial(port, baudrate, timeout=2)
            time.sleep(2)  # Wait for ESP32 to initialize
            
            # Clear any existing data
            self.ser.flushInput()
            self.ser.flushOutput()
            
            # Test connection
            print("📡 Testing connection...")
            response = self.read_response(timeout=3)
            
            if "READY" in response or "ESP-NOW" in response:
                self.connected = True
                print("✅ Connected successfully!")
                print(f"📋 ESP32 Response: {response.strip()}")
                return True
            else:
                print(f"⚠️  Connected but unexpected response: {response}")
                self.connected = True  # Still try to use it
                return True
                
        except serial.SerialException as e:
            print(f"❌ Connection failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
    
    def read_response(self, timeout=1):
        """Read response from ESP32"""
        if not self.ser:
            return "Not connected"
        
        start_time = time.time()
        response = ""
        
        while time.time() - start_time < timeout:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response += line + "\n"
                        # If we get a complete response, return it
                        if any(keyword in line for keyword in ["SUCCESS:", "ERROR:", "READY:", "INFO:"]):
                            return response
                except:
                    pass
            time.sleep(0.01)
        
        return response if response else "No response"
    
    def send_command(self, command):
        """Send color command to ESP32"""
        if not self.connected or not self.ser:
            print("❌ Not connected to ESP32")
            return False
        
        try:
            # Send command
            self.ser.write((command + '\n').encode())
            self.ser.flush()
            
            # Wait for response
            response = self.read_response(timeout=2)
            
            if "SUCCESS:" in response:
                print(f"✅ {response.strip()}")
                return True
            elif "ERROR:" in response:
                print(f"❌ {response.strip()}")
                return False
            else:
                print(f"📋 ESP32: {response.strip()}")
                return True
                
        except Exception as e:
            print(f"❌ Send failed: {e}")
            return False
    
    def show_menu(self):
        """Display color selection menu"""
        print("\n" + "="*50)
        print("🌈 ESP32 COLOR CONTROLLER")
        print("="*50)
        print("Select a color:")
        print("  1 or r = 🔴 Red")
        print("  2 or g = 🟢 Green") 
        print("  3 or b = 🔵 Blue")
        print("  4 or y = 🟡 Yellow")
        print("  5 or p = 🟣 Purple")
        print("  6 or c = 🔵 Cyan")
        print("  7 or w = ⚪ White")
        print("  8 or o = ⚫ Off")
        print("\nSpecial commands:")
        print("  menu  = Show this menu")
        print("  quit  = Exit program")
        print("  test  = Test all colors")
        print("-"*50)
    
    def test_all_colors(self):
        """Test all colors in sequence"""
        print("\n🧪 Testing all colors...")
        test_sequence = ['r', 'g', 'b', 'y', 'p', 'c', 'w', 'o']
        
        for cmd in test_sequence:
            color_name = self.colors[cmd][1]
            print(f"Testing {color_name}...")
            self.send_command(cmd)
            time.sleep(1)
        
        print("✅ Test sequence complete!")
    
    def run(self):
        """Main program loop"""
        print("🚀 ESP32 Color Controller Starting...")
        
        # Connect to ESP32
        if not self.connect():
            print("❌ Failed to connect. Exiting.")
            return
        
        self.show_menu()
        
        try:
            while True:
                user_input = input("\n🎨 Enter color command: ").strip().lower()
                
                if user_input in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                elif user_input == 'menu':
                    self.show_menu()
                elif user_input == 'test':
                    self.test_all_colors()
                elif user_input in self.colors:
                    cmd, color_name = self.colors[user_input]
                    print(f"🎯 Sending {color_name} command...")
                    self.send_command(cmd)
                elif user_input == '':
                    continue  # Skip empty input
                else:
                    print(f"❌ Unknown command: '{user_input}'")
                    print("💡 Type 'menu' to see available commands")
        
        except KeyboardInterrupt:
            print("\n👋 Interrupted by user. Goodbye!")
        
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()
                print("🔌 Serial connection closed.")

def main():
    controller = ESP32ColorController()
    controller.run()

if __name__ == "__main__":
    main()