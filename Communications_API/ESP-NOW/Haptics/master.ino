#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_NeoPixel.h>

// Slave ESP32 MAC Address - CHANGE THIS TO MATCH YOUR SLAVE
uint8_t slaveAddress[] = {0xCC, 0xBA, 0x97, 0x1D, 0x01, 0x74};

// LED setup
Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
uint32_t colors[5];

// ESP-Now peer info
esp_now_peer_info_t peerInfo;

// Global variables
bool slaveConnected = false;
int global_counter = 0;

// Callback when data is sent
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_SUCCESS) {
    Serial.println("ESP-Now: Data sent successfully");
    // Green LED for successful transmission
    strip.setPixelColor(0, strip.Color(0, 255, 0));
  } else {
    Serial.println("ESP-Now: Data send failed");
    // Red LED for failed transmission
    strip.setPixelColor(0, strip.Color(255, 0, 0));
  }
  strip.show();
}

void setup() {
  Serial.begin(115200); // USB Serial for Python communication
  
  // LED setup
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue during setup
  strip.show();
  
  Serial.println("Master ESP32 - Serial to ESP-Now Bridge");
  Serial.println("Slave MAC: CC:BA:97:1D:01:74");
  
  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register for a callback function that will be called when data is sent
  esp_now_register_send_cb(OnDataSent);
  
  // Register peer
  memcpy(peerInfo.peer_addr, slaveAddress, 6);
  peerInfo.channel = 0;  
  peerInfo.encrypt = false;
  
  // Add peer        
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer");
    strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
    strip.show();
    return;
  }
  
  Serial.println("ESP-Now initialized successfully");
  Serial.println("Waiting for serial data...");
  
  // Purple LED to indicate ready state
  strip.setPixelColor(0, strip.Color(128, 0, 128));
  strip.show();
}

void loop() {
  // Check for "test" command from Serial Monitor
  if (Serial.available() > 0) {
    // Peek at the first byte to see if it might be a text command
    uint8_t firstByte = Serial.peek();
    
    // If it looks like ASCII text (letters), treat as command
    if ((firstByte >= 'a' && firstByte <= 'z') || (firstByte >= 'A' && firstByte <= 'Z')) {
      String input = Serial.readString();
      input.trim(); // Remove whitespace
      
      if (input == "test") {
        Serial.println("Sending test command to slave...");
        
        // Create a test command packet (same format as Python)
        uint8_t testData[60];
        
        // Fill with 0xFF padding first
        for (int i = 0; i < 60; i++) {
          testData[i] = 0xFF;
        }
        
        // Create test command for motor addr=1, duty=7, freq=2, start
        int addr = 1;
        int duty = 7;
        int freq = 2;
        int start_or_stop = 1;
        
        int serial_group = addr / 16;  // Fixed: was addr // 16
        int serial_addr = addr % 16;
        
        testData[0] = (serial_group << 2) | (start_or_stop & 0x01);
        testData[1] = 0x40 | (serial_addr & 0x3F);
        testData[2] = 0x80 | ((duty & 0x0F) << 3) | ((freq & 0x07) << 1);
        
        Serial.println("Test command created:");
        Serial.printf("Byte1: 0x%02X, Byte2: 0x%02X, Byte3: 0x%02X\n", 
                      testData[0], testData[1], testData[2]);
        
        // Send via ESP-Now
        esp_err_t result = esp_now_send(slaveAddress, testData, 60);
        
        if (result == ESP_OK) {
          Serial.println("ESP-Now: Test command queued for transmission");
          strip.setPixelColor(0, strip.Color(255, 255, 0)); // Yellow
          strip.show();
        } else {
          Serial.println("ESP-Now: Error sending test command");
          strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red
          strip.show();
        }
        
        return; // Skip the regular data processing
      }
    }
  }
  
  // Check if there's binary data available (from Python)
  // Wait for at least some data, then try to collect 60 bytes
  if (Serial.available() > 0) {
    // Give Python time to send all data
    delay(50);
    
    int availableBytes = Serial.available();
    Serial.print("Received ");
    Serial.print(availableBytes);
    Serial.println(" bytes from Python");
    
    if (availableBytes >= 60) {
      uint8_t data[60];
      size_t bytesRead = Serial.readBytes(data, 60);
      
      // Print first few bytes for debugging
      Serial.print("First 9 bytes: ");
      for (int i = 0; i < 9; i++) {
        Serial.printf("0x%02X ", data[i]);
      }
      Serial.println();
      
      if (bytesRead == 60) {
        unsigned long timestamp = millis();
        Serial.print("Timestamp: ");
        Serial.print(timestamp);
        Serial.print(" ms, Data = ");
        Serial.print(bytesRead);
        Serial.print(" bytes, # = ");
        Serial.println(++global_counter);
        
        // Send data via ESP-Now to slave
        esp_err_t result = esp_now_send(slaveAddress, data, bytesRead);
        
        if (result == ESP_OK) {
          Serial.println("ESP-Now: Python data queued for transmission");
          // Yellow LED during transmission
          strip.setPixelColor(0, strip.Color(255, 255, 0));
          strip.show();
        } else {
          Serial.println("ESP-Now: Error sending Python data");
          // Red LED for error
          strip.setPixelColor(0, strip.Color(255, 0, 0));
          strip.show();
        }
      } else {
        Serial.print("Warning: Expected 60 bytes, got ");
        Serial.println(bytesRead);
      }
      
      // Clear any remaining bytes
      while (Serial.available() > 0) {
        Serial.read();
      }
    } else {
      Serial.print("Not enough bytes yet, waiting... (have ");
      Serial.print(availableBytes);
      Serial.println(")");
      
      // Clear partial data if it's been sitting too long
      delay(100);
      if (Serial.available() == availableBytes) { // No new data came in
        Serial.println("Clearing stale data");
        while (Serial.available() > 0) {
          Serial.read();
        }
      }
    }
  }
  
  // Small delay to prevent overwhelming the system
  delay(10);
}