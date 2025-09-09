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
  
  Serial.print("number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);
  
  // Initialize UART connections for actuator chains
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("initialize uart on ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) { // If the object did not initialize, then its configuration is invalid
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
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

  Serial.println("Ready to receive unlimited timed commands via USB Serial!");
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
    
    Serial.print("Batch received and queued in: ");
    Serial.print(t2 - t1);
    Serial.println("us");
  }
  
  // Execute any queued commands that are ready
  executeQueuedCommands();
  
  delay(1); // Small delay to prevent overwhelming the processor
}

void processSerialData(uint8_t* data, int length) {
  if (length % 5 == 0) {  // Ensure the length is a multiple of 5 bytes
    batch_start_time = millis(); // Record when this batch was received
    
    Serial.print("Processing batch of ");
    Serial.print(length / 5);
    Serial.println(" commands");

    for (int i = 0; i < length; i += 5) {
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];
      uint8_t delay_low = data[i+3];
      uint8_t delay_high = data[i+4];

      // Skip padding bytes (0xFF commands)
      if (byte1 == 0xFF) continue;

      // Extract parameters from the 5-byte command
      // byte1: [serial_group(4) | wave(1) | is_start(1) | addr_high(2)]
      // byte2: [addr_low(4) | freq(3) | duty_high(1)]  
      // byte3: [duty_low(7) | marker(1)]
      
      int serial_group_number = (byte1 >> 4) & 0x0F;
      int wave = (byte1 >> 3) & 0x01;
      int is_start = (byte1 >> 2) & 0x01;
      int addr_high = byte1 & 0x03;
      
      int addr_low = (byte2 >> 4) & 0x0F;
      int freq = (byte2 >> 1) & 0x07;
      int duty_high = byte2 & 0x01;
      
      int duty_low = (byte3 >> 1) & 0x7F;  // Skip marker bit
      
      // Reconstruct full values
      int addr = (addr_high << 4) | addr_low;  // 6 bits total (0-63)
      int duty = (duty_high << 7) | duty_low;  // 8 bits total, but we'll clamp to 0-99
      
      // Reconstruct 16-bit delay from little-endian bytes
      uint16_t delay_ms = delay_low | (delay_high << 8);

      // Queue the command for timed execution
      queueTimedCommand(serial_group_number, addr, is_start, duty, freq, wave, delay_ms);
    }
    
    Serial.print("Total commands in queue: ");
    Serial.println(command_queue.size());
  }
  else {
    Serial.print("ERROR: Invalid packet length: ");
    Serial.print(length);
    Serial.println(" (must be multiple of 5)");
  }
}

void queueTimedCommand(int serial_group_number, int addr, int is_start, int duty, int freq, int wave, uint16_t delay_ms) {
  // Validate duty range for 100 levels
  if (duty > 99) duty = 99;
  
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
  
  Serial.print("Queued command: addr=");
  Serial.print(addr);
  Serial.print(", start=");
  Serial.print(is_start);
  Serial.print(", duty=");
  Serial.print(duty);
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
      
      Serial.print("Executed command: addr=");
      Serial.print(it->addr);
      Serial.print(", start=");
      Serial.print(it->is_start);
      Serial.print(", duty=");
      Serial.print(it->duty);
      Serial.print(" at time=");
      Serial.println(current_time);
      
      // Remove executed command from queue
      it = command_queue.erase(it);
    } else {
      ++it;
    }
  }
}

/* Updated command format for 100 duty levels (2-byte protocol)
    The PIC expects this protocol:
    1. Address byte: [0|addr6|addr5|addr4|addr3|addr2|addr1|start]
    2. Data byte 1: [1|duty6|duty5|duty4|duty3|duty2|duty1|duty0] (0-99)
    3. Data byte 2: [1|0|0|0|0|freq2|freq1|freq0] (0-7)
    
    For stop commands, only the address byte is sent.
*/
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (is_start == 1) { // Start command: address + 2 data bytes
    uint8_t message[3];
    
    // Address byte (bit 7 = 0 for address byte)
    message[0] = (motor_addr << 1) | is_start;
    
    // Data byte 1 (bit 7 = 1 for data byte): duty level (0-99)
    message[1] = 0x80 | (duty & 0x7F);
    
    // Data byte 2 (bit 7 = 1 for data byte): frequency (0-7)
    message[2] = 0x80 | (freq & 0x07);
    
    serial_group[serial_group_number].write(message, 3);
    
    Serial.print("Sent start command: addr=");
    Serial.print(motor_addr);
    Serial.print(", duty=");
    Serial.print(duty);
    Serial.print(", freq=");
    Serial.print(freq);
    Serial.print(" (bytes: 0x");
    Serial.print(message[0], HEX);
    Serial.print(" 0x");
    Serial.print(message[1], HEX);
    Serial.print(" 0x");
    Serial.print(message[2], HEX);
    Serial.println(")");
    
  } else { // Stop command: only address byte
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
    
    Serial.print("Sent stop command: addr=");
    Serial.print(motor_addr);
    Serial.print(" (byte: 0x");
    Serial.print(message, HEX);
    Serial.println(")");
  }
}