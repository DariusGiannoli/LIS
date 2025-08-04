#include <esp_now.h>
#include <WiFi.h>
#include <SoftwareSerial.h>

// Your existing actuator setup
const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;

EspSoftwareSerial::UART serial_group[4];

// Structure to receive data (must match sender)
typedef struct struct_message {
  uint8_t data[60];
  int length;
} struct_message;

// Callback when data is received - same signature as your working version
void OnDataRecv(const esp_now_recv_info* recv_info, const uint8_t *incomingData, int len) {
  struct_message* receivedData = (struct_message*)incomingData;
  
  Serial.print("Received ");
  Serial.print(receivedData->length);
  Serial.println(" bytes from master");
  
  // Process the received data
  processSerialData(receivedData->data, receivedData->length);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=== ESP-NOW Actuator Slave ===");
  
  // Initialize UART connections for actuator chains
  Serial.println("Initializing actuator UART connections...");
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("UART on pin ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) {
      Serial.println("ERROR: Invalid pin configuration!");
    } else {
      Serial.println("UART initialized successfully");
    }
    delay(200);
  }
  
  // Setup pins
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(2, OUTPUT);
  digitalWrite(2, HIGH);
  
  WiFi.mode(WIFI_STA);
  
  // Show MAC address - same format as your working version
  Serial.println("Slave MAC Address:");
  Serial.print("uint8_t slaveAddress[] = {");
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
  
  Serial.println("Ready to receive actuator commands!");
}

void loop() {
  // Everything happens in the callback
  delay(100);
}

// Process the received actuator command data
void processSerialData(uint8_t* data, int length) {
  Serial.print("Processing ");
  Serial.print(length);
  Serial.print(" bytes: ");
  
  if (length % 3 == 0) {
    Serial.println("Valid packet");
    
    int commandCount = 0;
    for (int i = 0; i < length; i += 3) {
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];

      if (byte1 == 0xFF) {
        continue; // Skip padding
      }

      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;
      int duty = (byte3 >> 3) & 0x0F;
      int freq = (byte3 >> 1) & 0x03;
      int wave = byte3 & 0x01;

      Serial.printf("Command %d: Group=%d, Addr=%d, Start=%d, Duty=%d, Freq=%d, Wave=%d\n", 
                    commandCount++, serial_group_number, addr, is_start, duty, freq, wave);
      
      sendCommand(serial_group_number, addr, is_start, duty, freq, wave);
    }
    
    Serial.print("Processed ");
    Serial.print(commandCount);
    Serial.println(" commands");
  }
  else {
    Serial.print("ERROR: Invalid packet length: ");
    Serial.println(length);
  }
}

// Send command to actuator
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (serial_group_number >= subchain_num) {
    Serial.print("ERROR: Invalid serial group: ");
    Serial.println(serial_group_number);
    return;
  }
  
  if (is_start == 1) { // Start command
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
    
    Serial.printf("START → Group %d, Addr %d, Duty %d, Freq %d, Wave %d\n", 
                  serial_group_number, motor_addr, duty, freq, wave);
  } else { // Stop command
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
    
    Serial.printf("STOP → Group %d, Addr %d\n", serial_group_number, motor_addr);
  }
}