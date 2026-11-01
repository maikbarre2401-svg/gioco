// Collegamento ai dati: WebSocket quando si può, polling quando non si può.
//
// Il server spinge una sola fotografia per tutti i collegati invece di rispondere a una
// richiesta per client ogni tre secondi; se il WebSocket non è disponibile (proxy che lo
// blocca, browser antico) si ricade sul polling senza che il resto della pagina se ne accorga.

import { CFG, QS, Emettitore, api } from './util.js';

const RITENTA_MAX = 15000;
const PERIODO_POLL = 3000;

export class Live extends Emettitore {
  constructor() {
    super();
    this.ws = null;
    this.tentativi = 0;
    this.modo = 'avvio';
    this.ultimoEvento = 0;
    this.timerPoll = null;
    this.chiusa = false;
  }

  avvia() { this._apri(); return this; }

  stato(modo, dettaglio) {
    if (this.modo !== modo) { this.modo = modo; this.emit('collegamento', { modo, dettaglio }); }
  }

  _apri() {
    if (this.chiusa) return;
    let sock;
    try {
      const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
      sock = new WebSocket(proto + location.host + '/ws' + QS);
    } catch (e) { this._ripiega(e.message); return; }
    this.ws = sock;

    sock.onopen = () => { this.tentativi = 0; this._fermaPoll(); this.stato('ws'); };
    sock.onmessage = ev => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.t === 'ping') return;
      if (m.t === 'event' && m.d) this.ultimoEvento = Math.max(this.ultimoEvento, m.d.id || 0);
      this.emit(m.t, m.d);
    };
    sock.onerror = () => { };
    sock.onclose = ev => {
      if (this.chiusa) return;
      this.ws = null;
      this.tentativi++;
      if (ev.code === 4401) { this.stato('negato', 'token rifiutato'); return; }
      if (this.tentativi >= 2) this._ripiega('websocket non disponibile');
      const attesa = Math.min(RITENTA_MAX, 500 * Math.pow(2, this.tentativi));
      setTimeout(() => this._apri(), attesa);
    };
  }

  // ── ripiego: stesse informazioni, solo più lente
  _ripiega(motivo) {
    this.stato('poll', motivo);
    if (this.timerPoll) return;
    const giro = async () => {
      try {
        this.emit('state', await api('/api/state'));
        const r = await api('/api/events?limit=40' + (this.ultimoEvento ? '&since_id=' + this.ultimoEvento : ''));
        for (const e of (r.events || []).slice().reverse()) {
          this.ultimoEvento = Math.max(this.ultimoEvento, e.id);
          this.emit('event', e);
        }
      } catch (e) { this.emit('errore', e); }
    };
    this.timerPoll = setInterval(giro, PERIODO_POLL);
    giro();
  }

  _fermaPoll() { if (this.timerPoll) { clearInterval(this.timerPoll); this.timerPoll = null; } }

  chiudi() { this.chiusa = true; this._fermaPoll(); if (this.ws) this.ws.close(); }
}
