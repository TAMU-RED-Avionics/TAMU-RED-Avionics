#include <SPI.h>

const int BAUD = 115200;                                  // Serial BAUD rate (bits/second)

const int F_SCLK = 1000000;
const int CS_PIN = 10;
const int MOSI_PIN = 11;
const int MISO_PIN = 12;
const int SCLK_PIN = 13;


const SPISettings SPI_SETTINGS = SPISettings(F_SCLK, MSBFIRST, SPI_MODE0);

// const unsigned int retarded_cmd = 0x8400; // 1000 0100 0000 0000
const unsigned int TARD_CMD = 0x8800;

//                                                 manual-mode-vvvv v-enable-programming  v-print-addr vvvv-GPIO-outputs
const unsigned int POKE_CMD     = 0B0001'1000'0000'0000;       // 0001 1 0000 0      0       0            0000
//                                                   channel-select-0-^^^^ ^-2.5V ^-no-power-down

const unsigned int REV_POKE_CMD = 0B0000'0000'0001'1000;   // 0000 0000 0001 1000

const unsigned int CMD = POKE_CMD;


double nanoseconds(uint32_t elapsed_cycles) {
  double t_cpu = 1000000000.d * 1/F_CPU;   // F_CPU is in Hz, which is converted to s, which is then converted to ns
  return elapsed_cycles * t_cpu;
}

// This function will attempt to demonstrate a basic send and receive command
// If working correctly, the adc will output a reading from channel 0
uint16_t poke_adc() {
  // uint32_t start_time = micros();
  // Serial.println(micros() - start_time);

  Serial.println(CMD, BIN);

  uint32_t current_cycles = ARM_DWT_CYCCNT;
  digitalWrite(CS_PIN, LOW);
  Serial.println(nanoseconds(ARM_DWT_CYCCNT - current_cycles));
  
  current_cycles = ARM_DWT_CYCCNT;
  SPI.transfer16(CMD);
  Serial.println(nanoseconds(ARM_DWT_CYCCNT - current_cycles));
  
  delayMicroseconds(1);
  
  current_cycles = ARM_DWT_CYCCNT;
  digitalWrite(CS_PIN, HIGH);
  Serial.println(nanoseconds(ARM_DWT_CYCCNT - current_cycles));

  delayMicroseconds(1);

  current_cycles = ARM_DWT_CYCCNT;
  digitalWrite(CS_PIN, LOW);
  Serial.println(nanoseconds(ARM_DWT_CYCCNT - current_cycles));


  // Read the following frame, where it would then sample real data.
  current_cycles = ARM_DWT_CYCCNT;
  uint16_t val = SPI.transfer16(CMD);
  Serial.println(nanoseconds(ARM_DWT_CYCCNT - current_cycles));

  current_cycles = ARM_DWT_CYCCNT;
  digitalWrite(CS_PIN, HIGH);
  Serial.println(nanoseconds(ARM_DWT_CYCCNT - current_cycles));

  return val;
}

void setup() {
  Serial.begin(BAUD);
  Serial.println("Setting up");

  // set the slaveSelectPin as an output:
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);

  // initialize SPI:
  SPI.begin(); 
  SPI.beginTransaction(SPI_SETTINGS);
  Serial.println("Initialized SPI!");

  if (SPI.pinIsChipSelect(CS_PIN) && SPI.pinIsMISO(MISO_PIN) && SPI.pinIsMOSI(MOSI_PIN) && SPI.pinIsSCK(SCLK_PIN))
    Serial.println("Pins are configured correctly!");
  
}

void loop() {
  uint16_t raw = poke_adc();
  Serial.print("Raw 16-bit frame: 0B");
  Serial.println(raw, BIN);

  delay(1000); // slow print
}