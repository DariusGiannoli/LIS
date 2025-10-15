#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h> // Needed for the wifi_tx_info_t type

// MAC Address of the Slave ESP32
uint8_t slaveAddress[] = {0xB4, 0x3A, 0x45, 0xB0, 0xD3, 0x4C};

// Peer info structure
esp_now_peer_info_t peerInfo;

// Callback function that will be executed when data is sent
// Note the new function signature to match the updated library
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  Serial.print("\r\nLast Packet Send Status:\t");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
}
 
void setup() {
  // Initialize Serial Monitor
  Serial.begin(9600);
 
  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  // Register the send callback function
  esp_now_register_send_cb(OnDataSent);
  
  // Register the slave as a peer
  memcpy(peerInfo.peer_addr, slaveAddress, 6);
  peerInfo.channel = 0;  
  peerInfo.encrypt = false;
  
  // Add the peer        
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Failed to add peer");
    return;
  }

  Serial.println("Master Board Ready");
  Serial.println("Enter a command in the Serial Monitor to control the Slave's LED.");
  Serial.println("Commands: r (Red), g (Green), b (Blue), w (White), o (Off)");
}
 
void loop() {
  // Check if there's a character available from the Serial Monitor
  if (Serial.available() > 0) {
    char command = Serial.read();

    // Send the command character via ESP-NOW to the slave
    esp_err_t result = esp_now_send(slaveAddress, (uint8_t *) &command, sizeof(command));
   
    if (result == ESP_OK) {
      Serial.print("Sent command: ");
      Serial.println(command);
    }
    else {
      Serial.println("Error sending the data");
    }
  }
  delay(10); // A small delay to keep the loop stable
}