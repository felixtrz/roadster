# IWSDK replay data contract

Consume `reconstruction.json`. It contains 1,081 interpolated samples at 60 Hz
over 18 seconds. The underlying car observations are about 0.5005 seconds apart;
60 Hz is the delivery/interpolation rate, not a measurement rate.

- Metres, seconds, right-handed coordinates; +X approaches the ramp, +Y is up,
  +Z is the car's right. The ramp foot/lane center is (0,0,0).
- Time 0 is 07:08 in Tesla's event replay. The main broadcast clock owns timing.
- Car-local axes match world axes in the initial flat pose. Quaternions are
  `[x,y,z,w]`. Position is the midpoint of the nominal four tire-contact points.
  Flat ground puts this origin at Y=0. A scene parent may translate/rotate the
  entire reconstruction for a spectator viewpoint.
- `ramp.centerline` is the center of the visible driving deck, from foot to lip.
  Extrude it across `ramp.width` along Z. Chassis and support thickness belong
  below/outside the driving surface. Upper overhang is part of the polyline.
- `car` dimensions describe the authored/generated mesh, not a surveyed Tesla.
  Wheel contact coordinates are X±wheelbase/2, Y=0, Z±track/2. Different model
  wheelbase/track requires a rerun of the chord-contact solve.
- Each sample contains `time`, `position`, `quaternion`, `phase`,
  `thrusters:{attitude,lift}`, and `confidence`. Thruster values are visual
  envelopes from 0 to 1. Confidence values are descriptive judgments, not probabilities.
- Full wheel contact ends before the last wheel leaves the lip. During partial
  support, the front contacts may extend past the finite deck.
- Airborne position is conditional on the fitted camera and the verticalZ0
  plane. Airborne quaternion is inferred. Do not relabel the data as a measured
  full six-degree-of-freedom trajectory. See `README.md`, `depthPlaneSensitivity`, and the review.

Interpolate position linearly between adjacent 60 Hz samples and quaternion with
shortest-path spherical interpolation. The continuous fitted curves share
position and velocity at release; re-timing separate phase splines can break
that continuity. Use `events` for effect and UI timing instead of hardcoding a
landing time from an earlier reconstruction.
