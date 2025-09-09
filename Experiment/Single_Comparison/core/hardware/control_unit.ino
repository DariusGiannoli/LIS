/*
 * Standardized Tactile Control System for ESP32
 * 
 * Protocol: 5 bytes per command
 * Byte 1: [serial_group(4)] [reserved(2)] [start_or_stop(1)]
 * Byte 2: 0x40 | [addr(6)]  
 * Byte 3: 0x80 | [duty(4)] [freq(3)] [wave(1)]
 * Byte 4: delay_low (8 bits)
 * Byte 5: delay_high (8 bits)
 */

#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>
#include <vector>

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
uint32_t colors[5];
int color_num = 5;
int global_counter = 0;

// Command queue structure for timed execution
struct TimedCommand {
  unsigned long execute_time;  // When to execute this command (in millis)
  int serial_group_number;
  int addr;
  int is_start;
  int duty;
  int freq;
  int wave;
};

// Dynamic command queue using std::vector - NO SIZE LIMIT!
std::vector<TimedCommand> command_queue;
unsigned long batch_start_time = 0;  // When the current batch was received

EspSoftwareSerial::UART serial_group[4];

void setup() {
  Serial.begin(115200); // USB Serial for communication with PC
  
  Serial.print("Number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);
  
  // Initialize UART connections for actuator chains
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("Initializing UART on pin ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) { // If the object did not initialize, then its configuration is invalid
      Serial.println("❌ Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }
  
  // Reserve some initial capacity for performance (optional)
  command_queue.reserve(100);
  
  Serial.println("Starting Serial communication!");

  //setup LED
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(2, OUTPUT);
  digitalWrite(2, HIGH);
  strip.begin();
  strip.setBrightness(20);
  colors[0] = strip.Color(0, 255, 0);
  strip.setPixelColor(0, colors[0]);
  strip.show();

  Serial.println("✅ Ready to receive unlimited timed commands via USB Serial!");
  Serial.println("📦 Protocol: 5 bytes per command [group+start][addr][duty+freq+wave][delay_low][delay_high]");
}

void loop() {
  // Check if data is available on USB Serial
  if (Serial.available() > 0) {
    // Read available data
    int bytesAvailable = Serial.available();
    uint8_t buffer[bytesAvailable];
    
    unsigned long t1 = micros();
    
    Serial.readBytes(buffer, bytesAvailable);
    // Process the received data
    processSerialData(buffer, bytesAvailable);
    
    unsigned long t2 = micros();
    
    Serial.print("⚡ Batch processed in: ");
    Serial.print(t2 - t1);
    Serial.println("μs");
  }
  
  // Execute any queued commands that are ready
  executeQueuedCommands();
  
  delay(1); // Small delay to prevent overwhelming the processor
}

void processSerialData(uint8_t* data, int length) {
  if (length % 5 == 0) {  // Ensure the length is a multiple of 5 bytes
    batch_start_time = millis(); // Record when this batch was received
    
    Serial.print("📦 Processing batch of ");
    Serial.print(length / 5);
    Serial.println(" commands");

    for (int i = 0; i < length; i += 5) {
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];
      uint8_t delay_low = data[i+3];
      uint8_t delay_high = data[i+4];

      // Skip padding bytes (0xFF commands)
      if (byte1 == 0xFF) {
        Serial.println("⏭️  Skipping padding byte");
        continue;
      }

      // Extract parameters using STANDARDIZED protocol
      int serial_group_number = (byte1 >> 2) & 0x0F;  // Bits 5-2
      int is_start = byte1 & 0x01;                    // Bit 0
      int addr = byte2 & 0x3F;                        // Bits 5-0 (remove 0x40 prefix)
      int duty = (byte3 >> 3) & 0x0F;                 // Bits 6-3 ✅ CORRECT
      int freq = byte3 & 0x07;                        // Bits 2-0 ✅ FIXED (was >>1)
      int wave = byte3 & 0x01;                        // Bit 0   ✅ ADDED
      
      // Reconstruct 16-bit delay from little-endian bytes
      uint16_t delay_ms = delay_low | (delay_high << 8);

      // Debug: Print extracted values
      Serial.print("🔍 Command ");
      Serial.print((i/5) + 1);
      Serial.print(": group=");
      Serial.print(serial_group_number);
      Serial.print(", addr=");
      Serial.print(addr);
      Serial.print(", start=");
      Serial.print(is_start);
      Serial.print(", duty=");
      Serial.print(duty);
      Serial.print(", freq=");
      Serial.print(freq);
      Serial.print(", wave=");
      Serial.print(wave);
      Serial.print(", delay=");
      Serial.print(delay_ms);
      Serial.println("ms");

      // Validate extracted parameters
      if (serial_group_number >= subchain_num) {
        Serial.print("❌ Invalid serial group: ");
        Serial.println(serial_group_number);
        continue;
      }

      // Queue the command for timed execution
      queueTimedCommand(serial_group_number, addr, is_start, duty, freq, wave, delay_ms);
    }
    
    Serial.print("📋 Total commands in queue: ");
    Serial.println(command_queue.size());
  }
  else {
    Serial.print("❌ ERROR: Invalid packet length: ");
    Serial.print(length);
    Serial.println(" (must be multiple of 5 bytes)");
  }
}

void queueTimedCommand(int serial_group_number, int addr, int is_start, int duty, int freq, int wave, uint16_t delay_ms) {
  // Calculate execution time
  unsigned long execute_time = batch_start_time + delay_ms;
  
  // Create new command and add to queue
  TimedCommand cmd;
  cmd.execute_time = execute_time;
  cmd.serial_group_number = serial_group_number;
  cmd.addr = addr;
  cmd.is_start = is_start;
  cmd.duty = duty;
  cmd.freq = freq;
  cmd.wave = wave;
  
  command_queue.push_back(cmd);
  
  Serial.print("⏰ Queued: addr=");
  Serial.print(addr);
  Serial.print(", start=");
  Serial.print(is_start);
  Serial.print(", duty=");
  Serial.print(duty);
  Serial.print(", freq=");
  Serial.print(freq);
  Serial.print(", delay=");
  Serial.print(delay_ms);
  Serial.print("ms, execute_at=");
  Serial.println(execute_time);
}

void executeQueuedCommands() {
  unsigned long current_time = millis();
  
  // Check all queued commands to see if any are ready to execute
  for (auto it = command_queue.begin(); it != command_queue.end(); ) {
    if (current_time >= it->execute_time) {
      // Execute this command
      sendCommand(it->serial_group_number, 
                 it->addr,
                 it->is_start,
                 it->duty,
                 it->freq,
                 it->wave);
      
      Serial.print("⚡ EXECUTED: addr=");
      Serial.print(it->addr);
      Serial.print(", start=");
      Serial.print(it->is_start);
      Serial.print(", duty=");
      Serial.print(it->duty);
      Serial.print(", freq=");
      Serial.print(it->freq);
      Serial.print(" at t=");
      Serial.println(current_time);
      
      // Remove executed command from queue
      it = command_queue.erase(it);
    } else {
      ++it;
    }
  }
}

/* 
 * Send command to actuator using STANDARDIZED format
 * This now matches the Python protocol exactly
 */
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  // Validate serial group
  if (serial_group_number < 0 || serial_group_number >= subchain_num) {
    Serial.print("❌ Invalid serial group: ");
    Serial.println(serial_group_number);
    return;
  }

  if (is_start == 1) { 
    // Start command: two bytes
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    // ✅ FIXED: Use standardized format matching Python
    message[1] = 0x80 | ((duty & 0x0F) << 3) | (freq & 0x07) | (wave & 0x01);
    
    serial_group[serial_group_number].write(message, 2);
    
    Serial.print("📤 Sent START to group ");
    Serial.print(serial_group_number);
    Serial.print(", addr ");
    Serial.print(motor_addr);
    Serial.print(": duty=");
    Serial.print(duty);
    Serial.print(", freq=");
    Serial.print(freq);
    Serial.print(", wave=");
    Serial.println(wave);
    
  } else { 
    // Stop command: one byte
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
    
    Serial.print("📤 Sent STOP to group ");
    Serial.print(serial_group_number);
    Serial.print(", addr ");
    Serial.println(motor_addr);
  }
}

void printProtocolInfo() {
  Serial.println("📋 PROTOCOL INFORMATION:");
  Serial.println("Byte 1: [serial_group(4)] [reserved(2)] [start_or_stop(1)]");
  Serial.println("Byte 2: 0x40 | [addr(6)]");
  Serial.println("Byte 3: 0x80 | [duty(4)] [freq(3)] [wave(1)]");
  Serial.println("Byte 4: delay_low (8 bits)");
  Serial.println("Byte 5: delay_high (8 bits)");
  Serial.println("---");
}