#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_NeoPixel.h>

// NeoPixel setup for QT Py S3 - try different pin possibilities
#define NEOPIXEL_PIN 39  // Try this first
// If pin 39 doesn't work, try: 38, 35, or 21
#define NUM_PIXELS 1
Adafruit_NeoPixel strip(NUM_PIXELS, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

// Color definitions (RGB values)
uint32_t RED = strip.Color(255, 0, 0);
uint32_t GREEN = strip.Color(0, 255, 0);
uint32_t BLUE = strip.Color(0, 0, 255);
uint32_t YELLOW = strip.Color(255, 255, 0);
uint32_t PURPLE = strip.Color(255, 0, 255);
uint32_t CYAN = strip.Color(0, 255, 255);
uint32_t WHITE = strip.Color(255, 255, 255);
uint32_t OFF = strip.Color(0, 0, 0);

void flashColor(uint32_t color, String colorName) {
  Serial.println("Flashing " + colorName);
  strip.setPixelColor(0, color);
  strip.show();
  delay(500);
  strip.setPixelColor(0, OFF);
  strip.show();
}

void setColor(uint32_t color, String colorName) {
  Serial.println("Setting " + colorName);
  strip.setPixelColor(0, color);
  strip.show();
}

// Callback when data is received
void OnDataRecv(const esp_now_recv_info* recv_info, const uint8_t *incomingData, int len) {
  if (len == 1) {
    char command = (char)incomingData[0];
    
    Serial.print("Received command: ");
    Serial.println(command);
    
    switch(command) {
      case 'r':
        flashColor(RED, "RED");
        break;
      case 'g':
        flashColor(GREEN, "GREEN");
        break;
      case 'b':
        flashColor(BLUE, "BLUE");
        break;
      case 'y':
        flashColor(YELLOW, "YELLOW");
        break;
      case 'p':
        flashColor(PURPLE, "PURPLE");
        break;
      case 'c':
        flashColor(CYAN, "CYAN");
        break;
      case 'w':
        flashColor(WHITE, "WHITE");
        break;
      case 'o':
        setColor(OFF, "OFF");
        break;
      default:
        Serial.println("Unknown command: " + String(command));
        // Flash red twice for error
        flashColor(RED, "ERROR");
        delay(200);
        flashColor(RED, "ERROR");
        break;
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=== ESP-NOW LED Slave ===");
  
  // Initialize NeoPixel with debugging
  Serial.println("Initializing NeoPixel on pin " + String(NEOPIXEL_PIN) + "...");
  strip.begin();
  strip.setBrightness(50); // Set brightness to 50/255
  strip.setPixelColor(0, OFF);
  strip.show();
  Serial.println("NeoPixel initialized");
  
  // Test NeoPixel immediately
  Serial.println("Testing NeoPixel...");
  strip.setPixelColor(0, RED);
  strip.show();
  delay(1000);
  strip.setPixelColor(0, OFF);
  strip.show();
  Serial.println("NeoPixel test complete - did you see red light?");
  
  WiFi.mode(WIFI_STA);
  
  // Show MAC address
  Serial.println("Slave MAC Address:");
  Serial.print("uint8_t slaveMAC[] = {");
  String mac = WiFi.macAddress();
  mac.replace(":", ", 0x");
  Serial.print("0x" + mac);
  Serial.println("};");
  Serial.println();
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed!");
    return;
  }
  
  esp_now_register_recv_cb(OnDataRecv);
  
  Serial.println("Ready to receive color commands!");
  Serial.println("Commands: r, g, b, y, p, c, w, o");
  Serial.println("If no LED flashes, the pin might be wrong.");
}

void loop() {
  // Everything happens in the callback
  delay(100);
}