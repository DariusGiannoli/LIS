#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_NeoPixel.h>

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// MAC Address of the slave board - REPLACE WITH YOUR SLAVE'S MAC ADDRESS
uint8_t slaveAddress[] = {0xCC, 0xBA, 0x97, 0x1D, 0x01, 0x74}; // ← PUT YOUR SLAVE MAC HERE

// Structure to send data
typedef struct struct_message {
  uint8_t data[60]; // Maximum packet size to match your current system
  int length;
} struct_message;

struct_message myData;

// Callback when data is sent (updated for newer ESP32 core)
void OnDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_SUCCESS) {
    Serial.println("ESP-NOW: Data sent successfully");
    // Green LED for success
    strip.setPixelColor(0, strip.Color(0, 255, 0));
  } else {
    Serial.println("ESP-NOW: Failed to send data");
    // Red LED for failure
    strip.setPixelColor(0, strip.Color(255, 0, 0));
  }
  strip.show();
}

void setup() {
  Serial.begin(115200);
  
  // Initialize NeoPixel
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue during setup
  strip.show();
  
  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // Print MAC address
  Serial.print("Master MAC Address: ");
  Serial.println(WiFi.macAddress());
  
  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
    strip.show();
    return;
  }
  
  // Register send callback
  esp_now_register_send_cb(OnDataSent);
  
  // Register peer
  esp_now_peer_info_t peerInfo;
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
  
  Serial.println("ESP-NOW Master initialized successfully!");
  Serial.println("Ready to receive serial commands and forward via ESP-NOW");
  strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green for ready
  strip.show();
}

void loop() {
  // Check if data is available on USB Serial
  if (Serial.available() > 0) {
    // Read available data
    int bytesAvailable = Serial.available();
    uint8_t buffer[bytesAvailable];
    
    unsigned long t1 = micros();
    
    Serial.readBytes(buffer, bytesAvailable);
    
    // Prepare data for ESP-NOW transmission
    memcpy(myData.data, buffer, bytesAvailable);
    myData.length = bytesAvailable;
    
    // Send message via ESP-NOW
    esp_err_t result = esp_now_send(slaveAddress, (uint8_t *) &myData, sizeof(myData));
    
    if (result == ESP_OK) {
      Serial.print("ESP-NOW: Forwarding ");
      Serial.print(bytesAvailable);
      Serial.println(" bytes to slave");
    } else {
      Serial.println("ESP-NOW: Error sending data");
      strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
      strip.show();
    }
    
    unsigned long t2 = micros();
    Serial.print("Processed and forwarded in: ");
    Serial.print(t2 - t1);
    Serial.println("us");
  }
  
  delay(1);
}

// Function to update slave MAC address (call this if you need to change it)
void updateSlaveAddress(uint8_t* newAddress) {
  // Remove old peer
  esp_now_del_peer(slaveAddress);
  
  // Update address
  memcpy(slaveAddress, newAddress, 6);
  
  // Add new peer
  esp_now_peer_info_t peerInfo;
  memcpy(peerInfo.peer_addr, slaveAddress, 6);
  peerInfo.channel = 0;  
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);
  
  Serial.println("Slave address updated");
}