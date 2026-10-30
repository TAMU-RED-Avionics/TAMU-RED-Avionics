// Simeon Shaffar Oct 25 2025
#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>


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


// ----------------------------------------------------------------


/*
--------------------------------
THERMOCOUPLE DECLARATIONS
--------------------------------
*/

// Thermocouple libraries
// See example https://github.com/adafruit/Adafruit_MCP9600/blob/master/examples/mcp9600_test/mcp9600_test.ino

#include <Adafruit_MCP9600.h>

// Thermocouple I2C addresses
#define TC1_I2C_ADDR (0x60)   // 1100 000x  Corresponding to MCP9600 Address 0 (Vaddr = GND)
#define TC2_I2C_ADDR (0x67)   // 1100 111x  Corresponding to MCP9600 Address 7 (Vaddr = VDD = 3V3)

// Thermocouple mcp identifier
Adafruit_MCP9600 mcp1;
Adafruit_MCP9600 mcp2;

/*
--------------------------------
PRESSURE TRANSDUCER DECLARATIONS
--------------------------------
*/

// teensy pins to read signals
const int PT1_PIN = 23;                    // <-- USER INPUT
const int PT2_PIN = 22;                    // <-- USER INPUT

// analog and digital reading variables setup
int pt1_analog = 0;                        // analog reading from PT output signal
int pt2_analog = 0;                        // analog reading from PT output signal


// For the 0-5V digital signal PTs - Honeywell PX2AF1... series
// https://tinyurl.com/y9549dww
//
// parameter: a digital 0 - 1023 reading 
// returns: a reading in psi
//
double convert_PX2AF1XX500PAAAX_PT(int reading) {
  // 0 - 500 psia going into PT
  // 0.5 - 4.9 V comes out from that range
  // 0.33 - 2.97 V after voltage divider on the board
  // 102(.3) - 920(.7) range from the digital reading based off Teensy's 0 - 3.3V digital pin

  // So basically 102.3 - 920.7 range corresponds to 15 - 1000 psi range
  // y = (y2-y1)/(x2-x1) * (x - x1) + y1
  return (500.0 - 0.0) / (920.7 - 102.3) * (reading - 102.3) + 0.0;
}

// For the 4-20mA signal coming out of a 0-1500psi PT
// https://www.mcmaster.com/6017N19/

double convert_6017N19_PT(int reading) {
  // 0 - 1500 psia into PT
  // 4 - 20 mA coming out of PT
  // current goes through 160 Ohm resistor
  // 0.64 - 3.2 V coming off of 160 Ohm resistor
  // 198(.4) - 992 range from digital reading based off Teensy's 0 - 3.3V digital pin

  // So 198(.4) - 992 range corresponds to 0 - 1500 psi range
  // y = (y2-y1)/(x2-x1) * (x - x1) + y1
  return (1500.0 - 0.0) / (992.0 - 198.4) * (reading - 198.4) + 0.0;
}

/*
--------------------------------
LOAD CELL DECLARATIONS
--------------------------------
*/

#include <Adafruit_NAU7802.h>


// The Address of the bus on I2C1
#define LC_BUS_ADDR 0x70
#define LC1_ADDR 0
#define LC2_ADDR 1

// This is the object that talks directly to the LC ADC
Adafruit_NAU7802 nau1;
Adafruit_NAU7802 nau2;

// Lil' functioon that switches between bus outputs
void lc_select(uint8_t i) {
  if (i > 7) return;
  
  // Wire1 corresponds to sending data on I2C1
  Wire1.beginTransmission(LC_BUS_ADDR);
  Wire1.write(1 << i);
  Wire1.endTransmission();  
}

int32_t lc_read(uint8_t i) {
  lc_select(i);

  if (i == LC1_ADDR)
    return nau1.read();
  else if (i == LC2_ADDR)
    return nau2.read();
  else 
    return nau1.read(); //Default to nau1
}

double convert_DLY_103_500kg_LC(int32_t reading) {
  // Capacity of 0 to 500kg weight -> 0 to 500*9.81 N
  // Vref of 3V3
  // Product page says 2mV/V output
  // Manual test - weighing my 174g iPhone 13 it reads a digital reading of 1500 ± 100 (eyballing it)

  // 0 to 174g for my iphone
  // 0 to 1500 digital reading
  // y = (y2-y1)/(x2-x1) * (x-x1) + y1
  
  return (0.174 - 0.0) / (1500.0 - 0.0) * (reading - 0.0) + 0.0;
}



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

  // This stuff is hella finnicky, at least on the test PCB
  // Try pulling out the teensy, flashing it outside the board, unplugging it, remounting, and replugging in 
  if (!mcp1.begin(TC1_I2C_ADDR)) {
    Serial.println("TC1 ADC not found!");
    while (1); delay(10);  // Don't proceed.
  }

  if (!mcp2.begin(TC2_I2C_ADDR)) {
    Serial.println("TC2 ADC not found!");
    while (1); delay(10);  // Don't proceed.
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


  /*
  -----------------------
  LOAD CELL SET UP
  -----------------------
  */

  // Wire1 corresponds to I2C1 (The TCs use I2C0)
  Wire1.begin();
  lc_select(LC1_ADDR);
  if (!nau1.begin(&Wire1)) {
    Serial.println("Failed to find NAU7802");
    while (1) delay(10);  // Don't proceed.
  }
  lc_select(LC2_ADDR);
  if (!nau2.begin(&Wire1)) {
    Serial.println("Failed to find NAU7802");
    while (1) delay(10);  // Don't proceed.
  }
  Serial.println("Found both NAU7802 ICs!");
  
  //LC1 SETUP
  
  // Set config params for NAU chip (I have no idea what they should be but these were the default)
  lc_select(LC1_ADDR);
  nau1.setLDO(NAU7802_3V3);
  nau1.setGain(NAU7802_GAIN_128);
  nau1.setRate(NAU7802_RATE_10SPS);
  nau1.setPGACap(true); // Single channel setting - enable use of PGA stabilizer caps (Cfilter) on VIN2

  if (!nau1.calibrate(NAU7802_CALMOD_INTERNAL))
    Serial.println("Failed to Calibrate First NAU7802");
  else Serial.println("Calibrated First NAU7802");

  // Take 10 readings to flush out readings
  for (uint8_t i=0; i<10; i++) {
    while (! nau1.available()) delay(1);
    nau1.read();
  }
  

  //LC2 SETUP

  lc_select(LC2_ADDR);
  nau2.setLDO(NAU7802_3V3);
  nau2.setGain(NAU7802_GAIN_128);
  nau2.setRate(NAU7802_RATE_10SPS);
  nau2.setPGACap(true);

  if (!nau2.calibrate(NAU7802_CALMOD_INTERNAL))
    Serial.println("Failed to Calibrate Second NAU7802");
  else Serial.println("Calibrated Second NAU7802");

  for (uint8_t i=0; i<10; i++) {
    while (! nau2.available()) delay(1);
    nau2.read();
  }
  
  Serial.println("Finished Setup");
} // setup


/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  
  // Read PTs
  Serial.print("\nPT1 ADC (psia): "); Serial.print(convert_PX2AF1XX500PAAAX_PT(analogRead(PT1_PIN)));
  Serial.print("\tPT2 ADC (psig): "); Serial.print(convert_6017N19_PT(analogRead(PT2_PIN)));

  // Read TCs
  Serial.print("\tTC1 H (°C): "); Serial.print(mcp1.readThermocouple());
  Serial.print("\tTC1 C (°C):"); Serial.print(mcp1.readAmbient());

  Serial.print("\tTC2 H (°C): "); Serial.print(mcp2.readThermocouple());
  Serial.print("\tTC2 C (°C): "); Serial.print(mcp2.readAmbient());

  // Read LCs
  Serial.print("\tLC1 ADC (kg): "); Serial.print(convert_DLY_103_500kg_LC(lc_read(LC1_ADDR)));
  Serial.print("\tLC2 ADC (kg): "); Serial.print(convert_DLY_103_500kg_LC(lc_read(LC2_ADDR)));

  delay(100);

} // loop
