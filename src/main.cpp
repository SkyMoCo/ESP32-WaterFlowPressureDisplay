#include <Arduino.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <driver/gpio.h>   // gpio_get_level() is IRAM-safe; digitalRead() is not guaranteed to be

// ── Flow input ────────────────────────────────────────────────────────────────
// EKM 3/4" pulse meter: dry-contact (normally open) reed switch, no polarity,
// on its factory 24" armored lead.  The ESP32 mounts at the end of that lead,
// so the whole run is ~2 ft -- and a couple of feet from the pump contactor.
//
//   3V3 -> R1 1k -> FLOW_PIN, C1 100nF from FLOW_PIN to GND,
//   FLOW_PIN -> R2 100R -> cable -> reed -> GND.
//   Contact closed -> pin pulled LOW.
//
// R1 REPLACES the internal pull-up, and is the entire fix for the phantom
// pulses the first build counted.  The internal pull-up is ~45k, where only
// ~70 uA of capacitively coupled noise fakes an edge; at 1k it takes 3.3 mA.
// Grounding and the cable armor were both tried first and neither helped --
// capacitive injection into a high-impedance node has no ground path to break.
// C1 (100 us with R1) keeps short transients from flooding this ISR with edges.
#define FLOW_PIN            4        // free GPIO on the DevKit V1 header, not a strapping pin
                                     // (GPIO0/2/5/12/15 are; GPIO6-11 are the SPI flash)
#define FLOW_ACTIVE_LOW     1        // 1 = contact closure drives the pin LOW (reed to GND, pull-up to 3V3)
                                     // 0 = closure drives it HIGH (only if an inverting front end is ever added)
#define USE_INTERNAL_PULLUP 0        // 0 once R1 is fitted; 1 only for bench testing with a bare switch

// Pulse qualification.  A real closure holds the line asserted for tens of ms:
// at 100 pulses/cf a 3/4" meter running at its ~20 GPM rating turns over 4.5
// times a second (224 ms period), so the closure is ~100 ms.  Anything asserted
// for less than MIN_LOW_MS is contact bounce or noise, not water.
#define MIN_LOW_MS          5        // 20x margin against the shortest plausible real closure
#define MIN_PERIOD_MS       20       // reject a second pulse sooner than this (>50 Hz is not physical here)
#define MAX_PLAUSIBLE_GPM   30.0f    // above the meter's rating -> flag the sample as suspect

// ── Calibration ───────────────────────────────────────────────────────────────
// CALIBRATE: run a known volume through the meter and set this to
// actual_pulses / measured_cubic_feet.  100 is what the existing MQTT history
// implies; confirm it against the meter's register face before trusting totals.
#define PULSES_PER_CF     100.0f
#define GAL_PER_CF        7.48052f
#define GAL_PER_PULSE     (GAL_PER_CF / PULSES_PER_CF)

// 0-100 PSI sensor (0.5-4.5V linear output) on well pump discharge, read via a
// 10k (sensor->pin) / 10k (pin->GND) divider so 0.5-4.5V maps to 0.25-2.25V.
// The ESP32's ADC is only linear-and-calibrated over ~150-2450 mV at 11 dB --
// it saturates well below 3.3V, so a divider sized for the full rail would
// clip the top of the pressure range.
#define PRESSURE_PIN            34     // ADC1_CH6.  MUST be ADC1 (GPIO32-39): ADC2 is owned by
                                       // the WiFi radio and analogRead() on it fails while
                                       // connected.  GPIO34 is input-only, which is all we need.
#define PRESSURE_DIVIDER_RATIO  (10.0f / (10.0f + 10.0f))  // R2 / (R1 + R2)
#define PRESSURE_V_MIN          0.5f   // sensor output at 0 PSI
#define PRESSURE_V_MAX          4.5f   // sensor output at 100 PSI
#define PRESSURE_PSI_MAX        100.0f
// A healthy sensor never leaves 0.5-4.5V.  Near 0V means the signal wire is
// open (the divider pulls the pin to GND); near 5V means a short to supply.
#define PRESSURE_V_FAULT_LO     0.25f
#define PRESSURE_V_FAULT_HI     4.8f

#define LED_PIN           2          // onboard blue LED on the DevKit V1.  Also broken out, so an
                                     // external LED can hang off the same pin through its own
                                     // 220-330R.  (The old GPIO10 is wired to the SPI flash on
                                     // WROOM-32 and is not usable.)

// ── Displays ──────────────────────────────────────────────────────────────────
// Two 1.28" 240x240 GC9A01 round displays on one SPI bus.  SCLK/MOSI/DC/RST are
// shared and set in platformio.ini; each display has its own CS, driven here.
// Only the display whose CS is LOW listens, so one TFT_eSPI instance draws to
// either by flipping CS between draws.
//
// GPIO16/17 are free on WROOM-32; on a WROVER module they are the PSRAM bus
// and DC/RST would have to move.
#define DISPLAY_CS_PRESSURE   21
#define DISPLAY_CS_FLOW       22
#define DISPLAY_ROTATION      0      // 0-3, applied to both displays

// Gauge scales.  Pressure zones colour the arc: below LOW is red (pump not
// keeping up / lost prime), above HIGH is orange (switch not cutting out).
// Set them just outside the pressure switch's cut-in/cut-out.
#define GAUGE_PSI_MAX         100.0f
#define GAUGE_PSI_LOW         30.0f
#define GAUGE_PSI_HIGH        70.0f
#define GAUGE_GPM_MAX         20.0f  // the 3/4" meter's rating

#define PRESSURE_SAMPLE_MS    50
#define PRESSURE_EMA_ALPHA    0.1f   // ~0.5 s time constant at 50 ms samples
#define DISPLAY_FRAME_MS      100
#define GAUGE_EASING          0.35f  // fraction of the remaining distance the arc moves per frame
// With no pulse for this long the display shows 0 GPM.  At 0.075 gal/pulse
// that puts the floor at ~0.07 GPM -- anything slower reads as no flow.
#define FLOW_TIMEOUT_MS       60000

// ── Demo mode ─────────────────────────────────────────────────────────────────
// Build the "demo" env (pio run -e demo) to run with no sensors attached:
// pressure and flow are simulated and fed through the same smoothing, fault
// detection, gauges and MQTT publishing as real readings.  The flow input is
// not attached (GPIO 4 floats without its pull-up and would count noise), NVS
// is left alone so the real running total is never overwritten, and MQTT goes
// to separate topics under a separate client ID.
#ifndef DEMO_MODE
#define DEMO_MODE             0
#endif
#define DEMO_START_GALLONS    12345.0f   // big enough to show the thousands separator

#include "secrets.h"   // copy secrets.h.template → secrets.h and fill in your values

#define MQTT_PORT             1883
#if DEMO_MODE
#define MQTT_TOPIC_ROOT       "ranch/water-demo"
#define MQTT_CLIENT_ID        "pumphouse-esp32-demo"
#else
#define MQTT_TOPIC_ROOT       "ranch/water"
#define MQTT_CLIENT_ID        "pumphouse-esp32"   // must be unique on the broker: change it if the
                                                  // old ESP32-Water-Meter-Monitor board stays online
#endif
#define MQTT_TOPIC            MQTT_TOPIC_ROOT "/flow"
#define MQTT_TOPIC_PRESSURE   MQTT_TOPIC_ROOT "/pressure"
#define MQTT_TOPIC_STATUS     MQTT_TOPIC_ROOT "/status"
#define MQTT_TOPIC_DIAG       MQTT_TOPIC_ROOT "/diag"
// Uncomment if broker requires auth:
// #define MQTT_USER   "user"
// #define MQTT_PASS   "pass"

#define PUBLISH_MS         5000     // publish interval
#define NVS_SAVE_MS        300000   // flush total pulses to flash every 5 min (only if it changed)
#define MQTT_RETRY_MS      5000
#define WIFI_RESTART_MS    30000    // re-issue WiFi.begin() if auto-reconnect hasn't managed it by then

#define MIN_LOW_US     (MIN_LOW_MS * 1000ULL)
#define MIN_PERIOD_US  (MIN_PERIOD_MS * 1000ULL)

// ── ISR state ─────────────────────────────────────────────────────────────────
// portMUX protects 32/64-bit variables shared between ISR and main loop.
static portMUX_TYPE      isr_mux        = portMUX_INITIALIZER_UNLOCKED;
static volatile uint32_t intervalPulses = 0;
static volatile uint64_t totalPulses    = 0;

// Diagnostics: every edge is accounted for, so the published counters say
// whether the front end is clean or still picking up noise.
static volatile uint32_t edgeCount     = 0;   // interrupts seen
static volatile uint32_t shortLowCount = 0;   // asserted too briefly -- noise, or normal contact bounce
static volatile uint32_t tooFastCount  = 0;   // valid-looking but impossibly soon after the last accepted pulse

static volatile uint64_t assertedUs    = 0;   // start of the closure currently in progress, 0 if none
static volatile uint64_t lastAcceptUs  = 0;
static volatile uint64_t lastPeriodUs  = 0;   // time between the last two accepted pulses, 0 until there are two

// ── ISR ───────────────────────────────────────────────────────────────────────
// Qualification happens entirely in here, so nothing is lost while other code
// is busy. A pulse is accepted only on RELEASE, and only if the contact stayed
// asserted for MIN_LOW_MS -- a transient cannot satisfy that.
void IRAM_ATTR onEdge() {
    const uint64_t now      = esp_timer_get_time();
    const int      level    = gpio_get_level((gpio_num_t)FLOW_PIN);
#if FLOW_ACTIVE_LOW
    const bool     asserted = (level == 0);
#else
    const bool     asserted = (level != 0);
#endif

    portENTER_CRITICAL_ISR(&isr_mux);
    ++edgeCount;
    if (asserted) {
        // Start of a candidate closure. Bounce mid-closure just restarts the
        // timing, which costs at most one pulse's worth of width, never a count.
        assertedUs = now;
    } else if (assertedUs != 0) {
        const uint64_t heldUs = now - assertedUs;
        assertedUs = 0;
        if (heldUs < MIN_LOW_US) {
            ++shortLowCount;
        } else if (lastAcceptUs != 0 && (now - lastAcceptUs) < MIN_PERIOD_US) {
            ++tooFastCount;
        } else {
            lastPeriodUs = lastAcceptUs ? now - lastAcceptUs : 0;
            lastAcceptUs = now;
            ++intervalPulses;
            ++totalPulses;
        }
    }
    // A release with assertedUs == 0 means we booted mid-closure; ignore it
    // rather than crediting a pulse of unknown length.
    portEXIT_CRITICAL_ISR(&isr_mux);
}

// ── Shared state between loop() (core 1) and the network task (core 0) ───────
static portMUX_TYPE   data_mux      = portMUX_INITIALIZER_UNLOCKED;
static float          sharedPsi     = 0.0f;
static float          sharedVolts   = 0.0f;
static bool           sharedSensorOk = false;
static volatile bool  wifiUp        = false;   // single-byte flags: plain reads/writes are atomic
static volatile bool  mqttUp        = false;

// ── Peripherals ───────────────────────────────────────────────────────────────
static WiFiClient   wifiClient;
static PubSubClient mqtt(wifiClient);
static Preferences  prefs;
static uint64_t     lastSavedTotal = 0;

// TFT_eSPI caches the last column/row it addressed so drawPixel() can skip
// resending them.  That cache belongs to whichever display was selected when
// it was filled, so it must be dropped on every switch or the other display
// gets pixels at the wrong address.
class DualTFT : public TFT_eSPI {
public:
    void forgetAddressWindow() { addr_row = 0xFFFF; addr_col = 0xFFFF; }
};

static DualTFT      tft;
static TFT_eSprite  readoutSpr(&tft);   // centre number; drawn off-screen so it never flickers
static TFT_eSprite  footerSpr(&tft);    // small status line in the gap at the bottom of the dial

// ── Helpers ───────────────────────────────────────────────────────────────────
// Skips the write when nothing moved -- a well that sits idle would otherwise
// burn a flash write every 5 minutes for no reason.
static void nvsFlush() {
    portENTER_CRITICAL(&isr_mux);
    uint64_t total = totalPulses;
    portEXIT_CRITICAL(&isr_mux);
    if (total == lastSavedTotal) return;
    prefs.putULong64("total", total);
    lastSavedTotal = total;
}

// Reads the pressure sensor, undoes the divider, and maps 0.5-4.5V to 0-100 PSI.
static float readPressurePsi(float* outSensorVolts) {
    const uint32_t mv       = analogReadMilliVolts(PRESSURE_PIN);  // calibrated mV at the pin
    const float    vAtPin   = mv / 1000.0f;
    const float    vSensor  = vAtPin / PRESSURE_DIVIDER_RATIO;
    if (outSensorVolts) *outSensorVolts = vSensor;
    return (vSensor - PRESSURE_V_MIN) / (PRESSURE_V_MAX - PRESSURE_V_MIN) * PRESSURE_PSI_MAX;
}

// Flow rate for the display, from the spacing of the last two pulses.  The
// 5 s interval average published to MQTT moves in 0.9 GPM steps at low flow
// (one pulse per interval), too coarse and too slow for a gauge.  Once the
// meter goes quiet the estimate decays as gal/elapsed, so the needle falls
// smoothly instead of holding the last rate until the timeout.
#if DEMO_MODE
static volatile float demoGpm = 0.0f;   // written on core 1, read on both; 32-bit, so atomic
#endif

static float instantaneousGpm() {
#if DEMO_MODE
    return demoGpm;
#else
    portENTER_CRITICAL(&isr_mux);
    const uint64_t last   = lastAcceptUs;
    const uint64_t period = lastPeriodUs;
    portEXIT_CRITICAL(&isr_mux);

    if (last == 0 || period == 0) return 0.0f;
    const uint64_t since = esp_timer_get_time() - last;
    if (since > FLOW_TIMEOUT_MS * 1000ULL) return 0.0f;
    const uint64_t spanUs = since > period ? since : period;
    return GAL_PER_PULSE / (spanUs / 60e6f);
#endif
}

#if DEMO_MODE
// Stands in for readPressurePsi() and the flow ISR.  Every few seconds it picks
// a new random pressure and flow, then glides toward them the way the real
// system moves.  Some picks deliberately land in the low/high pressure zones,
// above MAX_PLAUSIBLE_GPM, or in a sensor fault, so every display state shows
// up within a minute or two.
static float demoReadPressurePsi(float* outSensorVolts) {
    static unsigned long nextChange = 0;
    static unsigned long lastMs     = millis();
    static float         psiTarget  = 50.0f, psiNow = 50.0f;
    static float         gpmTarget  = 0.0f,  gpmNow = 0.0f;
    static float         pulseFrac  = 0.0f;
    static bool          fault      = false;

    const unsigned long now = millis();
    const float         dt  = (now - lastMs) / 1000.0f;
    lastMs = now;

    if (now >= nextChange) {
        nextChange = now + random(2000, 6000);
        const long p = random(100);
        fault     = p < 4;
        psiTarget = p < 12 ? random(5, 30) : p < 20 ? random(72, 96) : random(35, 69);
        const long f = random(100);
        gpmTarget = f < 25 ? 0.0f
                  : f < 30 ? random(310, 350) / 10.0f     // over MAX_PLAUSIBLE_GPM -> red arc
                  :          random(10, 200) / 10.0f;
    }

    psiNow += (psiTarget - psiNow) * 0.05f;
    gpmNow += (gpmTarget - gpmNow) * 0.08f;
    if (gpmTarget == 0.0f && gpmNow < 0.05f) gpmNow = 0.0f;
    demoGpm = gpmNow;

    // Credit whole pulses the way the ISR would, so the total and the MQTT
    // interval average track the simulated flow.
    pulseFrac += gpmNow / 60.0f * dt / GAL_PER_PULSE;
    const uint32_t whole = (uint32_t)pulseFrac;
    pulseFrac -= whole;
    if (whole) {
        portENTER_CRITICAL(&isr_mux);
        intervalPulses += whole;
        totalPulses    += whole;
        portEXIT_CRITICAL(&isr_mux);
    }

    // Report through volts like the real sensor, so the fault check in loop()
    // is exercised too: an open signal wire reads 0 V.
    const float psi   = psiNow + random(-5, 6) / 10.0f;
    const float volts = fault ? 0.0f
                              : PRESSURE_V_MIN + psi / PRESSURE_PSI_MAX * (PRESSURE_V_MAX - PRESSURE_V_MIN);
    if (outSensorVolts) *outSensorVolts = volts;
    return (volts - PRESSURE_V_MIN) / (PRESSURE_V_MAX - PRESSURE_V_MIN) * PRESSURE_PSI_MAX;
}
#endif

// ── Network task ──────────────────────────────────────────────────────────────
// WiFi and MQTT run on core 0 so a dropped connection or dead broker, which
// can stall PubSubClient for seconds at a time, never freezes the gauges.
static void publishReadings() {
    portENTER_CRITICAL(&isr_mux);
    const uint32_t n         = intervalPulses;
    intervalPulses           = 0;
    const uint64_t tot       = totalPulses;
    const uint32_t edges     = edgeCount;     edgeCount     = 0;
    const uint32_t shortLows = shortLowCount; shortLowCount = 0;
    const uint32_t tooFast   = tooFastCount;  tooFastCount  = 0;
    portEXIT_CRITICAL(&isr_mux);

    const float cfTotal      = tot / PULSES_PER_CF;
    const float totalGallons = cfTotal * GAL_PER_CF;
    const float gpm          = (n / PULSES_PER_CF) * GAL_PER_CF / (PUBLISH_MS / 60000.0f);
    const bool  suspect      = gpm > MAX_PLAUSIBLE_GPM;

    char payload[224];
    snprintf(payload, sizeof(payload),
             "{\"gpm\":%.2f,\"gpm_inst\":%.2f,\"gallons_total\":%.2f,\"cf_total\":%.2f,"
             "\"pulse_count\":%llu,\"suspect\":%s}",
             gpm, instantaneousGpm(), totalGallons, cfTotal, (unsigned long long)tot,
             suspect ? "true" : "false");
    Serial.println(payload);

    // edges should be almost exactly 2x accepted when the front end is
    // clean (one assert + one release per pulse). A large short_lows count
    // with zero accepted means noise is still getting in.
    char diagPayload[160];
    snprintf(diagPayload, sizeof(diagPayload),
             "{\"edges\":%lu,\"accepted\":%lu,\"short_lows\":%lu,"
             "\"too_fast\":%lu,\"pin\":%d,\"rssi\":%d}",
             (unsigned long)edges, (unsigned long)n, (unsigned long)shortLows,
             (unsigned long)tooFast, gpio_get_level((gpio_num_t)FLOW_PIN),
             WiFi.RSSI());
    Serial.println(diagPayload);

    portENTER_CRITICAL(&data_mux);
    const float psi      = sharedPsi;
    const float volts    = sharedVolts;
    const bool  sensorOk = sharedSensorOk;
    portEXIT_CRITICAL(&data_mux);
    char pressurePayload[80];
    snprintf(pressurePayload, sizeof(pressurePayload),
             "{\"psi\":%.1f,\"volts\":%.3f,\"sensor_ok\":%s}",
             psi, volts, sensorOk ? "true" : "false");
    Serial.println(pressurePayload);

    if (mqtt.connected()) {
        digitalWrite(LED_PIN, HIGH);
        mqtt.publish(MQTT_TOPIC,          payload,         /*retained=*/false);
        mqtt.publish(MQTT_TOPIC_DIAG,     diagPayload,     /*retained=*/false);
        mqtt.publish(MQTT_TOPIC_PRESSURE, pressurePayload, /*retained=*/false);
        vTaskDelay(pdMS_TO_TICKS(100));
        digitalWrite(LED_PIN, LOW);
    }
}

static void networkTask(void*) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    Serial.printf("WiFi connecting to \"%s\"\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt.setKeepAlive(60);
    mqtt.setSocketTimeout(5);

    unsigned long wifiDownSince = millis();
    unsigned long lastMqttTry   = 0;
    unsigned long lastPublish   = millis();
    bool          bootSent      = false;
    bool          wasUp         = false;

    for (;;) {
        const unsigned long now = millis();

        if (WiFi.status() == WL_CONNECTED) {
            if (!wasUp) Serial.printf("WiFi OK  IP=%s\n", WiFi.localIP().toString().c_str());
            wasUp = true;
            wifiUp = true;

            if (!mqtt.connected() && now - lastMqttTry >= MQTT_RETRY_MS) {
                lastMqttTry = now;
                Serial.print("MQTT connecting... ");
#if defined(MQTT_USER) && defined(MQTT_PASS)
                const bool ok = mqtt.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS);
#else
                const bool ok = mqtt.connect(MQTT_CLIENT_ID);
#endif
                Serial.println(ok ? "OK" : "FAILED");

                if (ok && !bootSent) {
                    bootSent = true;
                    portENTER_CRITICAL(&isr_mux);
                    const uint64_t tot = totalPulses;
                    portEXIT_CRITICAL(&isr_mux);
                    char statusMsg[160];
                    snprintf(statusMsg, sizeof(statusMsg),
                             "boot pin=%d active_low=%d pulses_per_cf=%.0f min_low_ms=%d "
                             "total_pulses=%llu total_cf=%.2f display=dual_gc9a01",
                             FLOW_PIN, FLOW_ACTIVE_LOW, PULSES_PER_CF, MIN_LOW_MS,
                             (unsigned long long)tot, tot / PULSES_PER_CF);
                    mqtt.publish(MQTT_TOPIC_STATUS, statusMsg);
                    Serial.println(statusMsg);
                }
            }
            mqtt.loop();
        } else {
            if (wasUp) {
                Serial.println("WiFi lost");
                wifiDownSince = now;
            }
            wasUp  = false;
            wifiUp = false;
            if (now - wifiDownSince >= WIFI_RESTART_MS) {
                wifiDownSince = now;
                Serial.println("WiFi restarting");
                WiFi.disconnect();
                WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
            }
        }
        mqttUp = mqtt.connected();

        // Publishes (or at least logs) on schedule even offline, so the
        // interval counters are cleared at the same cadence either way.
        if (now - lastPublish >= PUBLISH_MS) {
            lastPublish = now;
            publishReadings();
        }

        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

// ── Gauges ────────────────────────────────────────────────────────────────────
// TFT_eSPI arc angles: 0 = 6 o'clock, increasing clockwise.  The dial sweeps
// 280 degrees and leaves a gap at the bottom for the status line.
#define CX              120
#define CY              120
#define ARC_START       40
#define ARC_END         320
#define ARC_R           117
#define ARC_IR          101
#define TICK_R_OUT      97
#define TICK_R_MAJOR    86
#define TICK_R_MINOR    91
#define LABEL_R         74

#define COL_BG          TFT_BLACK
#define COL_TRACK       0x2124      // dark grey
#define COL_TICK        0xBDF7      // light grey
#define COL_DIM         0x8410
#define COL_TEXT        TFT_WHITE
#define COL_PSI_OK      0x2FE6      // green
#define COL_PSI_LOW     TFT_RED
#define COL_PSI_HIGH    0xFC60      // orange
#define COL_FLOW        0x05FF      // cyan-blue
#define COL_FAULT       TFT_RED
#define COL_WARN        0xFE60      // amber

#define READOUT_W       150
#define READOUT_H       50
#define READOUT_Y       96          // top edge
#define FOOTER_W        136
#define FOOTER_H        18
#define FOOTER_Y        198

struct Gauge {
    uint8_t     cs;
    const char* title;
    const char* unit;
    float       max;
    float       majorStep;
    int         minorPerMajor;
    int         decimals;
    // Last drawn state -- each part is repainted only when it changes.
    float       shown;
    int         arcAngle;
    uint16_t    arcColor;
    char        readout[12];
    char        footer[24];
    uint16_t    footerColor;
};

#if DEMO_MODE
#define TITLE_PREFIX    "DEMO "     // so simulated numbers are never mistaken for real ones
#define COL_TITLE       COL_WARN
#else
#define TITLE_PREFIX    ""
#define COL_TITLE       COL_DIM
#endif

static Gauge pressureGauge = { DISPLAY_CS_PRESSURE, TITLE_PREFIX "PRESSURE", "PSI",
                               GAUGE_PSI_MAX, 20.0f, 4, 0,  0.0f, -1, 0, "", "", 0 };
static Gauge flowGauge     = { DISPLAY_CS_FLOW,     TITLE_PREFIX "FLOW",     "GPM",
                               GAUGE_GPM_MAX, 5.0f,  5, 1,  0.0f, -1, 0, "", "", 0 };

// Both CS lines are driven explicitly rather than toggled, so a display can
// never be left selected alongside the other.
static void selectDisplay(const Gauge* g) {
    digitalWrite(DISPLAY_CS_PRESSURE, (g == &pressureGauge) ? LOW : HIGH);
    digitalWrite(DISPLAY_CS_FLOW,     (g == &flowGauge)     ? LOW : HIGH);
    tft.forgetAddressWindow();
}

static void selectBothDisplays() {
    digitalWrite(DISPLAY_CS_PRESSURE, LOW);
    digitalWrite(DISPLAY_CS_FLOW,     LOW);
    tft.forgetAddressWindow();
}

static void deselectDisplays() {
    digitalWrite(DISPLAY_CS_PRESSURE, HIGH);
    digitalWrite(DISPLAY_CS_FLOW,     HIGH);
}

static int valueToAngle(const Gauge& g, float v) {
    if (v < 0.0f)  v = 0.0f;
    if (v > g.max) v = g.max;
    return ARC_START + (int)lroundf(v / g.max * (ARC_END - ARC_START));
}

static void polar(int angle, float r, float* x, float* y) {
    const float a = angle * DEG_TO_RAD;
    *x = CX - r * sinf(a);
    *y = CY + r * cosf(a);
}

// Static parts of a dial: ticks, scale numbers, title, unit.  Drawn once.
static void drawDialFace(Gauge& g) {
    selectDisplay(&g);
    tft.fillScreen(COL_BG);
    tft.drawArc(CX, CY, ARC_R, ARC_IR, ARC_START, ARC_END, COL_TRACK, COL_BG, true);

    const int   majors = (int)lroundf(g.max / g.majorStep);
    const int   steps  = majors * g.minorPerMajor;
    for (int i = 0; i <= steps; ++i) {
        const bool  major = (i % g.minorPerMajor) == 0;
        const int   angle = ARC_START + (int)lroundf((float)i / steps * (ARC_END - ARC_START));
        float x0, y0, x1, y1;
        polar(angle, TICK_R_OUT, &x0, &y0);
        polar(angle, major ? TICK_R_MAJOR : TICK_R_MINOR, &x1, &y1);
        tft.drawWideLine(x0, y0, x1, y1, major ? 3.0f : 1.5f, major ? COL_TICK : COL_DIM, COL_BG);

        if (major) {
            float lx, ly;
            polar(angle, LABEL_R, &lx, &ly);
            tft.setTextColor(COL_TICK, COL_BG);
            tft.setTextDatum(MC_DATUM);
            tft.drawNumber(lroundf(i / g.minorPerMajor * g.majorStep), (int)lx, (int)ly, 2);
        }
    }

    tft.setTextDatum(MC_DATUM);
    tft.setTextColor(COL_TITLE, COL_BG);
    tft.drawString(g.title, CX, 80, 2);
    tft.setTextColor(COL_TEXT, COL_BG);
    tft.drawString(g.unit, CX, 162, 4);

    g.arcAngle    = -1;   // force the dynamic parts to repaint
    g.readout[0]  = '\0';
    g.footer[0]   = '\0';
    deselectDisplays();
}

// valid=false greys the arc out and shows dashes (sensor fault).
static void updateGauge(Gauge& g, float target, bool valid, uint16_t color,
                        const char* footer, uint16_t footerColor) {
    // Ease toward the target so the arc glides instead of jumping.  Snap when
    // close, or the arc would creep by one degree for several frames.
    g.shown += (target - g.shown) * GAUGE_EASING;
    if (fabsf(target - g.shown) < g.max * 0.002f) g.shown = target;

    const int      angle    = valid ? valueToAngle(g, g.shown) : ARC_START;
    const uint16_t arcColor = valid ? color : COL_FAULT;

    char text[12];
    if (valid) snprintf(text, sizeof(text), "%.*f", g.decimals, g.shown);
    else       strcpy(text, "--");   // font 7 is 7-segment: digits, '-', '.', ':' only

    const bool arcDirty    = angle != g.arcAngle || arcColor != g.arcColor;
    const bool textDirty   = strcmp(text, g.readout) != 0;
    const bool footerDirty = strcmp(footer, g.footer) != 0 || footerColor != g.footerColor;
    if (!arcDirty && !textDirty && !footerDirty) return;

    selectDisplay(&g);

    // Repainting the filled and empty parts in place (no clear first) is what
    // keeps the arc flicker-free.  drawArc() leaves arc ends un-antialiased,
    // so the two segments butt together cleanly.
    if (arcDirty) {
        tft.drawArc(CX, CY, ARC_R, ARC_IR, ARC_START, angle,   arcColor,  COL_BG, true);
        tft.drawArc(CX, CY, ARC_R, ARC_IR, angle,     ARC_END, COL_TRACK, COL_BG, true);
        g.arcAngle = angle;
        g.arcColor = arcColor;
    }

    if (textDirty) {
        readoutSpr.fillSprite(COL_BG);
        readoutSpr.setTextDatum(MC_DATUM);
        readoutSpr.setTextColor(valid ? COL_TEXT : COL_FAULT, COL_BG);
        readoutSpr.drawString(text, READOUT_W / 2, READOUT_H / 2, 7);
        readoutSpr.pushSprite(CX - READOUT_W / 2, READOUT_Y);
        strcpy(g.readout, text);
    }

    if (footerDirty) {
        footerSpr.fillSprite(COL_BG);
        footerSpr.setTextDatum(MC_DATUM);
        footerSpr.setTextColor(footerColor, COL_BG);
        footerSpr.drawString(footer, FOOTER_W / 2, FOOTER_H / 2, 2);
        footerSpr.pushSprite(CX - FOOTER_W / 2, FOOTER_Y);
        strlcpy(g.footer, footer, sizeof(g.footer));
        g.footerColor = footerColor;
    }

    deselectDisplays();
}

// "1,234,567 gal" -- snprintf has no thousands separator.
static void formatGallons(char* out, size_t n, float gallons) {
    const uint32_t g = (uint32_t)(gallons + 0.5f);
    if (g >= 1000000UL)
        snprintf(out, n, "%lu,%03lu,%03lu gal", (unsigned long)(g / 1000000UL),
                 (unsigned long)(g / 1000UL % 1000UL), (unsigned long)(g % 1000UL));
    else if (g >= 1000UL)
        snprintf(out, n, "%lu,%03lu gal", (unsigned long)(g / 1000UL), (unsigned long)(g % 1000UL));
    else
        snprintf(out, n, "%lu gal", (unsigned long)g);
}

static void displaysInit() {
    pinMode(DISPLAY_CS_PRESSURE, OUTPUT);
    pinMode(DISPLAY_CS_FLOW,     OUTPUT);

    // Both selected: the init sequence, reset pulse and rotation reach both
    // controllers at once, since they share every other line.
    selectBothDisplays();
    tft.init();
    tft.setRotation(DISPLAY_ROTATION);
    deselectDisplays();

    readoutSpr.setColorDepth(16);
    readoutSpr.createSprite(READOUT_W, READOUT_H);
    footerSpr.setColorDepth(16);
    footerSpr.createSprite(FOOTER_W, FOOTER_H);

    drawDialFace(pressureGauge);
    drawDialFace(flowGauge);
}

static void displaysUpdate(float psi, bool sensorOk) {
    // Pressure display carries the connection status in its footer.
    const char* net;
    uint16_t    netColor;
    if (!wifiUp)      { net = "NO WIFI";  netColor = COL_WARN; }
    else if (!mqttUp) { net = "NO MQTT";  netColor = COL_WARN; }
    else              { net = "ONLINE";   netColor = COL_DIM;  }

    uint16_t psiColor = COL_PSI_OK;
    if (psi < GAUGE_PSI_LOW)  psiColor = COL_PSI_LOW;
    if (psi > GAUGE_PSI_HIGH) psiColor = COL_PSI_HIGH;
    updateGauge(pressureGauge, psi, sensorOk, psiColor,
                sensorOk ? net : "SENSOR FAULT", sensorOk ? netColor : COL_FAULT);

    // Flow display carries the running total.
    portENTER_CRITICAL(&isr_mux);
    const uint64_t tot = totalPulses;
    portEXIT_CRITICAL(&isr_mux);
    char total[24];
    formatGallons(total, sizeof(total), tot * GAL_PER_PULSE);

    const float gpm = instantaneousGpm();
    updateGauge(flowGauge, gpm, true, gpm > MAX_PLAUSIBLE_GPM ? COL_FAULT : COL_FLOW,
                total, COL_DIM);
}

// ── Arduino ───────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    pinMode(LED_PIN, OUTPUT);

#if DEMO_MODE
    Serial.println("DEMO MODE: simulated sensors, publishing to " MQTT_TOPIC_ROOT "/*");
    portENTER_CRITICAL(&isr_mux);
    totalPulses = (uint64_t)(DEMO_START_GALLONS / GAL_PER_PULSE);
    portEXIT_CRITICAL(&isr_mux);
#else
    // Restore cumulative pulse count from NVS (survives power loss / reboot).
    prefs.begin("flow", /*readOnly=*/false);
    const uint64_t saved = prefs.getULong64("total", 0);
    portENTER_CRITICAL(&isr_mux);
    totalPulses = saved;
    portEXIT_CRITICAL(&isr_mux);
    lastSavedTotal = saved;
    Serial.printf("Resumed: %llu pulses (%.1f cf, %.1f gal)\n",
                  saved, saved / PULSES_PER_CF, saved / PULSES_PER_CF * GAL_PER_CF);

#if USE_INTERNAL_PULLUP
    pinMode(FLOW_PIN, INPUT_PULLUP);
#else
    pinMode(FLOW_PIN, INPUT);        // external 1k pull-up to 3V3 required -- the pin floats without it
#endif
    // CHANGE, not FALLING: the pulse is qualified by how long it stays
    // asserted, which needs both edges.
    attachInterrupt(digitalPinToInterrupt(FLOW_PIN), onEdge, CHANGE);

    analogSetPinAttenuation(PRESSURE_PIN, ADC_11db);  // widest range; usable/linear to ~2.45V,
                                                      // which the 10k/10k divider stays under
#endif

    displaysInit();

    // Core 0 alongside the WiFi stack; loop() stays on core 1 with the displays.
    xTaskCreatePinnedToCore(networkTask, "net", 8192, nullptr, 1, nullptr, 0);
}

void loop() {
    static unsigned long lastSample  = 0;
    static unsigned long lastFrame   = 0;
    static float        psiAvg      = NAN;
    static float         voltsAvg    = NAN;

    const unsigned long now = millis();

    if (now - lastSample >= PRESSURE_SAMPLE_MS) {
        lastSample = now;
        float       volts = 0.0f;
#if DEMO_MODE
        const float psi   = demoReadPressurePsi(&volts);
#else
        const float psi   = readPressurePsi(&volts);
#endif
        if (isnan(psiAvg)) { psiAvg = psi; voltsAvg = volts; }
        psiAvg   += (psi   - psiAvg)   * PRESSURE_EMA_ALPHA;
        voltsAvg += (volts - voltsAvg) * PRESSURE_EMA_ALPHA;

        const bool ok = voltsAvg > PRESSURE_V_FAULT_LO && voltsAvg < PRESSURE_V_FAULT_HI;
        portENTER_CRITICAL(&data_mux);
        sharedPsi      = psiAvg;
        sharedVolts    = voltsAvg;
        sharedSensorOk = ok;
        portEXIT_CRITICAL(&data_mux);
    }

    if (now - lastFrame >= DISPLAY_FRAME_MS) {
        lastFrame = now;
        portENTER_CRITICAL(&data_mux);
        const float psi = sharedPsi;
        const bool  ok  = sharedSensorOk;
        portEXIT_CRITICAL(&data_mux);
        displaysUpdate(psi, ok);
    }

#if !DEMO_MODE
    static unsigned long lastNvsSave = 0;
    if (now - lastNvsSave >= NVS_SAVE_MS) {
        lastNvsSave = now;
        nvsFlush();
    }
#endif

    delay(5);
}
