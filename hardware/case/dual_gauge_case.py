"""
Wall-mount enclosure for the dual GC9A01 water gauge.

Fusion 360 script: Utilities -> Add-Ins -> Scripts and Add-Ins -> Scripts ->
the green +, point it at this folder, then Run.  It opens a new design and
builds these bodies in assembly position:

    Case body    front face with two display pockets, walls, screw bosses,
                 cable slot and vents.  Printed front-face-down it needs no
                 supports.
    Back plate   keyhole wall mounts, ESP32 pads, screwed on from behind.
    Clips L/R    two arcs per display that press the PCB into its pocket.

Dimensions live in CONFIG below, in millimetres.  To change the design, edit a
number and run the script again -- it builds a fresh design each time rather
than editing the old one.

The display module is NOT a plain circle: it is a round PCB with a pin-header
tab hanging off it.  `tab_count` is 1, so there is one slot, at the bottom --
which also stops the display going in upside down.  Set it to 2 for a module
with a tab at each end.

The round part, window, seat and tab relief come from the published MakerWorld
case for this module (makerworld.com/en/models/2001806), measured out of its
STLs: circle 39.0 across, window 36.0, front face 2.5 thick, pocket 3.8 deep,
1.6 relief under the tab for the solder joints on the pin header.  The tab
width is measured off the real part.

Hardware: 4x M3x10 (case), 8x M2x5 (display clips), 2x #6 wall screws.
"""

import adsk.core
import adsk.fusion
import math
import traceback

CONFIG = {
    # Build a single-pocket test tile instead of the case: same pocket, collar,
    # pads and clips, nothing else.  A ~15 minute print that says whether the
    # module actually drops in before you commit to the full case.
    'test_tile':     True,

    # ---- display module ----------------------------------------------------
    # Nominal part size; `fit` is added to every pocket dimension.
    'pcb_dia':        38.0,   # round part of the PCB
    'tab_count':         1,   # 1 = one tab, pointing down; 2 = top and bottom
    'pcb_tab_w':      23.5,   # width of the pin-header tab (0.925 in), which
                              # matches the 24.4 slot in the MakerWorld case
    'pcb_tab_reach':  26.3,   # circle centre to the tab tip
    'pcb_thick':       1.6,
    'pcb_fit':         0.8,   # 0.4 a side.  0.4 total was too tight to drop
                              # the PCB in; this also brings the tab slot to
                              # 24.3, which is what the MakerWorld case uses.
    'window_dia':    35.75,   # hole in the front face (1.407 in), measured off
                              # the glass.  Leaves the PCB 1.1 of seat to rest
                              # on, so don't open it up much further.
    'pocket_depth':    3.8,   # PCB plus whatever stands proud behind it
    'solder_relief':   1.6,   # sunk under the tab, for the pin solder joints
    'relief_in':      10.0,   # how close to the display centre that relief
                              # reaches.  The joints carry on past the tab and
                              # under the round part, so it runs in well past
                              # the seat.  Kept to the tab's width: widening it
                              # would undercut the collar wall.

    # ---- layout ------------------------------------------------------------
    'display_gap':    14.0,   # between the two round PCB edges
    'side_margin':    10.0,
    'top_margin':     10.0,   # beyond the tab tips
    'depth':          35.0,   # front face to back plate.  Must clear the
                              # header pins with dupont plugs on (~14 behind
                              # the PCB) plus the ESP32 on its pads.

    # ---- shell -------------------------------------------------------------
    'wall':            2.4,
    'front_thick':     2.5,
    'plate_thick':     6.0,   # 'bracket' needs bracket_t + gap of recess plus
                              # a couple of mm of wall left for the keyholes;
                              # 3.0 is plenty for the other mounting styles
    'corner_fillet':   4.0,   # 0 disables

    # ---- collar and display clips ------------------------------------------
    'collar_wall':     1.6,
    'clip_thick':      2.0,
    'clip_overlap':    2.0,   # how far a clip reaches over the PCB rim
    'clip_pad_dia':    6.0,
    'clip_pilot':      1.7,   # M2 thread-forming
    'clip_clear':      2.4,   # M2 clearance
    'clip_pilot_deep': 3.4,   # into pad and front wall, leaving a skin
    'clip_notch_in':   9.0,   # notch reaches this close to centre, clearing
                              # the tabs and the header behind them

    # ---- ESP32 mounting ----------------------------------------------------
    # 'snap'  four sprung fingers grip the long edges; press the board in,
    #         lift the fingers to get it out.  No screws, no tape.
    # 'pads'  four flat pads for foam tape, or screws if the board has holes.
    'esp_mount':    'snap',
    'esp_pcb_len':    51.5,   # long edge, runs vertically
    'esp_pcb_wid':    28.3,   # short edge, the USB-C end
    'esp_pcb_thick':   1.6,
    'esp_fit':         0.4,   # slack across the width
    'esp_pad_height':  4.0,   # standoff: clears the header pins, or the
                              # components if the board goes in pins-forward
    'esp_rail_w':      3.5,   # finger thickness
    'esp_lip':         1.0,   # how far a finger reaches over the board edge.
                              # Stays off the header pads, which sit ~2.5 in.
    'esp_lip_t':       1.2,
    'esp_finger_len': 14.0,
    'esp_finger_y':   13.0,   # finger centres, up and down from the middle
    'esp_pad_dia':     8.0,   # 'pads' mode only
    'esp_screw_holes': False, # True if your DevKit has mounting holes
    'esp_hole_dx':    23.0,
    'esp_hole_dy':    45.0,
    'esp_pilot':       2.2,

    # ---- I2C expansion board -----------------------------------------------
    # Four L-shaped clips on the back plate, beside the ESP32: a post at each
    # corner with a lip reaching over the board.  Tuck two corners under their
    # lips and press the other two down.
    # MEASURE your board -- these are placeholders.
    'i2c_mount':      True,
    'i2c_len':        30.0,   # along the case, like the DevKit
    'i2c_wid':        20.0,
    'i2c_thick':       1.6,
    'i2c_x':          36.0,   # centre on the plate; +x is right of the ESP32.
                              # Placed so the clips straddle the bracket studs
                              # rather than landing on them.
    'i2c_y':           0.0,
    'i2c_fit':         0.4,
    'i2c_standoff':    5.0,   # clears the bracket stud heads underneath
    'i2c_post':        3.0,   # clip thickness
    'i2c_arm':         4.0,   # how far each arm of the L runs along an edge
    'i2c_lip':         1.5,   # reach over the board corner
    'i2c_lip_t':       1.2,

    # ---- case screws -------------------------------------------------------
    'boss_dia':        7.0,
    'boss_pilot':      2.6,   # M3 thread-forming
    'boss_inset':      5.0,   # close enough that bosses merge into the walls
    'plate_clear':     3.4,

    # ---- wall mounting -----------------------------------------------------
    # 'bracket' separate wall plate: it keeps its screws, the case lifts off
    #           it.  The bracket sits in a recess in the back plate and its
    #           ears pass through notches, so the case still lies flat on the
    #           wall.  Hang it by lifting and dropping onto four studs.
    # 'ears'    flanges on the back plate itself; the whole case comes off the
    #           wall only by undoing its screws.
    # 'keyhole' slots that drop onto proud screw heads.
    # 'none'
    'wall_mount':  'bracket',
    'bracket_t':       3.0,   # wall plate thickness
    'bracket_rim':     3.0,   # rim left around its recess in the back plate
    'bracket_gap':     0.4,   # clearance around the bracket in that recess
    'stud_dia':        4.0,   # stud shank, rides in the keyhole slot
    'stud_head':       8.0,
    'stud_head_t':     2.5,
    'stud_dx':        70.0,   # stud spacing across
    'stud_dy':        34.0,   # stud spacing up
    'hang_slide':      9.0,   # how far the case drops to lock on
    'ear_count':         4,   # 4 = one per corner, 2 = one each side, centred
    'ear_len':        14.0,   # how far a flange stands out from the case
    'ear_height':     18.0,
    'ear_hole':        4.5,   # #8 or M4 wall screw
    'keyhole_dx':     35.0,
    'keyhole_y':       8.0,
    'keyhole_head':    8.0,
    'keyhole_shank':   4.2,
    'keyhole_slide':   9.0,

    # ---- openings ----------------------------------------------------------
    'cable_w':        14.0,
    'cable_len':       9.0,
    'vent_w':          2.4,
    'vent_len':       16.0,
    'vent_count':        4,
}


# Fusion works internally in centimetres.
def mm(value):
    return value / 10.0


def plane_at(root, z):
    """Construction plane parallel to XY, z mm behind the front face."""
    if abs(z) < 1e-9:
        return root.xYConstructionPlane
    planes = root.constructionPlanes
    inp = planes.createInput()
    inp.setByOffset(root.xYConstructionPlane, adsk.core.ValueInput.createByReal(mm(z)))
    return planes.add(inp)


def sketch_at(root, z):
    return root.sketches.add(plane_at(root, z))


def circle(sketch, x, y, dia):
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(mm(x), mm(y), 0), mm(dia / 2.0))


def rect(sketch, x0, y0, x1, y1):
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(mm(x0), mm(y0), 0),
        adsk.core.Point3D.create(mm(x1), mm(y1), 0))


def profiles(sketch, loops=None):
    """All profiles in a sketch, or only those with `loops` boundaries.

    Overlapping shapes split into several profiles; taking them all gives
    their union, which is how the circle-plus-tabs outline is built.
    loops=2 picks an annulus rather than the disc inside it."""
    col = adsk.core.ObjectCollection.create()
    for prof in sketch.profiles:
        if loops is None or prof.profileLoops.count == loops:
            col.add(prof)
    return col


def extrude(root, prof, distance, operation, participant=None):
    """Extrude `distance` mm; negative goes toward the front face."""
    feats = root.features.extrudeFeatures
    inp = feats.createInput(prof, operation)
    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(distance)))
    if participant is not None:
        inp.participantBodies = [participant]
    return feats.add(inp)


NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


class Case(object):
    def __init__(self, root, cfg):
        self.root = root
        self.cfg = cfg
        fit = cfg['pcb_fit']

        # Pocket the module drops into: circle plus a slot per tab.
        self.pocket_dia = cfg['pcb_dia'] + fit
        self.pocket_tab_w = cfg['pcb_tab_w'] + fit
        self.pocket_tab_reach = cfg['pcb_tab_reach'] + fit / 2

        # Collar walls standing around that pocket.
        cw = cfg['collar_wall']
        self.collar_dia = self.pocket_dia + 2 * cw
        self.collar_tab_w = self.pocket_tab_w + 2 * cw
        self.collar_tab_reach = self.pocket_tab_reach + cw
        self.collar_h = cfg['pcb_thick']

        # Clip screw pads sit just outside the collar, clear of the tabs.
        self.pad_radius = self.pocket_dia / 2.0 + cfg['clip_pad_dia'] / 2.0 + 0.5
        self.pad_angles = (30, 150, 210, 330)
        self.clip_od = 2 * (self.pad_radius + cfg['clip_clear'] / 2.0 + 1.2)
        self.clip_id = cfg['pcb_dia'] - 2 * cfg['clip_overlap']

        # Case outline.  Height is set by the tabs, width by the two circles.
        self.spacing = cfg['pcb_dia'] + cfg['display_gap']
        if cfg['test_tile']:
            self.width = self.collar_dia + 16.0
            # Only as tall as the module actually reaches, each way.
            top = self.collar_tab_reach if cfg['tab_count'] >= 2 else self.collar_dia / 2
            self.tile_y1 = top + 8.0
            self.tile_y0 = -(self.collar_tab_reach + 8.0)
            self.height = self.tile_y1 - self.tile_y0
            self.centres = (0.0,)
        else:
            self.width = self.spacing + cfg['pcb_dia'] + 2 * cfg['side_margin']
            # Symmetric about the windows even with a single tab, so the two
            # dials sit centred in the face.
            self.height = 2 * (cfg['pcb_tab_reach'] + cfg['top_margin'])
            self.centres = (-self.spacing / 2.0, self.spacing / 2.0)

        self.pcb_back_z = cfg['front_thick'] + cfg['pcb_thick']
        self.plate_face_z = cfg['depth'] - cfg['plate_thick']
        self.body = None
        self.plate = None
        self.bracket = None

        # Wall bracket and the recess it lives in.  The rim has to stay clear
        # of the corner bosses, or the case screw heads would land inside the
        # recess and hold the bracket off the plate.
        gap = cfg['bracket_gap']
        rim = max(cfg['bracket_rim'],
                  cfg['boss_inset'] + cfg['boss_dia'] / 2 + 1.0)
        self.recess_depth = cfg['bracket_t'] + gap
        self.recess_w = self.width - 2 * rim
        self.recess_h = self.height - 2 * rim
        self.bracket_w = self.recess_w - 2 * gap
        # Shorter than the recess by the drop travel, and sitting at the top of
        # it, so the case can be lifted off the studs.
        self.bracket_h = self.recess_h - cfg['hang_slide'] - 2 * gap
        self.bracket_cy = self.recess_h / 2 - gap - self.bracket_h / 2

    # -- outline helpers ---------------------------------------------------
    def tab_signs(self):
        """-1 is the tab pointing down, which every module has; +1 is the
        second one, only on two-tab modules.  A single slot also stops the
        display going in upside down."""
        return (-1, 1) if self.cfg['tab_count'] >= 2 else (-1,)

    def module_outline(self, sketch, x, dia, tab_w, tab_reach):
        """Circle plus a rectangle per tab, as overlapping shapes.  Taking
        every profile of the sketch gives their union."""
        circle(sketch, x, 0, dia)
        for sy in self.tab_signs():
            y0, y1 = sorted((0.0, sy * tab_reach))
            rect(sketch, x - tab_w / 2.0, y0, x + tab_w / 2.0, y1)

    def tab_rects(self, sketch, x, tab_w, tab_reach, inner):
        """Just the tab ends, from `inner` out to the tips."""
        for sy in self.tab_signs():
            y0, y1 = sorted((sy * inner, sy * tab_reach))
            rect(sketch, x - tab_w / 2.0, y0, x + tab_w / 2.0, y1)

    # -- main body ---------------------------------------------------------
    def shell(self):
        """Walls stop where the back plate starts, so the plate caps the case
        flush rather than sharing space with the walls."""
        cfg = self.cfg
        sk = sketch_at(self.root, 0)
        rect(sk, -self.width / 2, -self.height / 2, self.width / 2, self.height / 2)
        feat = extrude(self.root, sk.profiles.item(0), self.plate_face_z, NEW)
        self.body = feat.bodies.item(0)
        self.body.name = 'Case body'

        inner = sketch_at(self.root, cfg['front_thick'])
        w = self.width / 2 - cfg['wall']
        h = self.height / 2 - cfg['wall']
        rect(inner, -w, -h, w, h)
        extrude(self.root, inner.profiles.item(0),
                self.plate_face_z - cfg['front_thick'], CUT, self.body)

    def windows(self):
        sk = sketch_at(self.root, 0)
        for x in self.centres:
            circle(sk, x, 0, self.cfg['window_dia'])
        extrude(self.root, profiles(sk), self.cfg['front_thick'], CUT, self.body)

    def pockets(self):
        """Collar walls around each module, the pocket itself, and the relief
        under the tabs so the pin solder joints don't hold the PCB off its
        seat."""
        cfg = self.cfg

        outer = sketch_at(self.root, cfg['front_thick'])
        for x in self.centres:
            self.module_outline(outer, x, self.collar_dia,
                                self.collar_tab_w, self.collar_tab_reach)
        extrude(self.root, profiles(outer), self.collar_h, JOIN, self.body)

        pocket = sketch_at(self.root, cfg['front_thick'])
        for x in self.centres:
            self.module_outline(pocket, x, self.pocket_dia,
                                self.pocket_tab_w, self.pocket_tab_reach)
        extrude(self.root, profiles(pocket), self.collar_h, CUT, self.body)

        relief = sketch_at(self.root, cfg['front_thick'])
        for x in self.centres:
            self.tab_rects(relief, x, self.pocket_tab_w, self.pocket_tab_reach,
                           cfg['relief_in'])
        extrude(self.root, profiles(relief), -cfg['solder_relief'], CUT, self.body)

    def clip_pads(self):
        cfg = self.cfg
        pads = sketch_at(self.root, cfg['front_thick'])
        holes = sketch_at(self.root, self.pcb_back_z)
        for x in self.centres:
            for ang in self.pad_angles:
                px = x + self.pad_radius * math.cos(math.radians(ang))
                py = self.pad_radius * math.sin(math.radians(ang))
                circle(pads, px, py, cfg['clip_pad_dia'])
                circle(holes, px, py, cfg['clip_pilot'])
        extrude(self.root, profiles(pads), self.collar_h, JOIN, self.body)
        extrude(self.root, profiles(holes), -cfg['clip_pilot_deep'], CUT, self.body)

    def bosses(self):
        cfg = self.cfg
        bx = self.width / 2 - cfg['boss_inset']
        by = self.height / 2 - cfg['boss_inset']
        height = self.plate_face_z - cfg['front_thick']

        sk = sketch_at(self.root, cfg['front_thick'])
        holes = sketch_at(self.root, self.plate_face_z)
        for sx in (-1, 1):
            for sy in (-1, 1):
                circle(sk, sx * bx, sy * by, cfg['boss_dia'])
                circle(holes, sx * bx, sy * by, cfg['boss_pilot'])
        extrude(self.root, profiles(sk), height, JOIN, self.body)
        extrude(self.root, profiles(holes), -height, CUT, self.body)

    def cable_slot(self):
        """Notch in the bottom wall, lined up with the DevKit's USB-C end."""
        cfg = self.cfg
        board_back = self.plate_face_z - cfg['esp_pad_height']
        usb_z = board_back - 1.6 - 1.6          # PCB thickness, then connector
        sk = sketch_at(self.root, usb_z - cfg['cable_len'] / 2.0)
        rect(sk, -cfg['cable_w'] / 2, -self.height / 2 - 1,
             cfg['cable_w'] / 2, -self.height / 2 + cfg['wall'] + 1)
        extrude(self.root, profiles(sk), cfg['cable_len'], CUT, self.body)

    def vents(self):
        cfg = self.cfg
        if cfg['vent_count'] <= 0:
            return
        z0 = (cfg['depth'] - cfg['vent_len']) / 2.0
        y_in = self.height / 2 - cfg['wall'] - 1
        y_out = self.height / 2 + 1
        pitch = 16.0
        first = -pitch * (cfg['vent_count'] - 1) / 2.0
        sk = sketch_at(self.root, z0)
        for i in range(cfg['vent_count']):
            x = first + i * pitch
            rect(sk, x - cfg['vent_w'] / 2, y_in, x + cfg['vent_w'] / 2, y_out)
        extrude(self.root, profiles(sk), cfg['vent_len'], CUT, self.body)

    def fillet_corners(self):
        """Round the four upright outside corners.  Cosmetic: if the edge
        search misses, the script carries on with square corners."""
        r = self.cfg['corner_fillet']
        if r <= 0:
            return
        edges = adsk.core.ObjectCollection.create()
        for edge in self.body.edges:
            geom = edge.geometry
            if not isinstance(geom, adsk.core.Line3D):
                continue
            p0, p1 = geom.startPoint, geom.endPoint
            if abs(p0.x - p1.x) > 1e-6 or abs(p0.y - p1.y) > 1e-6:
                continue                      # not vertical
            if abs(abs(p0.x) - mm(self.width / 2)) > 1e-6:
                continue
            if abs(abs(p0.y) - mm(self.height / 2)) > 1e-6:
                continue
            edges.add(edge)
        if edges.count == 0:
            return
        fillets = self.root.features.filletFeatures
        inp = fillets.createInput()
        inp.addConstantRadiusEdgeSet(edges, adsk.core.ValueInput.createByReal(mm(r)), True)
        fillets.add(inp)

    # -- back plate --------------------------------------------------------
    def back_plate(self):
        cfg = self.cfg
        sk = sketch_at(self.root, self.plate_face_z)
        rect(sk, -self.width / 2, -self.height / 2, self.width / 2, self.height / 2)
        feat = extrude(self.root, sk.profiles.item(0), cfg['plate_thick'], NEW)
        self.plate = feat.bodies.item(0)
        self.plate.name = 'Back plate'

        bx = self.width / 2 - cfg['boss_inset']
        by = self.height / 2 - cfg['boss_inset']
        holes = sketch_at(self.root, self.plate_face_z)
        for sx in (-1, 1):
            for sy in (-1, 1):
                circle(holes, sx * bx, sy * by, cfg['plate_clear'])
        extrude(self.root, profiles(holes), cfg['plate_thick'], CUT, self.plate)

        mount = cfg['wall_mount']
        if mount == 'bracket':
            self.bracket_recess()
            self.keyholes(self.stud_keyholes())
        elif mount == 'ears':
            self.ears(self.plate, self.plate_face_z, cfg['plate_thick'],
                      self.ear_ys(self.height, 0.0), self.width / 2 - 1.0)
        elif mount == 'keyhole':
            self.keyholes(self.plain_keyholes())
        self.esp_mount()

    def ears(self, target, z, thick, ys, x_start):
        """Flanges out each side, in the plane of `target`, so the part they
        belong to lies flat on the wall.  The screws go in from the front, in
        the clear space beyond the case walls.  `x_start` is where the flange
        meets the part it grows from."""
        cfg = self.cfg
        r = cfg['ear_height'] / 2.0
        sk = sketch_at(self.root, z)
        holes = sketch_at(self.root, z)
        for sx in (-1, 1):
            for y in ys:
                x0 = sx * x_start
                x1 = sx * (self.width / 2 + cfg['ear_len'])
                rect(sk, min(x0, x1), y - r, max(x0, x1), y + r)
                circle(sk, x1 - sx * r, y, cfg['ear_height'])   # rounded end
                circle(holes, x1 - sx * r, y, cfg['ear_hole'])
        extrude(self.root, profiles(sk), thick, JOIN, target)
        extrude(self.root, profiles(holes), thick, CUT, target)

    def ear_ys(self, span, centre):
        """One ear per corner, or one each side on the centreline."""
        if self.cfg['ear_count'] >= 4:
            off = span / 2 - self.cfg['ear_height'] / 2
            return (centre - off, centre + off)
        return (centre,)

    def plain_keyholes(self):
        """Hang straight on two proud wall screws."""
        cfg = self.cfg
        return [(sx * cfg['keyhole_dx'], cfg['keyhole_y'], cfg['keyhole_head'],
                 cfg['keyhole_shank'], cfg['keyhole_slide'])
                for sx in (-1, 1)]

    def stud_ys(self):
        cfg = self.cfg
        return (self.bracket_cy - cfg['stud_dy'] / 2.0,
                self.bracket_cy + cfg['stud_dy'] / 2.0)

    def stud_keyholes(self):
        """Hang on the bracket's four studs.  A stud ends up at the top of its
        slot, so the big hole sits `hang_slide` below the stud position."""
        cfg = self.cfg
        return [(sx * cfg['stud_dx'] / 2.0, y - cfg['hang_slide'],
                 cfg['stud_head'] + 0.8, cfg['stud_dia'] + 0.8, cfg['hang_slide'])
                for sx in (-1, 1) for y in self.stud_ys()]

    def keyholes(self, spec):
        """Head goes through the big hole, then the case drops so the shank
        rides up the slot and the head is trapped behind the plate.

        In bracket mode only the wall left in front of the recess is cut."""
        cfg = self.cfg
        if cfg['wall_mount'] == 'bracket':
            z = self.plate_face_z
            depth = cfg['plate_thick'] - self.recess_depth
        else:
            z = self.plate_face_z
            depth = cfg['plate_thick']
        sk = sketch_at(self.root, z)
        for x, y, head, shank, slide in spec:
            top = y + slide
            circle(sk, x, y, head)
            circle(sk, x, top, shank)
            rect(sk, x - shank / 2, y, x + shank / 2, top)
        extrude(self.root, profiles(sk), depth, CUT, self.plate)

    def bracket_recess(self):
        """Pocket in the back of the plate that swallows the wall bracket,
        with notches at the ears, so the case still sits flat on the wall.
        Taller than the bracket by the drop travel."""
        cfg = self.cfg
        gap = cfg['bracket_gap']
        sk = sketch_at(self.root, cfg['depth'])
        rect(sk, -self.recess_w / 2, -self.recess_h / 2,
             self.recess_w / 2, self.recess_h / 2)
        # Slots through the rim for the ears, with room to travel as the case
        # is lifted off.
        r = cfg['ear_height'] / 2.0 + gap
        for y in self.ear_ys(self.bracket_h, self.bracket_cy):
            rect(sk, -self.width / 2 - 1, y - r - cfg['hang_slide'],
                 self.width / 2 + 1, y + r)
        extrude(self.root, profiles(sk), -self.recess_depth, CUT, self.plate)

    def wall_bracket(self):
        """Separate plate that stays on the wall: ears for four screws, studs
        the case hangs on.  Sits in the back plate's recess when hung."""
        cfg = self.cfg
        z_front = self.cfg['depth'] - cfg['bracket_t']

        cy, half = self.bracket_cy, self.bracket_h / 2
        sk = sketch_at(self.root, z_front)
        rect(sk, -self.bracket_w / 2, cy - half, self.bracket_w / 2, cy + half)
        feat = extrude(self.root, sk.profiles.item(0), cfg['bracket_t'], NEW)
        self.bracket = feat.bodies.item(0)
        self.bracket.name = 'Wall bracket'

        self.ears(self.bracket, z_front, cfg['bracket_t'],
                  self.ear_ys(self.bracket_h, cy), self.bracket_w / 2 - 1.0)

        # Studs: a shank through the wall left in front of the recess, then a
        # head behind it, trapped inside the case.
        shank_len = cfg['plate_thick'] - self.recess_depth + cfg['bracket_gap']
        shanks = sketch_at(self.root, z_front)
        heads = sketch_at(self.root, z_front - shank_len)
        for sx in (-1, 1):
            for y in self.stud_ys():
                circle(shanks, sx * cfg['stud_dx'] / 2.0, y, cfg['stud_dia'])
                circle(heads, sx * cfg['stud_dx'] / 2.0, y, cfg['stud_head'])
        extrude(self.root, profiles(shanks), -shank_len, JOIN, self.bracket)
        extrude(self.root, profiles(heads), -cfg['stud_head_t'], JOIN, self.bracket)

    def esp_mount(self):
        if self.cfg['esp_mount'] == 'snap':
            self.esp_snap()
        else:
            self.esp_pads()
        if self.cfg['i2c_mount']:
            self.i2c_clips()

    def i2c_clips(self):
        """Four L-shaped clips for a small I2C board, beside the ESP32.  Each
        corner gets a post with a lip over it; the board tucks under two and
        presses down under the other two.

        The standoff clears the bracket stud heads, which sit under it."""
        cfg = self.cfg
        half_w = (cfg['i2c_wid'] + cfg['i2c_fit']) / 2.0
        half_l = (cfg['i2c_len'] + cfg['i2c_fit']) / 2.0
        h_shoulder = cfg['i2c_standoff']
        h_board = h_shoulder + cfg['i2c_thick'] + 0.2
        h_top = h_board + cfg['i2c_lip_t']

        posts = sketch_at(self.root, self.plate_face_z)
        for sx in (-1, 1):
            for sy in (-1, 1):
                xe = cfg['i2c_x'] + sx * half_w
                ye = cfg['i2c_y'] + sy * half_l
                # Two overlapping arms make the L.
                self.corner_rect(posts, xe - sx * cfg['i2c_lip'], xe + sx * cfg['i2c_post'],
                                 ye - sy * cfg['i2c_arm'], ye + sy * cfg['i2c_post'])
                self.corner_rect(posts, xe - sx * cfg['i2c_arm'], xe + sx * cfg['i2c_post'],
                                 ye - sy * cfg['i2c_lip'], ye + sy * cfg['i2c_post'])
        extrude(self.root, profiles(posts), -h_top, JOIN, self.plate)

        # Clear the board's own footprint between shoulder and board top, which
        # is what leaves the lips proud and a shoulder to sit on.
        slot = sketch_at(self.root, self.plate_face_z - h_shoulder)
        rect(slot, cfg['i2c_x'] - half_w, cfg['i2c_y'] - half_l,
             cfg['i2c_x'] + half_w, cfg['i2c_y'] + half_l)
        extrude(self.root, profiles(slot), -(h_board - h_shoulder), CUT, self.plate)

    @staticmethod
    def corner_rect(sketch, xa, xb, ya, yb):
        rect(sketch, min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb))

    def esp_snap(self):
        """Four sprung fingers along the board's long edges.  Each is a post
        with a lip: the board presses past the lips and sits on the shoulders
        below them, standing off the plate far enough for its pins.

        The board goes in pins-forward, so the jumpers to the displays plug on
        from inside the case."""
        cfg = self.cfg
        half = cfg['esp_pcb_wid'] / 2 + cfg['esp_fit'] / 2
        lip_x = half - cfg['esp_lip']
        h_shoulder = cfg['esp_pad_height']
        h_board = h_shoulder + cfg['esp_pcb_thick'] + 0.2
        h_lip = h_board + cfg['esp_lip_t']
        half_len = cfg['esp_finger_len'] / 2.0
        ys = (-cfg['esp_finger_y'], cfg['esp_finger_y'])

        posts = sketch_at(self.root, self.plate_face_z)
        for sx in (-1, 1):
            for cy in ys:
                x0, x1 = sx * lip_x, sx * (half + cfg['esp_rail_w'])
                rect(posts, min(x0, x1), cy - half_len, max(x0, x1), cy + half_len)
        extrude(self.root, profiles(posts), -h_lip, JOIN, self.plate)

        # Undercut each finger between shoulder and board top, which is what
        # leaves a lip to snap over and a shoulder to sit on.
        slot = sketch_at(self.root, self.plate_face_z - h_shoulder)
        for sx in (-1, 1):
            for cy in ys:
                x0, x1 = sx * lip_x, sx * half
                rect(slot, min(x0, x1), cy - half_len - 0.5,
                     max(x0, x1), cy + half_len + 0.5)
        extrude(self.root, profiles(slot), -(h_board - h_shoulder), CUT, self.plate)

        # Stop at the far end so the board cannot creep away from the cable
        # slot.  The USB end stays open.
        stop = sketch_at(self.root, self.plate_face_z)
        y0 = cfg['esp_pcb_len'] / 2 + 0.4
        rect(stop, -10, y0, 10, y0 + 3.0)
        extrude(self.root, profiles(stop), -h_board, JOIN, self.plate)

    def esp_pads(self):
        """Four pads the DevKit sits on, raising it clear of its header pins.
        Screw them if your board has mounting holes, otherwise foam tape."""
        cfg = self.cfg
        dx = cfg['esp_hole_dx'] / 2.0
        dy = cfg['esp_hole_dy'] / 2.0
        sk = sketch_at(self.root, self.plate_face_z)
        for sx in (-1, 1):
            for sy in (-1, 1):
                circle(sk, sx * dx, sy * dy, cfg['esp_pad_dia'])
        extrude(self.root, profiles(sk), -cfg['esp_pad_height'], JOIN, self.plate)

        if not cfg['esp_screw_holes']:
            return
        holes = sketch_at(self.root, self.plate_face_z - cfg['esp_pad_height'])
        for sx in (-1, 1):
            for sy in (-1, 1):
                circle(holes, sx * dx, sy * dy, cfg['esp_pilot'])
        extrude(self.root, profiles(holes), cfg['esp_pad_height'], CUT, self.plate)

    # -- display clips -----------------------------------------------------
    def clips(self):
        """An annulus over each PCB rim, notched away at the tabs -- which
        leaves two arcs per display, each held by two M2 screws."""
        cfg = self.cfg
        for name, x in zip(('Clips L', 'Clips R'), self.centres):
            sk = sketch_at(self.root, self.pcb_back_z)
            circle(sk, x, 0, self.clip_od)
            circle(sk, x, 0, self.clip_id)
            feat = extrude(self.root, profiles(sk, loops=2), cfg['clip_thick'], NEW)
            clip = feat.bodies.item(0)
            clip.name = name

            notch = sketch_at(self.root, self.pcb_back_z)
            self.tab_rects(notch, x, self.pocket_tab_w + 1.0,
                           self.clip_od + 2.0, cfg['clip_notch_in'])
            extrude(self.root, profiles(notch), cfg['clip_thick'], CUT, clip)

            holes = sketch_at(self.root, self.pcb_back_z)
            for ang in self.pad_angles:
                px = x + self.pad_radius * math.cos(math.radians(ang))
                py = self.pad_radius * math.sin(math.radians(ang))
                circle(holes, px, py, cfg['clip_clear'])
            extrude(self.root, profiles(holes), cfg['clip_thick'], CUT, clip)

    def tile(self):
        """Flat plate carrying one pocket, for a fit test."""
        sk = sketch_at(self.root, 0)
        rect(sk, -self.width / 2, self.tile_y0, self.width / 2, self.tile_y1)
        feat = extrude(self.root, sk.profiles.item(0), self.cfg['front_thick'], NEW)
        self.body = feat.bodies.item(0)
        self.body.name = 'Fit test tile'

    def build(self):
        if self.cfg['test_tile']:
            self.tile()
            self.windows()
            self.pockets()
            self.clip_pads()
            self.clips()
            return
        self.shell()
        self.windows()
        self.pockets()
        self.clip_pads()
        self.bosses()
        self.cable_slot()
        self.vents()
        self.fillet_corners()
        self.back_plate()
        if self.cfg['wall_mount'] == 'bracket':
            self.wall_bracket()
        self.clips()


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType

        case = Case(design.rootComponent, CONFIG)
        case.build()

        # The root component cannot be renamed; the name comes from the
        # document, which is set when you save it.
        mount = ''
        if CONFIG['wall_mount'] == 'ears' and not CONFIG['test_tile']:
            across = case.width + 2 * (CONFIG['ear_len'] - CONFIG['ear_height'] / 2.0)
            ys = case.ear_ys()
            if len(ys) > 1:
                mount = ('Wall screws: {:.1f} mm apart across, {:.1f} mm apart '
                         'up.\n\n'.format(across, ys[1] - ys[0]))
            else:
                mount = 'Wall screws {:.1f} mm apart, level.\n\n'.format(across)

        ui.messageBox(
            'Built {:.1f} x {:.1f} x {:.1f} mm.\n\n'
            'Pocket: {:.1f} circle, {} tab slot(s) {:.1f} wide reaching {:.1f} '
            'from centre.\n\n'
            '{}'
            'Print the case body front-face-down, the back plate flat with\n'
            'its pads upward, the clips flat.  No supports.'
            .format(case.width, case.height, CONFIG['depth'],
                    case.pocket_dia, CONFIG['tab_count'], case.pocket_tab_w,
                    case.pocket_tab_reach, mount))
    except:
        if ui:
            ui.messageBox('Script failed:\n{}'.format(traceback.format_exc()))
