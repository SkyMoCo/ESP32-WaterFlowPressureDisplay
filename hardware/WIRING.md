# Wiring

Everything that connects to the ESP32, on one page. Pin assignments come from
[src/main.cpp](../src/main.cpp) and [platformio.ini](../platformio.ini); if you
change them there, change them here.

## Pin map

| GPIO | Goes to | Notes |
|---|---|---|
| 4 | flow meter reed, through its front end | needs the 1k pull-up below |
| 34 | pressure sensor, through its divider | input-only, ADC1 — must not move to ADC2 |
| 2 | status LED | onboard blue LED; also broken out |
| 18 | both displays, SCL / SCLK | shared |
| 23 | both displays, SDA / MOSI | shared |
| 16 | both displays, DC | shared |
| 17 | pressure display RST | |
| 27 | flow display RST | |
| 21 | pressure display CS | |
| 22 | flow display CS | |
| 25 | *free* — suggested I2C SDA | see below |
| 26 | *free* — suggested I2C SCL | see below |

Leave alone: GPIO 6-11 (SPI flash), GPIO 0/5/12/15 (strapping pins), GPIO 35/36/39
(input-only, no pull-ups).

## Power

```
 USB-C wall adapter ──► DevKit USB-C
                         │
                         ├─ 3V3 pin ──► both display VCC   (~50 mA each)
                         │              flow front end (R1)
                         │
                         └─ VIN pin ──► pressure sensor +5V
```

VIN is USB 5 V passed through, which only exists because the board runs off a
USB adapter. On a bare 3.3 V supply the pressure sensor would need its own 5 V.

Total draw is about 250 mA, so any phone charger will do. In a shed, solder
power to VIN/GND or glue the USB plug in — see [the shed notes](#in-an-unheated-shed).

## Displays

Two 1.28" 240×240 GC9A01 round modules. They share every line except CS and
RST, because only the display whose CS is low listens.

```
   GPIO 18 ─────┬──────────────┬─── SCL
   GPIO 23 ─────┼──────────────┼─── SDA
   GPIO 16 ─────┼──────────────┼─── DC
   3V3 ─────────┼──────────────┼─── VCC
   GND ─────────┼──────────────┼─── GND
                │              │
   GPIO 21 ─────┘ (CS)         │
   GPIO 17 ─────┘ (RST)        │
                   GPIO 22 ────┘ (CS)
                   GPIO 27 ────┘ (RST)

              PRESSURE          FLOW
```

BL/BLK, if your module has it, goes to 3V3 or stays unconnected — most modules
pull it up on board.

**SDA and SCL are easy to swap by mistake.** That gives a lit screen showing
nothing, because the clock arrives on the data pin. If a display stays black,
check those two first, then CS and RST: `pio run -e displaytest -t upload`
paints solid colours and tells them apart.

## Flow meter

EKM 3/4" pulse meter: a dry-contact reed switch, no polarity, on its factory
24" armored lead.

```
 3V3 ──[ R1 1k ]──┬─────────────── GPIO 4
                  │
                  ├──[ C1 100nF ]── GND
                  │
                  └──[ R2 100R ]──══ armored pair ══[ REED ]══ GND
```

| Ref | Part | Why |
|---|---|---|
| R1 | 1 kΩ to 3V3 | **required** — the pin floats without it |
| C1 | 100 nF to GND | 100 µs with R1; swallows transients |
| R2 | 100 Ω | limits C1's discharge into the reed on closure |

R1 replaces the internal pull-up and is the whole fix for phantom pulses. At
the internal 45 kΩ it takes only ~70 µA of coupled noise to fake an edge; at
1 kΩ it takes 3.3 mA, which contactor noise through a few pF cannot supply.
Shielding and grounding were both tried first and neither helped. The full
reasoning is in the [meter project's ReadMe](../../ESP32-Water-Meter-Monitor/ReadMe.md).

Land the cable armor on GND at the enclosure entry, **one point only**.

## Pressure sensor

0-100 PSI, 0.5-4.5 V linear output, 5 V supply.

```
 VIN (5V) ──► sensor +
 GND ───────► sensor −
                        0.5-4.5V
 sensor signal ──[ 10k ]──┬── GPIO 34   (0.25-2.25V here)
                          │
                          └──[ 10k ]── GND
```

**Never wire the 4.5 V output straight to a GPIO.** Two constraints set this
divider: GPIO 34 is on ADC1, because ADC2 belongs to the WiFi radio and reads
garbage once connected; and at 11 dB the ADC is only linear over roughly
150-2450 mV, so 10k/10k keeps the whole 0-100 PSI span inside that window.

## Status LED

GPIO 2 drives the onboard blue LED, flashed on each MQTT publish. The pin is
also broken out, so an external LED can share it:

```
 GPIO 2 ──[ 220-330R ]──►|── GND
                        LED
```

## I2C expansion board

Nothing in the firmware uses I2C yet, so the pins are your choice — but **not
the default 21/22**, which are the two display chip selects here. GPIO 25 and
26 are free and adjacent on the header:

```
 GPIO 25 ──► SDA        plus 3V3 and GND to the board
 GPIO 26 ──► SCL        4k7 pull-ups to 3V3 if the board has none
```

Most breakout boards include the pull-ups. Two devices on one bus need
different addresses.

## In an unheated shed

Dupont jumpers are a friction fit on tin-plated contacts. Thermal cycling and
damp air loosen them and grow oxide, so a display works for months and then
goes blank on a cold morning. For a permanent install:

- **Solder the display wires**, ideally straight to the module pads with the
  pin header removed — lower profile and a better joint.
- **Keep one serviceable connector**: terminate the harness in a female header
  that plugs onto the DevKit, so a dead ESP32 can be swapped.
- **Stranded wire, not solid.** Solid-core cracks at the joint under vibration
  and thermal movement.
- **Heatshrink the joints, hot-glue a strain relief** where the harness leaves
  each board.
- **Clean off the flux.** Residue is hygroscopic.
- **Conformal coat the boards** (acrylic spray, mask the connectors and glass).
  Condensation will kill this long before the cold does.
- **Don't seal the case.** A sealed box breathes as it heats and cools and
  condenses water inside. Leave the vents open and the cable slot draining.

The ESP32 is rated to -40 °C but GC9A01 modules are typically -20 to +70 °C.
Near freezing they go sluggish and washed out — harmless, but below about
-20 °C expect them to be unreadable until things warm up.
