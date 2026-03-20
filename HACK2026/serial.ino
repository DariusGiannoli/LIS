#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>
#include <string.h>

#define UART_BAUD     115200
#define RXBUF_SIZE    256
#define MIN_IFG_US    120
#define INTER_STOP_US 150
#define STOP_RETRIES  2

// modes
#define MODE_STOP     0b00
#define MODE_START    0b01
#define MODE_SOFTSTOP 0b10

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
const int subchain_pins[4] = {18,17,9,8};
const int subchain_num = 4;
EspSoftwareSerial::UART serial_group[4];

static uint8_t  rxBuf[RXBUF_SIZE];
static size_t   rxLen = 0;
static uint32_t last_tx_us[4] = {0,0,0,0};

static inline void guard_ifg(int group){
  if (group < 0 || group >= subchain_num) return;
  uint32_t now = micros(), dt = now - last_tx_us[group];
  if ((int32_t)dt < (int32_t)MIN_IFG_US) delayMicroseconds(MIN_IFG_US - dt);
  last_tx_us[group] = micros();
}

static inline void sendStopPIC(int group, int addr6){
  if (group < 0 || group >= subchain_num) return;
  uint8_t b = (uint8_t)(((addr6 & 0x3F) << 1) | 0x00);
  for (int k=0;k<STOP_RETRIES;++k){
    guard_ifg(group);
    serial_group[group].write(&b,1);
    serial_group[group].flush();
    delayMicroseconds(INTER_STOP_US);
  }
}

static inline void sendStartPIC(int group, int addr6, uint8_t duty5, uint8_t freq3, uint8_t wave){
  if (group < 0 || group >= subchain_num) return;
  uint8_t msg[3];
  msg[0] = (uint8_t)(((addr6 & 0x3F) << 1) | 0x01);                 // addr byte (MSB=0)
  msg[1] = (uint8_t)(0x80 | (duty5 & 0x1F));                        // data1 (MSB=1)
  msg[2] = (uint8_t)(0x80 | ((wave & 0x01) << 3) | (freq3 & 0x07)); // data2 (MSB=1)
  guard_ifg(group);
  serial_group[group].write(msg,3);
  serial_group[group].flush();
}

static inline void processFrame3(const uint8_t* f){
  // b1: [W][0][G3..G0][M1..M0]
  // b2: [0][0][A5..A0]
  // b3: [D4..D0][F2..F0]
  const uint8_t b1=f[0], b2=f[1], b3=f[2];
  if (b1==0xFF && b2==0xFF && b3==0xFF) return; // padding
  const uint8_t wave = (b1 >> 7) & 0x01;
  const uint8_t mode =  b1       & 0x03;
  const int group    = (b1 >> 2) & 0x0F;
  const int addr6    =  b2       & 0x3F;
  const uint8_t duty5= (b3 >> 3) & 0x1F;
  const uint8_t freq3=  b3       & 0x07;

  if (mode == MODE_STOP || mode == MODE_SOFTSTOP) sendStopPIC(group, addr6);
  else                                            sendStartPIC(group, addr6, duty5, freq3, wave);
}

void setup(){
  Serial.begin(UART_BAUD);
  for (int i=0;i<subchain_num;++i){
    serial_group[i].begin(UART_BAUD, SWSERIAL_8N1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(true);
    delay(30);
  }
  strip.begin(); strip.setBrightness(20);
  strip.setPixelColor(0, strip.Color(0,255,0)); strip.show();
  Serial.println("Ready (3-byte proto).");
}

void loop(){
  while (Serial.available()){
    if (rxLen < RXBUF_SIZE) rxBuf[rxLen++] = (uint8_t)Serial.read();
    else (void)Serial.read();
  }
  while (rxLen >= 3){
    processFrame3(rxBuf);
    memmove(rxBuf, rxBuf+3, rxLen-3);
    rxLen -= 3;
  }
  delay(1);
}