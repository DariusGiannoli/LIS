#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// --- ADD ALL YOUR SLAVE MAC ADDRESSES HERE ---
// The order here corresponds to the Slave ID (0, 1, 2, etc.)
uint8_t slaveAddresses[][6] = {
  {0xB4, 0x3A, 0x45, 0xB0, 0xD3, 0x4C}, // MAC Address for Slave ID 0
  {0xB4, 0x3A, 0x45, 0xB0, 0xCF, 0x1C}, // MAC Address for Slave ID 1
  // {0x11, 0x22, 0x33, 0x44, 0x55, 0x66}  // MAC Address for Slave ID 2
};

// A special broadcast MAC address (FF:FF:FF:FF:FF:FF)
const uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// We will use a special ID to signify a broadcast message
const uint8_t BROADCAST_ID = 255;

// Callback for when data is sent
// NOTE: The function signature is updated to match the newer ESP32 libraries.
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // Kept empty to not interfere with command serial traffic
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    return;
  }

  esp_now_register_send_cb(OnDataSent);
  
  // --- Register All Slaves as Peers ---
  // This is necessary so they can receive broadcast messages.
  int numSlaves = sizeof(slaveAddresses) / sizeof(slaveAddresses[0]);
  for (int i = 0; i < numSlaves; i++) {
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, slaveAddresses[i], 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
      return;
    }
  }
}

void loop() {
  // Packet size is 1 byte (Slave ID) + 60 bytes (motor command payload)
  if (Serial.available() >= 61) {
    // Read the first byte to determine the target
    uint8_t targetSlaveId = Serial.read();
    
    // Read the 60-byte motor command payload
    uint8_t payloadBuffer[60];
    int bytesRead = Serial.readBytes(payloadBuffer, sizeof(payloadBuffer));

    if (bytesRead > 0) {
      if (targetSlaveId == BROADCAST_ID) {
        // --- Send to All Slaves (Broadcast) ---
        esp_now_send(broadcastAddress, payloadBuffer, bytesRead);
      } else {
        // --- Send to a Specific Slave (Targeted) ---
        int numSlaves = sizeof(slaveAddresses) / sizeof(slaveAddresses[0]);
        if (targetSlaveId < numSlaves) {
          uint8_t* targetAddress = slaveAddresses[targetSlaveId];
          esp_now_send(targetAddress, payloadBuffer, bytesRead);
        }
      }
    }
  }
}