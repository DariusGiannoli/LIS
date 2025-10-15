#include <esp_now.h>
#include <WiFi.h>
#include <SoftwareSerial.h>

// This is the motor control logic from your control_unit.ino
const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
ESPSoftwareSerial::UART serial_group[4];

// Callback function that processes data received from the master
void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  // The received data is a motor command packet, process it directly.
  processMotorCommands(incomingData, len);
}

void setup() {
  // USB Serial for debugging messages
  Serial.begin(115200);

  // --- Motor Controller Setup (from control_unit.ino) ---
  for (int i = 0; i < subchain_num; ++i) {
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) {
      Serial.println("Invalid EspSoftwareSerial pin configuration");
    }
    delay(100);
  }
  Serial.println("Motor control pins initialized.");

  // --- ESP-NOW Setup ---
  WiFi.mode(WIFI_STA);
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register the receive callback function
  esp_now_register_recv_cb(OnDataRecv);
  Serial.println("Slave Board Ready. Waiting for motor commands...");
}

void loop() {
  // The loop is empty because all work is handled by the OnDataRecv callback.
}

// --- Motor Command Processing Logic (from control_unit.ino) ---

// This function decodes the byte packet received from the master
void processMotorCommands(const uint8_t* data, int length) {
  if (length % 3 == 0) {
    for (int i = 0; i < length; i += 3) {
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];

      if (byte1 == 0xFF) continue; // Skip padding bytes

      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;
      int duty = (byte3 >> 3) & 0x0F;
      int freq = (byte3 >> 1) & 0x03;
      int wave = byte3 & 0x01;

      sendCommandToMotor(serial_group_number, addr, is_start, duty, freq, wave);
    }
  }
}

// This function sends the final command to the correct motor chain
void sendCommandToMotor(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (serial_group_number >= subchain_num) return; // Safety check

  if (is_start == 1) { // Start command (2 bytes)
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
  } else { // Stop command (1 byte)
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
  }
}