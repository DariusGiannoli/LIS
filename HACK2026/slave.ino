#include <esp_now.h>
#include <WiFi.h>
#include <SoftwareSerial.h>

#define MIN_IFG_US    120
#define INTER_STOP_US 150
#define STOP_RETRIES  2

#define MODE_STOP     0b00
#define MODE_SOFTSTOP 0b10

const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
EspSoftwareSerial::UART serial_group[4];

static uint32_t last_tx_us[4] = {0, 0, 0, 0};

static inline void guard_ifg(int group) {
  if (group < 0 || group >= subchain_num) return;
  uint32_t now = micros(), dt = now - last_tx_us[group];
  if ((int32_t)dt < MIN_IFG_US) delayMicroseconds(MIN_IFG_US - dt);
  last_tx_us[group] = micros();
}

static void sendStopPIC(int group, int addr6) {
  if (group < 0 || group >= subchain_num) return;
  uint8_t b = (uint8_t)((addr6 & 0x3F) << 1); // stop bit = 0
  for (int k = 0; k < STOP_RETRIES; k++) {
    guard_ifg(group);
    serial_group[group].write(&b, 1);
    serial_group[group].flush();
    delayMicroseconds(INTER_STOP_US);
  }
}

static void sendStartPIC(int group, int addr6, uint8_t duty5, uint8_t freq3, uint8_t wave) {
  if (group < 0 || group >= subchain_num) return;
  uint8_t msg[3];
  msg[0] = (uint8_t)(((addr6 & 0x3F) << 1) | 0x01);                  // addr byte, start=1
  msg[1] = (uint8_t)(0x80 | (duty5 & 0x1F));                          // data1 (MSB=1)
  msg[2] = (uint8_t)(0x80 | ((wave & 0x01) << 3) | (freq3 & 0x07));  // data2 (MSB=1)
  guard_ifg(group);
  serial_group[group].write(msg, 3);
  serial_group[group].flush();
}

// 3-byte frame: b1=[W][0][G3..G0][M1..M0]  b2=[0][0][A5..A0]  b3=[D4..D0][F2..F0]
static void processFrame3(const uint8_t* f) {
  const uint8_t b1 = f[0], b2 = f[1], b3 = f[2];
  if (b1 == 0xFF && b2 == 0xFF && b3 == 0xFF) return; // padding

  const uint8_t wave  = (b1 >> 7) & 0x01;
  const uint8_t mode  =  b1       & 0x03;
  const int     group = (b1 >> 2) & 0x0F;
  const int     addr6 =  b2       & 0x3F;
  const uint8_t duty5 = (b3 >> 3) & 0x1F;
  const uint8_t freq3 =  b3       & 0x07;

  if (mode == MODE_STOP || mode == MODE_SOFTSTOP)
    sendStopPIC(group, addr6);
  else
    sendStartPIC(group, addr6, duty5, freq3, wave);
}

void OnDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *data, int len) {
  int complete = (len / 3) * 3;
  for (int i = 0; i < complete; i += 3) {
    processFrame3(data + i);
  }
}

void setup() {
  Serial.begin(115200);

  // WiFi must be initialized before reading MAC
  WiFi.mode(WIFI_STA);

  // Print MAC so you can copy it into master.ino
  Serial.print("Slave MAC: ");
  Serial.println(WiFi.macAddress());

  for (int i = 0; i < subchain_num; i++) {
    serial_group[i].begin(115200, SWSERIAL_8N1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(true);
    delay(30);
  }
  Serial.println("Motor pins ready.");

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }

  esp_now_register_recv_cb(OnDataRecv);
  Serial.println("Slave ready. Waiting for ESP-NOW commands...");
}

void loop() {}
