#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Adafruit_NeoPixel.h>

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("=== MAC Address Fix Test ===");
  
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(255, 165, 0)); // Orange during setup
  strip.show();
  
  Serial.println("1. Starting WiFi with proper initialization...");
  
  // More thorough WiFi initialization
  WiFi.mode(WIFI_STA);
  WiFi.begin(); // Start WiFi properly
  delay(1000);
  
  Serial.print("2. MAC Address attempt 1: ");
  Serial.println(WiFi.macAddress());
  
  // Alternative method to get MAC
  uint8_t mac[6];
  esp_wifi_get_mac(WIFI_IF_STA, mac);
  Serial.printf("3. MAC Address attempt 2: %02X:%02X:%02X:%02X:%02X:%02X\n", 
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  
  // Check if we got a valid MAC
  bool validMAC = false;
  for(int i = 0; i < 6; i++) {
    if(mac[i] != 0x00) {
      validMAC = true;
      break;
    }
  }
  
  if(validMAC) {
    Serial.println("4. ✅ Valid MAC address found!");
    
    // Now try ESP-NOW
    Serial.println("5. Initializing ESP-NOW...");
    esp_err_t result = esp_now_init();
    if (result == ESP_OK) {
      Serial.println("6. ✅ ESP-NOW initialized successfully!");
      strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green for success
    } else {
      Serial.print("6. ❌ ESP-NOW failed. Error: ");
      Serial.println(result);
      strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
    }
  } else {
    Serial.println("4. ❌ MAC address still invalid!");
    strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
  }
  
  strip.show();
}

void loop() {
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 5000) {
    Serial.print("Current MAC: ");
    Serial.println(WiFi.macAddress());
    lastPrint = millis();
  }
  delay(100);
}