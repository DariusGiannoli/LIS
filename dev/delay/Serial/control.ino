#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>

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
  bool active;  // Whether this command slot is in use
};

const int MAX_QUEUED_COMMANDS = 50;  // Maximum number of queued commands
TimedCommand command_queue[MAX_QUEUED_COMMANDS];
int queue_head = 0;  // Next available slot in queue
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
  
  // Initialize command queue
  for (int i = 0; i < MAX_QUEUED_COMMANDS; i++) {
    command_queue[i].active = false;
  }
  
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

  Serial.println("Ready to receive 5-byte timed commands via USB Serial!");
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
      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;
      int duty = (byte3 >> 3) & 0x0F;
      int freq = (byte3 >> 1) & 0x03;
      int wave = byte3 & 0x01;
      
      // Reconstruct 16-bit delay from little-endian bytes
      uint16_t delay_ms = delay_low | (delay_high << 8);

      // Queue the command for timed execution
      queueTimedCommand(serial_group_number, addr, is_start, duty, freq, wave, delay_ms);
    }
  }
  else {
    Serial.print("ERROR: Invalid packet length: ");
    Serial.print(length);
    Serial.println(" (must be multiple of 5)");
  }
}

void queueTimedCommand(int serial_group_number, int addr, int is_start, int duty, int freq, int wave, uint16_t delay_ms) {
  // Find next available slot in queue
  int slot = -1;
  for (int i = 0; i < MAX_QUEUED_COMMANDS; i++) {
    if (!command_queue[i].active) {
      slot = i;
      break;
    }
  }
  
  if (slot == -1) {
    Serial.println("ERROR: Command queue full!");
    return;
  }
  
  // Calculate execution time
  unsigned long execute_time = batch_start_time + delay_ms;
  
  // Store command in queue
  command_queue[slot].execute_time = execute_time;
  command_queue[slot].serial_group_number = serial_group_number;
  command_queue[slot].addr = addr;
  command_queue[slot].is_start = is_start;
  command_queue[slot].duty = duty;
  command_queue[slot].freq = freq;
  command_queue[slot].wave = wave;
  command_queue[slot].active = true;
  
  Serial.print("Queued command: addr=");
  Serial.print(addr);
  Serial.print(", start=");
  Serial.print(is_start);
  Serial.print(", delay=");
  Serial.print(delay_ms);
  Serial.print("ms, execute_at=");
  Serial.println(execute_time);
}

void executeQueuedCommands() {
  unsigned long current_time = millis();
  
  // Check all queued commands to see if any are ready to execute
  for (int i = 0; i < MAX_QUEUED_COMMANDS; i++) {
    if (command_queue[i].active && current_time >= command_queue[i].execute_time) {
      // Execute this command
      sendCommand(command_queue[i].serial_group_number, 
                 command_queue[i].addr,
                 command_queue[i].is_start,
                 command_queue[i].duty,
                 command_queue[i].freq,
                 command_queue[i].wave);
      
      Serial.print("Executed command: addr=");
      Serial.print(command_queue[i].addr);
      Serial.print(", start=");
      Serial.print(command_queue[i].is_start);
      Serial.print(" at time=");
      Serial.println(current_time);
      
      // Mark this slot as available
      command_queue[i].active = false;
    }
  }
}

/* command format
    command = {
        'addr':motor_addr,
        'mode':start_or_stop,
        'duty':3, # default
        'freq':2, # default
        'wave':0, # default
    }
*/
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (is_start == 1) { // Start command, two bytes
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
  } else { // Stop command, only one byte
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
  }
}