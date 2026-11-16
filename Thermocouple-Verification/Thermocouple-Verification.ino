/*
 * Thermocouple-Verification
 * -------------------------
 * Reads a thermocouple through an MCP9600 thermocouple amplifier over I2C on a
 * Teensy 4.1 and prints one reading per second to the USB serial port.
 *
 * Wiring (Teensy 4.1 default I2C bus, "Wire"):
 *   Teensy 3.3V  -> MCP9600 VIN / VDD
 *   Teensy GND   -> MCP9600 GND
 *   Teensy 18    -> MCP9600 SDA
 *   Teensy 19    -> MCP9600 SCL
 *
 * Required library: "Adafruit MCP9600" (plus its dependency "Adafruit BusIO").
 *
 * See README.md in this folder for full usage instructions.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MCP9600.h>

// ----------------------------- Configuration --------------------------------

#define SERIAL_BAUD        115200                     // ignored by Teensy USB serial, kept for other boards
#define MCP9600_I2C_ADDR   0x67                       // 0x60-0x67, set by the ADDR pin / jumpers
#define I2C_CLOCK_HZ       100000                     // MCP9600 supports up to 100 kHz
#define TC_TYPE            MCP9600_TYPE_K             // thermocouple type plugged into the MCP9600
#define ADC_RESOLUTION     MCP9600_ADCRESOLUTION_18   // 18-bit: best resolution, ~320 ms per conversion
#define FILTER_COEFF       0                          // 0 (off) to 7 (heaviest) on-chip IIR filter

const uint32_t POLL_INTERVAL_MS  = 1000;   // how often a reading is logged
const uint32_t RETRY_INTERVAL_MS = 2000;   // how often to retry if the sensor is missing
const uint32_t SERIAL_WAIT_MS    = 3000;   // max time to wait for the serial monitor at boot

// ------------------------------- Globals ------------------------------------

Adafruit_MCP9600 mcp;

bool     sensorReady  = false;   // true once the MCP9600 has been found and configured
uint32_t lastPollMs   = 0;       // millis() timestamp of the last logged reading
uint32_t lastRetryMs  = 0;       // millis() timestamp of the last reconnect attempt

// ------------------------------ Functions -----------------------------------

// Returns true if a device acknowledges at the MCP9600's I2C address.
bool sensorPresent() {
  Wire.beginTransmission(MCP9600_I2C_ADDR);
  return Wire.endTransmission() == 0;
}

// Finds the MCP9600 on the bus and applies the configuration above.
// Returns true on success.
bool initSensor() {
  if (!mcp.begin(MCP9600_I2C_ADDR, &Wire)) {
    return false;
  }

  mcp.setADCresolution(ADC_RESOLUTION);
  mcp.setThermocoupleType(TC_TYPE);
  mcp.setFilterCoefficient(FILTER_COEFF);
  mcp.enable(true);

  // Let the first conversion with the new settings finish before it is read.
  delay(400);
  return true;
}

// Reads the sensor once and prints a single CSV log line.
void logReading(uint32_t nowMs) {
  float hotJunctionC  = mcp.readThermocouple();   // temperature at the thermocouple tip
  float coldJunctionC = mcp.readAmbient();        // temperature of the MCP9600 chip itself
  float hotJunctionF  = hotJunctionC * 9.0f / 5.0f + 32.0f;

  Serial.print(nowMs);
  Serial.print(',');
  Serial.print(hotJunctionC, 2);
  Serial.print(',');
  Serial.print(hotJunctionF, 2);
  Serial.print(',');
  Serial.println(coldJunctionC, 2);
}

void printHeader() {
  Serial.println("time_ms,thermocouple_C,thermocouple_F,ambient_C");
}

// --------------------------------- Setup ------------------------------------

void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial && millis() < SERIAL_WAIT_MS) {
    // Wait briefly for the serial monitor so the boot messages are not lost,
    // but do not hang forever if the board is running without a PC attached.
  }

  Serial.println("# Thermocouple-Verification: Teensy 4.1 + MCP9600");

  Wire.begin();
  Wire.setClock(I2C_CLOCK_HZ);

  sensorReady = initSensor();
  if (sensorReady) {
    Serial.print("# MCP9600 found at 0x");
    Serial.println(MCP9600_I2C_ADDR, HEX);
    printHeader();
  } else {
    Serial.print("# ERROR: no MCP9600 at 0x");
    Serial.print(MCP9600_I2C_ADDR, HEX);
    Serial.println(" - check wiring and address. Retrying...");
  }

  lastPollMs  = millis();
  lastRetryMs = millis();
}

// --------------------------------- Loop -------------------------------------

void loop() {
  uint32_t nowMs = millis();

  // Sensor missing: keep trying to bring it up instead of logging garbage.
  if (!sensorReady) {
    if (nowMs - lastRetryMs >= RETRY_INTERVAL_MS) {
      lastRetryMs = nowMs;
      sensorReady = initSensor();
      if (sensorReady) {
        Serial.println("# MCP9600 connected");
        printHeader();
        lastPollMs = millis();
      } else {
        Serial.println("# ERROR: MCP9600 not responding, retrying...");
      }
    }
    return;
  }

  // Sensor healthy: log one reading every POLL_INTERVAL_MS.
  if (nowMs - lastPollMs >= POLL_INTERVAL_MS) {
    lastPollMs += POLL_INTERVAL_MS;   // advance by a fixed step so the period does not drift

    if (!sensorPresent()) {
      Serial.println("# ERROR: lost communication with MCP9600");
      sensorReady = false;
      lastRetryMs = nowMs;
      return;
    }

    logReading(nowMs);
  }
}
