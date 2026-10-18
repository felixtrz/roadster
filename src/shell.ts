/**
 * Browser-view presentation shell: intro card, broadcast HUD (g-force,
 * altitude, attitude, phase), and a transport bar with a chaptered scrubber.
 * It never owns replay state; every control calls back into ReplayControls,
 * which writes the RoadsterReplay component.
 */

export interface ShellHost {
  duration: number;
  phases: readonly { id: string; label: string; time: number }[];
  play(): void;
  pause(): void;
  toggle(): void;
  restart(): void;
  seek(seconds: number): void;
  setSpeed(speed: number): void;
  setView(mode: number): void;
  enterXR(): void;
}

export interface ShellFrame {
  time: number; playing: boolean; speed: number; view: number; phase: string;
  altitudeFt: number; g: number; pitchDeg: number; inverted: boolean; rollScale: number; impact: number;
}

const VIEW_LABELS = ['Show', 'Wide', 'Car', 'Top'];
const ICONS = {
  play: '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M7 5h3.6v14H7zM13.4 5H17v14h-3.6z" fill="currentColor"/></svg>',
  restart: '<svg viewBox="0 0 24 24"><path d="M12 5a7 7 0 1 1-6.62 4.73" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M4.2 4.6v5.2h5.2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  xr: '<svg viewBox="0 0 24 24"><path d="M3.5 8.5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v6.2a2 2 0 0 1-2 2h-3.6l-1.7-2.4a1.4 1.4 0 0 0-2.4 0l-1.7 2.4H5.5a2 2 0 0 1-2-2z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
};
const CAR_PROFILE = '<svg viewBox="0 0 64 24" class="car-profile"><path d="M3 16.5c0-2 1.4-3.4 4-4l9-1.6 8.6-5.2c1.6-.9 3.2-1.3 5.2-1.3h7.6c2.3 0 4.3.7 6 2l5 4 8.4 1.2c2.3.4 4.2 2 4.2 4.4v1.8H3z" fill="currentColor"/><circle cx="15" cy="18.6" r="4.2" fill="#0b0d10" stroke="currentColor" stroke-width="1.6"/><circle cx="49" cy="18.6" r="4.2" fill="#0b0d10" stroke="currentColor" stroke-width="1.6"/></svg>';

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, html = ''): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (html) node.innerHTML = html;
  return node;
}

function gauge(label: string, unit: string): { root: HTMLElement; value: HTMLElement; arc: SVGCircleElement } {
  const root = el('div', 'gauge');
  root.innerHTML = `<svg viewBox="0 0 100 100"><circle class="track" cx="50" cy="50" r="44"/><circle class="arc" cx="50" cy="50" r="44"/></svg>
    <div class="gauge-text"><span class="gauge-label">${label}</span><span class="gauge-value">0.0</span><span class="gauge-unit">${unit}</span></div>`;
  return { root, value: root.querySelector('.gauge-value') as HTMLElement, arc: root.querySelector('.arc') as SVGCircleElement };
}

export class BrowserShell {
  private readonly root: HTMLElement;
  private readonly intro: HTMLElement;
  private readonly hud: HTMLElement;
  private readonly playButton: HTMLButtonElement;
  private readonly speedButton: HTMLButtonElement;
  private readonly progress: HTMLElement;
  private readonly playhead: HTMLElement;
  private readonly playheadRail: HTMLElement;
  private readonly timeLabel: HTMLElement;
  private readonly phaseIndex: HTMLElement;
  private readonly phaseName: HTMLElement;
  private readonly viewButtons: HTMLButtonElement[] = [];
  private readonly segments: HTMLElement[] = [];
  private readonly gForce = gauge('G-Force', 'G');
  private readonly altitude = gauge('Altitude', 'FT');
  private readonly attitude: HTMLElement;
  private readonly tooltip: HTMLElement;
  private readonly cleanups: (() => void)[] = [];
  private readonly timeLabels: string[];
  private readonly gLabels: string[];
  private readonly altLabels: string[];
  private last = { time: -1, playing: false as boolean | null, speed: -1, view: -1, phase: '', g: -1, alt: -1, pitch: 999, inverted: false, roll: 999, progress: -1 };
  private idleTimer = 0;
  introActive = true;
  private wasPlaying = false;
  private scrubbing = false;

  constructor(private readonly host: ShellHost, xrAvailable: Promise<boolean>) {
    this.timeLabels = Array.from({ length: Math.ceil(host.duration * 10) + 1 }, (_, i) => (i / 10).toFixed(1).padStart(4, '0'));
    this.gLabels = Array.from({ length: 61 }, (_, i) => (i / 10).toFixed(1));
    this.altLabels = Array.from({ length: 1001 }, (_, i) => (i / 10).toFixed(1));
    const mount = document.getElementById('shell') ?? document.body.appendChild(el('div', ''));
    mount.id = 'shell';
    this.root = mount;
    this.root.innerHTML = '';
    this.root.append(el('div', 'grade'), el('div', 'grain'), el('div', 'letterbox top'), el('div', 'letterbox bottom'));

    // Intro card
    this.intro = el('section', 'intro');
    this.intro.innerHTML = `
      <div class="intro-inner">
        <p class="eyebrow"><span class="dot"></span>McGregor, Texas &middot; Night run</p>
        <h1 class="wordmark">ROADSTER</h1>
        <p class="subtitle">The Ramp</p>
        <p class="tagline">Seventy-two feet of curved concrete. A flip on cold-gas thrusters.<br/>A touchdown inside its own cloud.</p>
        <div class="intro-actions">
          <button class="cta" data-action="play"><span class="cta-icon">${ICONS.play}</span>Watch the run</button>
          <button class="ghost xr-only" data-action="xr">${ICONS.xr}Enter XR</button>
        </div>
        <p class="fineprint">A reconstruction from the broadcast. 18 seconds. Scrub, slow it down, or step inside.</p>
      </div>`;
    this.root.append(this.intro);

    // HUD
    this.hud = el('div', 'hud');
    const bug = el('div', 'bug', `<span class="live">REPLAY</span><span class="bug-title">ROADSTER <b>THE RAMP</b></span><span class="bug-sub">McGregor test site &middot; run 2</span>`);
    const phase = el('div', 'phase');
    this.phaseIndex = el('span', 'phase-index', '01');
    this.phaseName = el('span', 'phase-name', 'READY');
    phase.append(this.phaseIndex, this.phaseName);
    const left = el('div', 'cluster left');
    this.attitude = el('div', 'attitude', CAR_PROFILE);
    left.append(this.gForce.root, this.attitude);
    const right = el('div', 'cluster right');
    right.append(this.altitude.root);
    this.hud.append(bug, phase, left, right);
    this.root.append(this.hud);

    // Transport
    const bar = el('div', 'transport');
    this.playButton = el('button', 'icon-btn play', ICONS.pause);
    this.playButton.title = 'Play / pause (Space)';
    const restart = el('button', 'icon-btn', ICONS.restart); restart.title = 'Restart (R)';
    this.speedButton = el('button', 'pill-btn speed', '1&times;'); this.speedButton.title = 'Slow motion (S)';
    const timeline = el('div', 'timeline');
    const rail = el('div', 'rail');
    for (let i = 0; i < host.phases.length; i++) {
      const phaseDef = host.phases[i];
      const end = i + 1 < host.phases.length ? host.phases[i + 1].time : host.duration;
      const seg = el('div', 'segment');
      seg.style.left = `${(phaseDef.time / host.duration) * 100}%`;
      seg.style.width = `${((end - phaseDef.time) / host.duration) * 100}%`;
      seg.dataset.label = phaseDef.label;
      const tick = el('span', 'tick-label', phaseDef.label);
      seg.append(tick);
      rail.append(seg); this.segments.push(seg);
    }
    this.progress = el('div', 'progress');
    this.playhead = el('div', 'playhead');
    // the playhead rides a full-width layer moved by transform, so playback never forces a layout
    this.playheadRail = el('div', 'playhead-rail');
    this.playheadRail.append(this.playhead);
    this.tooltip = el('div', 'tooltip');
    rail.append(this.progress, this.playheadRail);
    timeline.append(rail, this.tooltip);
    this.timeLabel = el('span', 'time', `00.0 <i>/ ${host.duration.toFixed(1)}</i>`);
    const views = el('div', 'views');
    VIEW_LABELS.forEach((label, i) => {
      const b = el('button', 'view-btn', label); b.title = `${label} view (${i + 1})`;
      b.addEventListener('click', () => host.setView(i));
      views.append(b); this.viewButtons.push(b);
    });
    const xr = el('button', 'pill-btn xr xr-only', `${ICONS.xr}<span>Enter XR</span>`);
    bar.append(this.playButton, restart, this.speedButton, timeline, this.timeLabel, views, xr);
    this.root.append(bar);

    const on = <T extends Event>(target: EventTarget, type: string, fn: (e: T) => void, opts?: AddEventListenerOptions): void => {
      target.addEventListener(type, fn as EventListener, opts);
      this.cleanups.push(() => target.removeEventListener(type, fn as EventListener, opts));
    };
    on(this.playButton, 'click', () => host.toggle());
    on(restart, 'click', () => host.restart());
    on(this.speedButton, 'click', () => host.setSpeed(this.last.speed === 1 ? 0.25 : 1));
    on(xr, 'click', () => host.enterXR());
    on(this.intro.querySelector('[data-action="play"]') as HTMLElement, 'click', () => this.dismissIntro());
    on(this.intro.querySelector('[data-action="xr"]') as HTMLElement, 'click', () => { this.dismissIntro(); host.enterXR(); });
    const timeAt = (e: PointerEvent): number => {
      const r = rail.getBoundingClientRect();
      return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * host.duration;
    };
    on<PointerEvent>(timeline, 'pointerdown', (e) => {
      this.scrubbing = true; this.wasPlaying = this.last.playing === true;
      timeline.setPointerCapture(e.pointerId); host.seek(timeAt(e)); this.root.classList.add('scrubbing');
    });
    on<PointerEvent>(timeline, 'pointermove', (e) => {
      const t = timeAt(e);
      if (this.scrubbing) host.seek(t);
      const phaseLabel = [...host.phases].reverse().find((p) => p.time <= t)?.label ?? '';
      this.tooltip.textContent = `${phaseLabel}  ${t.toFixed(1)}s`;
      this.tooltip.style.left = `${(t / host.duration) * 100}%`;
    });
    const endScrub = (): void => {
      if (!this.scrubbing) return;
      this.scrubbing = false; this.root.classList.remove('scrubbing');
      if (this.wasPlaying) host.play();
    };
    on(timeline, 'pointerup', endScrub);
    on(timeline, 'pointercancel', endScrub);
    on(window, 'pointermove', () => this.poke());
    on(window, 'keydown', (e: KeyboardEvent) => {
      this.poke();
      if (this.introActive && (e.code === 'Space' || e.code === 'Enter')) { e.preventDefault(); e.stopImmediatePropagation(); this.dismissIntro(); }
      if (e.code === 'KeyS' && !this.introActive) host.setSpeed(this.last.speed === 1 ? 0.25 : 1);
    }, { capture: true });
    void xrAvailable.then((ok) => { this.root.classList.toggle('xr-available', ok); });
    this.root.classList.add('intro-active');
    this.poke();
  }

  private poke(): void {
    this.root.classList.remove('idle');
    window.clearTimeout(this.idleTimer);
    this.idleTimer = window.setTimeout(() => { if (this.last.playing) this.root.classList.add('idle'); }, 3200);
  }

  dismissIntro(): void {
    if (!this.introActive) return;
    this.introActive = false;
    this.root.classList.remove('intro-active');
    this.root.classList.add('intro-leaving');
    window.setTimeout(() => this.root.classList.remove('intro-leaving'), 1400);
    this.host.restart();
  }

  setVisible(visible: boolean): void { this.root.style.display = visible ? '' : 'none'; }

  update(frame: ShellFrame): void {
    const last = this.last;
    const tIndex = Math.max(0, Math.min(this.timeLabels.length - 1, Math.floor(frame.time * 10)));
    if (tIndex !== last.time) { last.time = tIndex; (this.timeLabel.firstChild as Text).data = `${this.timeLabels[tIndex]} `; }
    const progress = Math.round((frame.time / this.host.duration) * 2000) / 2000;
    if (progress !== last.progress) {
      last.progress = progress;
      this.progress.style.transform = `scaleX(${progress})`;
      this.playheadRail.style.transform = `translateX(${progress * 100}%)`;
    }
    if (frame.playing !== last.playing) {
      last.playing = frame.playing;
      this.playButton.innerHTML = frame.playing ? ICONS.pause : ICONS.play;
      this.root.classList.toggle('paused', !frame.playing);
    }
    if (frame.speed !== last.speed) {
      last.speed = frame.speed;
      this.speedButton.innerHTML = frame.speed === 1 ? '1&times;' : '&frac14;&times;';
      this.speedButton.classList.toggle('active', frame.speed !== 1);
      this.root.classList.toggle('slowmo', frame.speed !== 1);
    }
    if (frame.view !== last.view) {
      last.view = frame.view;
      this.viewButtons.forEach((b, i) => b.classList.toggle('active', i === frame.view));
    }
    if (frame.phase !== last.phase) {
      last.phase = frame.phase;
      let index = 0;
      this.host.phases.forEach((p, i) => { if (p.id === frame.phase) index = i; });
      const def = this.host.phases[index];
      this.phaseIndex.textContent = String(index + 1).padStart(2, '0');
      this.phaseName.textContent = def ? def.label : frame.phase;
      this.phaseName.classList.remove('flash'); void this.phaseName.offsetWidth; this.phaseName.classList.add('flash');
      this.segments.forEach((s, i) => { s.classList.toggle('current', i === index); s.classList.toggle('done', i < index); });
    }
    const g = Math.max(0, Math.min(60, Math.round(frame.g * 10)));
    if (g !== last.g) {
      last.g = g;
      this.gForce.value.textContent = this.gLabels[g];
      this.gForce.arc.style.strokeDashoffset = `${276.5 * (1 - Math.min(1, g / 40) * 0.75)}`;
      this.gForce.root.classList.toggle('hot', g >= 20);
    }
    const alt = Math.max(0, Math.min(1000, Math.round(frame.altitudeFt * 10)));
    if (alt !== last.alt) {
      last.alt = alt;
      this.altitude.value.textContent = this.altLabels[alt];
      this.altitude.arc.style.strokeDashoffset = `${276.5 * (1 - Math.min(1, alt / 800) * 0.75)}`;
    }
    const pitch = Math.round(frame.pitchDeg);
    const roll = Math.round(frame.rollScale * 50);
    if (pitch !== last.pitch || roll !== last.roll) {
      last.pitch = pitch; last.roll = roll;
      const r = roll / 50;
      this.attitude.style.setProperty('--pitch', `${-pitch}deg`);
      this.attitude.style.setProperty('--flip', `${Math.sign(r || 1) * Math.max(0.12, Math.abs(r))}`);
    }
  }

  dispose(): void {
    for (const cleanup of this.cleanups) cleanup();
    window.clearTimeout(this.idleTimer);
    this.root.innerHTML = '';
  }
}
