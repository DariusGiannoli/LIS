#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
uint32_t colors[5];
int color_num = 5;
int global_counter = 0;

EspSoftwareSerial::UART serial_group[4];

void setup() {
  Serial.begin(115200); // USB Serial for communication with PC
  
  Serial.print("number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);
  
  // Initialize UART connections for actuator chains
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("initialize uart on ");
    Serial.println(subchain_pins[i]);
    
    // --- MODIFIED ---
    // Init with 8-bit data, No parity, 1 stop bit (8N1)
    serial_group[i].begin(115200, SWSERIAL_8N1, -1, subchain_pins[i], false);
    
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) { // If the object did not initialize, then its configuration is invalid
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }
  
  Serial.println("Starting Serial communication!");

  //setup LED
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(2, OUTPUT);
  digitalWrite(2, HIGH);
  strip.begin();
  strip.setBrightness(20);
  colors[0] = strip.Color(0, 255, 0);
  strip.setPixelColor(0, colors[0]);
  strip.show();
  Serial.println("Ready to receive commands via USB Serial!");
}

void loop() {
  // Check if data is available on USB Serial
  if (Serial.available() > 0) {
    // Read available data
    int bytesAvailable = Serial.available();
    uint8_t buffer[bytesAvailable];
    
    unsigned long t1 = micros();

    Serial.readBytes(buffer, bytesAvailable);
    // Process the received data
    processSerialData(buffer, bytesAvailable);
    unsigned long t2 = micros();

    Serial.print("Correct received in : ");
    Serial.print(t2 - t1);
    Serial.println("us");

    
    
  }
  
  delay(1);
  // Small delay to prevent overwhelming the processor
}

void processSerialData(uint8_t* data, int length) {
  // Expect 4 bytes per command
  if (length % 4 == 0) {  
    unsigned long timestamp = millis();
    // Get current time in milliseconds

    for (int i = 0; i < length; i += 4) { // Increment by 4
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];
      uint8_t byte4 = data[i+3];
      // New 4th byte

      if (byte1 == 0xFF) continue;
      // Skip if the first byte of the command is 0xFF (padding)

      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;
      // 6-bit address
      int duty = byte3 & 0x7F;
      // 7-bit duty
      int freq = byte4 & 0x07;
      // 3-bit freq
      // int wave = byte3 & 0x01;
      // 'wave' is no longer used

      
      sendCommand(serial_group_number, addr, is_start, duty, freq);
    }
  }
  else{
    unsigned long timestamp = millis();
    // Get current time in milliseconds
    Serial.print("ERROR: Invalid packet length. Expected multiple of 4.");
  }
}

/* * New command format sent to Vibration Units:
 * * START command (3 bytes):
 * Byte 1: [0][ADDR(6-bit)][1]  (Address Byte, START=1)
 * Byte 2: [1][DUTY(7-bit)]   (Data Byte 1)
 * Byte 3: [1][0000][FREQ(3-bit)] (Data Byte 2)
 * * STOP command (1 byte):
 * Byte 1: [0][ADDR(6-bit)][0]  (Address Byte, START=0)
*/
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq) {
  
  if (serial_group_number < 0 || serial_group_number >= subchain_num) return;
  if (is_start == 1) { // Start command, THREE bytes
    uint8_t message[3];
    message[0] = (motor_addr << 1) | is_start; // Byte 1: Address + Start
    message[1] = 0x80 |
    (duty & 0x7F);         // Byte 2: Data + 7-bit Duty
    message[2] = 0x80 | (freq & 0x07);
    // Byte 3: Data + 3-bit Freq
    serial_group[serial_group_number].write(message, 3);
  } else { // Stop command, only one byte
    uint8_t message = (motor_addr << 1) | is_start;
    // Byte 1: Address + Stop
    serial_group[serial_group_number].write(&message, 1);
  }
}