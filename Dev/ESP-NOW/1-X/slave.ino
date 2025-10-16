#include <esp_now.h>
#include <WiFi.h>
#include <SoftwareSerial.h>
#include <Adafruit_NeoPixel.h>

// This file combines the ESP-NOW receiver with your original motor control logic.

// --- Motor and Peripheral Configuration ---
Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
// CORRECTED: The type for the array of SoftwareSerial objects is simply 'SoftwareSerial'.
SoftwareSerial serial_group[4];

// Function prototypes
void processMotorData(uint8_t* data, int length);
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave);

// --- ESP-NOW Callback ---
// This function is executed whenever a message is received from the master
void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  // Directly process the received payload as motor commands
  processMotorData((uint8_t*)incomingData, len);
}

void setup() {
  Serial.begin(115200); // USB Serial for debugging on the slave
  
  // --- Motor Controller Setup (from your control_unit.ino) ---
  for (int i = 0; i < subchain_num; ++i) {
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
  }
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue to show it's a slave
  strip.show();
  
  // --- ESP-NOW Setup ---
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    return;
  }
  esp_now_register_recv_cb(OnDataRecv);

  Serial.println("Slave Board Ready. Waiting for commands...");
}

void loop() {
  // All work is done in the OnDataRecv callback, so the loop can be empty.
  delay(10);
}

// --- Motor Command Logic (from your control_unit.ino) ---
void processMotorData(uint8_t* data, int length) {
  if (length % 3 == 0) {
    for (int i = 0; i < length; i += 3) {
      uint8_t byte1 = data[i];
      if (byte1 == 0xFF) continue;

      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];

      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;
      int duty = (byte3 >> 3) & 0x0F;
      int freq = (byte3 >> 1) & 0x03;
      int wave = byte3 & 0x01;
      
      sendCommand(serial_group_number, addr, is_start, duty, freq, wave);
    }
  }
}

void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (is_start == 1) { // Start command
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
  } else { // Stop command
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
  }
}