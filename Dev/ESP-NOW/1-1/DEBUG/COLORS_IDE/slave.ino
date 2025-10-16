#include <esp_now.h>
#include <WiFi.h>
// #include <esp_wifi.h> // This include is not needed for the receive callback type
#include <Adafruit_NeoPixel.h>

// Define the pin and number of pixels for your NeoPixel
#define NEOPIXEL_PIN 39
#define NUM_PIXELS 1

// Create an instance of the Adafruit_NeoPixel class
Adafruit_NeoPixel strip(NUM_PIXELS, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

// Callback function that will be executed when data is received
// Corrected the type from 'wifi_espnow_recv_info_t' to 'esp_now_recv_info_t'
void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  char command;
  // Copy the received data into the 'command' variable
  memcpy(&command, incomingData, sizeof(command));

  Serial.print("Command received: ");
  Serial.println(command);

  // Change the color based on the character received
  if (command == 'r') {
    strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red
    Serial.println("Setting color to RED");
  } else if (command == 'g') {
    strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green
    Serial.println("Setting color to GREEN");
  } else if (command == 'b') {
    strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue
    Serial.println("Setting color to BLUE");
  } else if (command == 'w') {
    strip.setPixelColor(0, strip.Color(255, 255, 255)); // White
    Serial.println("Setting color to WHITE");
  } else if (command == 'o') {
    strip.setPixelColor(0, strip.Color(0, 0, 0)); // Off
    Serial.println("Turning NeoPixel OFF");
  }

  // Send the updated color to the NeoPixel to make it light up
  strip.show();
}
 
void setup() {
  // Initialize Serial Monitor for debugging
  Serial.begin(9600);
  
  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);

  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register the receive callback function
  esp_now_register_recv_cb(OnDataRecv);

  // Initialize the NeoPixel library
  strip.begin(); 
  strip.setBrightness(50); // Set a moderate brightness
  strip.clear(); // Initialize with the pixel off
  strip.show(); 
  
  Serial.println("Slave Board Ready. Waiting for commands...");
}
 
void loop() {
  // The loop can be empty because all the work is handled
  // by the OnDataRecv callback function whenever a message arrives.
}