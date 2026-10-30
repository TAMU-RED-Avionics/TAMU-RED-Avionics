/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

#include <Arduino.h>

// time variables
long unsigned LAST_SENSOR_UPDATE = 0;                     // Timestamp of last sensor reading (microsec)
const long unsigned SENSOR_UPDATE_INTERVAL = 100000;        // sensor update interval (microsec)              <-- USER INPUT

// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT

/*
THERMOCOUPLE SET UP
----------------
*/

// Thermocouple libraries
#include <Wire.h>
#include <Adafruit_I2CDevice.h>
#include <Adafruit_I2CRegister.h>
#include <Adafruit_MCP9600.h>

// Thermocouple I2C addresses
#define I2C_ADDRESS1 (0x67)
//#define I2C_ADDRESS2 (0x66)

// Thermocouple mcp identifier
Adafruit_MCP9600 mcp;
//Adafruit_MCP9600 mcp2;


/*
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
  Serial.begin(BAUD);           // initializes serial communication at set baud rate
  Wire.begin();

  /*
  THERMOCOUPLE SET UP
  -----------------------
  */

  // Initialize MCP9600 sensors
  mcp.begin(I2C_ADDRESS1);
  //mcp2.begin(I2C_ADDRESS2);

  // Configure both sensors
  mcp.setADCresolution(MCP9600_ADCRESOLUTION_18);
  mcp.setThermocoupleType(MCP9600_TYPE_K);
  mcp.setFilterCoefficient(3);
  mcp.enable(true);

  //mcp2.setADCresolution(MCP9600_ADCRESOLUTION_18);
  //mcp2.setThermocoupleType(MCP9600_TYPE_K);
  //mcp2.setFilterCoefficient(3);
  //mcp2.enable(true);

  Serial.println("test3_TC");
}

/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  // check for last reading update
  if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
    LAST_SENSOR_UPDATE = micros();                               // update time

    // measure temp from thermocouples in °C
    float t1 = mcp.readThermocouple();
    
    Serial.print("t:"); Serial.print(LAST_SENSOR_UPDATE);                             // print time reading in microseconds
    Serial.print(",T1:"); Serial.print(t1);                                           // print thermocouple temperature in C
    Serial.println();
  }
}