"""Check dual_gauge_case.py without opening Fusion.

Imports the script with the Fusion API stubbed out, prints the derived sizes,
and tests the clearances that are easy to get wrong -- parts landing on each
other, clips printing over holes, pockets breaking through walls.  Run it after
editing CONFIG, before spending an hour of print time:

    python check_case.py

Every check has caught something real at least once.
"""
import math
import os
import sys
import types


class Any(object):
    """Stands in for any Fusion object: every attribute and call works."""
    def __getattr__(self, name):
        return Any()

    def __call__(self, *a, **k):
        return Any()


for name in ('adsk', 'adsk.core', 'adsk.fusion'):
    mod = types.ModuleType(name)
    mod.__getattr__ = lambda n: Any()
    sys.modules[name] = mod
sys.modules['adsk'].core = sys.modules['adsk.core']
sys.modules['adsk'].fusion = sys.modules['adsk.fusion']

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dual_gauge_case as M

cfg = dict(M.CONFIG)
# Always check the real case: in tile mode the outline is the tile's, which
# would make every case-level clearance meaningless.
if cfg['test_tile']:
    print('(CONFIG has test_tile on; checking the full case anyway)')
    cfg['test_tile'] = False
case = M.Case.__new__(M.Case)
M.Case.__init__(case, None, cfg)

PLUG = 14.0          # dupont housing standing off a board
DEVKIT_TALL = 3.2    # components / USB connector height above the PCB

inner_x = case.width / 2 - cfg['wall']
inner_y = case.height / 2 - cfg['wall']
bay_top = case.disp_cy - case.display_h / 2 if case.bay_h else None

print('case          {:.1f} W x {:.1f} H x {:.1f} D'
      .format(case.width, case.height, cfg['depth']))
print('display band  {:.1f} tall, centred y={:+.1f}'.format(case.display_h, case.disp_cy))
if case.bay_h:
    print('bay           {:.1f} tall, centred y={:+.1f}, top edge y={:+.1f}'
          .format(case.bay_h, case.bay_cy, bay_top))
print('pocket        circle {:.1f}, tab {:.1f} wide, {:.1f} reach, glass bore {:.2f}'
      .format(case.pocket_dia, case.pocket_tab_w, case.pocket_tab_reach, case.glass_bore))
print('clip          OD {:.2f}  ID {:.2f}  pads at r={:.2f}'
      .format(case.clip_od, case.clip_id, case.pad_radius))
print('boards on     {}  (base z={:.1f})'
      .format('case body' if case.on_body else 'back plate', case.mount_base_z))
print('main board    {} at ({:+.1f},{:+.1f})'
      .format(cfg['esp_mount'], case.board_x, case.board_y))
print('I2C board     {} at ({:+.1f},{:+.1f})'
      .format(cfg['i2c_mount'], case.i2c_x, case.i2c_y))
print('plate face z  {:.1f}   recess {:.1f} deep'.format(case.plate_face_z, case.recess_depth))
print('bracket       {:.1f} x {:.1f}, centred y={:+.2f}, studs y={}'
      .format(case.bracket_w, case.bracket_h, case.bracket_cy,
              ['{:+.1f}'.format(v) for v in case.stud_ys()]))
ears = case.ear_ys(case.bracket_h, case.bracket_cy)
print('wall screws   {:.1f} apart across, {:.1f} up'
      .format(case.width + 2 * (cfg['ear_len'] - cfg['ear_height'] / 2),
              (ears[1] - ears[0]) if len(ears) > 1 else 0))

print('\nchecks')
fails = []


def check(label, ok, detail):
    print('  {:<46} {:>4}  {}'.format(label, 'ok' if ok else 'FAIL', detail))
    if not ok:
        fails.append(label)


def box(cx, cy, w, h):
    return (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)


def overlap(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


# ---- display pocket -------------------------------------------------------
rim = (cfg['pcb_dia'] - cfg['glass_dia']) / 2
seat = (cfg['pcb_dia'] - case.glass_bore) / 2
check('PCB seat is wide enough to rest on', seat >= 0.7,
      '{:.2f} mm ledge, of {:.2f} rim available'.format(seat, rim))

check('glass bore clears the glass', case.glass_bore > cfg['glass_dia'] + 0.3,
      'bore {:.2f} vs glass {:.2f}'.format(case.glass_bore, cfg['glass_dia']))

check('aperture is smaller than the glass bore',
      cfg['window_dia'] < case.glass_bore - 1.0,
      'aperture {:.2f}, bezel overlap {:.2f} a side'
      .format(cfg['window_dia'], (case.glass_bore - cfg['window_dia']) / 2))

check('aperture clears the active area', cfg['window_dia'] > 32.4 + 1.0,
      'aperture {:.2f} vs 32.4 active'.format(cfg['window_dia']))

check('face left in front of the glass bore',
      cfg['front_thick'] - cfg['glass_depth'] >= 0.8,
      '{:.2f} mm'.format(cfg['front_thick'] - cfg['glass_depth']))

check('tab slot is wider than the tab', case.pocket_tab_w > cfg['pcb_tab_w'],
      'slot {:.2f} vs tab {:.2f}'.format(case.pocket_tab_w, cfg['pcb_tab_w']))

check('tab slot reaches past the circle',
      case.pocket_tab_reach > case.pocket_dia / 2,
      'reach {:.2f} vs circle radius {:.2f}'
      .format(case.pocket_tab_reach, case.pocket_dia / 2))

check('tab relief leaves floor', cfg['front_thick'] - cfg['solder_relief'] >= 0.8,
      '{:.2f} mm'.format(cfg['front_thick'] - cfg['solder_relief']))

check('relief runs in past the PCB seat',
      cfg['relief_in'] < case.pocket_dia / 2 - 1.5,
      'relief to {:.1f} from centre, seat at {:.1f}'
      .format(cfg['relief_in'], case.glass_bore / 2))

pilot_skin = cfg['front_thick'] - (cfg['clip_pilot_deep'] - cfg['pcb_thick'])
check('clip pilot leaves a skin on the front face', pilot_skin > 0.3,
      '{:.2f} mm'.format(pilot_skin))

check('clips clear each other', case.spacing - case.clip_od > 0.8,
      '{:.2f} mm between them'.format(case.spacing - case.clip_od))

check('clip pads clear the tab slots',
      case.pad_radius * math.cos(math.radians(30)) - cfg['clip_pad_dia'] / 2
      > case.collar_tab_w / 2,
      'pad inner x {:.2f} vs collar tab {:.2f}'
      .format(case.pad_radius * math.cos(math.radians(30)) - cfg['clip_pad_dia'] / 2,
              case.collar_tab_w / 2))

tab_tip = case.disp_cy - case.collar_tab_reach
check('collar tab clears the walls', tab_tip > -inner_y,
      'tab tip y={:+.2f} vs inner wall {:+.2f}'.format(tab_tip, -inner_y))

check('clips stay inside the side walls',
      max(case.centres) + case.clip_od / 2 < inner_x,
      'clip edge x={:.2f} vs inner wall {:.2f}'
      .format(max(case.centres) + case.clip_od / 2, inner_x))

check('clips stay inside the top wall',
      case.disp_cy + case.clip_od / 2 < inner_y,
      'clip top y={:+.2f} vs inner wall {:+.2f}'
      .format(case.disp_cy + case.clip_od / 2, inner_y))

# ---- depth ----------------------------------------------------------------
disp_stack = cfg['front_thick'] + cfg['pocket_depth'] + PLUG
check('display plugs clear the back plate', disp_stack < case.plate_face_z - 1.0,
      'plugs to z={:.1f}, plate face at z={:.1f}'
      .format(disp_stack, case.plate_face_z))

if case.on_body and cfg['esp_mount'] == 'expansion':
    exp_back = cfg['front_thick'] + cfg['exp_standoff'] + cfg['exp_thick']
    check('expansion board standoff clears its solder tails',
          cfg['exp_standoff'] >= 3.0, '{:.1f} mm'.format(cfg['exp_standoff']))

    SOCKET = 8.5     # female header the DevKit sits in
    devkit_top = exp_back + SOCKET + cfg['esp_pcb_thick'] + DEVKIT_TALL
    check('DevKit plugged on top clears the back plate',
          devkit_top < case.plate_face_z - 1.0,
          'stack to z={:.1f}, plate face at z={:.1f}'
          .format(devkit_top, case.plate_face_z))

    check('plugs on the expansion headers clear the back plate',
          exp_back + PLUG < case.plate_face_z - 1.0,
          'plugs to z={:.1f}, plate face at z={:.1f}'
          .format(exp_back + PLUG, case.plate_face_z))

    check('brackets stand proud of the board, tape included',
          cfg['exp_rise'] >= 1.0 and cfg['tape_thick'] < cfg['exp_standoff'],
          '{:.1f} mm above it, over {:.1f} of tape'
          .format(cfg['exp_rise'], cfg['tape_thick']))

    exp_pads = case.pad_grid(case.board_x, case.board_y, cfg['exp_len'],
                             cfg['exp_wid'], cfg['exp_pad'],
                             cfg['exp_pad_nx'], cfg['exp_pad_ny'])
    area = len(exp_pads) * cfg['exp_pad'] ** 2
    check('expansion board has tape area to grip', area > 300,
          '{} pads of {:.0f} square = {:.0f} mm2'
          .format(len(exp_pads), cfg['exp_pad'], area))

    check('its pads stay inside the board',
          all(abs(px - case.board_x) + cfg['exp_pad'] / 2 <= cfg['exp_len'] / 2
              and abs(py - case.board_y) + cfg['exp_pad'] / 2 <= cfg['exp_wid'] / 2
              for px, py in exp_pads),
          'outermost pad edge within the footprint')

elif case.on_body:
    esp_back = cfg['front_thick'] + cfg['esp_pad_height'] + cfg['esp_pcb_thick']
    check('ESP32 jumper plugs clear the back plate',
          esp_back + PLUG < case.plate_face_z - 1.0,
          'plugs to z={:.1f}, plate face at z={:.1f}'
          .format(esp_back + PLUG, case.plate_face_z))

    check('standoff clears the DevKit components',
          cfg['esp_pad_height'] > DEVKIT_TALL,
          'standoff {:.1f} vs components {:.1f}'
          .format(cfg['esp_pad_height'], DEVKIT_TALL))

if case.on_body:
    i2c_back = cfg['front_thick'] + cfg['i2c_standoff'] + cfg['i2c_thick']
    check('I2C board and its wiring clear the back plate',
          i2c_back + 6.0 < case.plate_face_z,
          'board back z={:.1f}, plate face z={:.1f}'
          .format(i2c_back, case.plate_face_z))

# ---- boards in the bay ----------------------------------------------------
span_x, span_y, mount_pad = case.primary_board()
label = 'expansion' if cfg['esp_mount'] == 'expansion' else 'ESP32'
esp_box = box(case.board_x, case.board_y, span_x + 2 * mount_pad,
              span_y + 2 * mount_pad)
print('\n{:<13} x {:+.1f}..{:+.1f}  y {:+.1f}..{:+.1f}  ({:.0f} x {:.0f} board)'
      .format(label + ' outline', esp_box[0], esp_box[1], esp_box[2], esp_box[3],
              span_x, span_y))

check('{} board clears the side walls'.format(label),
      esp_box[0] > -inner_x and esp_box[1] < inner_x,
      'x {:+.1f}..{:+.1f} vs +/-{:.1f}'.format(esp_box[0], esp_box[1], inner_x))

check('{} board clears top and bottom walls'.format(label),
      esp_box[2] > -inner_y and esp_box[3] < inner_y,
      'y {:+.1f}..{:+.1f} vs +/-{:.1f}'.format(esp_box[2], esp_box[3], inner_y))

if case.on_body and case.bay_h:
    check('{} board stays in the bay'.format(label),
          esp_box[3] < min(bay_top, tab_tip),
          'board top y={:+.1f}, bay top y={:+.1f}, tab tip y={:+.1f}'
          .format(esp_box[3], bay_top, tab_tip))

if cfg['i2c_mount'] != 'none':
    second = case.second_board()
    if second:
        i2c_box = box(case.i2c_x, case.i2c_y, second[0] + 2 * second[2],
                      second[1] + 2 * second[2])
        print('I2C outline   x {:+.1f}..{:+.1f}  y {:+.1f}..{:+.1f}  ({:.2f} x {:.2f} board)'
              .format(i2c_box[0], i2c_box[1], i2c_box[2], i2c_box[3],
                      second[0], second[1]))
    else:
        pads = case.i2c_pads()
        pr = cfg['i2c_pad_dia'] / 2
        i2c_box = (min(p[0] for p in pads) - pr, max(p[0] for p in pads) + pr,
                   min(p[1] for p in pads) - pr, max(p[1] for p in pads) + pr)
        print('I2C outline   x {:+.1f}..{:+.1f}  y {:+.1f}..{:+.1f}'.format(*i2c_box))

    check('I2C mounts clear the main board', not overlap(i2c_box, esp_box),
          'I2C from x={:+.1f}, {} to x={:+.1f}'
          .format(i2c_box[0], label, esp_box[1]))

    check('I2C mounts clear the side walls',
          i2c_box[0] > -inner_x and i2c_box[1] < inner_x,
          'x {:+.1f}..{:+.1f} vs +/-{:.1f}'.format(i2c_box[0], i2c_box[1], inner_x))

    check('I2C mounts clear top and bottom walls',
          i2c_box[2] > -inner_y and i2c_box[3] < inner_y,
          'y {:+.1f}..{:+.1f} vs +/-{:.1f}'.format(i2c_box[2], i2c_box[3], inner_y))

    if case.on_body and case.bay_h:
        check('I2C stays in the bay, clear of the display tabs',
              i2c_box[3] < min(bay_top, tab_tip),
              'board top y={:+.1f}, bay top y={:+.1f}'.format(i2c_box[3], bay_top))

    if second:
        i2c_tape = case.pad_grid(case.i2c_x, case.i2c_y, second[0], second[1],
                                 cfg['i2c_pad'], cfg['i2c_pad_nx'], cfg['i2c_pad_ny'])
        area = len(i2c_tape) * cfg['i2c_pad'] ** 2
        check('I2C board has tape area to grip', area > 100,
              '{} pads of {:.0f} square = {:.0f} mm2'
              .format(len(i2c_tape), cfg['i2c_pad'], area))

        check('its pads stay inside the board',
              all(abs(px - case.i2c_x) + cfg['i2c_pad'] / 2 <= second[0] / 2
                  and abs(py - case.i2c_y) + cfg['i2c_pad'] / 2 <= second[1] / 2
                  for px, py in i2c_tape),
              'outermost pad edge within the footprint')

        check('I2C brackets stand proud of the board, tape included',
              cfg['i2c_rise'] >= 1.0 and cfg['tape_thick'] < cfg['i2c_standoff'],
              '{:.1f} mm above it, over {:.1f} of tape'
              .format(cfg['i2c_rise'], cfg['tape_thick']))
    else:
        check('board lands on all four pads',
              cfg['i2c_wid'] >= cfg['i2c_pad_dx'] + 2
              and cfg['i2c_len'] >= cfg['i2c_pad_dy'] + 2,
              'pad centres {:.0f} x {:.0f}, board {:.0f} x {:.0f}'
              .format(cfg['i2c_pad_dx'], cfg['i2c_pad_dy'],
                      cfg['i2c_wid'], cfg['i2c_len']))

    # Only the plate carries studs and keyholes to collide with.
    if not case.on_body and not second:
        clash = []
        for ppx, ppy in pads:
            for sxv in (-cfg['stud_dx'] / 2, cfg['stud_dx'] / 2):
                for y in case.stud_ys():
                    if math.hypot(ppx - sxv, ppy - y) < pr + cfg['stud_head'] / 2:
                        clash.append('{:+.0f},{:+.0f}'.format(ppx, ppy))
        check('I2C pads miss the stud heads', not clash,
              'clash at {}'.format(clash) if clash else 'all clear')

        over = []
        for ppx, ppy in pads:
            for kx, ky, head, shank, slide in case.stud_keyholes():
                if (abs(ppx - kx) < pr + head / 2
                        and ky - head / 2 - pr < ppy < ky + slide + shank / 2 + pr):
                    over.append('{:+.0f},{:+.0f}'.format(ppx, ppy))
        check('I2C pads sit on solid plate', not over,
              'over keyhole at {}'.format(over) if over else 'clear of the keyholes')

# ---- cable slot -----------------------------------------------------------
if cfg['esp_mount'] == 'expansion':
    board_top = cfg['front_thick'] + cfg['exp_standoff'] + cfg['exp_thick']
    devkit_pcb = board_top + cfg['exp_socket']
    openings = [
        ('barrel jack', cfg['jack_wall'], cfg['jack_offset'], cfg['jack_w'],
         board_top - 1.0, board_top + cfg['jack_h'] + 1.0),
        ('USB-C', cfg['usb_wall'], cfg['usb_offset'], cfg['usb_w'],
         devkit_pcb - 1.0, devkit_pcb + cfg['usb_h']),
    ]
    print()
    for name, wall, off, w, z0, z1 in openings:
        along = (case.board_y if wall in ('left', 'right') else case.board_x) + off
        print('{:<13} {} wall at {:+.1f}, {:.0f} wide, z {:.1f}..{:.1f}'
              .format(name, wall, along, w, z0, z1))

        limit = inner_y if wall in ('left', 'right') else inner_x
        check('{} opening stays within the wall'.format(name),
              abs(along) + w / 2 < limit,
              'spans {:+.1f}..{:+.1f} vs +/-{:.1f}'
              .format(along - w / 2, along + w / 2, limit))

        check('{} opening clears the front face'.format(name),
              z0 >= cfg['front_thick'],
              'starts at z={:.1f}, face is {:.1f} thick'.format(z0, cfg['front_thick']))

        check('{} opening clears the back plate'.format(name),
              z1 < case.plate_face_z,
              'ends at z={:.1f}, plate face z={:.1f}'.format(z1, case.plate_face_z))

        edge = esp_box[0] if wall == 'left' else esp_box[1] if wall == 'right' \
            else esp_box[2]
        gap = (inner_x - abs(edge)) if wall in ('left', 'right') \
            else (inner_y - abs(edge))
        check('{} reaches that wall'.format(name), gap < 14.0,
              '{:.1f} mm from the board edge to the wall'.format(gap))

    side_gap = (abs(cfg['jack_offset'] - cfg['usb_offset'])
                - (cfg['jack_w'] + cfg['usb_w']) / 2)
    z_gap = (devkit_pcb - 1.0) - (board_top + cfg['jack_h'] + 1.0)
    check('wall left between the jack and USB openings',
          cfg['jack_wall'] != cfg['usb_wall'] or side_gap >= 2.5 or z_gap >= 2.5,
          '{:.1f} mm apart along the wall, {:+.1f} in height'
          .format(side_gap, z_gap))

    plug_top = board_top + PLUG
    check('wires off the 3-pin headers have room to turn',
          case.plate_face_z - plug_top >= 4.0,
          '{:.1f} mm between the plugs and the lid'
          .format(case.plate_face_z - plug_top))

# ---- back plate and bracket ----------------------------------------------
bx = case.width / 2 - cfg['boss_inset']
by = case.height / 2 - cfg['boss_inset']
check('case screw bosses clear of the bracket recess',
      bx - cfg['boss_dia'] / 2 > case.recess_w / 2
      or by - cfg['boss_dia'] / 2 > case.recess_h / 2,
      'boss edge x={:.1f} vs recess {:.1f}'
      .format(bx - cfg['boss_dia'] / 2, case.recess_w / 2))

check('bracket fits its recess with drop travel',
      case.bracket_cy + case.bracket_h / 2 <= case.recess_h / 2 - cfg['bracket_gap'] + 1e-9
      and case.bracket_cy - case.bracket_h / 2 - cfg['hang_slide'] >= -case.recess_h / 2 - 1e-9,
      'bracket {:+.1f}..{:+.1f}, recess {:+.1f}..{:+.1f}'
      .format(case.bracket_cy - case.bracket_h / 2, case.bracket_cy + case.bracket_h / 2,
              -case.recess_h / 2, case.recess_h / 2))

sy = case.stud_ys()
check('studs sit inside the bracket',
      min(sy) - cfg['stud_head'] / 2 > case.bracket_cy - case.bracket_h / 2
      and max(sy) + cfg['stud_head'] / 2 < case.bracket_cy + case.bracket_h / 2
      and cfg['stud_dx'] / 2 + cfg['stud_head'] / 2 < case.bracket_w / 2,
      'stud heads y {:+.1f}..{:+.1f}'
      .format(min(sy) - cfg['stud_head'] / 2, max(sy) + cfg['stud_head'] / 2))

check('keyholes stay on the plate',
      all(abs(y) + h / 2 < case.height / 2 for _, y, h, _, _ in case.stud_keyholes()),
      'lowest {:+.1f}'.format(min(y - h / 2 for _, y, h, _, _ in case.stud_keyholes())))

wall_left = cfg['plate_thick'] - case.recess_depth
check('wall left in front of the recess', wall_left >= 2.0, '{:.1f} mm'.format(wall_left))

check('stud heads clear the boards',
      case.on_body or cfg['stud_dx'] / 2 - cfg['stud_head'] / 2 > cfg['esp_pcb_wid'] / 2,
      'boards on the body' if case.on_body else 'stud inner edge {:.1f}'
      .format(cfg['stud_dx'] / 2 - cfg['stud_head'] / 2))

check('ears clear the case outline', case.bracket_w / 2 < case.width / 2,
      'bracket {:.1f} vs case {:.1f}'.format(case.bracket_w / 2, case.width / 2))

print('\n{} check(s) failed'.format(len(fails)) if fails else '\nall checks passed')
sys.exit(1 if fails else 0)
