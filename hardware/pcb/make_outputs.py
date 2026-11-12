"""Fab outputs for carrier.kicad_pcb: DRC, Gerbers + drill (zipped), JLCPCB BOM/CPL.

Run with KiCad's Python after build_pcb.py:

    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" make_outputs.py

Stops without writing anything if DRC finds a violation or an unrouted net.
"""
import csv
import os
import subprocess
import sys
import zipfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, 'carrier.kicad_pcb')
FAB = os.path.join(HERE, 'fab')
GERB = os.path.join(FAB, 'gerbers')
CLI = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'KiCad', '10.0', 'bin',
                   'kicad-cli.exe')

# value, LCSC part, notes.  Keyed by reference.
PARTS = {
    'R1': ('1k', 'C21190', 'flow pull-up'),
    'R2': ('100R', 'C22775', 'flow series'),
    'R3': ('10k', 'C25804', 'pressure divider top'),
    'R4': ('10k', 'C25804', 'pressure divider bottom'),
    'R5': ('330R', 'C23138', 'LED series'),
    'R6': ('4k7', 'C23162', 'I2C SDA pull-up'),
    'R7': ('4k7', 'C23162', 'I2C SCL pull-up'),
    'R8': ('10k', 'C25804', 'Q1 gate pull-down'),
    'C1': ('10uF 25V X5R 0805', 'C15850', '+5V bulk'),
    'C2': ('100nF', 'C14663', '+5V'),
    'C3': ('100nF', 'C14663', 'flow filter'),
    'C4': ('100nF', 'C14663', 'ADC filter'),
    'C5': ('10uF 25V X5R 0805', 'C15850', '3V3 bulk for displays'),
    'F1': ('PTC 500mA hold 1206 (Littelfuse 1206L050/15YR)', 'C315893', 'input fuse'),
    'D1': ('SMAJ5.0A TVS', 'C83329', 'input clamp'),
    'Q1': ('AO3401A P-MOSFET', 'C15127', 'reverse-polarity protection'),
}


def run(args):
    print('>', ' '.join(os.path.basename(a) if os.path.isabs(a) else a for a in args))
    r = subprocess.run([CLI] + args, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode not in (0,):
        print(r.stderr.strip())
    return r


def main():
    os.makedirs(GERB, exist_ok=True)
    rpt = os.path.join(FAB, 'drc.rpt')
    r = run(['pcb', 'drc', '--severity-all', '--refill-zones', '--save-board',
             '--exit-code-violations', '-o', rpt, PCB])
    if r.returncode != 0:
        sys.exit('DRC failed, see ' + rpt)

    for f in os.listdir(GERB):
        os.remove(os.path.join(GERB, f))
    run(['pcb', 'export', 'gerbers', '--no-protel-ext', '--subtract-soldermask',
         '-l', 'F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
         '-o', GERB + os.sep, PCB])
    run(['pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
         '--generate-map', '--map-format', 'gerberx2', '-o', GERB + os.sep, PCB])

    zpath = os.path.join(FAB, 'carrier_gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(GERB)):
            z.write(os.path.join(GERB, f), f)
    print('wrote', zpath)

    # ---- JLCPCB BOM + CPL (SMD parts only; through-hole is hand-soldered) ----
    board = pcbnew.LoadBoard(PCB)
    groups = {}
    cpl = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in PARTS:
            continue
        val, lcsc, _ = PARTS[ref]
        fpname = fp.GetFPID().GetLibItemName().wx_str()
        groups.setdefault((val, fpname, lcsc), []).append(ref)
        pos = fp.GetPosition()
        cpl.append([ref, f'{pcbnew.ToMM(pos.x):.3f}mm', f'{-pcbnew.ToMM(pos.y):.3f}mm',
                    'Top', f'{fp.GetOrientationDegrees() % 360:.0f}'])
    missing = set(PARTS) - {r for refs in groups.values() for r in refs}
    assert not missing, missing

    with open(os.path.join(FAB, 'carrier_bom_jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (val, fpname, lcsc), refs in sorted(groups.items(), key=lambda g: g[1][0]):
            w.writerow([val, ','.join(sorted(refs)), fpname, lcsc])
    with open(os.path.join(FAB, 'carrier_cpl_jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(sorted(cpl))
    print('wrote BOM and CPL to', FAB)

    for side in ('top', 'bottom'):
        run(['pcb', 'render', '--side', side, '--width', '1600', '--height', '1300',
             '-o', os.path.join(FAB, f'render_{side}.png'), PCB])


if __name__ == '__main__':
    main()
