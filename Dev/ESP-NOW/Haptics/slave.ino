// slave.ino — ESP32-S3 (Slave)
// ESP-NOW haptic receiver with PWM that compiles on Arduino-ESP32 v2.x and v3.x.
//
// If v3 is present => uses ledcAttach(pin, freq, res) + ledcWrite(pin, duty).
// Else => uses analogWriteResolution/analogWriteFrequency/analogWrite(pin, duty).

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_idf_version.h>
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5,0,0)
  #include <esp_wifi_types.h>   // esp_now_recv_info_t
#endif

// ---------- Hardware config (EDIT PINS TO MATCH YOUR WIRING) ----------
const int ACTUATOR_PINS[] = {
  // Choose PWM-capable pins for your QT Py ESP32-S3
  // Example placeholders; change to your actual pins:
  5, 6, 7, 9, 10, 11
};
const int NUM_ACTUATORS = sizeof(ACTUATOR_PINS) / sizeof(ACTUATOR_PINS[0]);

const int PWM_FREQ_HZ  = 200;  // ERM ~200-300; LRA often ~175-260
const int PWM_RES_BITS = 12;   // 0..(2^bits-1)
// ---------------------------------------------------------------------

// --------- Version detection for Arduino-ESP32 core ----------
#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
  #define USE_LEDC_V3 1
#else
  #define USE_LEDC_V3 0
#endif
// ------------------------------------------------------------

// ---- Message definition from Master ----
typedef struct __attribute__((packed)) {
  uint8_t  magic;        // 0xA5
  uint8_t  channel;      // 0..N-1 or 255=ALL
  uint8_t  duty_255;     // 0..255
  uint16_t duration_ms;  // little-endian
} HapticMsg;

struct ActivePulse {
  bool     active = false;
  uint32_t end_ms = 0;
  uint16_t duty_12b = 0;
};

ActivePulse pulses[16]; // safety headroom

inline uint16_t duty255_to_nbits(uint8_t d, int bits) {
  const uint32_t maxv = (1u << bits) - 1u;
  return (uint16_t)((uint32_t)d * maxv / 255u);
}

// -------------- PWM wrappers (v3 LEDC or portable analogWrite) --------------
static void pwmGlobalInit() {
#if USE_LEDC_V3
  // Nothing global needed for v3 LEDC; set per pin in attach.
#else
  // Portable path
  analogWriteResolution(PWM_RES_BITS);
  // Some cores provide per-pin freq; if not, this call may be global or a no-op.
  // We'll still try per-pin below before first write.
#endif
}

static void pwmAttachPinIdx(int idx) {
  const int pin = ACTUATOR_PINS[idx];
#if USE_LEDC_V3
  // New API: attach per pin with freq & resolution
  ledcAttach(pin, PWM_FREQ_HZ, PWM_RES_BITS);
  ledcWrite(pin, 0);
#else
  // Portable API: ensure freq for this pin, then write 0
  analogWriteFrequency(pin, PWM_FREQ_HZ); // okay if global/no-op on some cores
  analogWrite(pin, 0);
#endif
}

static void pwmWriteIdx(int idx, uint16_t duty) {
  const int pin = ACTUATOR_PINS[idx];
#if USE_LEDC_V3
  ledcWrite(pin, duty);
#else
  analogWrite(pin, duty);
#endif
}
// -----------------------------------------------------------------------------

void setActuatorDuty(int ch, uint16_t duty12) {
  if (ch < 0 || ch >= NUM_ACTUATORS) return;
  pwmWriteIdx(ch, duty12);
}

void startPulse(int ch, uint16_t duty12, uint16_t dur_ms) {
  if (ch < 0 || ch >= NUM_ACTUATORS) return;
  setActuatorDuty(ch, duty12);
  pulses[ch].active   = (dur_ms > 0);
  pulses[ch].duty_12b = duty12;
  pulses[ch].end_ms   = millis() + (uint32_t)dur_ms;
}

void stopIfExpired() {
  const uint32_t now = millis();
  for (int ch = 0; ch < NUM_ACTUATORS; ++ch) {
    if (pulses[ch].active && ((int32_t)(now - pulses[ch].end_ms) >= 0)) {
      pulses[ch].active = false;
      setActuatorDuty(ch, 0);
    }
  }
}

// ---- Receive callback (IDF version compatible) ----
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5,0,0)
void onRecv(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
#else
void onRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
#endif
  if (len != sizeof(HapticMsg)) {
    Serial.print(F("[ESP-NOW] Bad size: ")); Serial.println(len);
    return;
  }
  HapticMsg msg;
  memcpy(&msg, incomingData, sizeof(msg));
  if (msg.magic != 0xA5) {
    Serial.println(F("[ESP-NOW] Bad magic"));
    return;
  }

  const uint16_t duty12 = duty255_to_nbits(msg.duty_255, PWM_RES_BITS);

  if (msg.channel == 255) { // ALL
    for (int ch = 0; ch < NUM_ACTUATORS; ++ch) {
      startPulse(ch, duty12, msg.duration_ms);
    }
    Serial.print(F("RX: ALL duty=")); Serial.print(msg.duty_255);
    Serial.print(F(" dur=")); Serial.print(msg.duration_ms);
    Serial.println(F("ms"));
  } else {
    const int ch = (int)msg.channel;
    if (ch < 0 || ch >= NUM_ACTUATORS) {
      Serial.println(F("[ESP-NOW] Channel OOR"));
      return;
    }
    startPulse(ch, duty12, msg.duration_ms);
    Serial.print(F("RX: ch=")); Serial.print(ch);
    Serial.print(F(" duty=")); Serial.print(msg.duty_255);
    Serial.print(F(" dur="));  Serial.print(msg.duration_ms);
    Serial.println(F("ms"));
  }
}

void setup() {
  Serial.begin(500000);
  delay(200);
  Serial.println();
  Serial.println(F("=== Slave — ESP-NOW Haptics ==="));
  Serial.print(F("Slave STA MAC: "));
  Serial.println(WiFi.macAddress());

  pwmGlobalInit();
  for (int ch = 0; ch < NUM_ACTUATORS; ++ch) {
    pwmAttachPinIdx(ch);
  }

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true, true); // avoid AP/channel lock

  if (esp_now_init() != ESP_OK) {
    Serial.println(F("[ESP-NOW] Init failed"));
    while (true) { delay(1000); }
  }
  esp_now_register_recv_cb(onRecv);
  Serial.println(F("[ESP-NOW] Ready"));
}

void loop() {
  stopIfExpired();
  delay(1);
}
