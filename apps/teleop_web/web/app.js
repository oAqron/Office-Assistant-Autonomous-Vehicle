'use strict';

// ─────────────────────────────────────────────────────────────────────────────
//  Constants
// ─────────────────────────────────────────────────────────────────────────────

const WS_PATH       = '/ws';
const CMD_HZ        = 20;          // command send rate (Hz) — matches 0.1 s teleop loop
const RECONNECT_MS  = 3000;
const PING_INTERVAL = 2000;        // keep session lock alive
const DEADZONE      = 0.04;        // joystick dead-zone (normalised radius)

// ─────────────────────────────────────────────────────────────────────────────
//  Joystick (canvas, pointer events)
//  X-axis → linear_y (strafe right = positive)
//  Y-axis → linear_x (forward = positive, canvas Y is inverted)
// ─────────────────────────────────────────────────────────────────────────────

class Joystick {
  constructor(canvas) {
    this._canvas = canvas;
    this._ctx    = canvas.getContext('2d');
    this._size   = canvas.width;
    this._cx     = this._size / 2;
    this._cy     = this._size / 2;
    this._r_base = this._size / 2 - 10;
    this._r_knob = this._size / 8;
    this._dx = 0;
    this._dy = 0;
    this._active = false;

    canvas.addEventListener('pointerdown',  this._onDown.bind(this));
    canvas.addEventListener('pointermove',  this._onMove.bind(this));
    canvas.addEventListener('pointerup',    this._onUp.bind(this));
    canvas.addEventListener('pointercancel',this._onUp.bind(this));
    this._draw();
  }

  /** Returns {lx, ly} – forward/strafe – each in [-1, 1] with dead-zone. */
  getValue() {
    const norm = this._r_base;
    let x =  this._dx / norm;   // right = positive vy (strafe)
    let y = -this._dy / norm;   // up    = positive vx (forward) — canvas Y inverted
    const mag = Math.sqrt(x * x + y * y);
    if (mag < DEADZONE) return { lx: 0, ly: 0 };
    const scaled = (mag - DEADZONE) / (1 - DEADZONE);
    const s = Math.min(scaled, 1) / mag;
    return { lx: y * s, ly: x * s };
  }

  _onDown(e) {
    e.preventDefault();
    this._canvas.setPointerCapture(e.pointerId);
    this._active = true;
    this._update(e);
  }
  _onMove(e) {
    if (!this._active) return;
    e.preventDefault();
    this._update(e);
  }
  _onUp() {
    this._active = false;
    this._dx = 0;
    this._dy = 0;
    this._draw();
  }
  _update(e) {
    const rect = this._canvas.getBoundingClientRect();
    const scaleX = this._canvas.width  / rect.width;
    const scaleY = this._canvas.height / rect.height;
    const px = (e.clientX - rect.left) * scaleX - this._cx;
    const py = (e.clientY - rect.top)  * scaleY - this._cy;
    const dist = Math.sqrt(px * px + py * py);
    if (dist > this._r_base) {
      this._dx = (px / dist) * this._r_base;
      this._dy = (py / dist) * this._r_base;
    } else {
      this._dx = px;
      this._dy = py;
    }
    this._draw();
  }
  _draw() {
    const ctx = this._ctx, size = this._size, cx = this._cx, cy = this._cy;
    ctx.clearRect(0, 0, size, size);

    ctx.beginPath();
    ctx.arc(cx, cy, this._r_base, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(48, 54, 61, 0.9)';
    ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = 'rgba(22, 27, 34, 0.6)'; ctx.fill();

    ctx.strokeStyle = 'rgba(125, 133, 144, 0.25)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cx - this._r_base, cy); ctx.lineTo(cx + this._r_base, cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, cy - this._r_base); ctx.lineTo(cx, cy + this._r_base); ctx.stroke();

    const kx = cx + this._dx, ky = cy + this._dy;
    const { lx, ly } = this.getValue();
    const active = Math.sqrt(lx * lx + ly * ly) > 0;

    ctx.beginPath();
    ctx.arc(kx, ky, this._r_knob + 4, 0, Math.PI * 2);
    ctx.fillStyle = active ? 'rgba(88, 166, 255, 0.15)' : 'rgba(0,0,0,0)'; ctx.fill();

    const grad = ctx.createRadialGradient(kx - 4, ky - 4, 2, kx, ky, this._r_knob);
    grad.addColorStop(0, active ? '#79c0ff' : '#484f58');
    grad.addColorStop(1, active ? '#1f6feb' : '#21262d');
    ctx.beginPath(); ctx.arc(kx, ky, this._r_knob, 0, Math.PI * 2);
    ctx.fillStyle = grad; ctx.fill();
    ctx.strokeStyle = active ? '#58a6ff' : '#30363d'; ctx.lineWidth = 2; ctx.stroke();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Keyboard controller — WASD + Q/E matches original teleop script
//  w/s → vx   a/d → vy   q/e → vz
// ─────────────────────────────────────────────────────────────────────────────

class KeyboardController {
  constructor() {
    this._keys = new Set();
    window.addEventListener('keydown', e => {
      this._keys.add(e.key.toLowerCase());
      _updateKeyUI(this._keys);
    });
    window.addEventListener('keyup', e => {
      this._keys.delete(e.key.toLowerCase());
      _updateKeyUI(this._keys);
    });
    window.addEventListener('blur', () => { this._keys.clear(); _updateKeyUI(this._keys); });
  }

  /** Returns {lx, ly, az} each in [-1, 1]. */
  getValue() {
    const fwd   = this._keys.has('w') || this._keys.has('arrowup');
    const rev   = this._keys.has('s') || this._keys.has('arrowdown');
    const left  = this._keys.has('a') || this._keys.has('arrowleft');
    const right = this._keys.has('d') || this._keys.has('arrowright');
    const rotCCW = this._keys.has('q');
    const rotCW  = this._keys.has('e');
    return {
      lx: (fwd   ? 1 : 0) - (rev   ? 1 : 0),
      ly: (right ? 1 : 0) - (left  ? 1 : 0),
      az: (rotCW ? 1 : 0) - (rotCCW ? 1 : 0),
    };
  }
}

function _updateKeyUI(keys) {
  const map = {
    'key-w': ['w', 'arrowup'],
    'key-s': ['s', 'arrowdown'],
    'key-a': ['a', 'arrowleft'],
    'key-d': ['d', 'arrowright'],
    'key-q': ['q'],
    'key-e': ['e'],
  };
  for (const [id, triggers] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', triggers.some(k => keys.has(k)));
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Rotation button controller
//  Pointerdown/up on #btn-rot-ccw and #btn-rot-cw set a held rotation value.
// ─────────────────────────────────────────────────────────────────────────────

class RotationButtons {
  constructor() {
    this._az = 0;
    this._attach('btn-rot-ccw', -1);
    this._attach('btn-rot-cw',   1);
  }

  getValue() { return this._az; }

  _attach(id, value) {
    const btn = document.getElementById(id);
    if (!btn) return;
    const start = (e) => { e.preventDefault(); this._az = value; btn.classList.add('active'); };
    const stop  = ()  => { this._az = 0; btn.classList.remove('active'); };
    btn.addEventListener('pointerdown',  start);
    btn.addEventListener('pointerup',    stop);
    btn.addEventListener('pointercancel',stop);
    btn.addEventListener('pointerleave', stop);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Telemetry bars — show vx, vy, vz
// ─────────────────────────────────────────────────────────────────────────────

function _setBar(barId, valId, v) {
  const bar = document.getElementById(barId);
  const lbl = document.getElementById(valId);
  if (!bar || !lbl) return;
  const pct = Math.abs(v) * 50;
  if (v >= 0) {
    bar.style.left  = '50%';
    bar.style.width = pct + '%';
  } else {
    bar.style.left  = (50 - pct) + '%';
    bar.style.width = pct + '%';
  }
  bar.style.background = v > 0.05 ? 'var(--accent)' : v < -0.05 ? 'var(--yellow)' : 'var(--border)';
  lbl.textContent = v.toFixed(2);
}

function _updateTelemetry(lx, ly, az) {
  const fmt = v => v.toFixed(3);
  document.getElementById('tval-lx').textContent = fmt(lx);
  document.getElementById('tval-ly').textContent = fmt(ly);
  document.getElementById('tval-az').textContent = fmt(az);
  _setBar('bar-vx', 'barval-vx', lx);
  _setBar('bar-vy', 'barval-vy', ly);
  _setBar('bar-vz', 'barval-vz', az);
}

// ─────────────────────────────────────────────────────────────────────────────
//  Log strip
// ─────────────────────────────────────────────────────────────────────────────

const _logEl = document.getElementById('log');
let _logCount = 0;
const _MAX_LOG = 40;

function log(msg, level = '') {
  if (!_logEl) return;
  const entry = document.createElement('div');
  entry.className = 'entry' + (level ? ' ' + level : '');
  const ts = new Date().toLocaleTimeString('en-GB', { hour12: false });
  entry.textContent = `[${ts}] ${msg}`;
  _logEl.prepend(entry);
  if (++_logCount > _MAX_LOG) {
    while (_logEl.children.length > _MAX_LOG) _logEl.removeChild(_logEl.lastChild);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Main application
// ─────────────────────────────────────────────────────────────────────────────

class VehicleWebTeleop {
  constructor() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    this._wsUrl = `${proto}://${location.host}${WS_PATH}`;

    this._ws          = null;
    this._clientId    = null;
    this._hasLock     = false;
    this._estopActive = false;
    this._speedMult   = 0.6;

    this._joystick  = new Joystick(document.getElementById('joystick-canvas'));
    this._keyboard  = new KeyboardController();
    this._rotBtns   = new RotationButtons();

    this._bindUI();
    this._connect();
    this._startCmdLoop();
    this._startPingLoop();
  }

  // ── UI wiring ─────────────────────────────────────────────────────────────

  _bindUI() {
    document.getElementById('btn-lock').addEventListener('click', () => {
      if (this._hasLock) this._releaseLock();
      else               this._acquireLock();
    });

    document.getElementById('btn-estop').addEventListener('click', () => {
      this._send({ type: 'estop' });
      log('E-STOP sent', 'warn');
    });

    const slider  = document.getElementById('speed-slider');
    const speedEl = document.getElementById('speed-val');
    slider.addEventListener('input', () => {
      this._speedMult = slider.value / 100;
      speedEl.textContent = this._speedMult.toFixed(2) + '×';
    });
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────

  _connect() {
    log(`Connecting to ${this._wsUrl}…`);
    this._ws = new WebSocket(this._wsUrl);

    this._ws.onopen = () => {
      log('WebSocket connected');
      this._setConnected(true);
    };
    this._ws.onclose = () => {
      log('WebSocket closed – reconnecting…', 'warn');
      this._setConnected(false);
      this._hasLock = false;
      this._updateLockUI();
      setTimeout(() => this._connect(), RECONNECT_MS);
    };
    this._ws.onerror = () => log('WS error', 'error');
    this._ws.onmessage = (e) => {
      try { this._handleMessage(JSON.parse(e.data)); } catch (_) {}
    };
  }

  _send(obj) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN)
      this._ws.send(JSON.stringify(obj));
  }

  // ── Message handling ──────────────────────────────────────────────────────

  _handleMessage(msg) {
    switch (msg.type) {
      case 'assigned_id':
        this._clientId = msg.client_id;
        log(`Assigned ID: ${msg.client_id.slice(0, 8)}…`);
        break;
      case 'lock_status':
        this._hasLock = msg.controller_id === this._clientId;
        this._updateLockUI(msg);
        break;
      case 'lock_acquired':
        this._hasLock = true;
        this._updateLockUI();
        log('Lock acquired – you are in control');
        break;
      case 'lock_denied':
        log(`Lock denied: ${msg.reason}`, 'warn');
        break;
      case 'lock_released':
        if (msg.client_id === this._clientId) {
          this._hasLock = false;
          this._updateLockUI();
          log(`Lock released${msg.reason ? ' (' + msg.reason + ')' : ''}`);
        } else {
          log(`Other client released lock`);
        }
        break;
      case 'estop_activated':
        this._estopActive = true;
        document.getElementById('btn-estop').classList.add('active');
        log(`E-STOP by ${msg.triggered_by?.slice(0, 8)}`, 'error');
        break;
      case 'estop_cleared':
        this._estopActive = false;
        document.getElementById('btn-estop').classList.remove('active');
        log('E-STOP cleared');
        break;
      case 'pong': break;
      case 'error': log(`Server error: ${msg.message}`, 'error'); break;
    }
  }

  // ── Lock ──────────────────────────────────────────────────────────────────

  _acquireLock() { this._send({ type: 'acquire_lock' }); }
  _releaseLock() { this._send({ type: 'release_lock' }); }

  _updateLockUI(statusMsg) {
    const badge = document.getElementById('badge-lock');
    const text  = document.getElementById('badge-lock-text');
    const btn   = document.getElementById('btn-lock');
    if (this._hasLock) {
      badge.className = 'badge locked'; text.textContent = 'Controller';
      btn.textContent = 'Release Lock'; btn.classList.add('has-lock');
    } else if (statusMsg?.locked) {
      badge.className = 'badge'; text.textContent = 'Locked (other)';
      btn.textContent = 'Acquire Lock'; btn.classList.remove('has-lock');
    } else {
      badge.className = 'badge'; text.textContent = 'No lock';
      btn.textContent = 'Acquire Lock'; btn.classList.remove('has-lock');
    }
  }

  _setConnected(connected) {
    const badge = document.getElementById('badge-conn');
    const text  = document.getElementById('badge-conn-text');
    badge.className  = 'badge' + (connected ? ' connected' : '');
    text.textContent = connected ? 'Connected' : 'Disconnected';
  }

  // ── Command loop (20 Hz) ──────────────────────────────────────────────────
  // Priority: joystick (if active) overrides keyboard, per-axis.
  // Rotation buttons supplement keyboard Q/E.

  _startCmdLoop() {
    setInterval(() => {
      if (!this._hasLock) return;
      if (!this._ws || this._ws.readyState !== WebSocket.OPEN) return;

      const joy = this._joystick.getValue();   // {lx, ly}
      const kbd = this._keyboard.getValue();   // {lx, ly, az}

      // Joystick axes take priority when the knob is off-centre.
      const rawLx = Math.abs(joy.lx) > Math.abs(kbd.lx) ? joy.lx : kbd.lx;
      const rawLy = Math.abs(joy.ly) > Math.abs(kbd.ly) ? joy.ly : kbd.ly;
      // Rotation: keyboard Q/E + rotation buttons (additive, clamped)
      const rawAz = Math.max(-1, Math.min(1, kbd.az + this._rotBtns.getValue()));

      const lx = rawLx * this._speedMult;
      const ly = rawLy * this._speedMult;
      const az = rawAz * this._speedMult;

      this._send({ type: 'cmd_vel', linear_x: lx, linear_y: ly, angular_z: az });
      _updateTelemetry(lx, ly, az);

    }, 1000 / CMD_HZ);
  }

  // ── Heartbeat ─────────────────────────────────────────────────────────────

  _startPingLoop() {
    setInterval(() => {
      if (this._hasLock) this._send({ type: 'ping' });
    }, PING_INTERVAL);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Bootstrap
// ─────────────────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  window._teleop = new VehicleWebTeleop();
});
