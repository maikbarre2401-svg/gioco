// Memoria delle conversazioni: per ogni chat tiene gli ultimi messaggi così
// l'AI capisce il contesto. Viene salvata su disco in data/memoria.json.
import fs from 'node:fs';
import path from 'node:path';
import { PERCORSI } from './config.js';

const FILE = path.join(PERCORSI.dati, 'memoria.json');
const LIMITE_SALVATI = 60;

export class Memoria {
  constructor(file = FILE) {
    this.file = file;
    this.chat = new Map();
    this.timerSalvataggio = null;
    try {
      const dati = JSON.parse(fs.readFileSync(file, 'utf8'));
      for (const [k, v] of Object.entries(dati)) this.chat.set(k, v);
    } catch {
      // nessuna memoria salvata: si parte da zero
    }
  }

  // ruolo: "user" (l'altra persona) oppure "assistant" (il bot o tu)
  aggiungi(chiave, ruolo, testo) {
    if (!testo) return;
    const lista = this.chat.get(chiave) || [];
    const ultimo = lista[lista.length - 1];
    // messaggi consecutivi dello stesso ruolo vengono uniti
    if (ultimo && ultimo.ruolo === ruolo) {
      ultimo.testo += `\n${testo}`;
      ultimo.ora = Date.now();
    } else {
      lista.push({ ruolo, testo, ora: Date.now() });
    }
    if (lista.length > LIMITE_SALVATI) lista.splice(0, lista.length - LIMITE_SALVATI);
    this.chat.set(chiave, lista);
    this.salvaPresto();
  }

  ultimi(chiave, quanti) {
    const lista = this.chat.get(chiave) || [];
    return lista.slice(-Math.max(0, quanti));
  }

  cancella(chiave) {
    this.chat.delete(chiave);
    this.salvaPresto();
  }

  salvaPresto() {
    clearTimeout(this.timerSalvataggio);
    this.timerSalvataggio = setTimeout(() => this.salvaOra(), 2000);
    this.timerSalvataggio.unref?.();
  }

  salvaOra() {
    clearTimeout(this.timerSalvataggio);
    if (!this.file) return;
    try {
      fs.writeFileSync(this.file, JSON.stringify(Object.fromEntries(this.chat)));
    } catch (err) {
      console.error('⚠️  Impossibile salvare la memoria:', err.message);
    }
  }
}
