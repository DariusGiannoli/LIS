#include <esp_now.h>
#include <WiFi.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>

// LED setup
Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
uint32_t colors[5];

// Motor control setup - same as original BLE peripheral
const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
int global_counter = 0;

EspSoftwareSerial::UART serial_group[4];

// Function to send commands to motors - copied from original BLE code
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (is_start == 1) { // Start command, two bytes
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
  } else { // Stop command, only one byte
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
  }
}

// Process received data - adapted from MyCharacteristicCallbacks::onWrite()
void processReceivedData(const uint8_t *data, int len) {
  if (len % 3 == 0) {  // Ensure the length is a multiple of 3 bytes
    unsigned long timestamp = millis(); // Get current time in milliseconds
    Serial.print("Timestamp: ");
    Serial.print(timestamp);
    Serial.print(" ms, Data = ");
    Serial.print(len);
    Serial.print(" bytes, # = ");
    Serial.println(++global_counter);

    for (int i = 0; i < len; i += 3) {
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

      // Print received values for debugging
      Serial.print("Received: ");
      Serial.print("SG: "); Serial.print(serial_group_number);
      Serial.print(", Mode: "); Serial.print(is_start);
      Serial.print(", Addr: "); Serial.print(addr);
      Serial.print(", Duty: "); Serial.print(duty);
      Serial.print(", Freq: "); Serial.print(freq);
      Serial.print(", Wave: "); Serial.println(wave);
      
      sendCommand(serial_group_number, addr, is_start, duty, freq, wave);
    }
  } else {
    unsigned long timestamp = millis();
    Serial.print("Timestamp: ");
    Serial.print(timestamp);
    Serial.print(" ms, Data = ");
    Serial.print(len);
    Serial.println(", WRONG LENGTH!!!!!!!!!!!!!!!!");
  }
}

// Callback function that will be executed when data is received
void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *incomingData, int len) {
  char macStr[18];
  snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
           recv_info->src_addr[0], recv_info->src_addr[1], recv_info->src_addr[2], 
           recv_info->src_addr[3], recv_info->src_addr[4], recv_info->src_addr[5]);
  
  Serial.print("ESP-Now data received from: ");
  Serial.println(macStr);
  
  // Green LED to indicate data reception
  strip.setPixelColor(0, strip.Color(0, 255, 0));
  strip.show();
  
  // Process the received data
  processReceivedData(incomingData, len);
  
  // Return to blue LED after processing
  delay(100);
  strip.setPixelColor(0, strip.Color(0, 0, 255));
  strip.show();
}

void setup() {
  Serial.begin(500000); // Same as original BLE peripheral
  
  Serial.print("number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);
  
  // Initialize software serial for motor control - same as original
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("initialize uart on ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) { // If the object did not initialize, then its configuration is invalid
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }
  
  // LED setup - same as original
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(2, OUTPUT);
  digitalWrite(2, HIGH);
  strip.begin();
  strip.setBrightness(20);
  colors[0] = strip.Color(0, 255, 0);
  strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue to indicate ESP-Now mode
  strip.show();
  
  Serial.println("Slave ESP32 - ESP-Now to Serial Motors");
  
  // Set device as a Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red for error
    strip.show();
    return;
  }
  
  // Register for a callback function that will be called when data is received
  esp_now_register_recv_cb(OnDataRecv);
  
  Serial.println("ESP-Now initialized successfully");
  Serial.println("Waiting for ESP-Now data...");
  
  // Purple LED to indicate ready state
  strip.setPixelColor(0, strip.Color(128, 0, 128));
  strip.show();
}

void loop() {
  // Main processing is handled by the ESP-Now callback
  // Just keep the system running
  delay(10);
}