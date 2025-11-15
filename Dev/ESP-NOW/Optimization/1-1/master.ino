/*
 * OPTIMIZED ESP-NOW MASTER
 * Maximum throughput and reliability for motor control
 * 
 * Features:
 * - 500,000 baud (matches BLE)
 * - ESP-NOW optimized for low latency
 * - Packet validation and error handling
 * - Performance monitoring
 * - WiFi long-range mode for stability
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// ==================== CONFIGURATION ====================
// MAC Address of the Slave ESP32
uint8_t slaveAddress[] = {0xB4, 0x3A, 0x45, 0xB0, 0xD3, 0x4C};

// Performance settings
#define SERIAL_BAUD 500000        // Match BLE performance
#define MAX_PACKET_SIZE 250       // ESP-NOW max payload
#define ENABLE_DEBUG false        // Set true for debugging, false for max performance

// ==================== GLOBAL VARIABLES ====================
esp_now_peer_info_t peerInfo;

// Performance monitoring
unsigned long packetsSent = 0;
unsigned long packetsFailed = 0;
unsigned long lastStatsTime = 0;

// ==================== CALLBACK FUNCTIONS ====================
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_SUCCESS) {
    packetsSent++;
  } else {
    packetsFailed++;
    #if ENABLE_DEBUG
    Serial.println("Send failed!");
    #endif
  }
}

// ==================== SETUP ====================
void setup() {
  // Initialize Serial at high speed (matches BLE)
  Serial.begin(SERIAL_BAUD);
  while (!Serial && millis() < 3000); // Wait up to 3 sec for serial
  
  Serial.println("\n=== ESP-NOW MASTER - OPTIMIZED ===");

  // Set device as Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // OPTIMIZATION: Set WiFi to long-range mode for better reliability
  esp_wifi_set_protocol(WIFI_IF_STA, WIFI_PROTOCOL_LR);
  
  // OPTIMIZATION: Set WiFi to max power for better range
  esp_wifi_set_max_tx_power(84); // 84 = 21dBm (maximum)

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: ESP-NOW init failed!");
    return;
  }
  Serial.println("ESP-NOW initialized");

  // Register send callback
  esp_now_register_send_cb(OnDataSent);
  
  // Configure peer
  memset(&peerInfo, 0, sizeof(peerInfo));
  memcpy(peerInfo.peer_addr, slaveAddress, 6);
  peerInfo.channel = 0;  // Auto-select channel
  peerInfo.encrypt = false;
  peerInfo.ifidx = WIFI_IF_STA;
  
  // Add peer
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("ERROR: Failed to add peer!");
    return;
  }
  
  Serial.println("Peer added successfully");
  Serial.print("Slave MAC: ");
  for (int i = 0; i < 6; i++) {
    Serial.printf("%02X", slaveAddress[i]);
    if (i < 5) Serial.print(":");
  }
  Serial.println();
  
  Serial.println("=== MASTER READY ===");
  Serial.println("Waiting for commands from Python...");
  Serial.print("Serial baud: ");
  Serial.println(SERIAL_BAUD);
}

// ==================== MAIN LOOP ====================
void loop() {
  // Check for incoming data from Python
  if (Serial.available() > 0) {
    // Read incoming packet
    uint8_t buffer[MAX_PACKET_SIZE];
    int bytesRead = Serial.readBytes(buffer, sizeof(buffer));

    if (bytesRead > 0) {
      // OPTIMIZATION: Validate packet length (must be multiple of 3)
      if (bytesRead % 3 == 0) {
        // Send via ESP-NOW
        esp_err_t result = esp_now_send(slaveAddress, buffer, bytesRead);
        
        #if ENABLE_DEBUG
        if (result != ESP_OK) {
          Serial.print("Send error: ");
          Serial.println(result);
        }
        #endif
      } else {
        // Invalid packet length
        #if ENABLE_DEBUG
        Serial.print("Invalid length: ");
        Serial.print(bytesRead);
        Serial.println(" (not multiple of 3)");
        #endif
      }
    }
  }

  // OPTIMIZATION: Print performance stats every 10 seconds
  #if ENABLE_DEBUG
  if (millis() - lastStatsTime > 10000) {
    lastStatsTime = millis();
    float successRate = (packetsSent + packetsFailed) > 0 
                        ? (100.0 * packetsSent) / (packetsSent + packetsFailed) 
                        : 0;
    Serial.println("\n--- STATS ---");
    Serial.print("Sent: ");
    Serial.print(packetsSent);
    Serial.print(" | Failed: ");
    Serial.print(packetsFailed);
    Serial.print(" | Success rate: ");
    Serial.print(successRate, 1);
    Serial.println("%");
  }
  #endif
}
