
#include <Wire.h>
#include <NativeEthernet.h>

// ---------------- ETHERNET LINK ----------------
// Same addressing as E2_Teensy. Set your laptop's Ethernet to 192.168.1.175 / 255.255.255.0.
// Connect from the laptop with:   nc 192.168.1.174 5000
byte          MAC_ADDRESS[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress     LOCAL_IP(192, 168, 1, 174);
IPAddress     GATEWAY(192, 168, 1, 1);
IPAddress     SUBNET(255, 255, 255, 0);
const uint16_t TCP_PORT = 5000;

EthernetServer server(TCP_PORT);
EthernetClient client;

// Drop-in replacement for Serial: reads from TCP client or USB, writes to both.
class DualLink : public Stream {
public:
  void poll() {
    if (client && !client.connected()) client.stop();
    EthernetClient c = server.accept();
    if (c) {
      if (client) client.stop();   // newest connection wins
      client = c;
      client.println("Connected to load cell calibrator. Type help.");
    }
  }
  int available() override {
    poll();
    return (client ? client.available() : 0) + ::Serial.available();
  }
  int read() override {
    if (client && client.available()) return client.read();
    return ::Serial.read();
  }
  int peek() override {
    if (client && client.available()) return client.peek();
    return ::Serial.peek();
  }
  size_t write(uint8_t b) override { return write(&b, 1); }
  size_t write(const uint8_t *buf, size_t n) override {
    if (client && client.connected()) client.write(buf, n);
    ::Serial.write(buf, n);
    return n;
  }
  void flush() override { if (client) client.flush(); ::Serial.flush(); }
} Link;

void linkBegin() {
  Ethernet.begin(MAC_ADDRESS, LOCAL_IP, GATEWAY, SUBNET);
  server.begin();
  Serial.print("TCP server on ");
  Serial.print(Ethernet.localIP());
  Serial.print(":");
  Serial.println(TCP_PORT);
}

#define NUM_LC             6
#define MUX_ADDR           0x70
#define NAU_ADDR           0x2A
#define FIRST_MUX_CHANNEL  1
#define STREAM_MS          200
#define NAU_GAIN_BITS      7
#define NAU_LDO_BITS       5
#define NAU_RATE_BITS      3
#define NAU_USE_CHANNEL2   false

#define MAX_CAL_POINTS    12
#define CAL_SAMPLES       20

double LC_SLOPE[NUM_LC] = {
  1.0 / -3980.0,
  1.0 / -3880.0,
  1.0 / -3780.0,
  1.0 / -3680.0,
  1.0 / -3580.0,
  1.0
};

double LC_INTERCEPT[NUM_LC] = {
  0, 0, 0, 0, 0, 0
};

bool streaming = false;
bool present[NUM_LC] = {false};

unsigned long lastStream = 0;

// Calibration storage
double calWeights[NUM_LC][MAX_CAL_POINTS];
long calRaw[NUM_LC][MAX_CAL_POINTS];
int calCount[NUM_LC] = {0};

// NAU registers
#define R_PU_CTRL  0x00
#define R_CTRL1    0x01
#define R_CTRL2    0x02
#define R_ADCO_B2  0x12
#define R_ADCO_B1  0x13
#define R_ADCO_B0  0x14
#define R_ADC      0x15
#define R_PGA_PWR  0x1C

#define PU_RR      0x01
#define PU_PUD     0x02
#define PU_PUA     0x04
#define PU_PUR     0x08
#define PU_CS      0x10
#define PU_CR      0x20
#define PU_AVDDS   0x80


// --------------------------------------------------
// HARDWARE FUNCTIONS
// --------------------------------------------------

// Bit-banged I2C on pins 16/17 (same driver E2_Teensy uses).
#define LC_PIN_SCL       16
#define LC_PIN_SDA       17
#define LC_HALF_US       5     // ~100 kHz

inline void lc_dly()    { delayMicroseconds(LC_HALF_US); }
inline void lc_sdaRel() { pinMode(LC_PIN_SDA, INPUT); }
inline void lc_sdaLow() { pinMode(LC_PIN_SDA, OUTPUT); digitalWrite(LC_PIN_SDA, LOW); }
inline void lc_sclLow() { pinMode(LC_PIN_SCL, OUTPUT); digitalWrite(LC_PIN_SCL, LOW); }
inline void lc_sclRel() {
    pinMode(LC_PIN_SCL, INPUT);
    uint32_t t = micros();
    while (!digitalRead(LC_PIN_SCL) && micros() - t < 100) {}
}

void lc_i2c_start() {   // also serves as repeated start
    lc_sdaRel(); lc_dly(); lc_sclRel(); lc_dly();
    lc_sdaLow(); lc_dly(); lc_sclLow(); lc_dly();
}

void lc_i2c_stop() {
    lc_sdaLow(); lc_dly(); lc_sclRel(); lc_dly(); lc_sdaRel(); lc_dly();
}

bool lc_i2c_write_byte(uint8_t b) {
    for (int i = 0; i < 8; i++) {
        if (b & 0x80) lc_sdaRel(); else lc_sdaLow();
        lc_dly(); lc_sclRel(); lc_dly(); lc_sclLow();
        b <<= 1;
    }
    lc_sdaRel(); lc_dly(); lc_sclRel(); lc_dly();
    bool ack = !digitalRead(LC_PIN_SDA);
    lc_sclLow(); lc_dly();
    return ack;
}

uint8_t lc_i2c_read_byte(bool ack) {
    uint8_t b = 0;
    lc_sdaRel();
    for (int i = 0; i < 8; i++) {
        lc_dly(); lc_sclRel(); lc_dly();
        b = (b << 1) | (digitalRead(LC_PIN_SDA) ? 1 : 0);
        lc_sclLow();
    }
    if (ack) lc_sdaLow(); else lc_sdaRel();
    lc_dly(); lc_sclRel(); lc_dly(); lc_sclLow();
    lc_sdaRel(); lc_dly();
    return b;
}

bool lc_i2c_write(uint8_t addr, const uint8_t* d, uint8_t n) {
    lc_i2c_start();
    bool ok = lc_i2c_write_byte(addr << 1);
    for (uint8_t i = 0; ok && i < n; i++) ok = lc_i2c_write_byte(d[i]);
    lc_i2c_stop();
    return ok;
}

bool lc_i2c_write_read(uint8_t addr, uint8_t reg, uint8_t* d, uint8_t n) {
    lc_i2c_start();
    if (!lc_i2c_write_byte(addr << 1) || !lc_i2c_write_byte(reg)) { lc_i2c_stop(); return false; }
    lc_i2c_start();
    if (!lc_i2c_write_byte((addr << 1) | 1)) { lc_i2c_stop(); return false; }
    for (uint8_t i = 0; i < n; i++) d[i] = lc_i2c_read_byte(i < n - 1);
    lc_i2c_stop();
    return true;
}

// true = bit-bang (as E2_Teensy), false = hardware Wire1. Switch with "bus bb" / "bus hw".
bool useBitbang = true;

void busBegin() {
  if (useBitbang) {
    Wire1.end();
    lc_sdaRel(); lc_sclRel();
    for (int i = 0; i < 9; i++) { lc_sclLow(); lc_dly(); lc_sclRel(); lc_dly(); }
    lc_i2c_stop();
  } else {
    Wire1.begin();
    Wire1.setClock(100000);
  }
}

bool i2cPing(uint8_t addr) {
  if (useBitbang) return lc_i2c_write(addr, nullptr, 0);
  Wire1.beginTransmission(addr);
  return Wire1.endTransmission() == 0;
}

bool muxSelect(int lc) {
  uint8_t b = 1 << (lc + FIRST_MUX_CHANNEL);
  if (useBitbang) return lc_i2c_write(MUX_ADDR, &b, 1);
  Wire1.beginTransmission(MUX_ADDR);
  Wire1.write(b);
  return Wire1.endTransmission() == 0;
}

bool writeReg(uint8_t reg, uint8_t val) {
  if (useBitbang) {
    uint8_t d[2] = { reg, val };
    return lc_i2c_write(NAU_ADDR, d, 2);
  }
  Wire1.beginTransmission(NAU_ADDR);
  Wire1.write(reg);
  Wire1.write(val);
  return Wire1.endTransmission() == 0;
}

int readReg(uint8_t reg) {
  if (useBitbang) {
    uint8_t v = 0;
    return lc_i2c_write_read(NAU_ADDR, reg, &v, 1) ? v : -1;
  }
  Wire1.beginTransmission(NAU_ADDR);
  Wire1.write(reg);
  if (Wire1.endTransmission(false) != 0)
    return -1;
  if (Wire1.requestFrom((uint8_t)NAU_ADDR, (uint8_t)1) != 1)
    return -1;
  return Wire1.read();
}

const char *initFail = "";

bool nauInit(int lc) {
  initFail = "";
  if (!muxSelect(lc)) {
    initFail = "no ACK from mux (0x70)";
    return false;
  }

  if (!writeReg(R_PU_CTRL, PU_RR)) {
    initFail = "mux OK but no ACK from NAU7802 (0x2A)";
    return false;
  }

  delay(2);

  writeReg(R_PU_CTRL, PU_PUD);
  writeReg(R_PU_CTRL, PU_PUD | PU_PUA);

  unsigned long t = millis();

  while (!(readReg(R_PU_CTRL) & PU_PUR)) {
    if (millis() - t > 300) {
      initFail = "NAU7802 never reported power-up ready (PUR)";
      return false;
    }
    delay(2);
  }

  writeReg(
    R_CTRL1,
    (NAU_LDO_BITS << 3) | NAU_GAIN_BITS
  );

  writeReg(
    R_PU_CTRL,
    PU_AVDDS | PU_PUD | PU_PUA
  );

  writeReg(R_ADC, 0x30);

  int pga = readReg(R_PGA_PWR);

  if (pga >= 0)
    writeReg(R_PGA_PWR, pga | 0x80);

  uint8_t c2 =
    (NAU_RATE_BITS << 4) |
    (NAU_USE_CHANNEL2 ? 0x80 : 0x00);

  writeReg(R_CTRL2, c2);
  writeReg(R_CTRL2, c2 | 0x04);

  t = millis();

  // AFE self-calibration is best-effort: E2_Teensy skips it, and the regression
  // absorbs any offset/gain error, so a failure here only warns.
  while (readReg(R_CTRL2) & 0x04) {
    if (millis() - t > 1000) {
      initFail = "warning: AFE calibration timed out";
      break;
    }
    delay(5);
  }

  if (!initFail[0] && (readReg(R_CTRL2) & 0x08))
    initFail = "warning: AFE calibration error flag";

  writeReg(
    R_PU_CTRL,
    PU_AVDDS | PU_CS | PU_PUD | PU_PUA
  );

  return true;
}

bool nauReadRaw(int lc, long &raw) {
  if (!muxSelect(lc))
    return false;

  unsigned long t = millis();

  while (!(readReg(R_PU_CTRL) & PU_CR)) {
    if (millis() - t > 100)
      return false;
  }

  int b2 = readReg(R_ADCO_B2);
  int b1 = readReg(R_ADCO_B1);
  int b0 = readReg(R_ADCO_B0);

  if (b2 < 0 || b1 < 0 || b0 < 0)
    return false;

  long value =
    ((long)b2 << 16) |
    ((long)b1 << 8) |
    (long)b0;

  if (value & 0x800000)
    value |= 0xFF000000;

  raw = value;

  return true;
}

double calibratedValue(int lc, long raw) {
  return LC_SLOPE[lc] * (double)raw +
         LC_INTERCEPT[lc];
}


// --------------------------------------------------
// SERIAL INPUT
// --------------------------------------------------

void flushSerialInput() {
  delay(50);

  while (Link.available())
    Link.read();
}

String readLineBlocking() {
  while (!Link.available()) {}

  String s = Link.readStringUntil('\n');
  s.trim();

  return s;
}


// --------------------------------------------------
// LOAD CELL INITIALIZATION
// --------------------------------------------------

void initializeLoadCells() {
  for (int i = 0; i < NUM_LC; i++) {

    present[i] = nauInit(i);

    Link.print("LC");
    Link.print(i + 1);
    Link.print(" | MUX CH ");
    Link.print(i + FIRST_MUX_CHANNEL);
    Link.print(" | ");

    Link.print(present[i] ? "READY" : "NOT RESPONDING");
    if (initFail[0]) { Link.print(" ("); Link.print(initFail); Link.print(")"); }
    Link.println();
  }
}


// --------------------------------------------------
// READ AVERAGE RAW VALUE
// --------------------------------------------------

bool averageRaw(int lc, long &result) {
  long sum = 0;
  long raw;

  for (int i = 0; i < CAL_SAMPLES; i++) {

    if (!nauReadRaw(lc, raw)) {
      Link.println("ERROR: Failed to read load cell.");
      return false;
    }

    sum += raw;
    delay(50);
  }

  result = sum / CAL_SAMPLES;

  return true;
}


// --------------------------------------------------
// CALIBRATION REGRESSION
// --------------------------------------------------

bool updateCalibration(int lc) {

  int n = calCount[lc];

  if (n < 2) {
    Link.println("Need at least 2 calibration points.");
    return false;
  }

  double sumX = 0;
  double sumY = 0;
  double sumXY = 0;
  double sumXX = 0;

  for (int i = 0; i < n; i++) {

    double x = (double)calRaw[lc][i];
    double y = calWeights[lc][i];

    sumX += x;
    sumY += y;
    sumXY += x * y;
    sumXX += x * x;
  }

  double denominator =
    n * sumXX - sumX * sumX;

  if (fabs(denominator) < 0.000001) {
    Link.println("ERROR: Calibration points have no raw variation.");
    return false;
  }

  double slope =
    (n * sumXY - sumX * sumY) / denominator;

  double intercept =
    (sumY - slope * sumX) / n;

  LC_SLOPE[lc] = slope;
  LC_INTERCEPT[lc] = intercept;

  Link.println();
  Link.println("CALIBRATION UPDATED");

  Link.print("LC");
  Link.println(lc + 1);

  Link.print("SLOPE: ");
  Link.println(slope, 15);

  Link.print("INTERCEPT: ");
  Link.println(intercept, 15);

  Link.println();

  return true;
}


// --------------------------------------------------
// DISPLAY ALL CALIBRATIONS
// --------------------------------------------------

void listCalibrations() {

  Link.println();
  Link.println("========== ALL CALIBRATIONS ==========");

  for (int lc = 0; lc < NUM_LC; lc++) {

    Link.println();

    Link.print("LC");
    Link.println(lc + 1);

    if (calCount[lc] == 0) {
      Link.println("  No calibration points saved.");
      continue;
    }

    for (int i = 0; i < calCount[lc]; i++) {

      Link.print("  ");
      Link.print(calWeights[lc][i], 3);
      Link.print(" lbs raw: ");
      Link.println(calRaw[lc][i]);
    }

    Link.print("  SLOPE: ");
    Link.println(LC_SLOPE[lc], 15);

    Link.print("  INTERCEPT: ");
    Link.println(LC_INTERCEPT[lc], 15);
  }

  Link.println();
  Link.println("======================================");
}


// --------------------------------------------------
// CALIBRATE LOAD CELL
// --------------------------------------------------

void calibrateLC(int lc) {

  if (!present[lc]) {
    Link.println("ERROR: Load cell not working.");
    return;
  }

  Link.println();
  Link.println("================================");
  Link.print("CALIBRATING LC");
  Link.println(lc + 1);
  Link.println("================================");

  Link.print("Existing calibration points: ");
  Link.println(calCount[lc]);

  // First calibration: collect zero point
  if (calCount[lc] == 0) {

    flushSerialInput();

    Link.println();
    Link.println("Make sure NOTHING is on the load cell.");
    Link.println("Type y and press enter to continue.");

    while (true) {

      String resp = readLineBlocking();

      if (resp.equalsIgnoreCase("y"))
        break;

      Link.println("Type y to continue.");
    }

    Link.println();
    Link.println("Taking empty readings...");

    long zeroRaw;

    if (!averageRaw(lc, zeroRaw))
      return;

    calWeights[lc][0] = 0.0;
    calRaw[lc][0] = zeroRaw;
    calCount[lc] = 1;

    Link.println("Zero point saved.");

    Link.print("0 lbs raw: ");
    Link.println(zeroRaw);
  }

  else {

    Link.println();
    Link.println("Resuming existing calibration.");
    Link.println("Previous points have been preserved.");
  }

  // Keep adding weights until user says no
  while (true) {

    if (calCount[lc] >= MAX_CAL_POINTS) {
      Link.println();
      Link.println("Maximum calibration points reached.");
      break;
    }

    flushSerialInput();

    Link.println();
    Link.println("Place an object of KNOWN weight on the load cell.");

    Link.println("Enter its weight in pounds:");

    float knownWeight = 0;

    while (true) {

      String resp = readLineBlocking();

      knownWeight = resp.toFloat();

      if (knownWeight > 0)
        break;

      Link.println("Invalid weight. Enter a number greater than 0.");
    }

    Link.print("Using weight: ");
    Link.print(knownWeight, 3);
    Link.println(" lbs");

    Link.println("Taking weighted readings...");

    long weightedRaw;

    if (!averageRaw(lc, weightedRaw))
      return;

    Link.println("Weighted readings finished.");

    // Save new calibration point
    int index = calCount[lc];

    calWeights[lc][index] = knownWeight;
    calRaw[lc][index] = weightedRaw;

    calCount[lc]++;

    Link.println();
    Link.println("POINT SAVED");

    Link.print(knownWeight, 3);
    Link.print(" lbs raw: ");
    Link.println(weightedRaw);

    // Update regression using ALL points
    updateCalibration(lc);

    Link.println();
    Link.println("Add another weight? (y/n)");

    flushSerialInput();

    while (true) {

      String resp = readLineBlocking();

      if (resp.equalsIgnoreCase("y")) {
        break;
      }

      else if (resp.equalsIgnoreCase("n")) {

        Link.println();
        Link.println("Finished.");

        Link.print("LC");
        Link.print(lc + 1);
        Link.print(" SLOPE: ");
        Link.print(LC_SLOPE[lc], 15);

        Link.print(" INTERCEPT: ");
        Link.println(LC_INTERCEPT[lc], 15);

        Link.println();

        return;
      }

      else {
        Link.println("Please type y or n.");
      }
    }
  }
}



void busScan() {
  Link.println();
  Link.print("Bus: "); Link.println(useBitbang ? "bit-bang (pins 16/17)" : "hardware Wire1");
  if (useBitbang) {
    lc_sdaRel(); lc_sclRel(); delay(5);
    Link.print("Idle levels  SDA="); Link.print(digitalRead(LC_PIN_SDA) ? "HIGH" : "LOW");
    Link.print("  SCL="); Link.println(digitalRead(LC_PIN_SCL) ? "HIGH" : "LOW");
  }
  Link.print("Mux 0x70: "); Link.println(i2cPing(MUX_ADDR) ? "ACK" : "NO ACK");
  for (int lc = 0; lc < NUM_LC; lc++) {
    bool m = muxSelect(lc);
    bool n = m && i2cPing(NAU_ADDR);
    Link.print("LC"); Link.print(lc + 1);
    Link.print(" (mux ch "); Link.print(lc + FIRST_MUX_CHANNEL); Link.print("): ");
    Link.println(!m ? "mux select failed" : (n ? "NAU7802 ACK" : "no NAU7802"));
  }
  Link.println();
}

// --------------------------------------------------
// HELP COMMAND
// --------------------------------------------------

void printHelp() {

  Link.println();
  Link.println("========== COMMAND HELP ==========");

  Link.println();
  Link.println("CALIBRATION:");
  Link.println("  cal 1       Calibrate / resume LC1");
  Link.println("  cal 2       Calibrate / resume LC2");
  Link.println("  cal 3       Calibrate / resume LC3");
  Link.println("  cal 4       Calibrate / resume LC4");
  Link.println("  cal 5       Calibrate / resume LC5");
  Link.println("  cal 6       Calibrate / resume LC6");

  Link.println();
  Link.println("INFORMATION:");
  Link.println("  list        Show all calibration points");
  Link.println("  init        Re-initialize load cells and show status");
  Link.println("  scan        Check I2C bus: mux and each load cell");
  Link.println("  bus bb|hw   Switch I2C: bit-bang (default) or hardware Wire1");
  Link.println("  help        Show this help menu");

  Link.println();
  Link.println("STREAMING:");
  Link.println("  stream on   Start live readings");
  Link.println("  stream off  Stop live readings");

  Link.println();
  Link.println("==================================");
  Link.println();
}


// --------------------------------------------------
// PRINT LIVE READINGS
// --------------------------------------------------

void printReadings() {

  Link.println();

  for (int i = 0; i < NUM_LC; i++) {
    Link.print("LC");
    Link.print(i + 1);
    Link.print("\t");
  }

  Link.println();

  for (int i = 0; i < NUM_LC; i++)
    Link.print("RAW\t");

  Link.println();

  long rawValues[NUM_LC];
  bool valid[NUM_LC];

  for (int i = 0; i < NUM_LC; i++) {

    valid[i] = false;
    rawValues[i] = 0;

    if (present[i])
      valid[i] = nauReadRaw(i, rawValues[i]);

    if (valid[i])
      Link.print(rawValues[i]);
    else
      Link.print("ERROR");

    Link.print("\t");
  }

  Link.println();

  for (int i = 0; i < NUM_LC; i++)
    Link.print("CAL\t");

  Link.println();

  for (int i = 0; i < NUM_LC; i++) {

    if (valid[i]) {
      Link.print(
        calibratedValue(i, rawValues[i]),
        3
      );
    }

    else {
      Link.print("--");
    }

    Link.print("\t");
  }

  Link.println();
  Link.println("------------------------------------------------------------");
}


// --------------------------------------------------
// SERIAL COMMAND HANDLER
// --------------------------------------------------

void handleSerial() {

  if (!Link.available())
    return;

  String command = Link.readStringUntil('\n');
  command.trim();
  command.toLowerCase();

  if (command == "stream on") {

    streaming = true;
    Link.println("Streaming ON");
  }

  else if (command == "stream off") {

    streaming = false;
    Link.println("Streaming OFF");
  }

  else if (command == "list") {

    listCalibrations();
  }

  else if (command == "scan") {

    busScan();
  }

  else if (command == "bus bb" || command == "bus hw") {

    useBitbang = (command == "bus bb");
    busBegin();
    Link.print("Bus set to ");
    Link.println(useBitbang ? "bit-bang. Run init." : "hardware Wire1. Run init.");
  }

  else if (command == "init") {

    initializeLoadCells();
  }

  else if (command == "help") {

    printHelp();
  }

  else if (command.startsWith("cal ")) {

    int lc = command.substring(4).toInt();

    if (lc >= 1 && lc <= NUM_LC) {

      streaming = false;

      Link.print("Starting calibration for LC");
      Link.println(lc);

      calibrateLC(lc - 1);
    }

    else {
      Link.println("Invalid load cell. Use cal 1 through cal 6.");
    }
  }

  else {

    Link.println("Unknown command. Type help for commands.");
  }
}

void setup() {

  Serial.begin(115200);
  linkBegin();

  delay(500);

  busBegin();

  Link.println("LOAD CELL INITIALIZATION");

  initializeLoadCells();

  Link.println();
  Link.println("Type help to see available commands.");
  Link.println();
}


void loop() {

  handleSerial();

  if (streaming && millis() - lastStream >= STREAM_MS) {

    lastStream = millis();

    printReadings();
  }
}