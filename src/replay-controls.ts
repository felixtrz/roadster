import { AUTOMATION } from './automation.js';
import { type Entity, type UIKit, UIKitMLAsset, VisibilityState, type World } from '@iwsdk/core';
import { RoadsterReplay } from './replay-component.js';
import { VIEW_NAMES } from './replay-camera.js';
import { BrowserShell, type ShellFrame } from './shell.js';

export const PHASES = [
  { id: 'approach', label: 'Approach', time: 1.5 },
  { id: 'climb', label: 'Climb', time: 2.783 },
  { id: 'release', label: 'Release', time: 7.9 },
  { id: 'reorient', label: 'Reorient', time: 8.167 },
  { id: 'descent', label: 'Descent', time: 9.5 },
  { id: 'landing', label: 'Landing', time: 11.133 },
  { id: 'drive-away', label: 'Drive away', time: 11.833 },
] as const;

/**
 * One control surface, two presentations: the UIKitML panel (XR) and the HTML
 * shell (browser). Both, plus the keyboard and window.roadster, write the same
 * RoadsterReplay component.
 */
export class ReplayControls {
  viewMode = 0;
  readonly shell: BrowserShell;
  private readonly cleanups: (() => void)[] = [];
  private readonly phase: UIKit.Text;
  private readonly time: UIKit.Text;
  private readonly playLabel: UIKit.Text;
  private readonly speedLabel: UIKit.Text;
  private readonly viewLabel: UIKit.Text;
  private readonly progress: UIKit.Text;
  private readonly labels: string[];
  private readonly progressWidths: `${number}%`[];
  private readonly phaseProps = { text: 'READY' };
  private readonly timeProps = { text: '' };
  private readonly progressProps: { width: `${number}%` } = { width: '0%' };
  private lastTime = -1;
  private lastPhase = '';
  private lastProgress = -1;

  constructor(private readonly world: World, panel: UIKitMLAsset, private readonly states: () => Iterable<Entity>, readonly duration: number) {
    this.phase = panel.requireElementById<UIKit.Text>('Phase');
    this.time = panel.requireElementById<UIKit.Text>('Time');
    this.playLabel = panel.requireElementById<UIKit.Text>('PlayLabel');
    this.speedLabel = panel.requireElementById<UIKit.Text>('SpeedLabel');
    this.viewLabel = panel.requireElementById<UIKit.Text>('ViewLabel');
    this.progress = panel.requireElementById<UIKit.Text>('Progress');
    this.labels = Array.from({ length: Math.ceil(duration * 10) + 1 }, (_, i) => `${(i / 10).toFixed(1).padStart(4, '0')} / ${duration.toFixed(1)}`);
    this.progressWidths = Array.from({ length: 101 }, (_, i) => `${i}%` as `${number}%`);
    const bind = (id: string, action: () => void): void => {
      const element = panel.requireElementById(id); element.name = id;
      element.addEventListener('click', action);
      this.cleanups.push(() => element.removeEventListener('click', action));
    };
    bind('PlayPause', () => this.toggle());
    bind('Restart', () => this.restart());
    bind('SlowMotion', () => this.setSpeed(this.speed() === 1 ? 0.25 : 1));
    bind('View', () => this.setView((this.viewMode + 1) % VIEW_NAMES.length));
    bind('EnterXR', () => this.toggleXR());
    const xr = panel.requireElementById('EnterXR');
    const xrLabel = panel.requireElementById<UIKit.Text>('XRLabel');
    const view = panel.requireElementById('View');
    this.shell = new BrowserShell({
      duration, phases: PHASES,
      play: () => this.setPlaying(true), pause: () => this.setPlaying(false), toggle: () => this.toggle(),
      restart: () => this.restart(), seek: (t) => this.seek(t), setSpeed: (s) => this.setSpeed(s),
      setView: (m) => this.setView(m), enterXR: () => this.toggleXR(),
    }, this.xrSupported());
    this.cleanups.push(() => this.shell.dispose());
    this.cleanups.push(world.visibilityState.subscribe((state) => {
      const browser = state === VisibilityState.NonImmersive;
      xr.setProperties({ display: world.xrEnabled ? 'flex' : 'none' });
      xrLabel.setProperties({ text: browser ? 'Enter XR' : 'Exit XR' });
      view.setProperties({ display: browser ? 'flex' : 'none' });
      // The browser uses the HTML shell; the spatial panel is the XR control surface.
      panel.document.visible = !browser;
      this.shell.setVisible(browser);
    }));
    const keyboard = (event: KeyboardEvent): void => {
      if ((event.target as HTMLElement)?.matches('input,textarea,select')) return;
      if (event.repeat && ['Space', 'KeyR'].includes(event.code)) return;
      if (event.code === 'Space') { event.preventDefault(); this.toggle(); }
      if (event.code === 'KeyR') this.restart();
      if (event.code.startsWith('Digit')) {
        const mode = Number(event.code.slice(-1)) - 1;
        if (mode >= 0 && mode < VIEW_NAMES.length) this.setView(mode);
      }
      if (event.code === 'ArrowLeft' || event.code === 'ArrowRight') {
        event.preventDefault();
        for (const entity of this.states()) this.seek((entity.getValue(RoadsterReplay, 'elapsed') ?? 0) + (event.code === 'ArrowLeft' ? -0.5 : 0.5));
      }
    };
    window.addEventListener('keydown', keyboard);
    this.cleanups.push(() => window.removeEventListener('keydown', keyboard));
    if (AUTOMATION) Object.assign(window, { roadster: {
      seek: (seconds: number) => this.seek(seconds),
      play: () => this.setPlaying(true), pause: () => this.setPlaying(false),
      restart: () => this.restart(), view: (mode: number) => this.setView(mode),
      speed: (speed: number) => this.setSpeed(speed),
      skipIntro: () => { this.shell.introActive = false; document.getElementById('shell')?.classList.remove('intro-active'); },
      showIntro: () => { this.shell.introActive = true; document.getElementById('shell')?.classList.add('intro-active'); },
      duration, phases: PHASES,
      state: () => Array.from(this.states(), (entity) => ({ time: entity.getValue(RoadsterReplay, 'elapsed'), playing: entity.getValue(RoadsterReplay, 'playing'), phase: entity.getValue(RoadsterReplay, 'phase'), speed: entity.getValue(RoadsterReplay, 'speed'), view: this.viewMode })),
    } });
    if (AUTOMATION) this.cleanups.push(() => { Reflect.deleteProperty(window, 'roadster'); });
    // Hold on the opening frame behind the intro card until the viewer presses play.
    this.seek(0);
  }

  get introActive(): boolean { return this.shell.introActive; }

  private async xrSupported(): Promise<boolean> {
    if (!this.world.xrEnabled) return false;
    try { return (await navigator.xr?.isSessionSupported('immersive-vr')) ?? false; } catch { return false; }
  }

  private toggleXR(): void {
    if (this.world.visibilityState.peek() === VisibilityState.NonImmersive) void this.world.launchXR();
    else void this.world.exitXR();
  }

  private speed(): number {
    for (const entity of this.states()) return entity.getValue(RoadsterReplay, 'speed') ?? 1;
    return 1;
  }

  setSpeed(speed: number): void {
    if (!Number.isFinite(speed) || speed <= 0) return;
    for (const entity of this.states()) entity.setValue(RoadsterReplay, 'speed', speed);
    this.speedLabel.setProperties({ text: speed === 1 ? '1x' : `${speed}x` });
  }

  setView(mode: number): void {
    if (!Number.isFinite(mode)) return;
    this.viewMode = Math.max(0, Math.min(VIEW_NAMES.length - 1, Math.floor(mode)));
    this.viewLabel.setProperties({ text: `${VIEW_NAMES[this.viewMode]} view` });
  }

  seek(seconds: number): void {
    if (!Number.isFinite(seconds)) return;
    for (const entity of this.states()) entity.setValue(RoadsterReplay, 'elapsed', Math.max(0, Math.min(this.duration, seconds)));
    this.setPlaying(false);
  }

  restart(): void {
    for (const entity of this.states()) entity.setValue(RoadsterReplay, 'elapsed', 0);
    this.setPlaying(true);
  }

  setPlaying(playing: boolean): void {
    for (const entity of this.states()) entity.setValue(RoadsterReplay, 'playing', playing);
    this.playLabel.setProperties({ text: playing ? 'Pause' : 'Play' });
  }

  toggle(): void {
    if (this.shell.introActive) { this.shell.dismissIntro(); return; }
    for (const entity of this.states()) {
      if ((entity.getValue(RoadsterReplay, 'elapsed') ?? 0) >= this.duration) { this.restart(); return; }
      this.setPlaying(!entity.getValue(RoadsterReplay, 'playing'));
    }
  }

  update(seconds: number, phase: string, phaseLabel: string, frame: ShellFrame | null): void {
    const index = Math.max(0, Math.min(this.labels.length - 1, Math.floor(seconds * 10)));
    if (index !== this.lastTime) { this.lastTime = index; this.timeProps.text = this.labels[index]; this.time.setProperties(this.timeProps); }
    if (phase !== this.lastPhase) { this.lastPhase = phase; this.phaseProps.text = phaseLabel; this.phase.setProperties(this.phaseProps); }
    const progress = Math.round((seconds / this.duration) * 100);
    if (progress !== this.lastProgress) { this.lastProgress = progress; this.progressProps.width = this.progressWidths[progress]; this.progress.setProperties(this.progressProps); }
    if (frame) this.shell.update(frame);
  }

  dispose(): void { for (const cleanup of this.cleanups) cleanup(); }
}
