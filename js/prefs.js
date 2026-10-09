window.GL = window.GL || {};

(() => {
  'use strict';

  // Per-device settings and hacker progression, kept in localStorage when available.
  const KEY = 'ghostlink-prefs';
  const DEFAULTS = { codename: '', sound: true, voice: true, vibration: true, intro: 'full', xp: 0, stats: {} };
  let data = { ...DEFAULTS };
  try { data = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { /* storage blocked */ }

  const RANKS = ['Script kiddie', 'Curioso', 'Infiltrato', 'Operatore', 'Cacciatore di bug', 'Spettro', 'Fantasma', 'Leggenda della rete'];
  const listeners = new Set();

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(data)); } catch { /* storage blocked */ }
    listeners.forEach(fn => fn(data));
  }

  function get() { return data; }
  function set(patch) { data = { ...data, ...patch }; save(); }
  function onChange(fn) { listeners.add(fn); }

  // Level n needs 60·n² XP in total.
  function level(xp = data.xp) {
    const lvl = Math.floor(Math.sqrt(xp / 60)) + 1;
    const from = 60 * (lvl - 1) ** 2;
    const to = 60 * lvl ** 2;
    return { lvl, rank: RANKS[Math.min(lvl - 1, RANKS.length - 1)], progress: (xp - from) / (to - from), next: to - xp };
  }

  // Award XP for an action; returns the new level when the action levels the user up.
  function addXP(amount, action) {
    const before = level().lvl;
    const stats = { ...data.stats };
    if (action) stats[action] = (stats[action] || 0) + 1;
    data = { ...data, xp: data.xp + amount, stats };
    save();
    const after = level();
    return after.lvl > before ? after : null;
  }

  const CODENAMES = ['SPETTRO', 'NEBBIA', 'CORVO', 'GLITCH', 'FANTASMA', 'VIPERA', 'ECO', 'NODO', 'ZERO', 'OMBRA', 'PIXEL', 'RADAR'];
  function randomCodename() {
    const n = crypto.getRandomValues(new Uint8Array(2));
    return `${CODENAMES[n[0] % CODENAMES.length]}-${String(n[1] % 100).padStart(2, '0')}`;
  }

  function reset() { data = { ...DEFAULTS }; save(); }

  GL.prefs = { get, set, onChange, level, addXP, randomCodename, reset };
})();
