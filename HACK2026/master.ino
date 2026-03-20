#include <esp_now.h>
#include <WiFi.h>

// MAC Address of the Slave ESP32 — update this to match your slave's MAC
uint8_t slaveAddress[] = {0xB4, 0x3A, 0x45, 0xB0, 0xD3, 0x4C};

esp_now_peer_info_t peerInfo;

void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }

  esp_now_register_send_cb(OnDataSent);

  memcpy(peerInfo.peer_addr, slaveAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }

  Serial.println("Master ready.");
}

// Accumulate bytes from PC, send complete 3-byte frames via ESP-NOW
static uint8_t txBuf[60];
static int     txLen = 0;
static uint32_t lastPrint = 0;

void loop() {
  // Keep printing status every 2s so Serial Monitor catches it whenever it opens
  if (millis() - lastPrint > 2000) {
    Serial.println("Master ready.");
    lastPrint = millis();
  }

  while (Serial.available() > 0 && txLen < (int)sizeof(txBuf)) {
    txBuf[txLen++] = (uint8_t)Serial.read();
  }

  // Send as many complete 3-byte frames as possible
  if (txLen >= 3) {
    int sendLen = (txLen / 3) * 3;
    esp_now_send(slaveAddress, txBuf, sendLen);

    int remaining = txLen - sendLen;
    if (remaining > 0) memmove(txBuf, txBuf + sendLen, remaining);
    txLen = remaining;
  }
}
