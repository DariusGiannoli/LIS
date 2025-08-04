/*
 * MAC Address Utility for QT Py S3 ESP-NOW Setup
 * 
 * Upload this to any QT Py S3 board to get its MAC address
 * Use this MAC address in your ESP-NOW master board configuration
 */

#include <WiFi.h>
#include <Adafruit_NeoPixel.h>

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

void setup() {
  Serial.begin(115200);
  
  // Initialize NeoPixel
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue
  strip.show();
  
  // Set WiFi to station mode to get MAC address
  WiFi.mode(WIFI_STA);
  
  Serial.println("\n==================================================");
  Serial.println("QT PY S3 MAC ADDRESS UTILITY");
  Serial.println("==================================================");
  
  // Get and display MAC address
  String macAddress = WiFi.macAddress();
  Serial.println("Board MAC Address: " + macAddress);
  
  // Convert to array format for easy copy-paste
  Serial.println("\nFor ESP-NOW master code, use:");
  Serial.print("uint8_t slaveAddress[] = {");
  
  // Parse and format MAC address
  for (int i = 0; i < 6; i++) {
    String byteStr = macAddress.substring(i * 3, i * 3 + 2);
    int byteVal = strtol(byteStr.c_str(), NULL, 16);
    Serial.print("0x");
    if (byteVal < 16) Serial.print("0");
    Serial.print(byteVal, HEX);
    if (i < 5) Serial.print(", ");
  }
  Serial.println("};");
  
  Serial.println("\nCopy the line above and paste it into your master board code!");
  Serial.println("==================================================");
  
  // Green LED to indicate success
  strip.setPixelColor(0, strip.Color(0, 255, 0));
  strip.show();
}

void loop() {
  // Flash the LED every 2 seconds to show it's running
  static unsigned long lastFlash = 0;
  if (millis() - lastFlash > 2000) {
    strip.setPixelColor(0, strip.Color(0, 255, 0));
    strip.show();
    delay(100);
    strip.setPixelColor(0, strip.Color(0, 50, 0)); // Dim green
    strip.show();
    lastFlash = millis();
    
    // Repeat the MAC address every 10 seconds
    static int counter = 0;
    counter++;
    if (counter >= 5) { // Every 10 seconds (5 * 2 seconds)
      Serial.println("MAC Address: " + WiFi.macAddress());
      counter = 0;
    }
  }
  
  delay(100);
}