#include <SPI.h>

const int BAUD = 115200;                                  // Serial BAUD rate (bits/second)
const int F_SCLK = 20000000;
const double T_CPU = 1000000000.d * 1/F_CPU;   // F_CPU is in Hz, which is converted to s, which is then converted to ns

const int CS_PIN = 10;
const int MOSI_PIN = 11;
const int MISO_PIN = 12;
const int SCLK_PIN = 13;


const SPISettings SPI_SETTINGS = SPISettings(F_SCLK, MSBFIRST, SPI_MODE0);

// This command was used to do a basic poke of the ADC
//                                            manual-mode-vvvv v-enable-programming  v-print-addr vvvv-GPIO-outputs
const uint16_t POKE_CMD = 0B0001'1001'0000'0000;       // 0001 1 0001 0      0       0            0000
//                                              channel-select-1-^^^^ ^-2.5V ^-no-power-down

// This command is the starting point for manual reads (where you tell it what channel to read every time)
const uint16_t MANUAL_BASE_CMD = 0B0001'1000'0000'0000;
//                      manual_mode^^^^ ^enable_programming

// After we read from the adc we need to snip out only the actual analog reading
const uint16_t ANALOG_FILTER = 0B0000'1111'1111'1111;
//              ignore_channel_id^^^^

// Inverse of ANALOG_FILTER, this can be used to filter out the channel index that the ADC has output
const uint16_t CHANNEL_FILTER = 0B1111'0000'0000'0000;
//                 channel_id_only^^^^

double nanoseconds(uint32_t elapsed_cycles) {
  return elapsed_cycles * T_CPU;
}

uint16_t read_adc(uint16_t channel) {
  uint16_t cmd = MANUAL_BASE_CMD + (channel << 7);

  // First, we send an SPI frame to instruct the ADC what channel to use and put it into manual mode
  digitalWrite(CS_PIN, LOW);
  SPI.transfer16(cmd);
  digitalWrite(CS_PIN, HIGH);

  // Idk testing showed that we actually need to wait two frames for it to kick in, even though datasheet suggested one should be necessary
  digitalWrite(CS_PIN, LOW);
  SPI.transfer16(0);
  digitalWrite(CS_PIN, HIGH);

  // There is a little capacitor inside the ADC that has to discharge in between switches, best results when you let that drain
  delayMicroseconds(10);

  // Then, the second SPI frame it shits the ADC reading back to us. The output command does not matter
  digitalWrite(CS_PIN, LOW);
  uint32_t val = SPI.transfer16(0);
  digitalWrite(CS_PIN, HIGH);

  const uint16_t output_channel = (val & CHANNEL_FILTER) >> 12;

  // Serial.print("Command: "); Serial.println(cmd, BIN);
  // Serial.print("16-bit ADC frame: 0B"); Serial.println(val, BIN);
  
  if (output_channel != channel)
    Serial.println("ERROR: ADC says it is reading from the wrong channel");

  // Snip off the channel id from the response
  return val & ANALOG_FILTER;
}


void setup() {
  Serial.begin(BAUD);
  Serial.println("Setting up");

  // set the slaveSelectPin as an output:
  pinMode(CS_PIN, OUTPUT);

  // initialize SPI:
  SPI.begin(); 
  SPI.beginTransaction(SPI_SETTINGS);
  Serial.println("Initialized SPI!");

  if (SPI.pinIsChipSelect(CS_PIN) && SPI.pinIsMISO(MISO_PIN) && SPI.pinIsMOSI(MOSI_PIN) && SPI.pinIsSCK(SCLK_PIN))
    Serial.println("Pins are configured correctly!");
  
  // Assert the chip select (recommended to do this after beginTransaction according to Teensy SPI library docs)
  digitalWrite(CS_PIN, HIGH);
}

void loop() {
  for(int i = 0; i < 16; i++) {
    uint16_t reading = read_adc(i);
    Serial.print("Channel: "); Serial.print(i); Serial.print(", ADC Reading: "); Serial.println(reading);
  } 

  delay(100); //milliseconds
}
