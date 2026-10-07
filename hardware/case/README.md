# Wall-mount case

Fusion 360 script that builds the enclosure: [dual_gauge_case.py](dual_gauge_case.py).

In Fusion: **Utilities → Add-Ins → Scripts and Add-Ins → Scripts → green +**,
point it at this folder, select `dual_gauge_case`, **Run**. It opens a new
design and builds four bodies in assembly position.

To change anything, edit `CONFIG` at the top of the script and run it again. It
builds a fresh design each time rather than editing the previous one, so
nothing is lost by re-running.

Default size: **118.1 × 140.8 × 35 mm** — displays side by side in the top
band, an electronics bay under them. Both the width and the bay height are
derived from what has to fit in that bay, so the case is as small as its
contents allow.

```
   ┌──────────────────────────┐
   │     ( )        ( )       │   display band, 72.6 tall
   │                          │
   ├──────────────────────────┤
   │ ┌───────────────┐ ┌────┐ │   bay, 68.2, sized around the
   │ │  expansion    │ │ I2C│ │   expansion board
   │ │  board + ESP32│ │    │ │
   │ └─╥─────────────┘ └────┘ │
   └───╜──────────────────────┘
     USB out the left wall
```

**Everything mounts to the case body**, on posts off the inside of the front
face. The back plate is a plain lid, so you can wire the whole thing with the
lid off and nothing dangling from it.

Putting the boards beside the displays rather than behind them is also what
makes the case shallow: nothing stacks up front to back, so 32 mm covers the
deepest single item — a display with dupont plugs on, about 20 mm.

`bay_height` is derived from what has to fit (board, mounts, margins, wall), so
the case grows only as much as it must. Set a number to override it, or set
`board_mount` to `'plate'` for the old arrangement with the boards on the lid.

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
| `exp_len` / `exp_wid` | 67 / 51 | expansion board — sets the bay height |
| `i2c_len` / `i2c_wid` | 40 / 21.75 | I2C board — widens the case to fit beside it |
| `esp_pcb_len` / `esp_pcb_wid` | 51.5 / 28.3 | bare DevKit, for the other mount styles |
| `depth` | 35.0 | see below |

**Depth is the one to check first.** With the boards in the bay rather than
behind the displays, it only has to clear the deepest single stack — which is
now the dupont plugs on the expansion board's 3-pin headers at about 23 mm,
plus room for the wires to turn. If you solder straight to the pads instead,
28 mm would do.

## How the ESP32 mounts

`esp_mount` is `'expansion'`: the **ESP32 expansion board, 67 × 51 mm**, with
the DevKit plugged into it. An L-shaped bracket hugs each corner from the
outside, and a glue pad sits inside each corner for the board to bed down on.

```
   ┌─┐                     ┌─┐     L brackets, 2.4 walls, 12 arms
   │ └─┐ ▪    ▪    ▪  ┌──┘   │
   └─┐  └──────────────┘  ┌─┘     9 tape pads, 9 mm square,
     │  ▪    ▪    ▪       │        729 mm² in total
   ┌─┘  ┌──────────────┐  └─┐
   │ ┌─┘ ▪    ▪    ▪  └──┐  │     5 mm standoff clears its
   └─┘                     └─┘      solder tails underneath
```

Tape the pads, drop the board in against the brackets, press down. The brackets
hold it square and stop it sliding while you line it up, and the pad grid gives
double-sided tape real area to grip — a 3 × 3 grid set by `exp_pad_nx` /
`exp_pad_ny`.

Measured values go in `exp_len` / `exp_wid` / `exp_thick`, and `exp_fit` (0.6)
is the slack inside the brackets.

### The two openings

This board (an ESP32 30P expansion board: 3-pin headers down each side, barrel
jack bottom left) needs two holes in the **left wall**, at different heights
because the parts sit at different levels in the stack:

| Opening | Height above the face | Why there |
|---|---|---|
| Barrel jack | z 8.1 – 21.1 | the jack body sits on the expansion PCB |
| USB-C | z 16.6 – 24.6 | the DevKit sits `exp_socket` (8.5) higher, on its header |

They're 3 mm apart along the wall, which is a thin pillar of plastic — so if
you move one, re-run `check_case.py`, which measures that gap.

Aim them with `jack_wall` / `jack_offset` and `usb_wall` / `usb_offset`. The
offsets run along the wall from the **expansion board's centre**, so the jack
at -16.5 is 16.5 mm below centre, near the board's bottom edge. Sizes are
`jack_w` / `jack_h` and `usb_w` / `usb_h`, and they're the hole, not the part.

**This board sets the case height.** The bay is sized around it, so the case is
140.8 mm tall. To trim that: `bay_margin` (5) is the clearance to the bay
walls, and `exp_arm` / `exp_wall` set how much the brackets add.

It also sets the depth. Dupont plugs on those 3-pin headers reach z≈23, so at
35 mm deep there's 5.9 mm between the plugs and the lid for the wires to turn —
the thing that was tight at 32.

For the bare DevKit instead, `esp_mount` can be `'pads'` (four glue pads, same
idea as the I2C board — the bay shrinks to about 41 mm and the case to 113 mm)
or `'snap'` (four sprung fingers gripping the long edges, which add
`esp_rail_w` either side).

## I2C expansion board

`i2c_mount` is `'brackets'`: the **40 × 21.75 mm** board gets L brackets and
glue pads at its corners, exactly like the expansion board, on a 9 mm standoff
so wires can run underneath.

```
   ┌─┐             ┌─┐     40 mm runs up the case, 21.75 across
   │ └┐ ▪       ▪ ┌┘ │
   └┐ └───────────┘ ┌┘     6 tape pads, 6 mm square,
    │  ▪ I2C   ▪    │       216 mm² in total
   ┌┘ ┌───────────┐ └┐
   │ ┌┘ ▪       ▪ └┐ │     2.4 walls, 8 mm arms,
   └─┘             └─┘      standing 2 mm proud
```

**It's turned on its side** (`i2c_rotate`), long edge running up the case. At
40 mm wide it wouldn't fit the column beside a 67 mm expansion board otherwise.

`i2c_x` / `i2c_y` are `None`, which parks it against the free edge of the bay
beside the expansion board. Give them numbers to place it yourself, then re-run
`check_case.py` — it tests the brackets against the expansion board, the bay
walls and the display tabs above.

`i2c_mount` can also be `'standoffs'` (pads only, no brackets, for a board whose
size you'd rather not pin down) or `'clips'` (lipped clips that grip without
tape, but have to match the board closely).

`tape_thick` (1.0) is counted into the bracket height, so the brackets still
stand proud of a board sitting on tape rather than straight on the pads.

## Printing

No supports anywhere.

| Part | Orientation | Notes |
|---|---|---|
| Case body | Front face on the plate | Gives the best-looking front; the PCB seats and the board standoffs all grow upward from it, so nothing overhangs |
| Back plate | Flat, recess down | A plain lid now — no mounts on it |
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
| — | double-sided foam tape | expansion and I2C boards onto their pad grids |

## Assembly

Everything but the lid attaches to the case body, so this all happens with the
case face-down on the bench and the back open.

1. Drop each display into its pocket from inside, glass toward the window and
   the tab into its slot, then clamp the PCB rim with the two clips and four
   M2 screws. The clips are notched at the tab so they clear the header.
2. Tape the pad grids, then press each board down inside its L brackets — the
   expansion board on nine pads, the I2C board on six. The brackets locate
   them, so they go in square. Plug the DevKit into the expansion board.
3. Wire it up — see [hardware/WIRING.md](../WIRING.md). Everything is facing
   you and nothing is attached to the lid, which is the point of this layout.
4. Check the barrel jack and the DevKit's USB-C line up with their holes in
   the left wall, then screw the lid on.
5. Screw the **wall bracket** up on its own, four screws through the ears:
   **128.1 mm apart across, 94.0 mm apart vertically**.
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
