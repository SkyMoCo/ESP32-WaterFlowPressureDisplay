# ESP32 Water Flow & Pressure Display

Firmware for an ESP32 that reads the well's flow meter and pressure sensor,
shows both on two 1.28" round displays, and publishes everything to MQTT.

It builds on [ESP32-Water-Meter-Monitor](../ESP32-Water-Meter-Monitor) and
keeps that project's pulse qualification, pressure math, NVS persistence and
MQTT topics and payloads, so existing dashboards and history carry on
unchanged. The display wiring follows
[The Solar Universe's two-GC9A01 build](https://thesolaruniverse.wordpress.com/2024/01/02/esp32-microcontroller-with-two-circular-240240-pixel-displays-gca901/),
with the pins moved off the ones the meter already uses.

## Hardware

- DOIT ESP32 DevKit V1 (ESP32-WROOM-32)
- EKM 3/4" pulse meter on GPIO 4, 0-100 PSI sensor on GPIO 34, status LED on
  GPIO 2. These are wired exactly as in the meter project, including the
  1k/100nF/100R flow front end and the 10k/10k pressure divider; see its
  ReadMe for why each part is there.
- 2 × 1.28" 240×240 round TFT, GC9A01 controller, 3.3 V, about 50 mA each

### Display wiring

| ESP32 | Pressure display | Flow display |
|---|---|---|
| 3V3 | VCC | VCC |
| GND | GND | GND |
| GPIO 18 | SCL (SCLK) | SCL (SCLK) |
| GPIO 23 | SDA (MOSI) | SDA (MOSI) |
| GPIO 16 | DC | DC |
| GPIO 17 | RST | RST |
| GPIO 21 | CS | — |
| GPIO 22 | — | CS |
| (BL/BLK, if present) | 3V3 or unconnected | 3V3 or unconnected |

The article puts RST on GPIO 4 and DC on GPIO 2, but those pins are the flow
input and the LED here, so both move. GPIO 16/17 are free on a WROOM-32. On a
WROVER module they belong to the PSRAM, and DC/RST would need other pins
(update `platformio.ini`).

Both displays share every line except CS. The firmware brings both CS pins low
for `tft.init()`, so both controllers get the init sequence together. After
that, each draw selects only one of them.

## Displays

- **Left dial, pressure.** 0-100 PSI arc. It is green between
  `GAUGE_PSI_LOW` and `GAUGE_PSI_HIGH` (30 and 70 by default), red below that
  range and orange above it. Set the thresholds just outside your pressure
  switch's cut-in and cut-out. The footer shows `ONLINE`, `NO MQTT` or
  `NO WIFI`. If the sensor voltage leaves its valid range (open or shorted
  wire), the dial shows `--` and `SENSOR FAULT`.
- **Right dial, flow.** 0-20 GPM arc, with the running gallon total in the
  footer. The arc turns red above `MAX_PLAUSIBLE_GPM`.

The gauge reads flow from the time between the last two pulses. The 5 s
interval average moves in 0.9 GPM steps at low flow, which is too coarse and
slow for a needle. When pulses stop, the reading decays toward zero and reaches
zero after `FLOW_TIMEOUT_MS` (60 s).

Arcs are repainted in place and the numbers are drawn to off-screen sprites,
so the displays don't flicker.

## MQTT

Topics and payloads are the same as in the meter project, with two added
fields:

- `ranch/water/flow`: adds `gpm_inst`, the pulse-period rate the gauge shows,
  next to the existing interval-average `gpm`
- `ranch/water/pressure`: adds `sensor_ok`. Its `psi`/`volts` values are now a
  ~0.5 s moving average instead of a single ADC read.
- `ranch/water/diag` and `ranch/water/status` are unchanged. The boot message
  ends with `display=dual_gc9a01`.

WiFi and MQTT run in their own FreeRTOS task on core 0, so reconnect attempts
never stall the displays.

## Setup

1. Copy [include/secrets.h.template](include/secrets.h.template) to
   `include/secrets.h` and fill it in. It is gitignored.
2. **Client ID:** if this board replaces the old one, leave `MQTT_CLIENT_ID`
   as `pumphouse-esp32`. If both will run at once, change it. Two clients with
   the same ID keep disconnecting each other.
3. **Running total:** the total is stored in the board's own flash, so a
   fresh board starts at 0 gallons. Read the old board's `pulse_count` from
   MQTT before swapping if you want to carry it over.
4. Build and upload with PlatformIO (env `esp32doit-devkit-v1`). TFT_eSPI is
   configured entirely through `build_flags` in
   [platformio.ini](platformio.ini), so don't edit the library's
   `User_Setup.h`.

If the image is mirrored or colours are wrong on your particular modules, try
`DISPLAY_ROTATION` in `main.cpp`, or add `-D TFT_RGB_ORDER=TFT_BGR` /
`-D TFT_INVERSION_ON` to `build_flags`.
