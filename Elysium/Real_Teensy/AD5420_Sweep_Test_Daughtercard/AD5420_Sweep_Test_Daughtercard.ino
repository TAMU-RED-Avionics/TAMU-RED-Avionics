/*
 * AD5420_Sweep_Test_Daughtercard.ino — 4–20 mA sweep + validation for the AD5420 on the
 * TAMU RED Teensy 4.1 daughtercard (same circuit as the validated PWN_to_Analog_PCB test board).
 *
 * Pin map (from the pad nets in Teensy_Daughtercard.kicad_pcb) — AD5420 (U4) is on SPI1:
 *   Teensy 0  -> AD5420 LATCH  (net /CS)
 *   Teensy 26 -> AD5420 SDIN   (net /MOSI)   = MOSI1 default
 *   Teensy 1  <- AD5420 SDO    (net /MISO)   = MISO1 default (alt MISO1 pin 39 is /ENA3_3V3 here,
 *                                             so MISO is pinned to 1 explicitly)
 *   Teensy 27 -> AD5420 SCLK   (net /SCK)    = SCK1 default
 *   CLEAR: hard-wired to GNDD through R5 (10k) — not Teensy controlled, so no CLEAR test here
 *   ~FAULT: pulled up by R4, not routed to the Teensy -> faults read from the status register
 *   AD5420 DVCC <- VMC+ (Teensy 3V3), DVCC_SELECT tied to GNDD
 *   RSET: R6 15k -> REXT = 1;  REFOUT tied to REFIN (C6) -> internal 5 V reference
 *   AVDD = +12 V from J9;  IOUT -> J10 pin 2 (J10 pin 1 = GNDD)
 *
 * This sketch configures ONLY the four SPI1 pins. The relay and step/dir/enable lines that leave
 * through J6 are left untouched (undefined) — run this with the J6 harness unplugged.
 *
 * COMPLIANCE: the AD5420 needs ~2.5 V headroom, so with AVDD = 12 V the loop voltage tops out
 * near 9.5 V. Into 1 kΩ that is ~9.5 mA; above that the current clips and IOUT_FAULT should set.
 *
 * Serial Monitor: 115200 baud, line ending = "Newline". Type  h  for the command list.
 */

#include <SPI.h>
#include "AD5420_Types.h"   // must stay a separate tab: the IDE's auto-prototypes need these types first

// ---------------- Pins ----------------
constexpr uint8_t PIN_LATCH = 0;    // /CS
constexpr uint8_t PIN_MOSI  = 26;   // /MOSI
constexpr uint8_t PIN_MISO  = 1;    // /MISO
constexpr uint8_t PIN_SCK   = 27;   // /SCK
SPIClass& AD_SPI = SPI1;

// ---------------- Bench setup (editable at runtime too) ----------------
constexpr float AVDD_V            = 12.0f;
constexpr float HEADROOM_V        = 2.5f;   // AD5420 output compliance ≈ AVDD − 2.5 V
constexpr float EDGE_BAND_V       = 0.5f;   // don't judge the fault flag this close to compliance
constexpr float PASS_LIMIT_PCT    = 0.5f;   // bench screening limit, % of 16 mA span (= 80 µA)
constexpr float HYST_LIMIT_uA     = 20.0f;  // up vs down at the same setpoint
float    gLoadOhms = 1000.0f;   // measure your resistor unpowered and set it with:  R 998.6
float    gStep_mA  = 2.0f;      // sweep step:  step 1
uint32_t gDwell_ms = 1500;      // auto-sweep dwell per step:  dwell 3000
bool     gUnitsVolts = true;    // guided mode readings: volts across load (true) or mA in series

// ---------------- AD5420 registers ----------------
constexpr uint8_t  REG_NOP = 0x00, REG_DATA = 0x01, REG_READBACK = 0x02,
                   REG_CONTROL = 0x55, REG_RESET = 0x56;
constexpr uint16_t CTRL_REXT = 1u << 13, CTRL_OUTEN = 1u << 12, RANGE_4_20 = 0b101;
constexpr uint16_t CTRL_WORD = CTRL_REXT | CTRL_OUTEN | RANGE_4_20;   // 0x3005
constexpr uint16_t RB_STATUS = 0b00, RB_DATA = 0b01, RB_CONTROL = 0b10;
constexpr uint16_t STAT_IOUT_FAULT = 1u << 2, STAT_SLEW = 1u << 1, STAT_OVERTEMP = 1u << 0;

const SPISettings AD5420_SPI(1000000, MSBFIRST, SPI_MODE0);  // data in on SCLK rising edge

// ---------------- Low-level SPI ----------------
uint32_t ad5420Transfer(uint8_t addr, uint16_t data) {
  AD_SPI.beginTransaction(AD5420_SPI);
  digitalWriteFast(PIN_LATCH, LOW);
  uint32_t rx = (uint32_t)AD_SPI.transfer(addr) << 16;
  rx |= (uint32_t)AD_SPI.transfer(data >> 8) << 8;
  rx |= AD_SPI.transfer(data & 0xFF);
  digitalWriteFast(PIN_LATCH, HIGH);  // rising edge of LATCH loads the register
  AD_SPI.endTransaction();
  delayMicroseconds(10);
  return rx;
}
void ad5420Write(uint8_t addr, uint16_t data) { ad5420Transfer(addr, data); }
uint16_t ad5420Read(uint16_t sel) {
  ad5420Transfer(REG_READBACK, sel & 0x3);
  return (uint16_t)(ad5420Transfer(REG_NOP, 0) & 0xFFFF);
}

// ---------------- Conversions ----------------
uint16_t codeFor_mA(float mA) {
  if (mA < 4.0f) mA = 4.0f;
  if (mA > 20.0f) mA = 20.0f;
  uint32_t c = (uint32_t)((mA - 4.0f) / 16.0f * 65536.0f + 0.5f);
  return c > 0xFFFF ? 0xFFFF : (uint16_t)c;
}
float mA_forCode(uint16_t c) { return 4.0f + 16.0f * c / 65536.0f; }
float complianceV() { return AVDD_V - HEADROOM_V; }
float maxLinear_mA() { return complianceV() / gLoadOhms * 1000.0f; }

// ---------------- Serial line input ----------------
char   gLine[64];
size_t gLineLen = 0;

// Non-blocking: returns true when a full line is in gLine.
bool pollLine() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') { gLine[gLineLen] = 0; gLineLen = 0; return true; }
    if (gLineLen < sizeof(gLine) - 1) gLine[gLineLen++] = ch;
  }
  return false;
}
void readLineBlocking() { while (!pollLine()) { yield(); } }
void flushInput() { delay(20); while (Serial.available()) Serial.read(); gLineLen = 0; }

// ---------------- One setpoint (Point / Expect types live in AD5420_Types.h) ----------------
Expect expectationFor(float mA) {
  float vNeed = mA * 1e-3f * gLoadOhms;
  if (vNeed < complianceV() - EDGE_BAND_V) return EXP_LINEAR;
  if (vNeed > complianceV() + EDGE_BAND_V) return EXP_CLIP;
  return EXP_EDGE;
}

const char* faultCheck(const Point& p) {
  bool fault = p.status & STAT_IOUT_FAULT;
  if (p.rbData != p.code) return "SPI READBACK MISMATCH";
  if (p.status & STAT_OVERTEMP) return "OVERTEMP";
  switch (p.expect) {
    case EXP_LINEAR: return fault ? "UNEXPECTED IOUT FAULT" : "ok";
    case EXP_CLIP:   return fault ? "ok (clipping, fault set as expected)" : "NO FAULT but should be clipping";
    default:         return fault ? "edge (fault set)" : "edge (no fault)";
  }
}

void applyPoint(Point& p, uint32_t settle_ms) {
  p.code = codeFor_mA(p.target_mA);
  ad5420Write(REG_DATA, p.code);
  delay(settle_ms);
  p.rbData = ad5420Read(RB_DATA);
  p.status = ad5420Read(RB_STATUS);
  p.expect = expectationFor(p.target_mA);
}

// Build the up-then-down list: 4 -> 20 -> 4 in gStep_mA steps.
int buildSweep(Point* pts, int maxPts) {
  int n = (int)(16.0f / gStep_mA + 0.5f);
  if (n < 1) n = 1;
  int k = 0;
  for (int i = 0; i <= n && k < maxPts; i++)
    pts[k++] = { 4.0f + 16.0f * i / n, 0, 0, 0, EXP_LINEAR, true, NAN };
  for (int i = n - 1; i >= 0 && k < maxPts; i--)
    pts[k++] = { 4.0f + 16.0f * i / n, 0, 0, 0, EXP_LINEAR, false, NAN };
  return k;
}

void printSetupBanner() {
  Serial.printf("Load %.1f ohm, AVDD %.1f V -> compliance ~%.2f V -> linear up to ~%.2f mA\n",
                gLoadOhms, AVDD_V, complianceV(), min(20.0f, maxLinear_mA()));
}

// ---------------- Auto sweep (no measurements typed) ----------------
constexpr int MAX_PTS = 140;
Point gPts[MAX_PTS];

bool autoSweep() {   // returns false if aborted by a keypress
  int n = buildSweep(gPts, MAX_PTS);
  printSetupBanner();
  Serial.println("dir,target_mA,code,readback,V_load_expected,status,iout_fault,check");
  int problems = 0;
  for (int i = 0; i < n; i++) {
    Point& p = gPts[i];
    applyPoint(p, gDwell_ms);
    const char* chk = faultCheck(p);
    if (strncmp(chk, "ok", 2) && strncmp(chk, "edge", 4)) problems++;
    Serial.printf("%s,%.3f,0x%04X,0x%04X,%.3f,0x%04X,%s,%s\n", p.dir_up ? "up" : "down",
                  p.target_mA, p.code, p.rbData,
                  min(p.target_mA * 1e-3f * gLoadOhms, complianceV()), p.status,
                  (p.status & STAT_IOUT_FAULT) ? "Y" : "N", chk);
    if (Serial.available()) { flushInput(); Serial.println("Aborted."); ad5420Write(REG_DATA, 0); return false; }
  }
  ad5420Write(REG_DATA, 0);
  Serial.printf("Sweep done, back at 4 mA. Digital/fault checks: %s (%d problem%s)\n",
                problems ? "FAIL" : "PASS", problems, problems == 1 ? "" : "s");
  return true;
}

// ---------------- Guided validation sweep (you type the DMM reading) ----------------
void guidedSweep() {
  int n = buildSweep(gPts, MAX_PTS);
  printSetupBanner();
  Serial.printf("Guided sweep, %d points. Type the DMM reading in %s, Enter to skip, q to quit.\n",
                n, gUnitsVolts ? "VOLTS across the load" : "mA (meter in series)");
  for (int i = 0; i < n; i++) {
    Point& p = gPts[i];
    applyPoint(p, 50);
    float vExp = min(p.target_mA * 1e-3f * gLoadOhms, complianceV());
    Serial.printf("[%2d/%d] %-4s %6.3f mA (0x%04X) expect %s %.3f %s  %s > ",
                  i + 1, n, p.dir_up ? "up" : "down", p.target_mA, p.code,
                  p.expect == EXP_LINEAR ? "" : "~",
                  gUnitsVolts ? vExp : (p.expect == EXP_LINEAR ? p.target_mA : maxLinear_mA()),
                  gUnitsVolts ? "V" : "mA",
                  p.expect == EXP_CLIP ? "(clipping)" : p.expect == EXP_EDGE ? "(near compliance)" : "");
    readLineBlocking();
    if (gLine[0] == 'q') { Serial.println("quit"); n = i; break; }
    if (gLine[0]) {
      float v = atof(gLine);
      p.meas_mA = gUnitsVolts ? v / gLoadOhms * 1000.0f : v;
      p.status = ad5420Read(RB_STATUS);   // re-read after the dwell you spent measuring
      Serial.printf("%s -> %.4f mA, err %+.1f uA  [%s]\n", gLine, p.meas_mA,
                    (p.meas_mA - p.target_mA) * 1000.0f, faultCheck(p));
    } else {
      Serial.println("(skipped)");
    }
  }
  ad5420Write(REG_DATA, 0);

  // ---- Summary over the linear (in-compliance) region ----
  int m = 0; double sx = 0, sy = 0, sxx = 0, sxy = 0; float worst = 0, worstAt = 0;
  int faultProblems = 0, rbProblems = 0;
  for (int i = 0; i < n; i++) {
    const Point& p = gPts[i];
    if (p.rbData != p.code) rbProblems++;
    const char* chk = faultCheck(p);
    if (strncmp(chk, "ok", 2) && strncmp(chk, "edge", 4)) faultProblems++;
    if (p.expect != EXP_LINEAR || isnan(p.meas_mA)) continue;
    float e = p.meas_mA - p.target_mA;
    if (fabsf(e) > fabsf(worst)) { worst = e; worstAt = p.target_mA; }
    sx += p.target_mA; sy += p.meas_mA; sxx += p.target_mA * p.target_mA;
    sxy += p.target_mA * p.meas_mA; m++;
  }
  Serial.println("\n===== Validation summary =====");
  printSetupBanner();
  if (m >= 2) {
    double gain = (m * sxy - sx * sy) / (m * sxx - sx * sx);
    double off  = (sy - gain * sx) / m;
    float worstPct = fabsf(worst) / 16.0f * 100.0f;
    Serial.printf("Linear points measured: %d\n", m);
    Serial.printf("Fit: I_meas = %.5f * I_set %+.4f mA  (gain err %+.3f%%, offset %+.1f uA)\n",
                  gain, off, (gain - 1.0) * 100.0, off * 1000.0);
    Serial.printf("Worst error: %+.1f uA at %.3f mA = %.3f%% of span -> %s (limit %.2f%%)\n",
                  worst * 1000.0f, worstAt, worstPct, worstPct <= PASS_LIMIT_PCT ? "PASS" : "FAIL",
                  PASS_LIMIT_PCT);
  } else {
    Serial.println("Not enough linear-region readings for an accuracy fit.");
  }
  // Hysteresis: matching up/down setpoints
  float worstH = 0; int pairs = 0;
  for (int i = 0; i < n; i++) for (int j = i + 1; j < n; j++) {
    const Point &a = gPts[i], &b = gPts[j];
    if (a.dir_up && !b.dir_up && fabsf(a.target_mA - b.target_mA) < 1e-4f &&
        a.expect == EXP_LINEAR && !isnan(a.meas_mA) && !isnan(b.meas_mA)) {
      float h = fabsf(a.meas_mA - b.meas_mA) * 1000.0f;
      if (h > worstH) worstH = h;
      pairs++;
    }
  }
  if (pairs) Serial.printf("Up/down repeatability: worst %.1f uA over %d pairs -> %s (limit %.0f uA)\n",
                           worstH, pairs, worstH <= HYST_LIMIT_uA ? "PASS" : "FAIL", HYST_LIMIT_uA);
  Serial.printf("SPI readback: %s   Fault flag vs prediction: %s\n",
                rbProblems ? "FAIL" : "PASS", faultProblems ? "FAIL" : "PASS");
  // CSV dump for your records
  Serial.println("\ndir,target_mA,code,status,expect,meas_mA,err_uA");
  for (int i = 0; i < n; i++) {
    const Point& p = gPts[i];
    Serial.printf("%s,%.3f,0x%04X,0x%04X,%s,", p.dir_up ? "up" : "down", p.target_mA, p.code,
                  p.status, p.expect == EXP_LINEAR ? "linear" : p.expect == EXP_CLIP ? "clip" : "edge");
    if (isnan(p.meas_mA)) Serial.println(",");
    else Serial.printf("%.4f,%+.1f\n", p.meas_mA, (p.meas_mA - p.target_mA) * 1000.0f);
  }
  Serial.println("Back at 4 mA.");
}

// ---------------- Continuous triangle ramp (for a scope) ----------------
void triangleRamp() {
  Serial.println("Triangle ramp 4->20->4 mA (~1 s each way). Scope across the load. Press Enter to stop.");
  printSetupBanner();
  flushInput();
  while (!Serial.available()) {
    for (int i = 0; i <= 1023 && !Serial.available(); i++) { ad5420Write(REG_DATA, i * 64); delay(1); }
    for (int i = 1023; i >= 0 && !Serial.available(); i--) { ad5420Write(REG_DATA, i * 64); delay(1); }
  }
  flushInput();
  ad5420Write(REG_DATA, 0);
  Serial.println("Stopped, back at 4 mA.");
}

// ---------------- Status ----------------
void printStatus() {
  uint16_t ctrl = ad5420Read(RB_CONTROL), data = ad5420Read(RB_DATA), st = ad5420Read(RB_STATUS);
  Serial.printf("Control 0x%04X (%s)  Data 0x%04X = %.4f mA  Status 0x%04X  IOUT fault:%s  overtemp:%s\n",
                ctrl, ctrl == CTRL_WORD ? "ok" : "UNEXPECTED", data, mA_forCode(data), st,
                (st & STAT_IOUT_FAULT) ? "YES" : "no", (st & STAT_OVERTEMP) ? "YES" : "no");
  printSetupBanner();
}

void printHelp() {
  Serial.println(
    "\nCommands:\n"
    "  s            auto sweep 4->20->4 mA, prints CSV with readback + fault checks\n"
    "  g            guided validation sweep: you type the DMM reading at each step\n"
    "  t            continuous triangle ramp for a scope (Enter to stop)\n"
    "  <mA>         hold a current, e.g.  8.5\n"
    "  x            return to 4 mA\n"
    "  R <ohms>     load resistance used for V<->I math (measure yours), e.g.  R 998.6\n"
    "  step <mA>    sweep step size (default 2)\n"
    "  dwell <ms>   auto-sweep dwell per step (default 1500)\n"
    "  u v | u i    guided-mode units: volts across load, or mA with meter in series\n"
    "  ?            status / register readback\n"
    "  h            this help");
}

// ---------------- Setup / loop ----------------
bool initAD5420() {
  ad5420Write(REG_RESET, 0x0001);              // software reset, output tristated
  delay(1);
  ad5420Write(REG_CONTROL, CTRL_REXT | RANGE_4_20);  // configure range with output still off
  ad5420Write(REG_DATA, 0x0000);               // zero-scale = 4 mA
  ad5420Write(REG_CONTROL, CTRL_WORD);         // enable IOUT
  delay(1);
  uint16_t ctrl = ad5420Read(RB_CONTROL);
  Serial.printf("AD5420 control: wrote 0x%04X, read 0x%04X -> %s\n", CTRL_WORD, ctrl,
                ctrl == CTRL_WORD ? "OK" : "MISMATCH");
  if (ctrl != CTRL_WORD) {
    Serial.println("  SPI not talking. 0x0000 = no SDO / chip unpowered (check 3V3 + 12 V on J9);"
                   " 0xFFFF = MISO floating/shorted high; other = wiring or SPI mode.");
  }
  return ctrl == CTRL_WORD;
}

void setup() {
  pinMode(PIN_LATCH, OUTPUT);
  digitalWriteFast(PIN_LATCH, HIGH);

  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}
  delay(10);

  AD_SPI.setMOSI(PIN_MOSI);
  AD_SPI.setMISO(PIN_MISO);
  AD_SPI.setSCK(PIN_SCK);
  AD_SPI.begin();
  Serial.println("\n=== AD5420 4-20 mA sweep test (Teensy daughtercard, SPI1) ===");
  initAD5420();
  printStatus();
  printHelp();
}

void loop() {
  if (!pollLine()) return;
  char* s = gLine;
  while (*s == ' ') s++;
  if (!*s) return;

  if (!strcmp(s, "s"))       autoSweep();
  else if (!strcmp(s, "g"))  guidedSweep();
  else if (!strcmp(s, "t"))  triangleRamp();
  else if (!strcmp(s, "x"))  { ad5420Write(REG_DATA, 0); Serial.println("4 mA"); }
  else if (!strcmp(s, "?"))  printStatus();
  else if (!strcmp(s, "h"))  printHelp();
  else if (!strcmp(s, "i"))  initAD5420();
  else if (s[0] == 'R' && s[1] == ' ') {
    float r = atof(s + 2);
    if (r > 0) { gLoadOhms = r; printSetupBanner(); } else Serial.println("bad value");
  }
  else if (!strncmp(s, "step ", 5)) {
    float st = atof(s + 5);
    if (st >= 0.25f && st <= 16.0f) { gStep_mA = st; Serial.printf("step %.3f mA\n", gStep_mA); }
    else Serial.println("step must be 0.25..16 mA");
  }
  else if (!strncmp(s, "dwell ", 6)) { gDwell_ms = strtoul(s + 6, nullptr, 10); Serial.printf("dwell %lu ms\n", gDwell_ms); }
  else if (!strcmp(s, "u v")) { gUnitsVolts = true;  Serial.println("guided readings in volts across load"); }
  else if (!strcmp(s, "u i")) { gUnitsVolts = false; Serial.println("guided readings in mA (series meter)"); }
  else if ((s[0] >= '0' && s[0] <= '9') || s[0] == '.') {
    float mA = atof(s);
    if (mA < 4.0f || mA > 20.0f) { Serial.println("range is 4..20 mA"); return; }
    Point p = { mA, 0, 0, 0, EXP_LINEAR, true, NAN };
    applyPoint(p, 50);
    Serial.printf("Holding %.4f mA (code 0x%04X, readback 0x%04X). Expect %s%.3f V across load. Status 0x%04X [%s]\n",
                  mA_forCode(p.code), p.code, p.rbData, p.expect == EXP_LINEAR ? "" : "~",
                  min(mA * 1e-3f * gLoadOhms, complianceV()), p.status, faultCheck(p));
  }
  else Serial.println("? unknown command (h for help)");
}
