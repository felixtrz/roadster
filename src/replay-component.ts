import { createComponent, Types } from '@iwsdk/core';

/** Time is relative to the second ramp run (event 07:08). */
export const RoadsterReplay = createComponent('RoadsterReplay', {
  elapsed: { type: Types.Float32, default: 0 },
  playing: { type: Types.Boolean, default: true },
  speed: { type: Types.Float32, default: 1 },
  phase: { type: Types.String, default: 'Ready' },
});
