NAME = 'Smoothieboard'

import  os
import  subprocess
import  tempfile

import  wx

import  koko
from    koko.fab.path   import Path

from    koko.cam.panel  import FabPanel, OutputPanel

class GCodeOutput(OutputPanel):

    extension = '.gcode'

    def __init__(self, parent):
        OutputPanel.__init__(self, parent)

        FabPanel.construct(self, 'G-Code', [
            ('Mode', 'mode', ['Relative', 'Absolute']),
            ('Invert Z-axis', 'invertz', bool),
            ('Convert to inch', 'useinch', bool),
            ('Cut speed (mm/min)', 'feed',  float, lambda f: f > 0),
            ('Plunge rate (mm/min)', 'plunge',  float, lambda f: f > 0),
            ('Spindle speed (RPM)', 'spindle', float, lambda f: f > 0),
            ('Jog height (mm)', 'jog', float, lambda f: f > 0),
            ('Cut type', 'type', ['Conventional', 'Climb']),
            ('Tool number', 'tool', int, lambda f: f > 0),
            ('Coolant', 'coolant', bool)
        ])

        self.construct()


    def run(self, paths):
        ''' Convert the path from the previous panel into a g-code file
        '''

        koko.FRAME.status = 'Converting to .gcode file'

        values = self.get_values()
        if not values:  return False

        # Reverse direction for climb cutting
        if values['type']:
            paths = Path.sort([p.reverse() for p in paths])


        # Check to see if all of the z values are the same.  If so,
        # we can use 2D cutting commands; if not, we'll need
        # to do full three-axis motion control
        zmin = paths[0].points[0][2]
        flat = True
        for p in paths:
            if not all(pt[2] == zmin for pt in p.points):
                flat = False

        # Create a temporary file to store the .sbp instructions
        self.file = tempfile.NamedTemporaryFile(suffix=self.extension)

        self.file.write("%%\n")     # tape start
        if values['useinch']:
            self.file.write("G20\n")    # inch mode
        else:
            self.file.write("G21\n")    # mm mode
        self.file.write("G90\n")    # Absolute programming
        print values['mode']
        if values['mode'] == 0:  # Relative
            self.file.write("G92 X0 Y0 Z0\n")    # Reset position: current position=0,0,0

        scale = 1.0 # inch units
        scalez = -scale if values['invertz'] else scale

        if values['coolant']:   self.file.write("M8\n") # coolant on

        # Move up before starting spindle
        self.file.write("G0 Z%0.4f\n" % (scalez*values['jog']))
        self.file.write("M3 S%0.0f\n" % values['spindle']) # spindle speed
        self.file.write("G4 P1000\n") # pause one second to spin up spindle

        xy  = lambda x,y:   (scale*x, scale*y)
        xyz = lambda x,y,z: (scale*x, scale*y, scalez*z)

        for p in paths:

            # Move to the start of this path at the jog height
            self.file.write("G0 X%0.4f Y%0.4f Z%0.4f\n" %
                            xyz(p.points[0][0], p.points[0][1], values['jog']))

            # Plunge to the desired depth
            self.file.write("G1 Z%0.4f F%0.4f\n" %
                            (p.points[0][2]*scalez, scale*values['plunge']))

            # Restore XY feed rate
            self.file.write("G1 F%0.0f\n" % (scale*values['feed']))

            # Cut each point in the segment
            for pt in p.points:
                if flat:
                    self.file.write("G1 X%0.4f Y%0.4f" % xy(*pt[0:2]))
                else:
                    self.file.write("G1 X%0.4f Y%0.4f Z%0.4f" % xyz(*pt))
                self.file.write(" F%0.0f\n" % (scale*values['feed']))

            # Lift the bit up to the jog height at the end of the segment
            self.file.write("G1 Z%0.4f\n" % (scalez*values['jog']))

        self.file.write("M5\n") # spindle stop
        if values['coolant']:   self.file.write("M9\n") # coolant off
        self.file.write("%%\n")  # tape end
        self.file.flush()

        koko.FRAME.status = ''
        return True


################################################################################

from koko.cam.path_panels   import PathPanel

INPUT = PathPanel
PANEL = GCodeOutput

################################################################################

from koko.cam.inputs.cad import CadImgPanel

DEFAULTS = [
('<None>', {}),

('Fraise PCB', {
    PathPanel: [
        ('diameter',    0.1),
        ('offsets',     1),
        ('overlap',     '0'),
        ('threeD',      False),
        ('type',        'XY'),
        ('step',        0),
        ('depth',       '-0.1'),
        ],
    CadImgPanel:
        [('res', 5)],
    GCodeOutput:
        [('feed', 50),
         ('plunge', 25),
         ('spindle', 10000),
         ('jog', 5),
         ('tool', 1),
         ('coolant', False)]
    }
),

('Flat cutout (1/8")', {
    PathPanel: [
        ('diameter',    3.175),
        ('offsets',     1),
        ('overlap',     ''),
        ('threeD',      True),
        ('type',        'XY'),
        ('step',        1),
        ('depth',       ''),
        ],
    CadImgPanel:
        [('res', 5)],
    GCodeOutput:
        [('feed', 20),
         ('plunge', 2.5),
         ('spindle', 10000),
         ('jog', 5),
         ('tool', 1),
         ('coolant', False)]
    }
),

('Wax rough cut (1/8")', {
    PathPanel: [
        ('diameter',    3.175),
        ('offsets',     -1),
        ('overlap',     0.25),
        ('threeD',      True),
        ('type',        'XY'),
        ('step',        0.5),
        ('depth',       ''),
        ],
    CadImgPanel:
        [('res', 5)],
    GCodeOutput:
        [('feed', 20),
         ('plunge', 2.5),
         ('spindle', 10000),
         ('jog', 5),
         ('tool', 1),
         ('coolant', False)]
    }
),

('Wax finish cut (1/8")', {
    PathPanel:
        [('diameter',    3.175),
         ('offsets',     -1),
         ('overlap',     0.5),
         ('threeD',      True),
         ('type',        'XZ + YZ'),
         ('step',        0.5),
         ('depth',       ''),
        ],
    CadImgPanel:
        [('res', 5)],
    GCodeOutput:
        [('feed', 20),
         ('plunge', 2.5),
         ('spindle', 10000),
         ('jog', 5),
         ('tool', 1),
         ('coolant', False)]
    }
)
]
