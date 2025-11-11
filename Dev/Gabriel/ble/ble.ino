#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLEClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>

#define SERVICE_UUID        "f10016f6-542b-460a-ac8b-bbb0b2010599"
#define CHARACTERISTIC_UUID "f22535de-5375-44bd-8ca9-d0ea9ff9e410"

BLECharacteristic *csCharacteristic;
bool deviceConnected = false;

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

const int subchain_pins[8] = {26, 25, 5, 19, 21, 14, 32, 15};
const int subchain_num = 8;
uint32_t colors[5];
int color_num = 5;
int global_counter = 0;

// NB: tableau alloué à 4 UART logiciels dans ton code original.
// (On ne change pas cette logique ici pour rester focalisé sur le duty 5 bits)
EspSoftwareSerial::UART serial_group[4];

class MyCharacteristicCallbacks: public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue();

      // ⚠️ On passe à des trames de 4 octets (duty5 séparé de freq)
      if (value.length() % 4 == 0) {
          unsigned long timestamp = millis();
          Serial.print("Timestamp: ");
          Serial.print(timestamp);
          Serial.print(" ms, Data = ");
          Serial.print(value.length());
          Serial.print(" bytes, # = ");
          Serial.println(++global_counter);

          for (int i = 0; i < value.length(); i += 4) {
              uint8_t byte1 = value[i + 0];
              uint8_t byte2 = value[i + 1];
              uint8_t byte3 = value[i + 2];
              uint8_t byte4 = value[i + 3];

              // Skip full padding frame FF FF FF FF
              if (byte1 == 0xFF && byte2 == 0xFF && byte3 == 0xFF && byte4 == 0xFF) continue;

              int serial_group_number = (byte1 >> 2) & 0x0F;
              int is_start = byte1 & 0x01;
              int addr     = byte2 & 0x3F;
              int duty5    = byte3 & 0x1F;  // 5-bit duty
              int freq3    = byte4 & 0x07;  // 3-bit freq

              // DEBUG optionnel
              // Serial.printf("SG=%d, S=%d, A=%d, D5=%d, F3=%d\n",
              //               serial_group_number, is_start, addr, duty5, freq3);

              sendCommand(serial_group_number, addr, is_start, duty5, freq3);
          }
      } else {
          unsigned long timestamp = millis();
          Serial.print("Timestamp: ");
          Serial.print(timestamp);
          Serial.print(" ms, Data = ");
          Serial.print(value.length());
          Serial.print(", WRONG LENGTH!!!!!!!!!!!!!!!!");
      }
  }

  /*
   * Protocole ESP → PIC (inchangé côté PIC):
   *  START : 3 octets
   *    - Addr: (addr<<1)|1           // MSB=0, START=1
   *    - Data1: 0x80 | (duty5 & 0x1F)
   *    - Data2: 0x80 | (freq3 & 0x07)
   *  STOP : 1 octet
   *    - Addr: (addr<<1)|0
   */
  void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty5, int freq3) {
      if (serial_group_number < 0 || serial_group_number >= 4) return; // tableau serial_group[4]
      if (is_start == 1) { // START -> 3 octets
        uint8_t message[3];
        message[0] = (uint8_t)((motor_addr << 1) | 0x01);
        message[1] = (uint8_t)(0x80 | (duty5 & 0x1F));
        message[2] = (uint8_t)(0x80 | (freq3 & 0x07));
        serial_group[serial_group_number].write(message, 3);
      } else { // STOP -> 1 octet
        uint8_t message = (uint8_t)((motor_addr << 1) | 0x00);
        serial_group[serial_group_number].write(&message, 1);
      }
  }
};

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer, esp_ble_gatts_cb_param_t *param){
        Serial.println("connected!");
        Serial.println(BLEDevice::toString().c_str());
        char bda_str[18];
        sprintf(bda_str, "%02X:%02X:%02X:%02X:%02X:%02X", param->connect.remote_bda[0], param->connect.remote_bda[1], param->connect.remote_bda[2], param->connect.remote_bda[3], param->connect.remote_bda[4], param->connect.remote_bda[5]);
        Serial.println("Device connected with Address: " + String(bda_str));
        pServer->updateConnParams(param->connect.remote_bda, 0, 0, 0, 100);
        deviceConnected = true;
    }

    void onDisconnect(BLEServer* pServer) {
      Serial.println("disconnected!");
      delay(500);
      deviceConnected = false;
      BLEDevice::startAdvertising();
    }
};

void setup() {
  Serial.begin(500000);
  Serial.print("number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);

  // Soft UART init (on ne change pas la parité pour rester fidèle à ton code)
  for (int i = 0; i < 4; ++i) {
    Serial.print("initialize uart on ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) {
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }

  // LED
  strip.begin();
  strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0, 255, 0));
  strip.show();

  // BLE
  BLEDevice::init("QT Py ESP32-S3");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  BLEDevice::setMTU(128);
  BLEService *pService = pServer->createService(SERVICE_UUID);
  BLECharacteristic *pCharacteristic = pService->createCharacteristic(
                                         CHARACTERISTIC_UUID,
                                         BLECharacteristic::PROPERTY_READ |
                                         BLECharacteristic::PROPERTY_WRITE
                                       );
  pCharacteristic->setValue("0");
  pCharacteristic->setCallbacks(new MyCharacteristicCallbacks());

  pService->start();
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  BLEDevice::startAdvertising();
  Serial.println("Characteristic defined! Now you can read it in your phone!");
}

void loop() {
  // rien, tout est dans les callbacks BLE
}