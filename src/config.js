// Caricamento di .env e dei file di configurazione in config/.
// I file vengono riletti automaticamente quando cambiano: puoi modificarli
// (a mano o dal pannello) senza riavviare il bot.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import dotenv from 'dotenv';

const RADICE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
dotenv.config({ path: path.join(RADICE, '.env'), quiet: true });

export const PERCORSI = {
  radice: RADICE,
  config: process.env.CARTELLA_CONFIG || path.join(RADICE, 'config'),
  dati: process.env.CARTELLA_DATI || path.join(RADICE, 'data'),
};
PERCORSI.impostazioni = path.join(PERCORSI.config, 'impostazioni.json');
PERCORSI.regole = path.join(PERCORSI.config, 'regole.json');
PERCORSI.istruzioni = path.join(PERCORSI.config, 'istruzioni.md');
fs.mkdirSync(PERCORSI.dati, { recursive: true });

export const ENV = {
  groqApiKey: (process.env.GROQ_API_KEY || '').trim(),
  telegramToken: (process.env.TELEGRAM_BOT_TOKEN || '').trim(),
  telegramOwnerId: (process.env.TELEGRAM_OWNER_ID || '').trim(),
  whatsappAttivo: !/^(false|0|no)$/i.test((process.env.WHATSAPP_ATTIVO || 'true').trim()),
  whatsappNumero: (process.env.WHATSAPP_NUMERO || '').replace(/\D/g, ''),
  pannelloPorta: Number(process.env.PORT || process.env.PANNELLO_PORTA || 3000),
  pannelloPassword: (process.env.PANNELLO_PASSWORD || '').trim(),
};

export const IMPOSTAZIONI_PREDEFINITE = {
  attivo: true,
  nome_proprietario: '',
  fuso_orario: 'Europe/Rome',
  modello: 'llama-3.3-70b-versatile',
  modello_riserva: 'llama-3.1-8b-instant',
  modello_analisi: 'llama-3.1-8b-instant',
  modello_immagini: 'meta-llama/llama-4-scout-17b-16e-instruct',
  modello_audio: 'whisper-large-v3-turbo',
  lingua_audio: 'it',
  temperatura: 0.7,
  lunghezza_massima_risposta: 400,
  analisi_prima_di_rispondere: true,
  capisci_vocali: true,
  capisci_immagini: true,
  memoria_messaggi: 20,
  attesa_raggruppa_messaggi_sec: 4,
  ritardo_umano: true,
  segna_come_letto: true,
  ignora_messaggi_piu_vecchi_di_min: 15,
  pausa_se_rispondo_io_min: 30,
  rispondi_nei_gruppi: 'se_menzionato',
  contatti: { modalita: 'tutti', lista: [] },
  orario: { attivo: false, dalle: '20:00', alle: '08:00' },
  avvisami_se_serve_umano: true,
  whatsapp: true,
  telegram: true,
};

const cache = new Map();

function leggiConCache(file, interpreta, predefinito) {
  let mtime;
  try {
    mtime = fs.statSync(file).mtimeMs;
  } catch {
    return predefinito;
  }
  const c = cache.get(file);
  if (c && c.mtime === mtime) return c.valore;
  try {
    const valore = interpreta(fs.readFileSync(file, 'utf8'));
    cache.set(file, { mtime, valore });
    return valore;
  } catch (err) {
    console.error(`⚠️  Errore nel file ${path.basename(file)}: ${err.message}`);
    // se il file è rotto continuo a usare l'ultima versione valida
    return c ? c.valore : predefinito;
  }
}

function scriviFile(file, contenuto) {
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, contenuto);
  fs.renameSync(tmp, file);
  cache.delete(file);
}

export function impostazioni() {
  const lette = leggiConCache(PERCORSI.impostazioni, JSON.parse, {});
  return {
    ...IMPOSTAZIONI_PREDEFINITE,
    ...lette,
    contatti: { ...IMPOSTAZIONI_PREDEFINITE.contatti, ...(lette.contatti || {}) },
    orario: { ...IMPOSTAZIONI_PREDEFINITE.orario, ...(lette.orario || {}) },
  };
}

export function salvaImpostazioni(nuove) {
  scriviFile(PERCORSI.impostazioni, JSON.stringify(nuove, null, 2) + '\n');
}

export function regole() {
  const lette = leggiConCache(PERCORSI.regole, JSON.parse, []);
  return Array.isArray(lette) ? lette : [];
}

export function salvaRegole(nuove) {
  if (!Array.isArray(nuove)) throw new Error('Le regole devono essere una lista [ ... ]');
  scriviFile(PERCORSI.regole, JSON.stringify(nuove, null, 2) + '\n');
}

export function istruzioni() {
  return leggiConCache(PERCORSI.istruzioni, (t) => t.trim(), '');
}

export function salvaIstruzioni(testo) {
  scriviFile(PERCORSI.istruzioni, String(testo).trim() + '\n');
}
