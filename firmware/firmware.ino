#include <Encoder.h>

// ENCODER SETUP 
// Connect CLK and DT to these pins
Encoder enc1(2, 3);
Encoder enc2(4, 5);
Encoder enc3(6, 7);

long oldPos1 = 0;
long oldPos2 = 0;
long oldPos3 = 0;

//BUTTON SETUP 
const int NUM_BUTTONS = 13;
// Pins used: 8, 9, 10, 11, 12, 13 and A0, A1, A2, A3, A4, A5 
int buttonPins[NUM_BUTTONS] = {8, 9, 10, 11, 12, 13, A1, A2, A3, A0, 12, A4, A5}; 
String buttonNames[NUM_BUTTONS] = {"E1C", "E2C", "E3C", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10"};





int actualButtonState[NUM_BUTTONS]; 
int lastReading[NUM_BUTTONS];       
unsigned long lastDebounceTime[NUM_BUTTONS];
int debounceDelay = 25; 

void setup() {
  Serial.begin(115200); 

  for (int i = 0; i < NUM_BUTTONS; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
    actualButtonState[i] = HIGH; 
    lastReading[i] = HIGH;       
    lastDebounceTime[i] = 0;
  }
}

void loop() {
  long newPos1 = enc1.read();
  if (newPos1 >= oldPos1 + 4) { Serial.println("E1R"); oldPos1 = newPos1; } 
  else if (newPos1 <= oldPos1 - 4) { Serial.println("E1L"); oldPos1 = newPos1; }

  long newPos2 = enc2.read();
  if (newPos2 >= oldPos2 + 4) { Serial.println("E2R"); oldPos2 = newPos2; } 
  else if (newPos2 <= oldPos2 - 4) { Serial.println("E2L"); oldPos2 = newPos2; }

  long newPos3 = enc3.read();
  if (newPos3 >= oldPos3 + 4) { Serial.println("E3R"); oldPos3 = newPos3; } 
  else if (newPos3 <= oldPos3 - 4) { Serial.println("E3L"); oldPos3 = newPos3; }

  for (int i = 0; i < NUM_BUTTONS; i++) {
    int reading = digitalRead(buttonPins[i]);

    if (reading != lastReading[i]) {
      lastDebounceTime[i] = millis();
    }

    if ((millis() - lastDebounceTime[i]) > debounceDelay) {
      if (reading != actualButtonState[i]) {
        actualButtonState[i] = reading;
        if (actualButtonState[i] == LOW) {
          Serial.print(buttonNames[i]); Serial.println("_DOWN");
        } else {
          Serial.print(buttonNames[i]); Serial.println("_UP");
        }
      }
    }
    lastReading[i] = reading; 
  }
}