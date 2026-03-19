/*
 * VeriFace Smart Door — Arduino Sketch
 * Controls a relay on Pin 13 via serial commands from Django
 * 
 * Commands:
 *   OPEN   → sets Pin 13 HIGH → relay energizes → door unlocks
 *   CLOSE  → sets Pin 13 LOW  → relay de-energizes → door locks
 *   STATUS → returns current pin state (ON/OFF)
 * 
 * Baudrate: 9600
 */

char inputBuffer[20];
int devicePin = 13;

void setup() {
  pinMode(devicePin, OUTPUT);
  digitalWrite(devicePin, LOW); // Start locked
  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial on Leonardo/Micro
  }
  Serial.println("VeriFace Arduino Ready");
}

void loop() {
  if (Serial.available()) {
    int len = Serial.readBytesUntil('\n', inputBuffer, sizeof(inputBuffer) - 1);
    inputBuffer[len] = '\0';

    String command = String(inputBuffer);
    command.trim();

    if (command.equalsIgnoreCase("OPEN")) {
      digitalWrite(devicePin, HIGH);
      Serial.println("Device is ON");

    } else if (command.equalsIgnoreCase("CLOSE")) {
      digitalWrite(devicePin, LOW);
      Serial.println("Device is OFF");

    } else if (command.equalsIgnoreCase("STATUS")) {
      int pinState = digitalRead(devicePin);
      if (pinState == HIGH) {
        Serial.println("ON");
      } else {
        Serial.println("OFF");
      }

    } else {
      Serial.println("Unknown command");
    }
  }
}