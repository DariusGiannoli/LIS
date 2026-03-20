#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
}

void loop() {
  Serial.print("MAC: ");
  Serial.println(WiFi.macAddress());
  delay(2000);
}
