// unit_optimized.ino
// Changes vs original:
// - Removed memmove() buffering; use a small ring buffer for incoming USB frames.
// - No flush() after START writes (TX stays asynchronous).
// - STOP_RETRIES kept at 2 (works well per your feedback).
// - Kept 4-byte PC->ESP framing; ESP->PIC remains 3 bytes (addr/start + duty5 + freq3).
// - Duty expected on 5 bits from PC; still masked on ESP for safety.

#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>   // from EspSoftwareSerial

// ===== configuration =====
#define UART_BAUD         115200
#define INTER_STOP_US     150    // > 1 char time at 115200 (~87us)
#define STOP_RETRIES      2      // you confirmed this is enough
#define RXBUF_SIZE        512    // ring buffer size for USB CDC (must be >= 4 and reasonable)

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;

// 4 software UART TX for the 4 subchains
SoftwareSerial uarts[subchain_num];

// -------- ring buffer for USB CDC --------
static uint8_t rxbuf[RXBUF_SIZE];
static size_t  rx_head = 0;
static size_t  rx_tail = 0;

static inline size_t rb_count() {
  if (rx_head >= rx_tail) return rx_head - rx_tail;
  return RXBUF_SIZE - (rx_tail - rx_head);
}

static inline bool rb_push(uint8_t b) {
  size_t next = (rx_head + 1) % RXBUF_SIZE;
  if (next == rx_tail) return false; // full
  rxbuf[rx_head] = b;
  rx_head = next;
  return true;
}

static inline bool rb_pop(uint8_t &b) {
  if (rx_head == rx_tail) return false; // empty
  b = rxbuf[rx_tail];
  rx_tail = (rx_tail + 1) % RXBUF_SIZE;
  return true;
}

static inline bool rb_peek4(uint8_t out4[4]) {
  if (rb_count() < 4) return false;
  // copy 4 bytes starting at rx_tail without removing
  size_t t = rx_tail;
  for (int i=0;i<4;i++) {
    out4[i] = rxbuf[t];
    t = (t + 1) % RXBUF_SIZE;
  }
  return true;
}

static inline void rb_drop4() {
  rx_tail = (rx_tail + 4) % RXBUF_SIZE;
}

// -------- protocol helpers --------
static inline void sendStart3(uint8_t group, uint8_t addr_in_chain, uint8_t duty5, uint8_t freq3) {
  if (group >= subchain_num) return;
  SoftwareSerial &s = uarts[group];
  uint8_t a  = (uint8_t)((addr_in_chain & 0x07) << 1) | 0x01; // start bit LSB=1
  uint8_t d1 = (uint8_t)(0x80 | (duty5 & 0x1F));              // MSB=1 data
  uint8_t d2 = (uint8_t)(0x80 | (freq3 & 0x07));              // MSB=1 data
  s.write(a); s.write(d1); s.write(d2);
  // no flush() here (async TX for speed)
}

static inline void sendStop(uint8_t group, uint8_t addr_in_chain) {
  if (group >= subchain_num) return;
  SoftwareSerial &s = uarts[group];
  uint8_t a = (uint8_t)((addr_in_chain & 0x07) << 1); // start=0
  for (int i=0;i<STOP_RETRIES;i++) {
    s.write(a);
    s.flush();                       // ensure the stop byte is out
    delayMicroseconds(INTER_STOP_US);
  }
}

static inline void processFrame(const uint8_t f[4]) {
  const uint8_t b1 = f[0];
  const uint8_t b2 = f[1];
  const uint8_t b3 = f[2];
  const uint8_t b4 = f[3];

  const uint8_t start = b1 & 0x01;
  const uint8_t group = (b1 >> 1) & 0x0F;
  const uint8_t addr6 = b2 & 0x3F;
  const uint8_t addr  = addr6 & 0x07;      // only 0..7 are valid
  const uint8_t duty5 = b3 & 0x1F;
  const uint8_t freq3 = b4 & 0x07;

  if (group >= subchain_num) return;

  if (start) sendStart3(group, addr, duty5, freq3);
  else       sendStop(group, addr);
}

void setup() {
  Serial.begin(UART_BAUD);

  // status pixel
  strip.begin();
  strip.clear();
  strip.setPixelColor(0, strip.Color(0, 30, 0)); // green = ready
  strip.show();

  // init subchains (TX only, rx=-1)
  for (int i=0;i<subchain_num;i++) {
    uarts[i].begin(UART_BAUD, SWSERIAL_8N1, -1, subchain_pins[i], false, 256);
    // If your EspSoftwareSerial supports it, you can enable IRQ-driven TX:
    // uarts[i].enableIntTx(true);
  }
}

void loop() {
  // Ingest USB bytes into the ring buffer
  while (Serial.available()) {
    uint8_t b = (uint8_t)Serial.read();
    (void)rb_push(b); // if full, we drop (could count drops)
  }

  // Process complete frames
  uint8_t f[4];
  while (rb_peek4(f)) {
    processFrame(f);
    rb_drop4();
  }

  // Yield a bit to WiFi/RTOS if present
  delay(1);
}
