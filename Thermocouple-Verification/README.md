# Thermocouple-Verification

Firmware for a **Teensy 4.1** that reads a thermocouple through an **MCP9600** thermocouple amplifier over **I2C** and logs one reading per second to the USB serial port.

## Table of Contents

- [What It Does](#what-it-does)
- [Hardware Required](#hardware-required)
- [Wiring](#wiring)
- [Software Setup](#software-setup)
- [Uploading the Firmware](#uploading-the-firmware)
- [Viewing the Serial Log](#viewing-the-serial-log)
- [Serial Output Format](#serial-output-format)
- [Configuration](#configuration)
- [Code Explanation](#code-explanation)
  - [Includes and Configuration](#includes-and-configuration)
  - [Globals](#globals)
  - [`sensorPresent()`](#sensorpresent)
  - [`initSensor()`](#initsensor)
  - [`logReading()`](#logreading)
  - [`setup()`](#setup)
  - [`loop()`](#loop)
- [Troubleshooting](#troubleshooting)

## What It Does

1. On power-up, the Teensy starts USB serial and the I2C bus.
2. It looks for an MCP9600 at I2C address `0x67` and configures it (type K thermocouple, 18-bit ADC resolution).
3. Once per second it reads:
   - the **thermocouple (hot junction)** temperature, which is the temperature at the tip of the probe, and
   - the **ambient (cold junction)** temperature, which is the temperature of the MCP9600 chip itself.
4. It prints each reading as one comma-separated line on the serial port.
5. If the MCP9600 is missing or gets unplugged, it prints an error and keeps retrying every 2 seconds until the sensor comes back, then resumes logging on its own.

The MCP9600 does the thermocouple math internally (cold-junction compensation and linearization), so the Teensy receives a finished temperature in degrees Celsius.

## Hardware Required

- Teensy 4.1
- MCP9600 breakout board (for example, the Adafruit MCP9600)
- Type K thermocouple (other types work if you change `TC_TYPE`, see [Configuration](#configuration))
- Micro-USB cable
- Jumper wires

## Wiring

The sketch uses the Teensy 4.1's default I2C bus (`Wire`).

| Teensy 4.1 pin | MCP9600 pin | Purpose      |
| -------------- | ----------- | ------------ |
| 3.3V           | VIN / VDD   | Power        |
| GND            | GND         | Ground       |
| 18 (SDA)       | SDA         | I2C data     |
| 19 (SCL)       | SCL         | I2C clock    |

Notes:

- Connect the thermocouple to the MCP9600 screw terminals and match the polarity marked on the board. A reversed thermocouple reads a temperature that goes *down* when the probe is heated.
- I2C needs pull-up resistors on SDA and SCL. Most breakout boards (including Adafruit's) already have them. A bare MCP9600 chip needs external pull-ups (about 4.7 kΩ to 3.3V).
- Power the board from **3.3V**, not 5V. Teensy 4.1 pins are not 5V tolerant.
- The I2C address is set by the ADDR pin or jumper on the board. The Adafruit board defaults to `0x67`.

## Software Setup

1. Install the [Arduino IDE](https://www.arduino.cc/en/software).
2. Install Teensy support:
   - In the Arduino IDE, open **File > Preferences** and add `https://www.pjrc.com/teensy/package_teensy_index.json` to **Additional boards manager URLs**.
   - Open **Tools > Board > Boards Manager**, search for **Teensy**, and install it.
3. Install the sensor library:
   - Open **Tools > Manage Libraries**, search for **Adafruit MCP9600**, and install it.
   - When asked, choose **Install All** so the **Adafruit BusIO** dependency is installed too.

## Uploading the Firmware

1. Open `Thermocouple-Verification.ino` in the Arduino IDE.
2. Select **Tools > Board > Teensy > Teensy 4.1**.
3. Select **Tools > USB Type > Serial**.
4. Plug in the Teensy and select it under **Tools > Port**.
5. Click **Upload**. If the upload does not start, press the button on the Teensy once.

## Viewing the Serial Log

1. Open **Tools > Serial Monitor** (or the Serial Plotter for a live graph).
2. Any baud rate works, because the Teensy uses native USB serial. `115200` is the value set in the code.
3. A new line appears every second.

Any other serial terminal (PuTTY, `screen`, a Python script using `pyserial`) works as well. Because the output is CSV, you can save it to a `.csv` file and open it directly in Excel or pandas.

## Serial Output Format

Example output:

```
# Thermocouple-Verification: Teensy 4.1 + MCP9600
# MCP9600 found at 0x67
time_ms,thermocouple_C,thermocouple_F,ambient_C
1400,23.56,74.41,24.12
2400,23.62,74.52,24.12
3400,23.56,74.41,24.19
```

| Column           | Meaning                                                    |
| ---------------- | ---------------------------------------------------------- |
| `time_ms`        | Milliseconds since the Teensy powered up                   |
| `thermocouple_C` | Thermocouple (hot junction) temperature in °C              |
| `thermocouple_F` | The same temperature converted to °F                       |
| `ambient_C`      | MCP9600 chip (cold junction) temperature in °C             |

Lines that begin with `#` are status or error messages, not data. A logging script can skip them by ignoring any line that starts with `#`.

## Configuration

All settings are at the top of `Thermocouple-Verification.ino`.

| Setting             | Default                     | What it controls                                                                 |
| ------------------- | --------------------------- | -------------------------------------------------------------------------------- |
| `MCP9600_I2C_ADDR`  | `0x67`                      | I2C address of the MCP9600 (`0x60` to `0x67`)                                    |
| `I2C_CLOCK_HZ`      | `100000`                    | I2C bus speed. The MCP9600 supports up to 100 kHz                                |
| `TC_TYPE`           | `MCP9600_TYPE_K`            | Thermocouple type: `K`, `J`, `T`, `N`, `S`, `E`, `B`, or `R`                     |
| `ADC_RESOLUTION`    | `MCP9600_ADCRESOLUTION_18`  | ADC resolution: `18`, `16`, `14`, or `12` bit. Lower is faster but coarser       |
| `FILTER_COEFF`      | `0`                         | On-chip smoothing filter, `0` (off) to `7` (heaviest)                            |
| `POLL_INTERVAL_MS`  | `1000`                      | Time between logged readings, in milliseconds                                    |
| `RETRY_INTERVAL_MS` | `2000`                      | Time between reconnect attempts when the sensor is missing                       |
| `SERIAL_WAIT_MS`    | `3000`                      | How long to wait at boot for a serial monitor before starting anyway             |

An 18-bit conversion takes about 320 ms. If you lower `POLL_INTERVAL_MS` below that, pick a lower `ADC_RESOLUTION` too, or consecutive lines will repeat the same reading.

## Code Explanation

### Includes and Configuration

```cpp
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MCP9600.h>
```

- `Wire.h` is the Arduino I2C library. On the Teensy 4.1, `Wire` is the bus on pins 18 (SDA) and 19 (SCL).
- `Adafruit_MCP9600.h` is the driver that knows the MCP9600's registers, so the sketch can ask for a temperature without handling raw I2C bytes.

The `#define` and `const` values below the includes are the settings listed in [Configuration](#configuration).

### Globals

```cpp
Adafruit_MCP9600 mcp;
bool     sensorReady  = false;
uint32_t lastPollMs   = 0;
uint32_t lastRetryMs  = 0;
```

- `mcp` is the driver object that represents the sensor.
- `sensorReady` records whether the sensor is currently found and configured. The main loop uses it to decide between logging and reconnecting.
- `lastPollMs` and `lastRetryMs` hold timestamps used for the 1-second logging timer and the 2-second reconnect timer.

### `sensorPresent()`

```cpp
bool sensorPresent() {
  Wire.beginTransmission(MCP9600_I2C_ADDR);
  return Wire.endTransmission() == 0;
}
```

Sends an empty I2C message to the sensor's address. `endTransmission()` returns `0` only when a device acknowledges. This is a quick check that the sensor is still on the bus, and it runs before every reading so an unplugged sensor is reported instead of logged as bad data.

### `initSensor()`

Calls `mcp.begin()` to find the MCP9600 at the configured address, then applies the settings:

- `setADCresolution()` sets how finely the thermocouple voltage is measured.
- `setThermocoupleType()` tells the chip which voltage-to-temperature curve to use. This must match the thermocouple that is plugged in.
- `setFilterCoefficient()` sets the on-chip smoothing filter.
- `enable(true)` takes the chip out of sleep mode.

It then waits 400 ms so the first conversion made with the new settings is finished before anything reads it. It returns `true` if the sensor was found and `false` if not.

### `logReading()`

```cpp
float hotJunctionC  = mcp.readThermocouple();
float coldJunctionC = mcp.readAmbient();
float hotJunctionF  = hotJunctionC * 9.0f / 5.0f + 32.0f;
```

Reads the two temperatures from the sensor, converts the thermocouple temperature to Fahrenheit, and prints one CSV line: timestamp, °C, °F, ambient °C. Each temperature is printed with two decimal places.

### `setup()`

Runs once at power-up:

1. Starts USB serial and waits up to 3 seconds for a serial monitor to connect. The timeout means the board still runs when no PC is attached.
2. Starts the I2C bus at 100 kHz.
3. Calls `initSensor()`. On success it prints the address and the CSV header. On failure it prints an error, and `loop()` takes over the retrying.

### `loop()`

Runs continuously and never blocks, so it uses `millis()` timestamps instead of `delay()`.

**If the sensor is not ready**, it calls `initSensor()` again every `RETRY_INTERVAL_MS` and prints either a "connected" message with a fresh header or another error.

**If the sensor is ready**, it checks whether `POLL_INTERVAL_MS` has passed since the last reading:

```cpp
if (nowMs - lastPollMs >= POLL_INTERVAL_MS) {
  lastPollMs += POLL_INTERVAL_MS;
  ...
}
```

- The subtraction `nowMs - lastPollMs` keeps working correctly when `millis()` rolls over (after about 49 days).
- `lastPollMs` is advanced by exactly one interval rather than set to "now". This keeps readings exactly 1000 ms apart on average, instead of slowly drifting later by the time each reading takes.

It then calls `sensorPresent()`. If the sensor answers, it logs a reading. If not, it prints an error and clears `sensorReady`, which sends the loop back into reconnect mode.

## Troubleshooting

| Symptom                                           | Likely cause and fix                                                                                             |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `# ERROR: no MCP9600 at 0x67`                     | Check power, ground, SDA (18), and SCL (19). Confirm the board's address matches `MCP9600_I2C_ADDR`.              |
| `# ERROR: lost communication with MCP9600`        | A wire came loose while running. Logging resumes automatically once the connection is restored.                  |
| Compile error: `Adafruit_MCP9600.h: No such file` | The Adafruit MCP9600 library is not installed. See [Software Setup](#software-setup).                            |
| Temperature drops when the probe is heated        | The thermocouple leads are reversed. Swap them at the screw terminals.                                           |
| Reading is far off or pinned at an extreme value  | The thermocouple is disconnected or broken, or `TC_TYPE` does not match the thermocouple.                        |
| Nothing appears in the serial monitor             | Check that the right port is selected and that **Tools > USB Type** is set to **Serial**.                        |
| Readings are noisy                                | Raise `FILTER_COEFF` (try `2` to `4`) and keep thermocouple wires away from power and valve wiring.              |
