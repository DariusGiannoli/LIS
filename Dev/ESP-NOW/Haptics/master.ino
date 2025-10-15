#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// MAC Address of the Slave ESP32
uint8_t slaveAddress[] = {0xB4, 0x3A, 0x45, 0xB0, 0xD3, 0x4C};

// Peer info structure
esp_now_peer_info_t peerInfo;

// Callback function for when data is sent
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // This is optional but good for debugging. 
  // We avoid printing here to keep the serial channel clear for commands.
}

void setup() {
  // Initialize Serial Monitor at the same baud rate as the Python script
  Serial.begin(115200);

  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    // If it fails, we won't be able to send anything.
    return;
  }

  // Register the send callback function
  esp_now_register_send_cb(OnDataSent);
  
  // Register the slave as a peer
  memcpy(peerInfo.peer_addr, slaveAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  // Add the peer
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    // If it fails, we won't be able to send anything.
    return;
  }
}

void loop() {
  // Check if there is data available from the Python script
  if (Serial.available() > 0) {
    // Create a buffer to hold the incoming data. 60 bytes matches the Python script's padding.
    uint8_t buffer[60];
    int bytesRead = Serial.readBytes(buffer, sizeof(buffer));

    // Send the received data packet to the slave via ESP-NOW
    if (bytesRead > 0) {
      esp_now_send(slaveAddress, buffer, bytesRead);
    }
  }
}