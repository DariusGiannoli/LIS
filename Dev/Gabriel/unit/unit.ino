#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>       // EspSoftwareSerial
#include <HardwareSerial.h>

#ifndef PIN_NEOPIXEL
#define PIN_NEOPIXEL  PIN_NEOPIXEL  // défini par la BSP Adafruit, sinon remplacez par la pin réelle
#endif

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// Pins TX des 4 sous-chaînes
const int subchain_pins[4] = {18, 17, 9, 8}; // g0..g3
const int subchain_num = 4;

// UART matériel pour groupe 0 (TX=GPIO18)
HardwareSerial H0(1);

// UARTs software pour groupes 1..3
EspSoftwareSerial::UART serial_group[4];

void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty5, int freq2) {
  motor_addr &= 0x3F;  // 6 bits
  duty5      &= 0x1F;  // 5 bits
  freq2      &= 0x03;  // 2 bits

  uint8_t addr_byte = (uint8_t)((motor_addr << 1) | (is_start ? 1 : 0));

  if (is_start) {
    uint8_t data_byte = (uint8_t)(0x80 | (duty5 << 2) | (freq2 & 0x03));

    // DEBUG
    Serial.printf("[TX g%d a%d] START d=%u f=%u  -> %02X %02X\n",
                  serial_group_number, motor_addr, duty5, freq2, addr_byte, data_byte);

    if (serial_group_number == 0) {
      H0.write(&addr_byte, 1);
      H0.write(&data_byte, 1);
    } else {
      serial_group[serial_group_number].write(&addr_byte, 1);
      serial_group[serial_group_number].write(&data_byte, 1);
    }
  } else {
    // STOP
    Serial.printf("[TX g%d a%d] STOP -> %02X\n", serial_group_number, motor_addr, addr_byte);
    if (serial_group_number == 0) {
      H0.write(&addr_byte, 1);
    } else {
      serial_group[serial_group_number].write(&addr_byte, 1);
    }
  }
}

// Décode les paquets 4 octets venant du PC (USB CDC)
void processSerialData(uint8_t* data, int length) {
  if (length % 4 != 0) {
    Serial.println("ERROR: Invalid packet length (must be multiple of 4)");
    return;
  }
  for (int i = 0; i < length; i += 4) {
    uint8_t b1 = data[i + 0];
    uint8_t b2 = data[i + 1];
    uint8_t b3 = data[i + 2];
    uint8_t b4 = data[i + 3];

    if (b1 == 0xFF) continue; // padding

    int serial_group_number = (b1 >> 2) & 0x0F;
    int is_start = b1 & 0x01;
    int addr     = b2 & 0x3F;   // 0..63, on n'utilise que 0..7
    int duty5    = b3 & 0x1F;   // 0..31
    int freq2    = b4 & 0x03;   // 0..3

    if (serial_group_number < 0 || serial_group_number >= subchain_num) {
      Serial.println("ERROR: group out of range");
      continue;
    }
    sendCommand(serial_group_number, addr, is_start, duty5, freq2);
  }
}

void setup() {
  Serial.begin(115200); // USB CDC vers PC
  while(!Serial && millis() < 3000){}

  Serial.println("\n[ESP32 Bridge] boot");

  // UART matériel groupe 0 : TX=GPIO18, 8E1
  H0.begin(115200, SERIAL_8E1, -1, subchain_pins[0], false);

  // UARTs software (8E1) pour groupes 1..3
  for (int i = 1; i < subchain_num; ++i) {
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) {
      Serial.printf("Invalid SoftSerial config on pin %d\n", subchain_pins[i]);
    }
    delay(50);
  }

  // LED de statut
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 128, 0)); // vert = prêt
  strip.show();

  Serial.print("TX pins: ");
  for (int i=0;i<subchain_num;i++){ Serial.print(subchain_pins[i]); Serial.print(i<subchain_num-1?',':'\n'); }
  Serial.println("Ready to receive 4-byte commands over USB Serial.");
}

void loop() {
  int n = Serial.available();
  if (n > 0) {
    static uint8_t buf[256];
    n = n > (int)sizeof(buf) ? sizeof(buf) : n;
    int got = Serial.readBytes(buf, n);
    if (got > 0) processSerialData(buf, got);
  }
}