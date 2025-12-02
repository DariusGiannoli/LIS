#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>
#include <string.h>

#define UART_BAUD     115200
#define RXBUF_SIZE    256
#define MIN_IFG_US    120

// 4-byte protocol: [W G M][A][duty%][freq]

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

// FIXED: Forward the complete 4-byte command to PIC as-is
static inline void forwardToPIC(int group, const uint8_t* cmd){
  if (group < 0 || group >= subchain_num) return;
  guard_ifg(group);
  serial_group[group].write(cmd, 4);  // Send all 4 bytes
  serial_group[group].flush();
}

static inline void processFrame4(const uint8_t* f){
  // b1: [W][0][G3..G0][M1..M0]
  // b2: [0][0][A5..A0]
  // b3: [0][D6..D0]  duty% 0-100 (7 bits)
  // b4: [0][0][0][0][0][F2..F0]
  const uint8_t b1=f[0], b2=f[1], b3=f[2], b4=f[3];
  if (b1==0xFF && b2==0xFF && b3==0xFF && b4==0xFF) return; // padding
  
  const int group = (b1 >> 2) & 0x0F;
  
  // Simply forward the entire 4-byte command to the PIC
  forwardToPIC(group, f);
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
  Serial.println("Ready (4-byte proto: duty 0-100%).");
}

void loop(){
  while (Serial.available()){
    if (rxLen < RXBUF_SIZE) rxBuf[rxLen++] = (uint8_t)Serial.read();
    else (void)Serial.read();
  }
  while (rxLen >= 4){
    processFrame4(rxBuf);
    memmove(rxBuf, rxBuf+4, rxLen-4);
    rxLen -= 4;
  }
  delay(1);
}
