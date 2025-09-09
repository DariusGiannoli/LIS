#include <esp_now.h>
#include <WiFi.h>

// MAC Address of your slave board - UPDATE THIS WITH YOUR SLAVE'S MAC!
uint8_t slaveAddress[] = {0xCC, 0xBA, 0x97, 0x1D, 0x01, 0x74};

// Structure to send data (60 bytes for actuator commands)
typedef struct struct_message {
  uint8_t data[60];
  int length;
} struct_message;

struct_message myData;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=== ESP-NOW Actuator Master ===");
  Serial.print("Master MAC: ");
  Serial.println(WiFi.macAddress());
  
  WiFi.mode(WIFI_STA);
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed!");
    return;
  }
  
  // Add peer - exactly like your working version
  esp_now_peer_info_t peerInfo;
  memset(&peerInfo, 0, sizeof(peerInfo));
  memcpy(peerInfo.peer_addr, slaveAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
  
  Serial.println("✓ Connected to slave!");
  Serial.println("Ready to receive commands from Python");
  Serial.println("Type 'test' to send a test command");
}

void loop() {
  // Handle manual test command
  if (Serial.available() > 0) {
    String input = Serial.readString();
    input.trim();
    
    if (input == "test") {
      Serial.println("Sending test command...");
      
      // Create a simple test command (start actuator 0)
      myData.data[0] = 0x01; // Group 0, start
      myData.data[1] = 0x40; // Address 0
      myData.data[2] = 0x88; // Duty 1, freq 0, wave 0
      myData.length = 3;
      
      // Fill rest with padding
      for (int i = 3; i < 60; i++) {
        myData.data[i] = 0xFF;
      }
      
      esp_err_t result = esp_now_send(slaveAddress, (uint8_t*)&myData, sizeof(myData));
      
      if (result == ESP_OK) {
        Serial.println("✓ Test command sent!");
      } else {
        Serial.println("✗ Test failed");
        Serial.print("Error code: ");
        Serial.println(result);
      }
      return;
    }
    
    // Handle binary data from Python
    int bytesAvailable = input.length();
    
    Serial.print("Received ");
    Serial.print(bytesAvailable);
    Serial.print(" bytes from Python, sending to slave...");
    
    // Copy data to structure
    memcpy(myData.data, input.c_str(), bytesAvailable);
    myData.length = bytesAvailable;
    
    // Pad to 60 bytes
    for (int i = bytesAvailable; i < 60; i++) {
      myData.data[i] = 0xFF;
    }
    
    // Send via ESP-NOW
    esp_err_t result = esp_now_send(slaveAddress, (uint8_t*)&myData, sizeof(myData));
    
    if (result == ESP_OK) {
      Serial.println(" ✓ Sent!");
    } else {
      Serial.println(" ✗ Failed!");
      Serial.print("Error: ");
      Serial.println(result);
    }
  }
  
  delay(1);
}