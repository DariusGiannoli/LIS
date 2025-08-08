#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>
#include <vector>

// LED setup
Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
uint32_t colors[5];

// Motor control setup - same as original BLE peripheral
const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
int global_counter = 0;

EspSoftwareSerial::UART serial_group[4];

// Timing scheduler structures
struct TimedCommand {
  uint32_t execute_time;    // When to execute (millis() timestamp)
  uint8_t serial_group;     // Serial group number
  uint8_t address;          // Motor address
  uint8_t duty;             // Duty cycle
  uint8_t freq;             // Frequency
  uint8_t wave;             // Wave type
  bool is_start;            // Start (true) or stop (false)
  
  // Constructor
  TimedCommand(uint32_t exec_time, uint8_t sg, uint8_t addr, bool start, uint8_t d, uint8_t f, uint8_t w)
    : execute_time(exec_time), serial_group(sg), address(addr), duty(d), freq(f), wave(w), is_start(start) {}
};

// Command queue for timing
std::vector<TimedCommand> command_queue;
uint32_t batch_start_time = 0;  // Reference time for batch commands

// Function to send commands to motors - copied from original BLE code
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

// Process received data with timing support
void processReceivedData(const uint8_t *data, int len) {
  // Determine command format based on packet length
  bool is_timed_format = false;
  int bytes_per_command = 3;
  
  if (len == 100) {
    // New format: 100 bytes = 20 commands × 5 bytes (with timing)
    is_timed_format = true;
    bytes_per_command = 5;
  } else if (len == 60) {
    // Old format: 60 bytes = 20 commands × 3 bytes (immediate execution)
    is_timed_format = false;
    bytes_per_command = 3;
  } else {
    Serial.print("Warning: Unexpected packet length: ");
    Serial.println(len);
    return;
  }
  
  if (len % bytes_per_command != 0) {
    Serial.println("Error: Packet length not multiple of command size");
    return;
  }

  unsigned long timestamp = millis();
  Serial.print("Timestamp: ");
  Serial.print(timestamp);
  Serial.print(" ms, Data = ");
  Serial.print(len);
  Serial.print(" bytes, Format = ");
  Serial.print(is_timed_format ? "TIMED" : "IMMEDIATE");
  Serial.print(", # = ");
  Serial.println(++global_counter);
  
  // Set batch start time for timed commands
  if (is_timed_format) {
    batch_start_time = millis();
    Serial.print("Batch start time: ");
    Serial.println(batch_start_time);
  }

  int commands_processed = 0;
  for (int i = 0; i < len; i += bytes_per_command) {
    uint8_t byte1 = data[i];
    uint8_t byte2 = data[i+1];
    uint8_t byte3 = data[i+2];

    if (byte1 == 0xFF) continue; // Skip padding bytes

    int serial_group_number = (byte1 >> 2) & 0x0F;
    int is_start = byte1 & 0x01;
    int addr = byte2 & 0x3F;
    int duty = (byte3 >> 3) & 0x0F;
    int freq = (byte3 >> 1) & 0x03;
    int wave = byte3 & 0x01;

    if (is_timed_format && i+4 < len) {
      // Extract timing information (16-bit delay in milliseconds)
      uint16_t delay_ms = data[i+3] | (data[i+4] << 8);
      uint32_t execute_time = batch_start_time + delay_ms;
      
      // Add to command queue
      command_queue.emplace_back(execute_time, serial_group_number, addr, is_start, duty, freq, wave);
      
      Serial.print("Queued: ");
      Serial.print("SG: "); Serial.print(serial_group_number);
      Serial.print(", Mode: "); Serial.print(is_start);
      Serial.print(", Addr: "); Serial.print(addr);
      Serial.print(", Duty: "); Serial.print(duty);
      Serial.print(", Freq: "); Serial.print(freq);
      Serial.print(", Wave: "); Serial.print(wave);
      Serial.print(", Delay: "); Serial.print(delay_ms);
      Serial.print("ms, Execute at: "); Serial.println(execute_time);
      
    } else {
      // Immediate execution (old format or delay=0)
      Serial.print("Immediate: ");
      Serial.print("SG: "); Serial.print(serial_group_number);
      Serial.print(", Mode: "); Serial.print(is_start);
      Serial.print(", Addr: "); Serial.print(addr);
      Serial.print(", Duty: "); Serial.print(duty);
      Serial.print(", Freq: "); Serial.print(freq);
      Serial.print(", Wave: "); Serial.println(wave);
      
      sendCommand(serial_group_number, addr, is_start, duty, freq, wave);
    }
    
    commands_processed++;
  }
  
  Serial.print("Processed ");
  Serial.print(commands_processed);
  Serial.print(" commands, ");
  Serial.print(command_queue.size());
  Serial.println(" commands in queue");
}

// Execute queued commands whose time has come
void processTimedCommands() {
  uint32_t now = millis();
  
  for (auto it = command_queue.begin(); it != command_queue.end();) {
    if (now >= it->execute_time) {
      // Time to execute this command
      Serial.print("Executing: ");
      Serial.print("SG: "); Serial.print(it->serial_group);
      Serial.print(", Addr: "); Serial.print(it->address);
      Serial.print(", Start: "); Serial.print(it->is_start);
      Serial.print(", Duty: "); Serial.print(it->duty);
      Serial.print(", Freq: "); Serial.print(it->freq);
      Serial.print(", Wave: "); Serial.print(it->wave);
      Serial.print(" at "); Serial.println(now);
      
      sendCommand(it->serial_group, it->address, it->is_start, it->duty, it->freq, it->wave);
      
      // Remove executed command from queue
      it = command_queue.erase(it);
      
      // Flash LED briefly to indicate command execution
      strip.setPixelColor(0, strip.Color(255, 255, 255)); // White flash
      strip.show();
      delay(1);
      strip.setPixelColor(0, strip.Color(0, 0, 255)); // Back to blue
      strip.show();
      
    } else {
      ++it;
    }
  }
}

// Callback function that will be executed when data is received
void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  char macStr[18];
  snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
           recv_info->src_addr[0], recv_info->src_addr[1], recv_info->src_addr[2], 
           recv_info->src_addr[3], recv_info->src_addr[4], recv_info->src_addr[5]);
  
  Serial.print("ESP-Now data received from: ");
  Serial.println(macStr);
  
  // Green LED to indicate data reception
  strip.setPixelColor(0, strip.Color(0, 255, 0));
  strip.show();
  
  // Process the received data
  processReceivedData(incomingData, len);
  
  // Return to blue LED after processing
  delay(100);
  strip.setPixelColor(0, strip.Color(0, 0, 255));
  strip.show();
}

void setup() {
  Serial.begin(500000); // Same as original BLE peripheral
  
  Serial.print("number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);
  
  // Initialize software serial for motor control - same as original
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
  
  // LED setup - same as original
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(2, OUTPUT);
  digitalWrite(2, HIGH);
  strip.begin();
  strip.setBrightness(20);
  colors[0] = strip.Color(0, 255, 0);
  strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue to indicate ESP-Now mode
  strip.show();
  
  Serial.println("Slave ESP32 - ESP-Now to Serial Motors (WITH TIMING SCHEDULER)");
  Serial.println("Supported formats:");
  Serial.println("  - 60 bytes: 20 commands × 3 bytes (immediate execution)");
  Serial.println("  - 100 bytes: 20 commands × 5 bytes (timed execution)");
  
  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
    strip.show();
    return;
  }
  
  // Register for a callback function that will be called when data is received
  esp_now_register_recv_cb(OnDataRecv);
  
  Serial.println("ESP-Now initialized successfully");
  Serial.println("Timing scheduler initialized");
  Serial.println("Waiting for ESP-Now data...");
  
  // Purple LED to indicate ready state
  strip.setPixelColor(0, strip.Color(128, 0, 128));
  strip.show();
}

void loop() {
  // Process timed commands - this is the main timing scheduler
  processTimedCommands();
  
  // Small delay to prevent overwhelming the system while maintaining timing precision
  delay(1);  // 1ms precision for timing
}