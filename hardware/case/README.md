# Wall-mount case

Fusion 360 script that builds the enclosure: [dual_gauge_case.py](dual_gauge_case.py).

In Fusion: **Utilities → Add-Ins → Scripts and Add-Ins → Scripts → green +**,
point it at this folder, select `dual_gauge_case`, **Run**. It opens a new
design and builds four bodies in assembly position.

To change anything, edit `CONFIG` at the top of the script and run it again. It
builds a fresh design each time rather than editing the previous one, so
nothing is lost by re-running.

Default size: **111.2 × 72.6 × 35 mm**, displays side by side.

## The display pocket

These modules are not round. The PCB is a circle with a pin-header tab hanging
off the bottom, so the pocket is a circle plus one slot:

```
      ╭─────────────╮
     │   ╭───────╮   │      window 35.5 through the front face
     │  │  glass  │  │      circle 38.0, seated on a 1.25 wide ledge
     │   ╰┈┈┈┬┬┈┈┈╯   │     relief runs in to 10 from the centre ┈┈┈
      ╰──┬──┴┴──┬──╯
         │      │           tab 23.5 wide (0.925 in)
         └──────┘           tip 26.3 from the circle centre
```

One slot rather than two, so the display can only go in the right way up. Set
`tab_count` to 2 for a module with a tab at each end.

The pocket floor drops **1.6 mm** under the tab for the pin solder joints,
which would otherwise hold the PCB off its seat. That relief carries on past
the seat and in under the round part of the PCB, as far as `relief_in` (10 mm
from the centre), because the joints don't stop at the tab. It stays the tab's
width — widening it would undercut the collar wall and leave it printing over
thin air.

The case stays symmetric about the windows, so the two dials sit centred in the
face even though the modules are lopsided.

The front face thickness (2.5), pocket depth (3.8) and the idea of the solder
relief came from the published MakerWorld case for this module
([model 2001806](https://makerworld.com/en/models/2001806-1-28-round-tft-display-case-gc9a01)),
measured out of its STL meshes. The circle, window and tab are measured off the
real part instead — that case has two symmetrical tab slots and a wider tab
than these modules actually have.

The `CONFIG` values are nominal part sizes; `pcb_fit` (0.4) is added to each
pocket dimension, so a 23.5 tab gets a 23.9 slot. Raise `pcb_fit` to 0.6 if
your printer runs fat.

## Check before you print

[check_case.py](check_case.py) runs the script with the Fusion API stubbed out,
prints the derived sizes, and tests the clearances that are easy to get wrong:

```
python check_case.py
```

Run it after editing `CONFIG`. It has caught clip arms landing on the bracket
studs, a clip post printing over a keyhole, and the back plate sharing space
with the case walls — each of which would have been an hour of wasted print.

## Print the test tile first

Set `test_tile` to `True` and run the script. You get a flat plate with one
pocket, its collar, the screw pads and a pair of clips — about 15 minutes of
printing. Check that the module drops in, sits flat on its seat, and clamps
without rocking. Then set it back to `False` and print the real case.

## Measure before printing

Check these against your own parts and update `CONFIG`:

| Setting | Default | What to measure |
|---|---|---|
| `pcb_dia` | 38.0 | the round part of the PCB |
| `window_dia` | 35.5 | front opening; leaves a 1.25 ledge for the PCB |
| `pcb_tab_w` | 23.5 | tab width — 0.925 in, measured |
| `pcb_tab_reach` | 26.3 | circle centre to the tab tip |
| `tab_count` | 1 | how many tabs your module has |
| `pcb_thick` | 1.6 | PCB thickness |
| `pocket_depth` | 3.8 | PCB plus anything standing proud behind it |
| `esp_pcb_len` / `esp_pcb_wid` | 51.5 / 28.3 | DevKit PCB |
| `depth` | 35.0 | see below |

**Depth is the one to check first.** It has to clear the display headers with
dupont plugs attached (about 14 mm behind the display PCB) plus the ESP32 on
its pads. If your plugs stack deeper, or you use right-angle connectors and
want it slimmer, change `depth`.

## How the ESP32 mounts

`esp_mount` is `'snap'`: four sprung fingers on the back plate grip the board's
long edges. Press it in, and lift a finger with a fingernail to get it out. No
screws, no tape, and nothing that depends on your board having mounting holes.

```
   finger ─┐   ┌─ finger        each finger has a lip 1.0 over the
          ▐█▌ ▐█▌               board edge and a shoulder below it
   ┌───────┴───┴───────┐
   │   DevKit, pins    │        pins point forward, into the case,
   │   toward the      │        so the display jumpers plug on from
   │   front           │        inside while the case is open
   └───────────────────┘
        USB-C ↓ out the bottom slot
```

The board goes in **pins forward** — component side toward the back plate. The
4 mm standoff clears the components, and the header pins face into the case
where you can reach them. The USB connector opening points along the board, so
it lines up with the bottom slot either way up.

The lip reaches 1.0 mm over the edge; the header pads on a DevKit V1 sit about
2.5 mm in, so it grips bare PCB. Worth eyeballing on your board — widen
`esp_lip` if there's room, shrink it if it fouls anything.

Set `esp_mount` to `'pads'` for the older arrangement: four flat pads for foam
tape, or screws if you set `esp_screw_holes` to `True` and measure the hole
spacing into `esp_hole_dx` / `esp_hole_dy`.

## I2C expansion board

`i2c_mount` adds four L-shaped clips to the right of the ESP32, one per corner
of the board. Each is a post with a lip reaching over the corner: tuck two
corners under their lips, then press the other two down.

```
      ┌─┐         ┌─┐        L clips, lip over each corner
      │ └─      ──┘ │
      │  I2C board  │        5 mm standoff, so a bracket stud
      │ ┌─      ──┐ │        head can sit underneath
      └─┘         └─┘
```

**The dimensions are placeholders — measure your board** into `i2c_len`,
`i2c_wid` and `i2c_thick` (defaults 30 × 20 × 1.6). `i2c_x` / `i2c_y` move it
around the plate.

Its position isn't arbitrary: it has to miss the ESP32 cradle on one side, the
case wall on the other, and the bracket's stud heads and keyhole slots
underneath. The default (x = 36, arms 4 mm) straddles the studs with about
1 mm to spare. If you move it or make it bigger, check those clearances —
a clip post over a keyhole would have nothing to print onto.

There's room for a board up to about 26 mm wide in that bay. Anything larger
wants the left-hand side too, or the `ears` mounting style, which has no studs
in the way.

## Printing

No supports anywhere.

| Part | Orientation | Notes |
|---|---|---|
| Case body | Front face on the plate | Gives the best-looking front; the PCB seats are part of the solid front face, so nothing overhangs |
| Back plate | Flat, recess down, snap fingers up | The finger lips are a 1.0 mm overhang, which bridges fine |
| Wall bracket | Flat, studs up | The stud heads overhang 2 mm; fine in PLA, but slow the first layer over them if your printer droops |
| Clips L / Clips R | Flat | Two arcs per display, four in total; small and quick, so print spares |

PLA or PETG, 0.2 mm layers, 3 perimeters. PETG if it hangs anywhere that gets
direct sun or summer heat.

## Hardware

| Qty | Item | Use |
|---|---|---|
| 4 | M3 × 10 self-tapping | back plate into the corner bosses |
| 8 | M2 × 5 self-tapping | display clips (4 per display) |
| 4 | #8 or M4 pan-head wall screws | bracket ears, with drywall anchors |
| — | dupont jumpers | displays to the ESP32 |

## Assembly

1. Drop each display into its pocket from inside, glass toward the window and
   tabs into the two slots, then clamp the PCB rim with the two clips and four
   M2 screws. The clips are notched at the tabs so they clear the headers.
2. Press the DevKit into the snap fingers on the back plate, pins forward and
   the USB-C end toward the bottom.
3. Wire the displays to the ESP32 — see the wiring table in the
   [main ReadMe](../../ReadMe.md). Do this before closing the case; the plugs
   are the tightest thing in there.
4. Feed the USB cable out through the bottom slot and screw the back plate on.
5. Screw the **wall bracket** up on its own, four screws through the ears:
   **121.2 mm apart across, 25.8 mm apart vertically**.
6. Hang the case on it — hold it about 9 mm high so the four studs pass
   through the big holes, then let it drop. The bracket disappears into the
   recess in the back plate and its ears pass through notches in the rim, so
   the case still lies flat on the wall.

To take it down, lift 9 mm and pull. The wall screws stay put. `wall_mount` can
also be `'ears'` (flanges on the case itself) or `'keyhole'` (hang on two proud
screw heads).

## Known rough edges

- The pocket geometry is copied from someone else's case for the same module,
  not measured off your parts. The test tile exists for exactly this reason.
- The 1.6 mm tab relief assumes the pin solder joints are the only thing on
  the front of the tabs. If your module has more there, deepen
  `solder_relief`.
- The keyhole screw heads sit inside the case. They clear the ESP32 and the
  clips, but if you move things around in `CONFIG`, check that first.
- Vents are in the top wall only. Consumption is about 250 mA total, so heat
  isn't really a concern; they're cheap insurance.
