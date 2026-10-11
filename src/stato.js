// Stato del bot che deve sopravvivere ai riavvii (chat in pausa) e registro
// degli ultimi eventi mostrati nel pannello.
import fs from 'node:fs';
import path from 'node:path';
import { EventEmitter } from 'node:events';
import { PERCORSI } from './config.js';

const FILE_STATO = path.join(PERCORSI.dati, 'stato.json');
const MAX_EVENTI = 300;

function caricaJson(file, predefinito) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return predefinito;
  }
}

class Stato extends EventEmitter {
  constructor() {
    super();
    const salvato = caricaJson(FILE_STATO, {});
    // chiave chat -> timestamp di fine pausa (Infinity = finché non riprendi tu)
    this.pause = new Map(
      Object.entries(salvato.pause || {}).map(([k, v]) => [k, v === null ? Infinity : v]),
    );
    this.nomiChat = new Map(Object.entries(salvato.nomiChat || {}));
    this.eventi = [];
    this.piattaforme = {
      groq: { stato: 'avvio' },
      whatsapp: { stato: 'spento' },
      telegram: { stato: 'spento' },
    };
    this.statistiche = { ricevuti: 0, risposti: 0, ignorati: 0, errori: 0 };
  }

  salva() {
    const pause = {};
    for (const [k, v] of this.pause) pause[k] = v === Infinity ? null : v;
    const dati = { pause, nomiChat: Object.fromEntries(this.nomiChat) };
    fs.writeFileSync(FILE_STATO, JSON.stringify(dati, null, 2));
  }

  ricordaNome(chiave, nome) {
    if (nome && this.nomiChat.get(chiave) !== nome) {
      this.nomiChat.set(chiave, nome);
      this.salva();
    }
  }

  // minuti = null -> pausa senza scadenza
  pausaChat(chiave, minuti = null) {
    this.pause.set(chiave, minuti == null ? Infinity : Date.now() + minuti * 60_000);
    this.salva();
    this.emit('cambiato');
  }

  riprendiChat(chiave) {
    this.pause.delete(chiave);
    this.salva();
    this.emit('cambiato');
  }

  chatInPausa(chiave) {
    const fine = this.pause.get(chiave);
    if (fine === undefined) return false;
    if (fine > Date.now()) return true;
    this.pause.delete(chiave);
    this.salva();
    return false;
  }

  elencoPause() {
    const ora = Date.now();
    return [...this.pause]
      .filter(([, fine]) => fine > ora)
      .map(([chiave, fine]) => ({
        chiave,
        nome: this.nomiChat.get(chiave) || chiave,
        fino: fine === Infinity ? null : new Date(fine).toISOString(),
      }));
  }

  impostaPiattaforma(nome, info) {
    this.piattaforme[nome] = { ...this.piattaforme[nome], ...info };
    this.emit('cambiato');
  }

  registra(evento) {
    const e = { ora: new Date().toISOString(), ...evento };
    this.eventi.unshift(e);
    if (this.eventi.length > MAX_EVENTI) this.eventi.length = MAX_EVENTI;
    if (e.esito === 'risposto' || e.esito === 'risposta fissa') this.statistiche.risposti++;
    else if (e.esito === 'errore') this.statistiche.errori++;
    else if (e.esito === 'ignorato') this.statistiche.ignorati++;
    this.emit('evento', e);
    return e;
  }
}

export const stato = new Stato();
