
void setup() {
  Serial.begin(115200);
}

void loop() {

  if (Serial.available()) {
    while (Serial.available()) {
      Serial.write(Serial.read());
    }
  }
}