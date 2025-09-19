#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <SoftwareSerial.h>

Adafruit_NeoPixel strip(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

const int subchain_pins[4] = {18, 17, 9, 8};
const int subchain_num = 4;
uint32_t colors[5];
int color_num = 5;
int global_counter = 0;

EspSoftwareSerial::UART serial_group[4];

void setup() {
  Serial.begin(115200); // USB Serial for communication with PC
  
  Serial.print("number of hardware serial available: ");
  Serial.println(SOC_UART_NUM);
  
  // Initialize UART connections for actuator chains
  for (int i = 0; i < subchain_num; ++i) {
    Serial.print("initialize uart on ");
    Serial.println(subchain_pins[i]);
    serial_group[i].begin(115200, SWSERIAL_8E1, -1, subchain_pins[i], false);
    serial_group[i].enableIntTx(false);
    if (!serial_group[i]) { // If the object did not initialize, then its configuration is invalid
      Serial.println("Invalid EspSoftwareSerial pin configuration, check config");
    }
    delay(200);
  }
  
  Serial.println("Starting Serial communication!");

  //setup LED
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(2, OUTPUT);
  digitalWrite(2, HIGH);
  strip.begin();
  strip.setBrightness(20);
  colors[0] = strip.Color(0, 255, 0);
  strip.setPixelColor(0, colors[0]);
  strip.show();

  Serial.println("Ready to receive commands via USB Serial!");
}

void loop() {
  // Check if data is available on USB Serial
  if (Serial.available() > 0) {
    // Read available data
    int bytesAvailable = Serial.available();
    uint8_t buffer[bytesAvailable];
    
    unsigned long t1 = micros();

    Serial.readBytes(buffer, bytesAvailable);
    // Process the received data
    processSerialData(buffer, bytesAvailable);

    unsigned long t2 = micros();

    Serial.print("Correct received in : ");
    Serial.print(t2 - t1);
    Serial.println("us");

    
    
  }
  
  delay(1); // Small delay to prevent overwhelming the processor
}

void processSerialData(uint8_t* data, int length) {
  if (length % 3 == 0) {  // Ensure the length is a multiple of 3 bytes
    unsigned long timestamp = millis(); // Get current time in milliseconds

    for (int i = 0; i < length; i += 3) {
      uint8_t byte1 = data[i];
      uint8_t byte2 = data[i+1];
      uint8_t byte3 = data[i+2];

      if (byte1 == 0xFF) continue; // Skip if the first byte of the command is 0xFF

      int serial_group_number = (byte1 >> 2) & 0x0F;
      int is_start = byte1 & 0x01;
      int addr = byte2 & 0x3F;
      int duty = (byte3 >> 3) & 0x0F;
      int freq = (byte3 >> 1) & 0x03;
      int wave = byte3 & 0x01;

      
      sendCommand(serial_group_number, addr, is_start, duty, freq, wave);
    }
  }
  else{
    unsigned long timestamp = millis(); // Get current time in milliseconds
    Serial.print("ERROR");
  }
}

/* command format
    command = {
        'addr':motor_addr,
        'mode':start_or_stop,
        'duty':3, # default
        'freq':2, # default
        'wave':0, # default
    }
*/
void sendCommand(int serial_group_number, int motor_addr, int is_start, int duty, int freq, int wave) {
  if (is_start == 1) { // Start command, two bytes
    uint8_t message[2];
    message[0] = (motor_addr << 1) | is_start;
    message[1] = 0x80 | (duty << 3) | (freq << 1) | wave;
    serial_group[serial_group_number].write(message, 2);
  } else { // Stop command, only one byte
    uint8_t message = (motor_addr << 1) | is_start;
    serial_group[serial_group_number].write(&message, 1);
  }
}