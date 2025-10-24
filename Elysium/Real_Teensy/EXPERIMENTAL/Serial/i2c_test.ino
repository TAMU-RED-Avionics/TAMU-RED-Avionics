#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

// Thermocouple libraries
// See example https://github.com/adafruit/Adafruit_MCP9600/blob/master/examples/mcp9600_test/mcp9600_test.ino
#include <Wire.h>
#include <Adafruit_I2CDevice.h>
#include <Adafruit_I2CRegister.h>
#include <Adafruit_MCP9600.h>


/*
-------------------------------------------------------------------
  This Teensy code is meant to be the initial checkout test of the 
  Sensor Test PCB V5
-------------------------------------------------------------------
*/

//                       USER INPUT SETTINGS
// ----------------------------------------------------------------

// Ethernet & Comms
IPAddress REMOTE(192, 168, 1, 175);                       // The IP Address of the master computer we are connecting to 
IPAddress LOCAL(192, 168, 1, 174);                        // The IP Address of this microcontroller on the master's network
const int BAUD = 115200;                                  // Serial BAUD rate (bits/second)
unsigned int PORT = 8888;                                 // The port to bind to (assumed to be identical to the GUI running on the master)

// Timing Intervals
const int unsigned SYSTEM_LOOP_INTERVAL = 1;              // The loop delay of the overall system - configures the NOOP TX Rate (millisec)
const long unsigned ABORTED_MSG_INTERVAL = 500 * 1000;    // Interval for printing "aborted" when in an abort state (microsec)
const long unsigned SENSOR_UPDATE_INTERVAL = 100 * 1000;  // Interval for sending sensor data (microsec)

const long unsigned NOOP_TX_INTERVAL = 10 * 1000;          // Minimum time to wait in between sending NOOP heartbeats (microsec)
const long unsigned NOOP_RX_TIMEOUT =  100 * 1000;         // Timeout to consider a lack of a NOOP packet coming in as a miss (microsec)


// Valves
const int NCS1_PIN = 0;
const int NCS2_PIN = 0;
const int NCS3_PIN = 0;
const int NCS5_PIN = 0;
const int NCS6_PIN = 0;
const int LABV1_PIN = 0;
const int GV1_PIN = 0;
const int GV2_PIN = 0;

// Igniter
const int IGN1_PIN = 0;
const int IGN2_PIN = 0;

// Thermocouple I2C addresses
#define TC1_I2C_ADDR (0x60)   // 1100 000x  Corresponding to MCP9600 Address 0 (Vaddr = GND)
#define TC2_I2C_ADDR (0x67)   // 1100 111x  Corresponding to MCP9600 Address 7 (Vaddr = VDD = 3V3)

// Thermocouple mcp identifier
Adafruit_MCP9600 mcp1;
Adafruit_MCP9600 mcp2;

// ----------------------------------------------------------------

/*
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
  // Initialize serial for debugging
  Serial.begin(BAUD);
  Serial.println("Initialized Serial");

  /*
  -----------------------
  THERMOCOUPLE SET UP
  -----------------------
  */

  // Initialize MCP9600 sensors
  if (!mcp1.begin(TC1_I2C_ADDR)) {
    Serial.println("TC1 ADC not found!");
    while (1);
  }

  if (!mcp2.begin(TC2_I2C_ADDR)) {
    Serial.println("TC2 ADC not found!");
    while (1);
  }

  Serial.println("Found both TC1 and TC2 ADC!");

  // Configure both sensors
  // 18 bit resolution, which is the highest and has up to 300ms conversion time
  mcp1.setADCresolution(MCP9600_ADCRESOLUTION_18);
  // 0.0625C As the resolution (step size) of cold junction temperature - based on MCP9600 datasheet
  mcp1.setAmbientResolution(RES_ZERO_POINT_0625);
  //Type K - Nickel-Chromium and Nickel-Aluminum TCs operating from -200C to 1372C according to Grok
  mcp1.setThermocoupleType(MCP9600_TYPE_K);  
  // Filter coeff ranges from 0 to 15, where 0 is all data being raw and 15 is heavy averaging of all the data (minimal noise) 
  mcp1.setFilterCoefficient(3);
  mcp1.enable(true);

  mcp2.setADCresolution(MCP9600_ADCRESOLUTION_18);
  mcp2.setAmbientResolution(RES_ZERO_POINT_0625);
  mcp2.setThermocoupleType(MCP9600_TYPE_K);
  mcp2.setFilterCoefficient(3);
  mcp2.enable(true);
  
  Serial.println("Finished Setup");
} // setup


/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  Serial.write("Looping");

  Serial.print("TC1 Hot Junction: "); Serial.println(mcp1.readThermocouple());
  Serial.print("TC1 Cold Junction: "); Serial.println(mcp1.readAmbient());
  Serial.print("TC1 ADC: "); Serial.print(mcp1.readADC() * 2); Serial.println(" uV");

  Serial.print("TC2 Hot Junction: "); Serial.println(mcp2.readThermocouple());
  Serial.print("TC2 Cold Junction: "); Serial.println(mcp2.readAmbient());
  Serial.print("TC2 ADC: "); Serial.print(mcp2.readADC() * 2); Serial.println(" uV");
  delay(1000);

} // loop