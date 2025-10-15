// master.ino — ESP32-S3 (Master, red tape)
// Compatible with ESP-IDF < 5 and >= 5 callback signatures.

#include <WiFi.h>
#include <esp_now.h>
#include <esp_idf_version.h>
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5,0,0)
  #include <esp_wifi_types.h>   // wifi_tx_info_t
#endif

// ======= SET YOUR SLAVE MAC HERE =======
uint8_t SLAVE_MAC[] = {0xB4, 0x3A, 0x45, 0xB0, 0xD3, 0x4C}; // B4:3A:45:B0:D3:4C

// Optional: for logs
const char* MASTER_MAC_STR = "CC:BA:97:1C:FF:F4";
const char* SLAVE_MAC_STR  = "B4:3A:45:B0:D3:4C";

// Binary message structure (packed)
typedef struct __attribute__((packed)) {
  uint8_t  magic;        // 0xA5 guard
  uint8_t  channel;      // 0..N-1 or 255=ALL
  uint8_t  duty_255;     // 0..255
  uint16_t duration_ms;  // little-endian
} HapticMsg;

esp_now_peer_info_t peerInfo;
char lineBuf[96];
size_t lineLen = 0;

// ---- Send callback (IDF version compatible) ----
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5,0,0)
void onSend(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  // info may be nullptr on some cores; status is authoritative
  Serial.print(F("[ESP-NOW] Send status: "));
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? F("SUCCESS") : F("FAIL"));
}
#else
void onSend(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print(F("[ESP-NOW] Send status: "));
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? F("SUCCESS") : F("FAIL"));
}
#endif
// ------------------------------------------------

bool addPeerIfNeeded(const uint8_t mac[6]) {
  if (esp_now_is_peer_exist(mac)) return true;
  memset(&peerInfo, 0, sizeof(peerInfo));
  memcpy(peerInfo.peer_addr, mac, 6);
  peerInfo.channel = 0;     // 0 = current channel
  peerInfo.encrypt = false; // set true if you configure keys
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println(F("[ESP-NOW] Failed to add peer"));
    return false;
  }
  Serial.println(F("[ESP-NOW] Peer added"));
  return true;
}

bool parseAndSend(const char* line) {
  // Expect: V,<channel|ALL>,<duty>,<duration_ms>
  char buf[96];
  strncpy(buf, line, sizeof(buf));
  buf[sizeof(buf)-1] = '\0';

  char* tok = strtok(buf, ",");
  if (!tok || (tok[0] != 'V' && tok[0] != 'v')) {
    Serial.println(F("ERR: Expected 'V' at start"));
    return false;
  }

  tok = strtok(NULL, ",");
  if (!tok) { Serial.println(F("ERR: Missing channel/ALL")); return false; }

  int channel = 0;
  bool isAll = false;
  if (strcasecmp(tok, "ALL") == 0) {
    isAll = true; channel = 255;
  } else {
    channel = atoi(tok);
    if (channel < 0 || channel > 254) {
      Serial.println(F("ERR: channel out of range (0..254 or ALL)"));
      return false;
    }
  }

  tok = strtok(NULL, ",");
  if (!tok) { Serial.println(F("ERR: Missing duty")); return false; }
  int duty = atoi(tok);
  if (duty < 0) duty = 0;
  if (duty > 255) duty = 255;

  tok = strtok(NULL, ",");
  if (!tok) { Serial.println(F("ERR: Missing duration_ms")); return false; }
  long dur = atol(tok);
  if (dur < 0) dur = 0;
  if (dur > 60000) dur = 60000;

  HapticMsg msg{0xA5, (uint8_t)channel, (uint8_t)duty, (uint16_t)dur};

  if (!addPeerIfNeeded(SLAVE_MAC)) return false;

  esp_err_t r = esp_now_send(SLAVE_MAC, (uint8_t*)&msg, sizeof(msg));
  if (r != ESP_OK) {
    Serial.print(F("[ESP-NOW] Send error: ")); Serial.println((int)r);
    return false;
  }

  Serial.print(F("TX -> Slave "));
  Serial.print(SLAVE_MAC_STR);
  Serial.print(F(" | ch=")); Serial.print(channel);
  Serial.print(F(" duty=")); Serial.print(duty);
  Serial.print(F(" dur="));  Serial.print((int)dur);
  Serial.println(F(" ms"));
  return true;
}

void setup() {
  Serial.begin(500000);
  delay(200);
  Serial.println();
  Serial.println(F("=== Master (red) — ESP-NOW Haptics ==="));
  Serial.print(F("Master (red) MAC: ")); Serial.println(MASTER_MAC_STR);
  Serial.print(F("Slave MAC:        ")); Serial.println(SLAVE_MAC_STR);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true, true); // avoid AP association/channel lock

  if (esp_now_init() != ESP_OK) {
    Serial.println(F("[ESP-NOW] Init failed"));
    while (true) { delay(1000); }
  }
  esp_now_register_send_cb(onSend);
  Serial.println(F("[ESP-NOW] Ready. Send: V,0,180,250 or V,ALL,120,500"));
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuf[lineLen] = '\0';
      if (lineLen > 0) parseAndSend(lineBuf);
      lineLen = 0;
    } else if (lineLen < sizeof(lineBuf)-1) {
      lineBuf[lineLen++] = c;
    }
  }
}
