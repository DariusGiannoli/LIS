/*
 * OPTIMIZED ESP-NOW MASTER (1-to-Many)
 * Routes commands to multiple slaves or broadcasts to all
 * 
 * Features:
 * - 500,000 baud (matches BLE, configurable)
 * - ESP-NOW optimized for low latency
 * - Multi-slave routing with broadcast support
 * - Packet validation and error handling
 * - Per-slave performance monitoring
 * - WiFi long-range mode for stability
 * 
 * Packet Format: [1 byte Slave ID][60 bytes payload]
 * Slave ID 255 = Broadcast to all slaves
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// ==================== CONFIGURATION ====================
// Performance settings
#define SERIAL_BAUD 500000        // Match BLE performance (set to 115200 if issues)
#define MAX_PACKET_SIZE 250       // ESP-NOW max payload
#define ENABLE_DEBUG false        // Set true for debugging, false for max performance
#define ENABLE_PER_SLAVE_STATS true  // Track stats per slave

// Expected packet format
#define PACKET_HEADER_SIZE 1      // 1 byte for Slave ID
#define PACKET_PAYLOAD_SIZE 60    // 60 bytes for motor commands
#define TOTAL_PACKET_SIZE (PACKET_HEADER_SIZE + PACKET_PAYLOAD_SIZE)  // 61 bytes

// Broadcast ID (sends to all slaves)
const uint8_t BROADCAST_ID = 255;

// ==================== SLAVE CONFIGURATION ====================
// --- ADD ALL YOUR SLAVE MAC ADDRESSES HERE ---
// The order here corresponds to the Slave ID (0, 1, 2, etc.)
uint8_t slaveAddresses[][6] = {
  {0xB4, 0x3A, 0x45, 0xB0, 0xD3, 0x4C}, // Slave ID 0
  {0xB4, 0x3A, 0x45, 0xB0, 0xCF, 0x1C}, // Slave ID 1
  // Add more slave MAC addresses here as needed
  // {0x11, 0x22, 0x33, 0x44, 0x55, 0x66}  // Slave ID 2
};

const int numSlaves = sizeof(slaveAddresses) / sizeof(slaveAddresses[0]);

// Broadcast address (sends to all)
const uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ==================== PERFORMANCE MONITORING ====================
// Global stats
unsigned long totalPacketsSent = 0;
unsigned long totalPacketsFailed = 0;
unsigned long invalidPackets = 0;
unsigned long lastStatsTime = 0;

// Per-slave stats (optional)
#if ENABLE_PER_SLAVE_STATS
struct SlaveStats {
  unsigned long packetsSent;
  unsigned long packetsFailed;
  unsigned long lastSendTime;
};
SlaveStats slaveStats[sizeof(slaveAddresses) / sizeof(slaveAddresses[0])];
unsigned long broadcastsSent = 0;
unsigned long broadcastsFailed = 0;
#endif

// ==================== CALLBACK FUNCTIONS ====================
// ==================== CALLBACK FUNCTIONS ====================
// ==================== CALLBACK FUNCTIONS ====================
// UPDATED callback function with 'des_addr'
void OnDataSent(const esp_now_send_info_t *info, esp_now_send_status_t status) {
  // We get the mac_addr from the 'info' struct now
  const uint8_t* mac_addr = info->des_addr;  // <-- FIX: Was peer_addr
  
  if (status == ESP_NOW_SEND_SUCCESS) {
    totalPacketsSent++;
  } else {
    totalPacketsFailed++;
    #if ENABLE_DEBUG
    Serial.println("Send failed!");
    #endif
  }
  
  // Update per-slave stats if enabled
  #if ENABLE_PER_SLAVE_STATS
  // Find which slave this was
  for (int i = 0; i < numSlaves; i++) {
    if (memcmp(mac_addr, slaveAddresses[i], 6) == 0) {
      if (status == ESP_NOW_SEND_SUCCESS) {
        slaveStats[i].packetsSent++;
      } else {
        slaveStats[i].packetsFailed++;
      }
      slaveStats[i].lastSendTime = millis();
      return;
    }
  }
  // If not found, might be broadcast
  if (memcmp(mac_addr, broadcastAddress, 6) == 0) {
    if (status == ESP_NOW_SEND_SUCCESS) {
      broadcastsSent++;
    } else {
      broadcastsFailed++;
    }
  }
  #endif
}

// ==================== SETUP ====================
void setup() {
  // Initialize Serial at high speed
  Serial.begin(SERIAL_BAUD);
  while (!Serial && millis() < 3000); // Wait up to 3 sec for serial
  
  Serial.println("\n=== ESP-NOW MASTER (1-to-Many) - OPTIMIZED ===");
  Serial.print("Number of slaves: ");
  Serial.println(numSlaves);

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
  
  // Register all slaves as peers
  Serial.println("Registering slaves...");
  for (int i = 0; i < numSlaves; i++) {
    esp_now_peer_info_t peerInfo = {};
    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, slaveAddresses[i], 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    peerInfo.ifidx = WIFI_IF_STA;
    
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
      Serial.print("ERROR: Failed to add Slave ");
      Serial.println(i);
    } else {
      Serial.print("  Slave ");
      Serial.print(i);
      Serial.print(" (");
      for (int j = 0; j < 6; j++) {
        Serial.printf("%02X", slaveAddresses[i][j]);
        if (j < 5) Serial.print(":");
      }
      Serial.println(") added");
      
      #if ENABLE_PER_SLAVE_STATS
      slaveStats[i].packetsSent = 0;
      slaveStats[i].packetsFailed = 0;
      slaveStats[i].lastSendTime = 0;
      #endif
    }
  }
  
  Serial.println("=== MASTER READY ===");
  Serial.println("Waiting for commands from Python...");
  Serial.print("Packet format: [1 byte Slave ID][");
  Serial.print(PACKET_PAYLOAD_SIZE);
  Serial.println(" bytes payload]");
  Serial.print("Broadcast ID: ");
  Serial.println(BROADCAST_ID);
  Serial.print("Serial baud: ");
  Serial.println(SERIAL_BAUD);
}

// ==================== MAIN LOOP ====================
void loop() {
  // Check for incoming data from Python
  // Expected: 61 bytes = 1 byte Slave ID + 60 bytes payload
  if (Serial.available() >= TOTAL_PACKET_SIZE) {
    // Read Slave ID (first byte)
    uint8_t targetSlaveId = Serial.read();
    
    // Read payload (60 bytes)
    uint8_t payloadBuffer[PACKET_PAYLOAD_SIZE];
    int bytesRead = Serial.readBytes(payloadBuffer, sizeof(payloadBuffer));

    if (bytesRead != PACKET_PAYLOAD_SIZE) {
      // Incomplete packet
      #if ENABLE_DEBUG
      Serial.print("ERROR: Incomplete payload. Expected ");
      Serial.print(PACKET_PAYLOAD_SIZE);
      Serial.print(", got ");
      Serial.println(bytesRead);
      #endif
      invalidPackets++;
      return;
    }

    // OPTIMIZATION: Validate payload length (must be multiple of 3)
    if (bytesRead % 3 != 0) {
      #if ENABLE_DEBUG
      Serial.print("ERROR: Invalid payload length ");
      Serial.print(bytesRead);
      Serial.println(" (not multiple of 3)");
      #endif
      invalidPackets++;
      return;
    }

    // Route packet based on Slave ID
    esp_err_t result;
    
    if (targetSlaveId == BROADCAST_ID) {
      // --- BROADCAST to all slaves ---
      #if ENABLE_DEBUG
      Serial.println("Broadcasting to all slaves");
      #endif
      result = esp_now_send(broadcastAddress, payloadBuffer, bytesRead);
      
    } else if (targetSlaveId < numSlaves) {
      // --- TARGETED send to specific slave ---
      #if ENABLE_DEBUG
      Serial.print("Sending to Slave ");
      Serial.println(targetSlaveId);
      #endif
      result = esp_now_send(slaveAddresses[targetSlaveId], payloadBuffer, bytesRead);
      
    } else {
      // --- INVALID Slave ID ---
      #if ENABLE_DEBUG
      Serial.print("ERROR: Invalid Slave ID ");
      Serial.print(targetSlaveId);
      Serial.print(" (max: ");
      Serial.print(numSlaves - 1);
      Serial.println(")");
      #endif
      invalidPackets++;
      return;
    }

    // Check send result
    #if ENABLE_DEBUG
    if (result != ESP_OK) {
      Serial.print("ERROR: Send failed with code ");
      Serial.println(result);
    }
    #endif
  }

  // OPTIMIZATION: Print performance stats every 10 seconds
  #if ENABLE_DEBUG
  if (millis() - lastStatsTime > 10000) {
    lastStatsTime = millis();
    float successRate = (totalPacketsSent + totalPacketsFailed) > 0 
                        ? (100.0 * totalPacketsSent) / (totalPacketsSent + totalPacketsFailed) 
                        : 0;
    
    Serial.println("\n========== MASTER STATS ==========");
    Serial.print("Total sent: ");
    Serial.println(totalPacketsSent);
    Serial.print("Total failed: ");
    Serial.println(totalPacketsFailed);
    Serial.print("Invalid packets: ");
    Serial.println(invalidPackets);
    Serial.print("Success rate: ");
    Serial.print(successRate, 1);
    Serial.println("%");
    
    #if ENABLE_PER_SLAVE_STATS
    Serial.println("\n--- Per-Slave Stats ---");
    for (int i = 0; i < numSlaves; i++) {
      Serial.print("Slave ");
      Serial.print(i);
      Serial.print(": Sent=");
      Serial.print(slaveStats[i].packetsSent);
      Serial.print(", Failed=");
      Serial.print(slaveStats[i].packetsFailed);
      
      if (slaveStats[i].lastSendTime > 0) {
        unsigned long timeSince = millis() - slaveStats[i].lastSendTime;
        Serial.print(", Last seen ");
        Serial.print(timeSince / 1000);
        Serial.print("s ago");
      } else {
        Serial.print(", Never contacted");
      }
      Serial.println();
    }
    
    if (broadcastsSent + broadcastsFailed > 0) {
      Serial.print("Broadcasts: Sent=");
      Serial.print(broadcastsSent);
      Serial.print(", Failed=");
      Serial.println(broadcastsFailed);
    }
    #endif
    
    Serial.println("==================================\n");
  }
  #endif
}
