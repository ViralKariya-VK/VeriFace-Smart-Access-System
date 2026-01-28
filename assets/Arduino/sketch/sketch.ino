char inputBuffer[20];           // Buffer to store incoming command
int devicePin = 13;             // Change this if using another pin

void setup() {
  pinMode(devicePin, OUTPUT);   // Set pin as output
  Serial.begin(9600);           // Match the Python baudrate
  while (!Serial) {
    ; // Wait for Serial to initialize on some boards (e.g., Leonardo)
  }
  Serial.println("Arduino Ready");  // Optional: startup message
}

void loop() {
  if (Serial.available()) {
    int len = Serial.readBytesUntil('\n', inputBuffer, sizeof(inputBuffer) - 1);
    inputBuffer[len] = '\0';    // Null-terminate the input

    String command = String(inputBuffer);
    command.trim();             // Remove trailing \r or whitespace

    if (command.equalsIgnoreCase("OPEN")) {
      digitalWrite(devicePin, HIGH);
      Serial.println("Device is ON");  // Optional: feedback
    } else if (command.equalsIgnoreCase("CLOSE")) {
      digitalWrite(devicePin, LOW);
      Serial.println("Device is OFF"); // Optional: feedback
    } else if (command.equalsIgnoreCase("STATUS")){
      int pinState = digitalRead(devicePin);
      if(pinState == HIGH){
        Serial.println("ON");
      }else{
        Serial.println("OFF");
      }
    } else{
      Serial.println("Unknown command"); // Optional: help with debugging
    }
  }
}
