# Thruster firing: footage study and physics model

`solve_thrusters.py` produces `src/data/thrusters.json`. That file holds the car's air-phase attitude and the thrust of each of its four corner nozzles, sampled every 1/60 s. `TrackPlayer` plays it back, and `ReplayEffects` gives each nozzle its own plume, fixed to the car body.

## What the footage shows

Frames were sampled at full rate: every 1/30 s from the broadcast clip and its close replay angle, and every 1/24 s from Tesla's official overhead edit. They were kept in `artifacts/thruster-study/`, which is not distributed because it is cut from Tesla's footage (see [NOTICE.md](../../NOTICE.md)); the most useful sheets were `official-flip-1.jpg`, `official-flip-2.jpg`, `flip-close-1/2/3.jpg` and `main-flip.jpg`. The frame labels below (d…, r…, B…) refer to those sheets and to `references/roadster/frames.json`.

1. **The car leaves the overhang lip upside down.** While it is still inverted, cyan jets stream from nozzles on one side toward the sky (overhead frames d001–d007; replay r063–r090).
2. **It rolls about its long axis to wheels-down.** The heading never changes: the overhead edit sees the belly, then the side, then the roof (d009–d033), and the front-on replay sees the car turn in the image plane (r101–r146).
3. **There are no side thrusters.** The four corner nozzles point down, perpendicular to the floor pan. A jet that looks sideways or splayed (d033–d051) is one of these nozzles, seen while the car is still banked.
4. **The roll is a two-sided burn.** The nozzles on one side start it. Upside down, they push that side toward the ground. The opposite side then fires to stop the roll (d033–d041 show a long plume on the far side). After that, all four fire together to arrest the fall and hover into the cloud (B09–B11, d043–d081).
5. **Broadcast timing:** the car is at the lip at about 8.25 s, rolled 90° at about 8.75 s, and upright at about 9.45 s.

## Model

- **Rigid car.** Mass is 1,900 kg. The inertias come from a 4.6 × 2.0 × 1.2 m box: about 870 kg·m² in roll, 4,000 in yaw and 3,600 in pitch.
- **Nozzles.** They sit under the floor, inboard of the wheels, at (±1.05, 0.14, ±0.55) m in the car frame. They point straight down, perpendicular to the floor pan, and each produces up to 15 kN. The roll torque comes from the sideways offset of each side's pair from the centre of mass.
- **Attitude.** The roll is a constant-torque bang-bang burn over [8.25, 9.45] s, about 8.7 rad/s². That needs about 7.6 kN·m of torque, roughly 14 kN on one side at a 0.55 m lever arm.
- **Thrust allocation.** For every sample, the required body wrench is computed. The force is m(a − g) from the track. The torque is Iα + ω × Iω from the attitude. The wrench is then split across the four nozzles by bounded least squares, solved exactly by active-set enumeration.

## Result

- **8.2–8.8 s:** the right-side pair fires (about 10 kN each). This also accounts for the fitted track falling faster than gravity just after the lip: upside down, the nozzles push the car toward the ground.
- **8.9–9.4 s:** the left-side pair fires to stop the roll.
- **9.5–10.4 s:** all four fire at up to full thrust (about 54 kN total) to arrest a fall of about 12 m/s.
- **11.2–11.5 s:** a cushioning burn before touchdown.

Between those burns, the fitted track's weak-acceleration prior implies brief free fall. The footage instead shows plumes running continuously, so a 40% hover floor is applied from 9.6 to 11.45 s. That is a stated departure from pure inverse dynamics.

## Limits

The track's air positions are a single-camera fit and are not surveyed. Mass, inertia, nozzle layout and maximum thrust are engineering estimates, chosen to agree with the footage. The roll direction (right side first) is a choice; the footage shows one side firing but doesn't fix which side in the track's frame.
