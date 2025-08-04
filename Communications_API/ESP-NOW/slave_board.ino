#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// Your existing actuator setup - EXACTLY from your original file
const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
uint32_t colors[5];
int color_num = 5;
int global_counter = 0;

EspSoftwareSerial::UART serial_group[4];

// Structure to receive data (must match sender)
typedef struct struct_message {
  uint8_t data[60];
  int length;
} struct_message;

struct_message incomingData;

// Callback when data is received via ESP-NOW (updated for newer ESP32 core)
void OnDataRecv(const esp_now_recv_info *recv_info, const uint8_t *incomingData, int len) {
  struct_message* receivedData = (struct_message*)incomingData;
  
  Serial.print("ESP-NOW: Received ");
  Serial.print(receivedData->length);
  Serial.println(" bytes");
  
  // Visual feedback - flash blue
  strip.setPixelColor(0, strip.Color(0, 0, 255));
  strip.show();
  
  unsigned long t1 = micros();
  
  // Process the received data using YOUR EXISTING function
  processSerialData(receivedData->data, receivedData->length);
  
  unsigned long t2 = micros();
  
  Serial.print("Processed ESP-NOW data in: ");
  Serial.print(t2 - t1);
  Serial.println("us");
  
  // Return to green (ready state)
  strip.setPixelColor(0, strip.Color(0, 255, 0));
  strip.show();
}

void setup() {
  Serial.begin(115200); // USB Serial for debugging
  
  Serial.print("Number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);
  
  // Initialize UART connections for actuator chains - YOUR EXISTING CODE
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("Initialize UART on pin ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) {
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }
  
  Serial.println("Starting ESP-NOW communication!");

  // Setup LED - YOUR EXISTING CODE
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(2, OUTPUT);
  digitalWrite(2, HIGH);
  strip.begin();
  strip.setBrightness(20);
  colors[0] = strip.Color(0, 255, 0);
  
  // Set as orange during setup
  strip.setPixelColor(0, strip.Color(255, 165, 0));
  strip.show();
  
  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // Print MAC address (you used this for the master)
  Serial.print("Slave MAC Address: ");
  Serial.println(WiFi.macAddress());
  
  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
    strip.show();
    return;
  }
  
  // Register receive callback
  esp_now_register_recv_cb(OnDataRecv);
  
  Serial.println("ESP-NOW Slave initialized successfully!");
  Serial.println("Ready to receive commands via ESP-NOW and control actuators!");
  
  // Green for ready
  strip.setPixelColor(0, colors[0]);
  strip.show();
}

void loop() {
  // The main work is done in the ESP-NOW callback function
  // Just keep the loop running with a small delay
  delay(1);
}

// YOUR EXISTING processSerialData function - EXACTLY the same
void processSerialData(uint8_t* data, int length) {
  if (length % 3 == 0) {  // Ensure the length is a multiple of 3 bytes
    unsigned long timestamp = millis(); // Get current time in milliseconds

    for (int i = 0; i < length; i += 3) {
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];

      if (byte1 == 0xFF) continue; // Skip if the first byte of the command is 0xFF

      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;
      int duty = (byte3 >> 3) & 0x0F;
      int freq = (byte3 >> 1) & 0x03;
      int wave = byte3 & 0x01;

      sendCommand(serial_group_number, addr, is_start, duty, freq, wave);
    }
  }
  else {
    unsigned long timestamp = millis(); // Get current time in milliseconds
    Serial.println("ERROR: Invalid data length");
  }
}

// YOUR EXISTING sendCommand function - EXACTLY the same
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (serial_group_number >= subchain_num) {
    Serial.print("ERROR: Invalid serial group number: ");
    Serial.println(serial_group_number);
    return;
  }
  
  if (is_start == 1) { // Start command, two bytes
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
    
    Serial.print("Sent START command to group ");
    Serial.print(serial_group_number);
    Serial.print(", addr ");
    Serial.print(motor_addr);
    Serial.print(", duty ");
    Serial.print(duty);
    Serial.print(", freq ");
    Serial.print(freq);
    Serial.print(", wave ");
    Serial.println(wave);
  } else { // Stop command, only one byte
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
    
    Serial.print("Sent STOP command to group ");
    Serial.print(serial_group_number);
    Serial.print(", addr ");
    Serial.println(motor_addr);
  }
}