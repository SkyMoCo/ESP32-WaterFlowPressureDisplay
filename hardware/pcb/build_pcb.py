"""Builds the carrier PCB for the ESP32 water flow / pressure display.

Run with KiCad's own Python (it needs the pcbnew module):

    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" build_pcb.py

It writes carrier.kicad_pcb next to this file, placed and routed.  Then
make_outputs.py fills the ground pours, runs DRC, and writes the Gerbers,
drill file, BOM and CPL.

Coordinates below are in mm with the origin at the board's bottom-left
corner and y pointing UP (the way the board hangs in the case: screw
terminals along the bottom edge, display headers along the top, DevKit USB
toward the left wall).  P() converts to KiCad's y-down page coordinates.
"""
import os
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_FP = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'KiCad', '10.0',
                        'share', 'kicad', 'footprints')
LOCAL_LIB = os.path.join(HERE, 'carrier.pretty')
OUT = os.path.join(HERE, 'carrier.kicad_pcb')

W, H = 67.0, 54.0           # board size
X0, Y0 = 100.0, 100.0        # where the board sits on the KiCad page

# ---- DevKit socket geometry -------------------------------------------------
PITCH = 2.54
ROW_X0 = 6.0                 # x of the pin at the USB end
Y_BOT = 14.0                 # 3V3 ... D23 row
Y_TOP_N = Y_BOT + 22.86      # VIN ... EN row, 0.9" DevKits
Y_TOP_W = Y_BOT + 25.40      # VIN ... EN row, 1.0" DevKits (DOIT V1)

def col(i):                  # x of DevKit pin i, counted from the USB end
    return ROW_X0 + PITCH * i

def gap(i):                  # x halfway between DevKit pins i and i+1
    return ROW_X0 + PITCH * i + PITCH / 2

# DOIT ESP32 DevKit V1, 30 pin.  Index 0 is at the USB end.
TOP_PINS = ['VIN', 'GND', 'D13', 'D12', 'D14', 'D27', 'D26', 'D25', 'D33',
            'D32', 'D35', 'D34', 'VN', 'VP', 'EN']
BOT_PINS = ['3V3', 'GND', 'D15', 'D2', 'D4', 'D16', 'D17', 'D5', 'D18',
            'D19', 'D21', 'RX0', 'TX0', 'D22', 'D23']

# DevKit pin -> net.  Everything not listed is left unconnected.
DEVKIT_NETS = {
    ('T', 'VIN'): '+5V', ('T', 'GND'): 'GND', ('B', 'GND'): 'GND',
    ('B', '3V3'): '+3V3',
    ('B', 'D4'): 'FLOW_GPIO', ('T', 'D34'): 'PRES_ADC', ('B', 'D2'): 'LED_GPIO',
    ('B', 'D18'): 'SCLK', ('B', 'D23'): 'MOSI', ('B', 'D16'): 'DC',
    ('B', 'D17'): 'RST_P', ('T', 'D27'): 'RST_F',
    ('B', 'D21'): 'CS_P', ('B', 'D22'): 'CS_F',
    ('T', 'D25'): 'SDA', ('T', 'D26'): 'SCL',
}

# ---- top strip: display / I2C headers and the channel under them -----------
Y_HDR = 48.4
LV = [40.95 + 0.85 * k for k in range(8)]       # track levels in the channel
J5_X = [gap(1) + PITCH * k for k in range(7)]   # pressure display header
J6_X = [gap(9) + PITCH * k for k in range(7)]   # flow display header
J7_X = [gap(17) + PITCH * k for k in range(4)]  # I2C header
HDR_PINS = ['GND', '+3V3', 'SCLK', 'MOSI', 'RST', 'DC', 'CS']   # module order
HDR_LBL = ['GND', 'VCC', 'SCL', 'SDA', 'RES', 'DC', 'CS']
I2C_PINS = ['GND', '+3V3', 'SCL', 'SDA']
I2C_LBL = ['GND', '3V3', 'SCL', 'SDA']

# ---- bottom strip: screw terminals ----------------------------------------
Y_TERM = 5.4
TERMS = [   # ref, first pin x, nets, labels, title
    ('J4', 13.0, ['LED_EXT', 'GND'], ['LED', 'G'], 'LED'),
    ('J2', 21.0, ['FLOW_EXT', 'GND'], ['FLOW', 'G'], 'FLOW'),
    ('J3', 29.0, ['+5V', 'GND', 'PRES_SIG'], ['+5V', 'G', 'SIG'], 'PRESSURE'),
    ('J1', 40.5, ['GND', '+5V_IN'], ['G', '+5V'], '5V IN'),
]

# antenna keep-out: no copper on either layer under the WROOM antenna end
KEEPOUT = (43.5, 10.0, W, 40.5)

# track widths
W_SIG, W_3V3, W_PWR = 0.25, 0.4, 0.6
VIA_D, VIA_DRILL = 0.6, 0.3


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(X0 + x), pcbnew.FromMM(Y0 + H - y))


def unP(v):
    return (pcbnew.ToMM(v.x) - X0, H - (pcbnew.ToMM(v.y) - Y0))


# ---------------------------------------------------------------------------
def write_devkit_footprint():
    """Female-header footprint for the DevKit with both top-row spacings."""
    os.makedirs(LOCAL_LIB, exist_ok=True)
    lines = ['(footprint "ESP32_DevKit_30P_DualRow" (version 20240108) '
             '(generator "build_pcb.py") (layer "F.Cu")',
             '  (descr "Sockets for a 30-pin ESP32 DevKit. Bottom row fixed; '
             'top row at 0.9in (22.86) or 1.0in (25.40). Fit one top socket.")',
             '  (attr through_hole)',
             '  (property "Reference" "U1" (at 0 -3) (layer "F.Fab") '
             '(effects (font (size 1 1) (thickness 0.15))))',
             '  (property "Value" "ESP32_DevKit_V1" (at 0 3) (layer "F.Fab") '
             '(effects (font (size 1 1) (thickness 0.15))))']

    def pad(num, x, y):
        shape = 'rect' if num in ('1', '16') else 'circle'
        lines.append(f'  (pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) '
                     f'(size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask"))')

    # footprint origin = bottom-row pin 0; KiCad y is down, so "up" is -y
    for i in range(15):
        x = PITCH * i
        pad(str(16 + i), x, 0)                       # bottom row: 16..30
        pad(str(1 + i), x, -(Y_TOP_N - Y_BOT))       # top row narrow
        pad(str(1 + i), x, -(Y_TOP_W - Y_BOT))       # top row wide
    # socket outlines on silk
    for yy in (0, -(Y_TOP_N - Y_BOT), -(Y_TOP_W - Y_BOT)):
        x1, x2 = -1.27, PITCH * 14 + 1.27
        y1, y2 = yy - 1.27, yy + 1.27
        lines.append(f'  (fp_rect (start {x1} {y1}) (end {x2} {y2}) '
                     f'(stroke (width 0.12) (type solid)) (layer "F.SilkS"))')
    # DevKit outline on the fab layer only.  No courtyard: the DevKit sits
    # 8.5 mm up on its sockets, and the 0603 parts underneath are meant to.
    lines.append(f'  (fp_rect (start -6.0 1.4) (end {PITCH*14+10} '
                 f'{-(Y_TOP_W - Y_BOT) - 1.4}) (stroke (width 0.1) (type solid))'
                 f' (layer "F.Fab"))')
    lines.append(')')
    with open(os.path.join(LOCAL_LIB, 'ESP32_DevKit_30P_DualRow.kicad_mod'), 'w') as f:
        f.write('\n'.join(lines) + '\n')


# ---------------------------------------------------------------------------
class Builder:
    def __init__(self):
        self.b = pcbnew.NewBoard(OUT)
        self.nets = {}
        self.fps = {}

    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    # ---- footprints ----
    def load(self, lib, name):
        path = LOCAL_LIB if lib == 'local' else os.path.join(KICAD_FP, lib + '.pretty')
        fp = pcbnew.FootprintLoad(path, name)
        assert fp is not None, (lib, name)
        return fp

    def place(self, ref, lib, name, x, y, rot=0, value='', anchor=None):
        """Place a footprint.  With anchor, that pad lands on (x, y)."""
        fp = self.load(lib, name)
        fp.SetReference(ref)
        fp.SetValue(value or name)
        self.b.Add(fp)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(x, y))
        if anchor is not None:
            pp = self.pad(fp, anchor).GetPosition()
            fp.Move(P(x, y) - pp)
        fp.Reference().SetVisible(False)
        self.fps[ref] = fp
        return fp

    @staticmethod
    def pad(fp, num):
        for p in fp.Pads():
            if p.GetNumber() == str(num):
                return p
        raise KeyError(num)

    def pads(self, ref, num):
        return [p for p in self.fps[ref].Pads() if p.GetNumber() == str(num)]

    def pp(self, ref, num, which=0):
        """Math coords of a pad.  which picks among same-numbered pads."""
        ps = sorted(self.pads(ref, num), key=lambda p: unP(p.GetPosition())[1])
        return unP(ps[which].GetPosition())

    def setnet(self, ref, num, netname):
        for p in self.pads(ref, num):
            p.SetNet(self.net(netname))

    def two_pin(self, ref, lib, name, x, y, vertical, net_a, net_b, value):
        """Unpolarised R/C/F: net_a goes on the left (or lower) pad."""
        fp = self.place(ref, lib, name, x, y, 90 if vertical else 0, value)
        pa, pb = sorted(fp.Pads(), key=lambda p: unP(p.GetPosition())[1 if vertical else 0])
        pa.SetNet(self.net(net_a))
        pb.SetNet(self.net(net_b))
        return unP(pa.GetPosition()), unP(pb.GetPosition())

    # ---- copper ----
    def track(self, netname, layer, pts, w=W_SIG):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(P(x1, y1))
            t.SetEnd(P(x2, y2))
            t.SetWidth(pcbnew.FromMM(w))
            t.SetLayer(layer)
            t.SetNet(self.net(netname))
            self.b.Add(t)

    def via(self, netname, x, y):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(P(x, y))
        v.SetDrill(pcbnew.FromMM(VIA_DRILL))
        v.SetWidth(pcbnew.FromMM(VIA_D))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.net(netname))
        self.b.Add(v)

    def text(self, s, x, y, layer=pcbnew.F_SilkS, size=1.0, rot=0, thick=0.15,
             justify=None):
        t = pcbnew.PCB_TEXT(self.b)
        t.SetText(s)
        t.SetPosition(P(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
        t.SetTextThickness(pcbnew.FromMM(thick))
        if rot:
            t.SetTextAngleDegrees(rot)
        if layer in (pcbnew.B_SilkS,):
            t.SetMirrored(True)
        if justify == 'left':
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        self.b.Add(t)

    def poly(self, pts):
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in pts:
            chain.Append(P(x, y))
        chain.SetClosed(True)
        return chain

    def zone(self, netname, layer, pts, prio=0):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(layer)
        z.SetNet(self.net(netname))
        z.Outline().AddOutline(self.poly(pts))
        z.SetLocalClearance(pcbnew.FromMM(0.3))
        z.SetMinThickness(pcbnew.FromMM(0.25))
        z.SetThermalReliefGap(pcbnew.FromMM(0.4))
        z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.45))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(prio)
        self.b.Add(z)
        return z

    def keepout(self, x1, y1, x2, y2):
        z = pcbnew.ZONE(self.b)
        z.SetIsRuleArea(True)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        z.SetLayerSet(ls)
        z.Outline().AddOutline(self.poly([(x1, y1), (x2, y1), (x2, y2), (x1, y2)]))
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetZoneName('antenna keepout')
        self.b.Add(z)

    def edge(self):
        r = 1.0
        segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)),
                ((W - r, H), (r, H)), ((0, H - r), (0, r))]
        for a, c in segs:
            s = pcbnew.PCB_SHAPE(self.b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(P(*a))
            s.SetEnd(P(*c))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(pcbnew.FromMM(0.1))
            self.b.Add(s)
        k = r * (1 - 0.70710678)
        for st, md, en in [((0, r), (k, k), (r, 0)),
                           ((W - r, 0), (W - k, k), (W, r)),
                           ((W, H - r), (W - k, H - k), (W - r, H)),
                           ((r, H), (k, H - k), (0, H - r))]:
            s = pcbnew.PCB_SHAPE(self.b)
            s.SetShape(pcbnew.SHAPE_T_ARC)
            s.SetArcGeometry(P(*st), P(*md), P(*en))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(pcbnew.FromMM(0.1))
            self.b.Add(s)


# ---------------------------------------------------------------------------
def build():
    write_devkit_footprint()
    B = Builder()
    F, Bk = pcbnew.F_Cu, pcbnew.B_Cu
    ds = B.b.GetDesignSettings()
    ds.SetCopperLayerCount(2)

    B.edge()

    # ---- DevKit sockets ----
    B.place('U1', 'local', 'ESP32_DevKit_30P_DualRow', col(0), Y_BOT,
            value='ESP32 DevKit V1 (30p) on 2x 1x15 female headers', anchor='16')
    for i, name in enumerate(TOP_PINS):
        if ('T', name) in DEVKIT_NETS:
            B.setnet('U1', 1 + i, DEVKIT_NETS[('T', name)])
    for i, name in enumerate(BOT_PINS):
        if ('B', name) in DEVKIT_NETS:
            B.setnet('U1', 16 + i, DEVKIT_NETS[('B', name)])

    # ---- mounting holes ----
    for k, (x, y) in enumerate([(3.5, 3.5), (63.5, 3.5), (3.5, 50.5), (63.5, 50.5)]):
        B.place(f'H{k+1}', 'MountingHole', 'MountingHole_3.2mm_M3', x, y, value='M3')

    # ---- screw terminals ----
    for ref, x, nets, labels, title in TERMS:
        n = len(nets)
        B.place(ref, 'TerminalBlock_Phoenix',
                f'TerminalBlock_Phoenix_PT-1,5-{n}-3.5-H_1x{n:02d}_P3.50mm_Horizontal',
                x, Y_TERM, value=f'Screw terminal {n}P 3.5mm', anchor='1')
        for k, nm in enumerate(nets):
            B.setnet(ref, k + 1, nm)
            B.text(labels[k], x + 3.5 * k, 9.6, size=0.9, thick=0.15)
        B.text(f'{ref} {title}', x + 3.5 * (n - 1) / 2, 1.9, layer=pcbnew.B_SilkS,
               size=0.9)

    # ---- display + I2C headers ----
    def header(ref, xs, nets, labels, value):
        n = len(xs)
        fp = B.place(ref, 'Connector_PinHeader_2.54mm',
                     f'PinHeader_1x{n:02d}_P2.54mm_Vertical', xs[0], Y_HDR, rot=90,
                     value=value, anchor='1')
        assert abs(B.pp(ref, n)[0] - xs[-1]) < 0.01, 'header runs the wrong way'
        for k, nm in enumerate(nets):
            B.setnet(ref, k + 1, nm)
            B.text(labels[k], xs[k], 51.55, size=0.8, rot=90, thick=0.15)
    header('J5', J5_X, ['GND', '+3V3', 'SCLK', 'MOSI', 'RST_P', 'DC', 'CS_P'],
           HDR_LBL, 'Pressure display (GC9A01)')
    header('J6', J6_X, ['GND', '+3V3', 'SCLK', 'MOSI', 'RST_F', 'DC', 'CS_F'],
           HDR_LBL, 'Flow display (GC9A01)')
    header('J7', J7_X, ['GND', '+3V3', 'SCL', 'SDA'], I2C_LBL, 'I2C')

    # ---- power input: J1 -> F1 -> Q1 (reverse protection) -> +5V ----
    R0603, C0603 = ('Resistor_SMD', 'R_0603_1608Metric'), ('Capacitor_SMD', 'C_0603_1608Metric')
    f1a, f1b = B.two_pin('F1', 'Fuse', 'Fuse_1206_3216Metric', 48.9, 5.6, False,
                         '+5V_IN', '+5V_F', '500mA PTC')
    B.place('D1', 'Diode_SMD', 'D_SMA', 51.6, 2.0, rot=180, value='SMAJ5.0A')
    B.setnet('D1', 1, '+5V_F')
    B.setnet('D1', 2, 'GND')
    B.place('Q1', 'Package_TO_SOT_SMD', 'SOT-23', 54.1, 5.6, rot=180, value='AO3401A')
    B.setnet('Q1', 1, 'Q1_G')
    B.setnet('Q1', 2, '+5V')
    B.setnet('Q1', 3, '+5V_F')
    qg, qs, qd = B.pp('Q1', 1), B.pp('Q1', 2), B.pp('Q1', 3)
    r8a, r8b = B.two_pin('R8', *R0603, qg[0] + 2.7, qg[1] - 1.2, False, 'Q1_G', 'GND', '10k')
    c1a, c1b = B.two_pin('C1', 'Capacitor_SMD', 'C_0805_2012Metric', 58.4, qs[1],
                         False, '+5V', 'GND', '10uF')
    c2a, c2b = B.two_pin('C2', *C0603, 58.2, 8.7, False, '+5V', 'GND', '100nF')

    j1v = B.pp('J1', 2)
    B.track('+5V_IN', F, [j1v, (j1v[0] + 1.5, f1a[1]), f1a], W_PWR)
    d1k = B.pp('D1', 1)
    B.track('+5V_F', F, [f1b, qd], W_PWR)
    B.track('+5V_F', F, [d1k, (d1k[0], 3.6), (qd[0], 4.6), qd], W_PWR)
    B.track('Q1_G', F, [qg, r8a])
    B.track('+5V', F, [qs, c1a], W_PWR)
    PV = (55.6, 8.7)                                   # +5V down to the B.Cu bus
    B.track('+5V', F, [qs, (PV[0], qs[1] + 0.5), PV, c2a], W_PWR)
    B.via('+5V', *PV)
    X5 = 4.3                                           # +5V bus up the left edge
    B.track('+5V', Bk, [PV, (PV[0], 9.6), (X5, 9.6), (X5, Y_TOP_N), (col(0), Y_TOP_N)], W_PWR)
    j3v = B.pp('J3', 1)
    B.track('+5V', Bk, [j3v, (j3v[0], 9.6)], W_PWR)

    # ---- dual top row: tie each used narrow pad to its wide twin ----
    for i, name in enumerate(TOP_PINS):
        nm = DEVKIT_NETS.get(('T', name))
        if nm:
            w = W_PWR if nm == '+5V' else W_SIG
            B.track(nm, F, [(col(i), Y_TOP_N), (col(i), Y_TOP_W)], w)

    # ---- 3V3 column: DevKit 3V3 pin up through the gap by VIN/GND ----
    X33 = gap(0)
    B.track('+3V3', Bk, [(col(0), Y_BOT), (col(0), Y_BOT + 1.5), (X33, Y_BOT + 2.77),
                         (X33, LV[5])], 0.3)

    # ---- LED: D2 -> R5 -> J4 ----
    r5a, r5b = B.two_pin('R5', *R0603, gap(2), 16.9, True, 'LED_EXT', 'LED_GPIO', '330R')
    j4 = B.pp('J4', 1)
    B.track('LED_EXT', F, [j4, (j4[0], 10.5), (gap(2), 11.5), r5a])
    d2 = (col(3), Y_BOT)
    B.track('LED_GPIO', F, [r5b, (d2[0], r5b[1]), d2])

    # ---- flow front end: 3V3 -R1 1k- D4 -C3 100n- GND, D4 -R2 100R- J2 ----
    YF = 19.5
    r1a, r1b = B.two_pin('R1', *R0603, 13.0, YF, False, '+3V3', 'FLOW_GPIO', '1k')
    B.via('+3V3', X33, YF)
    B.track('+3V3', F, [(X33, YF), r1a], W_3V3)
    d4 = (col(4), Y_BOT)
    B.track('FLOW_GPIO', F, [d4, (d4[0], YF), r1b])
    c3a, c3b = B.two_pin('C3', *C0603, d4[0], 21.6, True, 'FLOW_GPIO', 'GND', '100nF')
    B.track('FLOW_GPIO', F, [(d4[0], YF), c3a])
    B.via('GND', d4[0], 23.6)
    B.track('GND', F, [c3b, (d4[0], 23.6)], W_SIG)
    r2a, r2b = B.two_pin('R2', *R0603, 19.6, YF, False, 'FLOW_GPIO', 'FLOW_EXT', '100R')
    B.track('FLOW_GPIO', F, [(d4[0], YF), r2a])
    j2 = B.pp('J2', 1)
    B.track('FLOW_EXT', F, [r2b, (gap(6), YF), (gap(6), 12.0), (j2[0], 10.5), j2])

    # ---- pressure: J3 SIG -R3 10k- ADC -R4 10k- GND, C4 100n ----
    xs = gap(11)
    r3a, r3b = B.two_pin('R3', *R0603, xs, 17.6, True, 'PRES_SIG', 'PRES_ADC', '10k')
    j3s = B.pp('J3', 3)
    B.track('PRES_SIG', F, [j3s, (j3s[0], 7.5), (xs, 8.8), r3a])
    YA = 19.5
    adc_top = (col(11), Y_TOP_N)
    B.track('PRES_ADC', F, [r3b, (xs, YA), (col(11), YA), adc_top])
    r4a, r4b = B.two_pin('R4', *R0603, 37.0, 21.0, True, 'PRES_ADC', 'GND', '10k')
    c4a, c4b = B.two_pin('C4', *C0603, 38.8, 21.0, True, 'PRES_ADC', 'GND', '100nF')
    B.track('PRES_ADC', F, [(xs, YA), (38.8, YA), c4a])
    B.track('PRES_ADC', F, [(37.0, YA), r4a])
    for gx, (gp) in ((37.0, r4b), (38.8, c4b)):
        B.via('GND', gx, 23.0)
        B.track('GND', F, [gp, (gx, 23.0)])

    # ---- 3V3 bulk cap ----
    YC5 = 25.0
    c5a, c5b = B.two_pin('C5', 'Capacitor_SMD', 'C_0805_2012Metric', 9.9, YC5, False,
                         '+3V3', 'GND', '10uF')
    B.via('+3V3', X33, YC5)
    B.track('+3V3', F, [(X33, YC5), c5a], W_3V3)
    B.via('GND', 12.4, YC5)
    B.track('GND', F, [c5b, (12.4, YC5)], W_3V3)

    # ---- I2C pull-ups, under the DevKit next to D25/D26 ----
    YP = 32.6
    B.via('+3V3', X33, YP)
    B.track('+3V3', F, [(X33, YP), (col(7), YP)], W_3V3)
    for ref, i, nm in (('R7', 6, 'SCL'), ('R6', 7, 'SDA')):
        ra, rb = B.two_pin(ref, *R0603, col(i), 34.2, True, '+3V3', nm, '4k7')
        B.track('+3V3', F, [(col(i), YP), ra], W_3V3)
        B.track(nm, F, [rb, (col(i), Y_TOP_N)])

    # ---- display buses on B.Cu, bottom row -> channel under the headers ----
    def riser(nm, i, gx, y_end):
        x = col(i)
        B.track(nm, Bk, [(x, Y_BOT), (x, Y_BOT + 1.5), (gx, Y_BOT + 2.77), (gx, y_end)])

    riser('DC', 5, gap(4), LV[1])          # D16
    riser('RST_P', 6, gap(5), Y_HDR)       # D17, straight into J5 RES
    riser('SCLK', 8, gap(8), LV[4])        # D18
    riser('CS_P', 10, gap(9), LV[0])       # D21
    riser('CS_F', 13, gap(12), LV[0])      # D22
    riser('MOSI', 14, gap(13), LV[2])      # D23
    # from the top row (wide pad) straight up
    for nm, i, lv in (('RST_F', 5, LV[3]), ('SCL', 6, LV[6]), ('SDA', 7, LV[7])):
        B.track(nm, Bk, [(col(i), Y_TOP_W), (col(i), lv)])

    # channel: F.Cu runs at fixed levels, B.Cu stubs up into the header pins
    J5, J6, J7 = J5_X, J6_X, J7_X
    chan = [  # net, level, arrival x, header pin xs
        ('CS_P', 0, gap(9), [J5[6]]),
        ('CS_F', 0, gap(12), [J6[6]]),
        ('DC', 1, gap(4), [J5[5], J6[5]]),
        ('MOSI', 2, gap(13), [J5[3], J6[3]]),
        ('RST_F', 3, col(5), [J6[4]]),
        ('SCLK', 4, gap(8), [J5[2], J6[2]]),
        ('+3V3', 5, X33, [J5[1], J6[1], J7[1]]),
        ('SCL', 6, col(6), [J7[2]]),
        ('SDA', 7, col(7), [J7[3]]),
    ]
    for nm, lv, ax, hx in chan:
        y = LV[lv]
        w = W_3V3 if nm == '+3V3' else W_SIG
        xs_ = sorted([ax] + hx)
        B.track(nm, F, [(xs_[0], y), (xs_[-1], y)], w)
        B.via(nm, ax, y)
        for x in hx:
            B.via(nm, x, y)
            B.track(nm, Bk, [(x, y), (x, Y_HDR)], w if nm != '+3V3' else 0.3)

    # ---- GND stitching ----
    for x, y in [(10.4, 21.5), (10.4, 29.0), (14.6, 26.0), (24.0, 21.5), (24.0, 29.0),
                 (29.0, 24.0), (32.2, 29.0), (36.0, 27.0), (39.0, 31.5),
                 (2.0, 20.0), (2.0, 30.0), (2.0, 42.0), (46.0, 8.5), (61.0, 8.5),
                 (61.0, 44.5), (65.0, 44.5), (6.0, 52.6), (27.6, 52.6), (47.8, 52.6),
                 (2.0, 8.0), (26.3, 11.0), (39.0, 11.3)]:
        B.via('GND', x, y)

    # ---- keepout + ground pours ----
    B.keepout(*KEEPOUT)
    m = 0.3
    outline = [(m, m), (W - m, m), (W - m, H - m), (m, H - m)]
    B.zone('GND', F, outline)
    B.zone('GND', Bk, outline)

    # DevKit GND pins: solid to the pours (the 3V3 riser beside them leaves
    # room for only one thermal spoke on B.Cu)
    for p in B.pads('U1', 2) + B.pads('U1', 17):
        p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    # ---- silkscreen ----
    B.text('ESP32 FLOW / PRESSURE', 55.5, 33.0, size=1.0)
    B.text('CARRIER v1.0', 55.5, 31.2, size=1.0)
    B.text('<- USB', 1.2, 26.6, size=1.0, rot=90)
    B.text('1.0in', 44.2, Y_TOP_W, size=0.8, justify='left')
    B.text('0.9in', 44.2, Y_TOP_N, size=0.8, justify='left')
    B.text('J5 PRESSURE DISPLAY', 55.5, 27.6, size=0.9)
    B.text('J6 FLOW DISPLAY', 55.5, 25.8, size=0.9)
    B.text('J7 I2C', 55.5, 24.0, size=0.9)
    B.text('NO COPPER: ANTENNA', 55.5, 19.0, size=0.8)
    B.text('ESP32 water flow / pressure carrier v1.0', 33.5, 27.0,
           layer=pcbnew.B_SilkS, size=1.2)
    B.text('J5 pressure disp   J6 flow disp   J7 I2C', 33.5, 45.0 - 20.0,
           layer=pcbnew.B_SilkS, size=0.9)

    # Zones are left unfilled here: the Python ZONE_FILLER ignores holes and
    # edge clearance.  make_outputs.py refills them through kicad-cli.
    B.b.Save(OUT)
    print('wrote', OUT)


if __name__ == '__main__':
    build()
