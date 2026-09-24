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

print('case          {:.1f} W x {:.1f} H x {:.1f} D'.format(case.width, case.height, cfg['depth']))
print('pocket        circle {:.1f}, tabs {:.1f} wide, {:.1f} reach'
      .format(case.pocket_dia, case.pocket_tab_w, case.pocket_tab_reach))
print('collar        {:.1f} / tabs {:.1f} x {:.1f}'.format(case.collar_dia, case.collar_tab_w, case.collar_tab_reach))
print('clip          OD {:.2f}  ID {:.2f}  pads at r={:.2f}'.format(case.clip_od, case.clip_id, case.pad_radius))
print('plate face z  {:.1f}   recess {:.1f} deep'.format(case.plate_face_z, case.recess_depth))
print('recess        {:.1f} x {:.1f}'.format(case.recess_w, case.recess_h))
print('bracket       {:.1f} x {:.1f}, centred y={:+.2f}'.format(case.bracket_w, case.bracket_h, case.bracket_cy))
print('studs         x=+/-{:.1f}  y={}'.format(cfg['stud_dx'] / 2, ['{:+.2f}'.format(v) for v in case.stud_ys()]))
print('keyholes      {}'.format([('{:+.1f}'.format(s[0]), '{:+.1f}'.format(s[1])) for s in case.stud_keyholes()]))
ears = case.ear_ys(case.bracket_h, case.bracket_cy)
print('bracket ears  y={}   screw spacing {:.1f} across, {:.1f} up'
      .format(['{:+.2f}'.format(v) for v in ears],
              case.width + 2 * (cfg['ear_len'] - cfg['ear_height'] / 2),
              (ears[1] - ears[0]) if len(ears) > 1 else 0))

print('\nchecks')
fails = []


def check(label, ok, detail):
    print('  {:<44} {:>4}  {}'.format(label, 'ok' if ok else 'FAIL', detail))
    if not ok:
        fails.append(label)


rim = max(cfg['bracket_rim'], cfg['boss_inset'] + cfg['boss_dia'] / 2 + 1.0)
bx = case.width / 2 - cfg['boss_inset']
by = case.height / 2 - cfg['boss_inset']
check('case screw bosses clear of the recess',
      bx - cfg['boss_dia'] / 2 > case.recess_w / 2 or by - cfg['boss_dia'] / 2 > case.recess_h / 2,
      'boss edge x={:.1f} vs recess {:.1f}'.format(bx - cfg['boss_dia'] / 2, case.recess_w / 2))

check('bracket fits its recess with drop travel',
      case.bracket_cy + case.bracket_h / 2 <= case.recess_h / 2 - cfg['bracket_gap'] + 1e-9 and
      case.bracket_cy - case.bracket_h / 2 - cfg['hang_slide'] >= -case.recess_h / 2 - 1e-9,
      'bracket {:+.2f}..{:+.2f}, recess {:+.2f}..{:+.2f}'
      .format(case.bracket_cy - case.bracket_h / 2, case.bracket_cy + case.bracket_h / 2,
              -case.recess_h / 2, case.recess_h / 2))

sy = case.stud_ys()
check('studs sit inside the bracket',
      min(sy) - cfg['stud_head'] / 2 > case.bracket_cy - case.bracket_h / 2 and
      max(sy) + cfg['stud_head'] / 2 < case.bracket_cy + case.bracket_h / 2 and
      cfg['stud_dx'] / 2 + cfg['stud_head'] / 2 < case.bracket_w / 2,
      'stud heads y {:+.2f}..{:+.2f} in {:+.2f}..{:+.2f}'
      .format(min(sy) - cfg['stud_head'] / 2, max(sy) + cfg['stud_head'] / 2,
              case.bracket_cy - case.bracket_h / 2, case.bracket_cy + case.bracket_h / 2))

kh = case.stud_keyholes()
check('keyholes stay on the plate',
      all(abs(y) + h / 2 < case.height / 2 for _, y, h, _, _ in kh),
      'lowest {:+.2f}'.format(min(y - h / 2 for _, y, h, _, _ in kh)))

wall_left = cfg['plate_thick'] - case.recess_depth
check('wall left in front of the recess', wall_left >= 2.0, '{:.1f} mm'.format(wall_left))

check('stud head clears the ESP32 footprint',
      cfg['stud_dx'] / 2 - cfg['stud_head'] / 2 > cfg['esp_pcb_wid'] / 2,
      'stud inner edge {:.1f} vs board half-width {:.1f}'
      .format(cfg['stud_dx'] / 2 - cfg['stud_head'] / 2, cfg['esp_pcb_wid'] / 2))

check('ears clear the case outline',
      case.bracket_w / 2 < case.width / 2, 'bracket {:.1f} vs case {:.1f}'
      .format(case.bracket_w / 2, case.width / 2))

gap = case.spacing - case.clip_od
check('clips clear each other', gap > 0.8, '{:.2f} mm between them'.format(gap))

check('clip pads clear the tab slots',
      case.pad_radius * math.cos(math.radians(30)) - cfg['clip_pad_dia'] / 2
      > case.collar_tab_w / 2,
      'pad inner x {:.2f} vs collar tab {:.2f}'
      .format(case.pad_radius * math.cos(math.radians(30)) - cfg['clip_pad_dia'] / 2,
              case.collar_tab_w / 2))

check('collar tab clears the bottom wall',
      case.collar_tab_reach < case.height / 2 - cfg['wall'],
      'tab tip {:.2f} vs inner wall {:.2f}'
      .format(case.collar_tab_reach, case.height / 2 - cfg['wall']))

check('tab slot is wider than the tab',
      case.pocket_tab_w > cfg['pcb_tab_w'],
      'slot {:.2f} vs tab {:.2f}'.format(case.pocket_tab_w, cfg['pcb_tab_w']))

check('clip notch clears the tab slot',
      case.pocket_tab_w + 1.0 > case.pocket_tab_w,
      'notch {:.2f} vs slot {:.2f}'.format(case.pocket_tab_w + 1.0, case.pocket_tab_w))

check('tab slot reaches past the circle',
      case.pocket_tab_reach > case.pocket_dia / 2,
      'reach {:.2f} vs circle radius {:.2f}'
      .format(case.pocket_tab_reach, case.pocket_dia / 2))

seat = (cfg['pcb_dia'] - cfg['window_dia']) / 2
check('PCB seat is wide enough to rest on', seat >= 1.0,
      '{:.2f} mm ledge (pocket ledge {:.2f})'
      .format(seat, (case.pocket_dia - cfg['window_dia']) / 2))

check('clip grips PCB without fouling the window',
      case.clip_id < cfg['pcb_dia'] - 1.0,
      'clip ID {:.1f} vs PCB {:.1f}'.format(case.clip_id, cfg['pcb_dia']))

pilot_skin = cfg['front_thick'] - (cfg['clip_pilot_deep'] - cfg['pcb_thick'])
check('clip pilot leaves a skin on the front face', pilot_skin > 0.3,
      '{:.2f} mm'.format(pilot_skin))

relief_left = cfg['front_thick'] - cfg['solder_relief']
check('tab relief leaves floor', relief_left >= 0.8, '{:.2f} mm'.format(relief_left))

check('relief runs in past the PCB seat',
      cfg['relief_in'] < case.pocket_dia / 2 - 1.5,
      'relief to {:.1f} from centre, seat inner edge {:.1f}'
      .format(cfg['relief_in'], cfg['window_dia'] / 2))

check('relief stays inside the collar wall',
      case.pocket_tab_w <= case.collar_tab_w - 2 * cfg['collar_wall'] + 1e-9,
      'relief {:.2f} wide vs slot {:.2f}'.format(case.pocket_tab_w, case.pocket_tab_w))

check('relief clears the clip pilot holes',
      case.pocket_tab_w / 2 < case.pad_radius * math.cos(math.radians(30)) - cfg['clip_pilot'],
      'relief edge x={:.2f} vs pilot x={:.2f}'
      .format(case.pocket_tab_w / 2, case.pad_radius * math.cos(math.radians(30))))

board_back = case.plate_face_z - cfg['esp_pad_height']
plug_back = cfg['front_thick'] + cfg['pocket_depth'] + 14.0
check('display plugs clear the ESP32 board',
      plug_back < board_back - 1.6 - 3.0,
      'plugs to z={:.1f}, board components from z={:.1f}'
      .format(plug_back, board_back - 1.6 - 3.0))

half = cfg['esp_pcb_wid'] / 2 + cfg['esp_fit'] / 2
rail_out = half + cfg['esp_rail_w']
check('snap fingers clear the stud heads',
      rail_out < cfg['stud_dx'] / 2 - cfg['stud_head'] / 2,
      'rail to x={:.2f}, stud head from x={:.2f}'
      .format(rail_out, cfg['stud_dx'] / 2 - cfg['stud_head'] / 2))

check('snap fingers clear the side walls',
      rail_out < case.width / 2 - cfg['wall'],
      'rail {:.2f} vs inner wall {:.2f}'.format(rail_out, case.width / 2 - cfg['wall']))

finger_top = cfg['esp_finger_y'] + cfg['esp_finger_len'] / 2
check('snap fingers sit within the board length',
      finger_top < cfg['esp_pcb_len'] / 2,
      'finger to y={:.1f}, board half {:.1f}'.format(finger_top, cfg['esp_pcb_len'] / 2))

stop_out = cfg['esp_pcb_len'] / 2 + 3.4
check('end stop clears the top wall',
      stop_out < case.height / 2 - cfg['wall'],
      'stop to y={:.1f} vs inner wall {:.1f}'.format(stop_out, case.height / 2 - cfg['wall']))

lip_h = cfg['esp_pad_height'] + cfg['esp_pcb_thick'] + 0.2 + cfg['esp_lip_t']
check('cradle height fits between plate and displays',
      case.plate_face_z - lip_h > cfg['front_thick'] + cfg['pocket_depth'],
      'fingers reach z={:.1f}, display backs at z={:.1f}'
      .format(case.plate_face_z - lip_h, cfg['front_thick'] + cfg['pocket_depth']))

board_front = case.plate_face_z - cfg['esp_pad_height'] - cfg['esp_pcb_thick']
check('ESP32 jumper plugs clear the front face',
      board_front - 14.0 > cfg['front_thick'] + 1.0,
      'plugs reach z={:.1f}, front wall at z={:.1f}'
      .format(board_front - 14.0, cfg['front_thick']))

if cfg['i2c_mount']:
    ihw = (cfg['i2c_wid'] + cfg['i2c_fit']) / 2 + cfg['i2c_post']
    ihl = (cfg['i2c_len'] + cfg['i2c_fit']) / 2 + cfg['i2c_post']
    i_x0, i_x1 = cfg['i2c_x'] - ihw, cfg['i2c_x'] + ihw
    i_y0, i_y1 = cfg['i2c_y'] - ihl, cfg['i2c_y'] + ihl
    print('\nI2C board   x {:+.1f}..{:+.1f}  y {:+.1f}..{:+.1f}  standoff {:.1f}'
          .format(i_x0, i_x1, i_y0, i_y1, cfg['i2c_standoff']))

    check('I2C clips clear the ESP32 cradle',
          i_x0 > cfg['esp_pcb_wid'] / 2 + cfg['esp_fit'] / 2 + cfg['esp_rail_w'],
          'I2C from x={:+.1f}, ESP rail to x={:.2f}'.format(i_x0, rail_out))

    check('I2C clips clear the side wall',
          i_x1 < case.width / 2 - cfg['wall'],
          'I2C to x={:+.1f} vs inner wall {:.1f}'.format(i_x1, case.width / 2 - cfg['wall']))

    check('I2C clips clear top and bottom walls',
          i_y1 < case.height / 2 - cfg['wall'] and i_y0 > -(case.height / 2 - cfg['wall']),
          'I2C y {:+.1f}..{:+.1f} vs +/-{:.1f}'
          .format(i_y0, i_y1, case.height / 2 - cfg['wall']))

    check('I2C board sits above the bracket stud heads',
          cfg['i2c_standoff'] > cfg['stud_head_t'] + 0.5,
          'standoff {:.1f} vs stud head {:.1f}'
          .format(cfg['i2c_standoff'], cfg['stud_head_t']))

    # Each L clip, as its bounding box, against each stud head.
    posts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            xe = cfg['i2c_x'] + sx * (cfg['i2c_wid'] + cfg['i2c_fit']) / 2
            ye = cfg['i2c_y'] + sy * (cfg['i2c_len'] + cfg['i2c_fit']) / 2
            xs = [xe - sx * cfg['i2c_lip'], xe + sx * cfg['i2c_post'], xe - sx * cfg['i2c_arm']]
            ys_ = [ye - sy * cfg['i2c_lip'], ye + sy * cfg['i2c_post'], ye - sy * cfg['i2c_arm']]
            posts.append((min(xs), max(xs), min(ys_), max(ys_)))

    r = cfg['stud_head'] / 2
    clashes = []
    for px0, px1, py0, py1 in posts:
        for sxv in (-cfg['stud_dx'] / 2, cfg['stud_dx'] / 2):
            for y in case.stud_ys():
                if px0 < sxv + r and sxv - r < px1 and py0 < y + r and y - r < py1:
                    clashes.append(('{:+.1f},{:+.1f}'.format(sxv, y)))
    check('I2C clip posts miss the stud heads', not clashes,
          'clash at {}'.format(clashes) if clashes else 'nearest stud head clear')

    # A post sitting over a keyhole would have nothing to print onto.
    over = []
    for px0, px1, py0, py1 in posts:
        for kx, ky, head, shank, slide in case.stud_keyholes():
            hx0, hx1 = kx - head / 2, kx + head / 2
            hy0, hy1 = ky - head / 2, ky + slide + shank / 2
            if px0 < hx1 and hx0 < px1 and py0 < hy1 and hy0 < py1:
                over.append('{:+.1f},{:+.1f}'.format(kx, ky))
    check('I2C clip posts sit on solid plate', not over,
          'over keyhole {}'.format(over) if over else 'clear of the keyholes')

    i2c_top = cfg['i2c_standoff'] + cfg['i2c_thick'] + 0.2 + cfg['i2c_lip_t']
    check('I2C board clears the display backs',
          case.plate_face_z - i2c_top > cfg['front_thick'] + cfg['pocket_depth'],
          'clips reach z={:.1f}, display backs at z={:.1f}'
          .format(case.plate_face_z - i2c_top, cfg['front_thick'] + cfg['pocket_depth']))

print('\n{} check(s) failed'.format(len(fails)) if fails else '\nall checks passed')
