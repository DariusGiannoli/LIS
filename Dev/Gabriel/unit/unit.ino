#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>          // using EspSoftwareSerial::UART below
// #include <ESPSoftwareSerial.h>    // (uncomment if your setup needs this)

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
uint32_t colors[5];
int color_num = 5;
int global_counter = 0;

EspSoftwareSerial::UART serial_group[4];

void setup() {
  Serial.begin(115200); // USB Serial to PC

  Serial.print("number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);

  // Initialize UARTs for actuator chains: 115200 8E1 (even parity).
  // PIC expects the 9th bit == parity(data). 8E1 provides exactly that.
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("initialize uart on ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) {
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }

  Serial.println("Starting Serial communication!");

  // LED setup
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
    uint8_t buffer[bytesAvailable];

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

// PC->ESP32 format (unchanged):
// 4 bytes per command:
//   byte1: [ .... GGGG .. S ]  (we use: group = (byte1>>2)&0x0F, start = byte1&1)
//   byte2: [ ...... AAAA AA ]  (6-bit address)
//   byte3: duty (we now use only 5 LSBs: 0..31)
//   byte4: freq (we now use only 2 LSBs: 0..3)
void processSerialData(uint8_t* data, int length) {
  if (length % 4 == 0) {
    for (int i = 0; i < length; i += 4) {
      uint8_t byte1 = data[i + 0];
      uint8_t byte2 = data[i + 1];
      uint8_t byte3 = data[i + 2];
      uint8_t byte4 = data[i + 3];

      if (byte1 == 0xFF) continue; // padding

      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;       // 6-bit address (0..63)
      int duty = byte3 & 0x1F;       // 5-bit duty   (0..31)  <— changed
      int freq = byte4 & 0x03;       // 2-bit freq   (0..3)   <— changed

      // clamp (safety)
      if (duty > 31) duty = 31;
      if (freq > 3)  freq = 3;

      sendCommand(serial_group_number, addr, is_start, duty, freq);
    }
  } else {
    Serial.println("ERROR: Invalid packet length. Expected multiple of 4.");
  }
}

/*
 * Device on-wire format (to PIC16F18313):
 *
 * START (2 bytes total):
 *   Byte 1 (address): [0][ADDR(6-bit)][1]     // MSB=0, start=1
 *   Byte 2 (data)   : [1][DUTY5][FREQ2]       // MSB=1, duty 0..31 = bits 6..2, freq 0..3 = bits 1..0
 *
 * STOP (1 byte total):
 *   Byte 1 (address): [0][ADDR(6-bit)][0]     // MSB=0, start=0
 *
 * Note: UART is 8E1 so the parity bit transmitted equals parity(data),
 * which the PIC uses as its RX9D "parity" check.
 */
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty5, int freq2) {
  if (serial_group_number < 0 || serial_group_number >= subchain_num) return;

  // clamp fields
  motor_addr &= 0x3F; // 6-bit
  duty5      &= 0x1F; // 5-bit
  freq2      &= 0x03; // 2-bit

  if (is_start == 1) {
    // START: 2 bytes (addr + packed data)
    uint8_t msg[2];
    msg[0] = (uint8_t)((motor_addr << 1) | 0x01);                // MSB=0, start=1
    msg[1] = (uint8_t)(0x80 | (duty5 << 2) | (freq2 & 0x03));    // MSB=1, pack duty+freq
    serial_group[serial_group_number].write(msg, 2);
  } else {
    // STOP: 1 byte (addr with start=0)
    uint8_t msg = (uint8_t)((motor_addr << 1) | 0x00);           // MSB=0, start=0
    serial_group[serial_group_number].write(&msg, 1);
  }
}