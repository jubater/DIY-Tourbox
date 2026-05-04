## DIY Tourbox 

This project's target was to build a device like tourbox mainly focused for drawing , but all its features makes it a customizable, one-handed editing controlle. It replicates what TourBox and other macro software does.

## About

Unlike many macro pads that emulate a HID (Human Interface Device) keyboard directly on the chip, **NotTourBox** uses a Raw Data (i dnt know what its called) approach:

 The Arduino  Acts as a raw input sensor. It constantly monitors the buttons and encoders. When an action occurs, it sends a simple string to the PC.
 The application listens to the Serial stream and Identifies which application is currently in focus, Looks up the assigned macro for that specific button and app, Simulates the keystrokes or mouse actions using the `pynput` library.

 Why this approach?
* did this because I dont have to re-flash the Arduino code every time to change a shortcut.
* there is App Awareness so the console knows whether Photoshop, Blender, or Premiere Pro, and changes its behavior automatically.

## Features
* **Auto-Switching Profiles:** Automatically detects the active window (e.g., Photoshop) and swaps hardware mapping instantly.
* **Layered Logic:** Supports up to 3 modifier layers (Mod 1, 2, 3), You will understand when you use it. 
* **Custom Shortcut:** Create custom multi-key macros,
* **Hardware Support:** Logic for 12 buttons and 3 rotary encoders with click support. Right now only 9 button can be used because of limited pinout, In future I will use a matrix to increase buttons. 
* **System Tray Integration:** Runs silently in the background.



### Components Used:
* **Microcontroller:** Ardunoi Leonardo
* **Buttons:** 12x  Buttons 
* **Encoders:** 3x Rotary Encoders (with built-in push switches)


###  Pin Mapping

the pins are mapped as follows:

| Component | Pin Type | Arduino Pins | Function |
| :--- | :--- | :--- | :--- |
| **Buttons 1-9** | Digital & Analog input | D[11] - D[13], A[0] - A[5]| Macro Triggers (B1-B9) |
| **Encoder 1** | Interrupt/Digital | D[2], D[3] | Scroll/Value Adjust (E1) |
| **Encoder 2** | Interrupt/Digital | D[4], D[5] | Scroll/Value Adjust (E2) |
| **Encoder 3** | Interrupt/Digital | D[6], D[7] | Scroll/Value Adjust (E3) |
| **Encoder Clicks**| Digital Input | D[8], D[9], D[10]| Center Clicks (E1C, E2C, E3C) |



### Instructions ###
1. **Wiring:** Connect one side of each button/encoder pin to the specified Arduino Pin and the other side to GND .
2. **Firmware:** Open `firmware/pro_console/pro_console.ino` in the Arduino IDE.
3. **Upload:** Select your board and port, then click **Upload**.
4. **Integration:** Once uploaded, the Python Dashboard will automatically recognize the inputs when the COM port is connected.