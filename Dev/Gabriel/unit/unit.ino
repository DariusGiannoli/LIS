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
    
    // 8N1, 115200 baud
    serial_group[i].begin(115200, SWSERIAL_8N1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) {
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }
  
  Serial.println("Starting Serial communication!");

  // Setup LED
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
  if (Serial.available() > 0) {
    int bytesAvailable = Serial.available();
    uint8_t buffer[bytesAvailable];         // assumes GCC VLA support on ESP32 toolchain
    unsigned long t1 = micros();
    Serial.readBytes(buffer, bytesAvailable);
    processSerialData(buffer, bytesAvailable);
    unsigned long t2 = micros();

    Serial.print("Correct received in : ");
    Serial.print(t2 - t1);
    Serial.println("us");
  }
  delay(1);
}

void processSerialData(uint8_t* data, int length) {
  // Expect 4 bytes per command from PC → Arduino
  if (length % 4 == 0) {
    unsigned long timestamp = millis();
    (void)timestamp;

    for (int i = 0; i < length; i += 4) {
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];
      uint8_t byte4 = data[i+3];

      if (byte1 == 0xFF) continue; // padding

      int serial_group_number = (byte1 >> 2) & 0x0F; // 0..3 used
      int is_start = byte1 & 0x01;
      int addr  = byte2 & 0x3F;   // 6-bit address (0..63)
      int duty5 = byte3 & 0x1F;   // *** 5-bit duty (0..31) ***
      int freq  = byte4 & 0x07;   // 3-bit freq (0..7)

      sendCommand(serial_group_number, addr, is_start, duty5, freq);
    }
  } else {
    unsigned long timestamp = millis();
    (void)timestamp;
    Serial.println("ERROR: Invalid packet length. Expected multiple of 4.");
  }
}

/*
 * New command format sent from Arduino → Vibration Units (PIC):
 *
 * START command (3 bytes total):
 *   Byte 1: [0][ADDR(6-bit)][1]         (Address Byte, START=1)
 *   Byte 2: [1][-----][DUTY(5-bit)]     (Data Byte 1, DUTY in bits [4:0])
 *   Byte 3: [1][-----][FREQ(3-bit)]     (Data Byte 2, FREQ in bits [2:0])
 *
 * STOP command (1 byte total):
 *   Byte 1: [0][ADDR(6-bit)][0]         (Address Byte, START=0)
 *
 * Notes:
 * - PIC maps DUTY 0..31 → 0..99 internally with rounding.
 * - MSB=1 marks data bytes; MSB=0 marks address bytes.
 */
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty5, int freq) {
  if (serial_group_number < 0 || serial_group_number >= subchain_num) return;

  if (is_start == 1) { // Start command → send 3 bytes
    uint8_t message[3];
    // Address byte (MSB must be 0)
    message[0] = (uint8_t)((motor_addr & 0x3F) << 1) | (uint8_t)(is_start & 0x01);
    // Data Byte 1: MSB=1, DUTY in bits [4:0]
    message[1] = (uint8_t)(0x80 | (duty5 & 0x1F));
    // Data Byte 2: MSB=1, FREQ in bits [2:0]
    message[2] = (uint8_t)(0x80 | (freq & 0x07));

    serial_group[serial_group_number].write(message, 3);
  } else { // Stop command → send 1 byte
    uint8_t message = (uint8_t)((motor_addr & 0x3F) << 1); // start=0 in bit0
    serial_group[serial_group_number].write(&message, 1);
  }
}