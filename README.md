## Not Tourbox 

**Not Tourbox** is a Python application designed to interface with custom Arduino-based macro pads and controllers. It replicates what TourBox and other macro software does.

## Features
* **Auto-Switching Profiles:** Automatically detects the active window (e.g., Photoshop) and swaps hardware mapping instantly.
* **Layered Logic:** Supports up to 3 modifier layers (Mod 1, 2, 3), You will understand when you use it. 
* **Custom Shortcut Engine:** Create custom multi-key macros,
* **Hardware Support:** Built-in logic for 12 buttons and 3 rotary encoders with click support.
* **System Tray Integration:** Runs silently in the background while you work.

##
* **GUI:** `CustomTkinter` 
* **Input Handling:** `pynput`
* **Communication:** `pyserial`
* **OS Integration:** `pywin32`, `psutil`

### Components Used:
* **Microcontroller:** Arduino [Model Name]
* **Buttons:** 12x Momentary Push Buttons (Tactile switches)
* **Encoders:** 3x Rotary Encoders (with built-in push switches)


### 📍 Pin Mapping

To ensure high performance and avoid ghosting, the pins are mapped as follows:

| Component | Pin Type | Arduino Pins | Function |
| :--- | :--- | :--- | :--- |
| **Buttons 1-12** | Digital Input | D[X] - D[X] | Macro Triggers (B1-B12) |
| **Encoder 1** | Interrupt/Digital | D[X], D[X] | Scroll/Value Adjust (E1) |
| **Encoder 2** | Interrupt/Digital | D[X], D[X] | Scroll/Value Adjust (E2) |
| **Encoder 3** | Interrupt/Digital | D[X], D[X] | Scroll/Value Adjust (E3) |
| **Encoder Clicks**| Digital Input | D[X], D[X], D[X]| Center Clicks (E1C, E2C, E3C) |

*Note: All inputs utilize internal `INPUT_PULLUP` resistors. Wiring should connect the pin to Ground (GND) when the switch is closed.*

### 🛠️ Assembly Instructions
1. **Wiring:** Connect one side of each button/encoder pin to the specified Arduino Digital Pin and the other side to a common Ground (GND) rail.
2. **Firmware:** Open `firmware/pro_console/pro_console.ino` in the Arduino IDE.
3. **Upload:** Select your board and port, then click **Upload**.
4. **Integration:** Once uploaded, the Python Dashboard will automatically recognize the inputs when the COM port is connected.