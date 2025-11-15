#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>   // EspSoftwareSerial provides this header
#include <string.h>           // for memmove

// ===== configuration =====
#define UART_BAUD         115200
#define INTER_STOP_US     150    // > 1 char time at 115200 (≈87us)
#define STOP_RETRIES      2      // send STOP twice for reliability
#define RXBUF_SIZE        256    // USB->ESP frame buffer

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;

EspSoftwareSerial::UART serial_group[4];

// USB receive buffer (collects arbitrary chunks and processes in 4-byte frames)
static uint8_t rxBuf[RXBUF_SIZE];
static size_t  rxLen = 0;

// ---------- helpers ----------
static inline void sendStop(int group, int addr) {
  if (group < 0 || group >= subchain_num) return;
  uint8_t b = (uint8_t)(((addr & 0x3F) << 1) | 0x00);  // MSB=0, START=0
  for (int k = 0; k < STOP_RETRIES; ++k) {
    serial_group[group].write(&b, 1);
    serial_group[group].flush();              // ensure it's out on the wire
    delayMicroseconds(INTER_STOP_US);         // give the chain time to swallow it
  }
}

static inline void sendStart3(int group, int addr, uint8_t duty5, uint8_t freq) {
  if (group < 0 || group >= subchain_num) return;
  uint8_t msg[3];
  msg[0] = (uint8_t)(((addr & 0x3F) << 1) | 0x01); // MSB=0, START=1
  msg[1] = (uint8_t)(0x80 | (duty5 & 0x1F));       // MSB=1, 5-bit duty
  msg[2] = (uint8_t)(0x80 | (freq  & 0x07));       // MSB=1, 3-bit freq
  serial_group[group].write(msg, 3);
  serial_group[group].flush();
}

static inline void processFrame(const uint8_t *f) {
  // Format from PC → ESP (still 4 bytes):
  // b1: [---- grp(4) ----][x][x][start]
  // b2: [addr(6) --------][--]
  // b3: [duty5(5) -------][---]
  // b4: [freq(3) --------][----]
  const uint8_t b1 = f[0], b2 = f[1], b3 = f[2], b4 = f[3];
  if (b1 == 0xFF) return; // padding/no-op

  const int group   = (b1 >> 2) & 0x0F;
  const int isStart =  b1       & 0x01;
  const int addr    =  b2       & 0x3F;
  const uint8_t duty5 = b3 & 0x1F;
  const uint8_t freq  = b4 & 0x07;

  if (isStart) sendStart3(group, addr, duty5, freq);
  else         sendStop(group, addr);
}

// ========== Arduino ==========
void setup() {
  Serial.begin(UART_BAUD);

  // Initialize 4 software UART TX lines
  for (int i = 0; i < subchain_num; ++i) {
    serial_group[i].begin(UART_BAUD, SWSERIAL_8N1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(true);   // ✅ smoother TX timing
    if (!serial_group[i]) {
      Serial.println("EspSoftwareSerial pin config invalid!");
    }
    delay(50);
  }

  // Little status LED
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 255, 0));
  strip.show();

  Serial.println("Ready.");
}

void loop() {
  // Ingest any incoming USB bytes into buffer
  while (Serial.available()) {
    if (rxLen < RXBUF_SIZE) {
      rxBuf[rxLen++] = (uint8_t)Serial.read();
    } else {
      (void)Serial.read(); // drop if overflow; optional: count drops
    }
  }

  // Process complete 4-byte frames; keep any remainder for next loop
  while (rxLen >= 4) {
    processFrame(rxBuf);
    memmove(rxBuf, rxBuf + 4, rxLen - 4);
    rxLen -= 4;
  }

  delay(1);
}