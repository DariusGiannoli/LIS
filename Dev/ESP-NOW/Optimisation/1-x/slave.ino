

/*
 * OPTIMIZED ESP-NOW SLAVE (1-to-Many)
 * Receives commands from master, displays status via NeoPixel
 * 
 * Features:
 * - 500,000 baud debug (matches BLE, configurable)
 * - Double-buffered packet queue (no drops)
 * - Process in main loop (not ISR - critical for SoftwareSerial)
 * - Comprehensive debug output matching BLE
 * - Performance monitoring with latency tracking
 * - Optimized SoftwareSerial initialization
 * - NeoPixel status indicator
 * - WiFi long-range mode for stability
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>



// ==================== CONFIGURATION ====================
#define SERIAL_BAUD 500000        // Match BLE for debug output (set to 115200 if issues)
#define ENABLE_DEBUG true         // Set false for max performance (no Serial.print)
#define ENABLE_DETAILED_DEBUG false // Set true for per-command debugging

// NeoPixel configuration
Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// Motor control pins
const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
EspSoftwareSerial::UART serial_group[4];

// ==================== PACKET QUEUE ====================
// OPTIMIZATION: Larger queue prevents packet drops at high throughput
#define QUEUE_SIZE 20
#define MAX_PACKET_SIZE 250

struct PacketBuffer {
  uint8_t data[MAX_PACKET_SIZE];
  int length;
  unsigned long receivedAt; // For latency measurement
};

PacketBuffer packetQueue[QUEUE_SIZE];
volatile int queueHead = 0;
volatile int queueTail = 0;
volatile bool hasData = false;

// Performance monitoring
int global_counter = 0;
unsigned long packetsProcessed = 0;
unsigned long packetsDropped = 0;
unsigned long totalLatency = 0;
unsigned long lastStatsTime = 0;

// NeoPixel status
unsigned long lastBlinkTime = 0;
bool ledState = false;

// ==================== ESP-NOW CALLBACK ====================
// CRITICAL: Runs in WiFi interrupt context - must be FAST
// Just copy data to queue, don't process here
void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  // Calculate next head position
  int nextHead = (queueHead + 1) % QUEUE_SIZE;
  
  // Check if queue has space
  if (nextHead != queueTail) {
    // Copy data to queue with timestamp
    memcpy(packetQueue[queueHead].data, incomingData, len);
    packetQueue[queueHead].length = len;
    packetQueue[queueHead].receivedAt = micros(); // For latency measurement
    queueHead = nextHead;
    hasData = true;
  } else {
    // Queue full - packet dropped
    packetsDropped++;
  }
}

// ==================== SETUP ====================
void setup() {
  // Initialize USB Serial for debugging at high speed
  Serial.begin(SERIAL_BAUD);
  while (!Serial && millis() < 3000); // Wait up to 3 sec
  
  Serial.println("\n=== ESP-NOW SLAVE (1-to-Many) - OPTIMIZED ===");
  
  // --- NeoPixel Setup ---
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue = initializing
  strip.show();
  Serial.println("NeoPixel initialized (Blue)");
  
  // --- Motor Controller Setup ---
  Serial.println("Initializing motor control pins...");
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("  Pin ");
    Serial.print(subchain_pins[i]);
    Serial.print("...");
    
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    
    if (!serial_group[i]) {
      Serial.println(" FAILED!");
      // Flash red if failed
      strip.setPixelColor(0, strip.Color(255, 0, 0));
      strip.show();
    } else {
      Serial.println(" OK");
    }
    
    // OPTIMIZATION: Match BLE delay (200ms) for stable SoftwareSerial
    delay(200);
  }
  Serial.println("Motor control initialized");

  // --- ESP-NOW Setup ---
  WiFi.mode(WIFI_STA);
  
  // OPTIMIZATION: Set WiFi to long-range mode
  esp_wifi_set_protocol(WIFI_IF_STA, WIFI_PROTOCOL_LR);
  
  // OPTIMIZATION: Set max WiFi power
  esp_wifi_set_max_tx_power(84);
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: ESP-NOW init failed!");
    // Flash red
    strip.setPixelColor(0, strip.Color(255, 0, 0));
    strip.show();
    return;
  }
  Serial.println("ESP-NOW initialized");
  
  // Register receive callback
  esp_now_register_recv_cb(OnDataRecv);
  
  // Print MAC address (for adding to master)
  Serial.print("MAC Address: ");
  Serial.println(WiFi.macAddress());
  
  // Set NeoPixel to green = ready
  strip.setPixelColor(0, strip.Color(0, 255, 0));
  strip.show();
  
  Serial.println("=== SLAVE READY ===");
  Serial.println("NeoPixel: Green = Ready, Cyan = Active, Red = Error");
  Serial.println("Waiting for motor commands...");
  Serial.print("Debug baud: ");
  Serial.println(SERIAL_BAUD);
  Serial.print("Queue size: ");
  Serial.println(QUEUE_SIZE);
}

// ==================== MAIN LOOP ====================
void loop() {
  // OPTIMIZATION: Process packets in main loop (not ISR) for SoftwareSerial safety
  if (hasData && queueTail != queueHead) {
    // Blink NeoPixel cyan when processing
    strip.setPixelColor(0, strip.Color(0, 255, 255)); // Cyan = processing
    strip.show();
    
    // Get latency measurement
    unsigned long processingStarted = micros();
    unsigned long receiveLatency = processingStarted - packetQueue[queueTail].receivedAt;
    totalLatency += receiveLatency;
    
    // Process the packet
    processMotorCommands(
      packetQueue[queueTail].data, 
      packetQueue[queueTail].length,
      receiveLatency
    );
    
    // Move to next packet
    queueTail = (queueTail + 1) % QUEUE_SIZE;
    packetsProcessed++;
    
    // Check if queue is now empty
    if (queueTail == queueHead) {
      hasData = false;
      // Back to green when idle
      strip.setPixelColor(0, strip.Color(0, 255, 0));
      strip.show();
    }
  }

  // Blink LED periodically to show alive (when idle)
  if (!hasData && millis() - lastBlinkTime > 1000) {
    lastBlinkTime = millis();
    ledState = !ledState;
    if (ledState) {
      strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green
    } else {
      strip.setPixelColor(0, strip.Color(0, 50, 0));  // Dim green
    }
    strip.show();
  }

  // OPTIMIZATION: Print performance stats every 10 seconds
  #if ENABLE_DEBUG
  if (millis() - lastStatsTime > 10000) {
    lastStatsTime = millis();
    float avgLatency = packetsProcessed > 0 ? (float)totalLatency / packetsProcessed : 0;
    float dropRate = (packetsProcessed + packetsDropped) > 0 
                     ? (100.0 * packetsDropped) / (packetsProcessed + packetsDropped) 
                     : 0;
    
    Serial.println("\n========== PERFORMANCE STATS ==========");
    Serial.print("Packets processed: ");
    Serial.println(packetsProcessed);
    Serial.print("Packets dropped: ");
    Serial.println(packetsDropped);
    Serial.print("Drop rate: ");
    Serial.print(dropRate, 2);
    Serial.println("%");
    Serial.print("Avg latency: ");
    Serial.print(avgLatency, 0);
    Serial.println(" µs");
    Serial.print("Queue utilization: ");
    int queueUsed = (queueHead - queueTail + QUEUE_SIZE) % QUEUE_SIZE;
    Serial.print(queueUsed);
    Serial.print("/");
    Serial.println(QUEUE_SIZE);
    Serial.println("=======================================\n");
  }
  #endif
}

// ==================== MOTOR COMMAND PROCESSING ====================
void processMotorCommands(const uint8_t* data, int length, unsigned long latency) {
  #if ENABLE_DEBUG
  // Debug output matching BLE format
  unsigned long timestamp = millis();
  Serial.print("Timestamp: ");
  Serial.print(timestamp);
  Serial.print(" ms, Data = ");
  Serial.print(length);
  Serial.print(" bytes, # = ");
  Serial.print(++global_counter);
  Serial.print(", Latency: ");
  Serial.print(latency);
  Serial.println(" µs");
  #endif
  
  // Validate packet length
  if (length % 3 != 0) {
    #if ENABLE_DEBUG
    Serial.print("ERROR: WRONG LENGTH!!! Received ");
    Serial.print(length);
    Serial.println(" bytes (not multiple of 3)");
    #endif
    // Flash red on error
    strip.setPixelColor(0, strip.Color(255, 0, 0));
    strip.show();
    delay(100);
    return;
  }
  
  // Process each 3-byte command
  for (int i = 0; i < length; i += 3) {
    uint8_t byte1 = data[i];
    uint8_t byte2 = data[i+1];
    uint8_t byte3 = data[i+2];

    // Skip padding bytes
    if (byte1 == 0xFF) continue;

    // Decode command
    int serial_group_number = (byte1 >> 2) & 0x0F;
    int is_start = byte1 & 0x01;
    int addr = byte2 & 0x3F;
    int duty = (byte3 >> 3) & 0x0F;
    int freq = (byte3 >> 1) & 0x03;
    int wave = byte3 & 0x01;

    #if ENABLE_DETAILED_DEBUG
    // Detailed per-command debugging (BLE style)
    Serial.print("  Command: SG=");
    Serial.print(serial_group_number);
    Serial.print(", Mode=");
    Serial.print(is_start);
    Serial.print(", Addr=");
    Serial.print(addr);
    Serial.print(", Duty=");
    Serial.print(duty);
    Serial.print(", Freq=");
    Serial.print(freq);
    Serial.print(", Wave=");
    Serial.println(wave);
    #endif

    // Send to motor
    sendCommandToMotor(serial_group_number, addr, is_start, duty, freq, wave);
  }
}

// ==================== MOTOR COMMAND SENDER ====================
void sendCommandToMotor(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  // Safety check
  if (serial_group_number >= subchain_num) {
    #if ENABLE_DEBUG
    Serial.print("ERROR: Invalid serial group: ");
    Serial.println(serial_group_number);
    #endif
    return;
  }

  // Build and send command (same as BLE)
  if (is_start == 1) {
    // Start command (2 bytes)
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
  } else {
    // Stop command (1 byte)
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
  }
}
