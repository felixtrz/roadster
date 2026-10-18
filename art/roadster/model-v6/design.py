"""Roadster v6 design spec: the character lines, traced from the orthographic turnaround
(art/roadster/reference-images/turnaround-v2.png; side view scaled to 4.6 m length, front/rear views
to 1.31 m height) with plan widths from the Tripo sections. Blender axes: metres, z up, the car faces
-Y, its left is +X, floor z = 0. Each line is (y, x, z) knots; C and Fc lie on the mirror plane."""
import numpy as np

# centreline: nose -> hood -> cowl -> windshield -> roof -> rear glass -> deck -> Kamm tail
C = [(-2.28, 0, .515), (-2.15, 0, .585), (-1.95, 0, .665), (-1.70, 0, .750), (-1.50, 0, .815), (-1.37, 0, .865),
     (-1.25, 0, .945), (-1.00, 0, 1.085), (-0.60, 0, 1.235), (-0.30, 0, 1.305), (0.00, 0, 1.330), (0.50, 0, 1.300),
     (1.00, 0, 1.235), (1.50, 0, 1.150), (2.00, 0, 1.045), (2.28, 0, .985)]
# hood crease (front) -> windshield edge / A-pillar inner -> roof glass edge -> rear glass edge
RM = [(-2.28, .78, .52), (-2.15, .76, .59), (-1.95, .72, .67), (-1.70, .68, .755), (-1.50, .64, .82), (-1.37, .67, .872),
      (-1.30, .76, .905), (-1.22, .815, .945), (-1.00, .785, 1.050), (-0.60, .700, 1.190), (-0.30, .650, 1.262), (0.00, .630, 1.288),
      (0.50, .600, 1.258), (1.00, .540, 1.198), (1.50, .450, 1.112), (2.00, .330, 1.012), (2.28, .300, .972)]
RAIL = [(-2.28, .006, -.002), (-1.37, .006, -.002), (-1.20, .008, -.003), (-1.0, .028, -.010), (2.28, .034, -.012)]   # (y, dx, dz) rail width
# fender peak (front) -> beltline / daylight-opening bottom -> buttress outer edge -> deck shoulder
B = [(-2.28, .845, .555), (-2.15, .925, .630), (-1.95, 1.000, .720), (-1.70, 1.045, .815), (-1.50, 1.055, .880),
     (-1.37, 1.035, .912), (-1.25, .995, .925), (-0.85, .965, .872), (-0.40, .955, .918), (0.00, .950, .962),
     (0.50, .950, 1.020), (0.95, .955, 1.068), (1.20, .970, 1.060), (1.50, .985, 1.040), (1.80, .990, 1.012),
     (2.05, .990, .992), (2.28, .965, .958)]
# shoulder crease: top edge of the body side
S = [(-2.28, .880, .500), (-2.15, .970, .565), (-1.95, 1.070, .635), (-1.70, 1.140, .725), (-1.50, 1.160, .762),
     (-1.30, 1.150, .765), (-1.10, 1.120, .780), (-0.80, 1.075, .800), (0.00, 1.060, .840), (0.50, 1.080, .878),
     (1.00, 1.110, .908), (1.40, 1.110, .920), (1.80, 1.090, .930), (2.10, 1.060, .930), (2.28, 1.020, .918)]
# widest line (lower side crease)
W = [(-2.28, .870, .400), (-2.15, .960, .420), (-1.95, 1.080, .460), (-1.70, 1.165, .580), (-1.50, 1.175, .620),
     (-1.30, 1.170, .600), (-1.10, 1.130, .500), (-0.80, 1.095, .420), (0.00, 1.090, .400), (0.50, 1.115, .420),
     (0.90, 1.145, .470), (1.20, 1.150, .560), (1.45, 1.130, .680), (1.80, 1.100, .800), (2.10, 1.070, .840),
     (2.28, 1.040, .860)]
# paint split: black rocker below, sweeping up into the black rear quarter (side view)
K = [(-2.28, .860, .350), (-2.15, .945, .350), (-1.95, 1.065, .350), (-1.70, 1.150, .350), (-1.50, 1.160, .340),
     (-1.10, 1.115, .300), (-0.50, 1.080, .310), (0.00, 1.075, .330), (0.50, 1.100, .370), (1.00, 1.135, .450),
     (1.25, 1.135, .530), (1.55, 1.110, .630), (1.80, 1.085, .680), (2.10, 1.055, .740), (2.28, 1.025, .780)]
# rocker / bumper bottom outer edge, floor edge, floor centre
Lz = [(-2.28, .200), (-2.00, .150), (-1.50, .125), (0.00, .105), (1.50, .125), (2.00, .200), (2.28, .280)]
LIN = .055            # rocker tuck-in from K
FIN = .120            # floor edge inboard of L
WHEELS = {'F': dict(y=-1.47, r=0.368, w=0.300, x=1.015), 'R': dict(y=1.43, r=0.374, w=0.340, x=1.005)}
# daylight opening (side glass) ends: front along the A-pillar, rear a raked cut forming the tip
DLO_FRONT = ((-1.40, .86), (-1.22, 1.10))          # (y, z) line: glass is behind it
DLO_REAR = ((0.86, 1.065), (1.08, 1.205))           # glass is ahead of it
CANOPY = (-1.37, 2.03)                               # dark canopy (windshield + roof + rear glass) y range
DOOR_FRONT = ((-1.10, .30), (-1.06, .90))
DOOR_REAR = ((0.06, .30), (0.24, 1.0))
