// Display wiring diagnostic.  Not part of the firmware: build it with
//
//   pio run -e displaytest -t upload
//
// It ignores the sensors and gauges and paints solid colours in three phases,
// so a screen that stays black says which wire is at fault:
//
//   BOTH (red)   -- both CS low, both displays addressed at once.
//   A ONLY (green) -- only the pressure display's CS (21) low.
//   B ONLY (blue)  -- only the flow display's CS (22) low.
//
// Reading the result on the screen that does not work:
//   * red in BOTH, but nothing in its own phase -> its CS pin or jumper
//   * black in every phase                      -> its RST, or a data line
//     (DC/SCLK/MOSI) not actually landing on that module
//   * flickers, partial or corrupt fills         -> signal integrity; drop
//     SPI_FREQUENCY in platformio.ini to 20000000
#include <Arduino.h>
#include <TFT_eSPI.h>

#define CS_A    21   // pressure display
#define CS_B    22   // flow display
#define RST_A   17
#define RST_B   27

static TFT_eSPI tft;

static void cs(bool a, bool b) {
    digitalWrite(CS_A, a ? LOW : HIGH);
    digitalWrite(CS_B, b ? LOW : HIGH);
}

static void fill(uint16_t color, const char* label) {
    tft.fillScreen(color);
    tft.setTextColor(TFT_WHITE, color);
    tft.setTextDatum(MC_DATUM);
    tft.drawString(label, 120, 120, 4);
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\nDisplay wiring test");
    Serial.printf("CS_A=%d CS_B=%d RST_A=%d RST_B=%d DC=%d SCLK=%d MOSI=%d %dHz\n",
                  CS_A, CS_B, RST_A, RST_B, TFT_DC, TFT_SCLK, TFT_MOSI, SPI_FREQUENCY);

    pinMode(CS_A, OUTPUT);
    pinMode(CS_B, OUTPUT);
    pinMode(RST_A, OUTPUT);
    pinMode(RST_B, OUTPUT);

    cs(false, false);
    digitalWrite(RST_A, HIGH); digitalWrite(RST_B, HIGH); delay(5);
    digitalWrite(RST_A, LOW);  digitalWrite(RST_B, LOW);  delay(20);
    digitalWrite(RST_A, HIGH); digitalWrite(RST_B, HIGH); delay(150);

    cs(true, true);
    tft.init();
    tft.setRotation(0);
    cs(false, false);
}

void loop() {
    Serial.println("BOTH (red)");
    cs(true, true);
    fill(TFT_RED, "BOTH");
    cs(false, false);
    delay(3000);

    Serial.println("A ONLY (green) - pressure, CS 21");
    cs(true, false);
    fill(TFT_DARKGREEN, "A ONLY");
    cs(false, false);
    delay(3000);

    Serial.println("B ONLY (blue) - flow, CS 22");
    cs(false, true);
    fill(TFT_BLUE, "B ONLY");
    cs(false, false);
    delay(3000);
}
