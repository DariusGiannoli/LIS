#include <esp_now.h>
#include <WiFi.h>

// Slave MAC address
uint8_t slaveMAC[] = {0xCC, 0xBA, 0x97, 0x1D, 0x01, 0x74};

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=== ESP-NOW Color Controller ===");
  Serial.print("Master MAC: ");
  Serial.println(WiFi.macAddress());
  
  WiFi.mode(WIFI_STA);
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed!");
    return;
  }
  
  // Add peer
  esp_now_peer_info_t peerInfo;
  memset(&peerInfo, 0, sizeof(peerInfo));
  memcpy(peerInfo.peer_addr, slaveMAC, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
  
  Serial.println("✓ Connected to slave!");
  Serial.println();
  Serial.println("Commands:");
  Serial.println("r = Red flash");
  Serial.println("g = Green flash"); 
  Serial.println("b = Blue flash");
  Serial.println("y = Yellow flash");
  Serial.println("p = Purple flash");
  Serial.println("c = Cyan flash");
  Serial.println("w = White flash");
  Serial.println("o = Off (turn off LED)");
  Serial.println();
  Serial.println("Type a command and press Enter:");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readString();
    input.trim();
    input.toLowerCase();
    
    if (input.length() == 1) {
      char command = input.charAt(0);
      
      // Send single character command
      esp_err_t result = esp_now_send(slaveMAC, (uint8_t*)&command, 1);
      
      if (result == ESP_OK) {
        String colorName = "";
        switch(command) {
          case 'r': colorName = "Red"; break;
          case 'g': colorName = "Green"; break;
          case 'b': colorName = "Blue"; break;
          case 'y': colorName = "Yellow"; break;
          case 'p': colorName = "Purple"; break;
          case 'c': colorName = "Cyan"; break;
          case 'w': colorName = "White"; break;
          case 'o': colorName = "Off"; break;
          default: colorName = "Unknown"; break;
        }
        Serial.println("✓ Sent: " + colorName + " command");
      } else {
        Serial.println("✗ Send failed");
      }
    } else {
      Serial.println("Enter single letter: r, g, b, y, p, c, w, or o");
    }
  }
}