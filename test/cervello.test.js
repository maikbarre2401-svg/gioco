// Prova il cervello del bot con un'AI finta (nessuna chiamata a Groq).
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// i log del bot confondono il test runner di Node quando gira in parallelo
console.log = () => {};
console.warn = () => {};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'assistente-test-'));
process.env.CARTELLA_CONFIG = path.join(tmp, 'config');
process.env.CARTELLA_DATI = path.join(tmp, 'dati');
fs.mkdirSync(process.env.CARTELLA_CONFIG, { recursive: true });

const { salvaImpostazioni, salvaRegole, salvaIstruzioni, IMPOSTAZIONI_PREDEFINITE } = await import('../src/config.js');
const { Cervello, dentroOrario } = await import('../src/cervello.js');
const { Memoria } = await import('../src/memoria.js');
const { stato } = await import('../src/stato.js');

const REGOLE = [
  { nome: 'Prezzi', quando_contiene: ['quanto costa'], rispondi_con: 'Costa 10 euro.' },
  { nome: 'Spam', quando_regex: 'bitcoin', non_rispondere: true },
  {
    nome: 'Appuntamenti',
    quando_significa: 'vuole fissare un appuntamento',
    istruzioni_per_ai: 'Chiedi giorno e ora.',
    avvisami: true,
  },
];

function impostazioniTest(extra = {}) {
  salvaImpostazioni({
    ...IMPOSTAZIONI_PREDEFINITE,
    attesa_raggruppa_messaggi_sec: 0,
    ritardo_umano: false,
    segna_come_letto: false,
    ...extra,
  });
}

class AIFinta {
  constructor() {
    this.analisi = { intento: 'saluto', serve_risposta: true, serve_umano: false, regola: null };
    this.chiamate = { analizza: [], rispondi: [], trascrivi: 0, immagini: 0 };
  }
  async analizza(sistema, utente) {
    this.chiamate.analizza.push({ sistema, utente });
    return this.analisi;
  }
  async rispondi(sistema, messaggi) {
    this.chiamate.rispondi.push({ sistema, messaggi });
    return { testo: '**Ciao!** Come posso aiutarti?', modello: 'finto' };
  }
  async trascrivi() {
    this.chiamate.trascrivi++;
    return 'ci vediamo domani alle cinque';
  }
  async descriviImmagine() {
    this.chiamate.immagini++;
    return 'un gatto su un divano';
  }
}

let ai;
let cervello;
let inviati;
let avvisi;

function messaggio(testo, extra = {}) {
  return {
    piattaforma: 'whatsapp',
    chiave: 'whatsapp:393331234567@s.whatsapp.net',
    chatId: '393331234567@s.whatsapp.net',
    idContatto: '393331234567',
    nomeContatto: 'Mario',
    isGruppo: false,
    testo,
    ora: Date.now(),
    invia: async (t) => inviati.push(t),
    ...extra,
  };
}

// aspetta che il cervello abbia finito di elaborare tutte le chat
async function finito() {
  for (let i = 0; i < 50; i++) {
    await new Promise((r) => setTimeout(r, 5));
    if (cervello.buffer.size === 0 && cervello.code.size === 0) return;
  }
  throw new Error('elaborazione non terminata');
}

beforeEach(() => {
  impostazioniTest();
  salvaRegole(REGOLE);
  salvaIstruzioni('Sei il mio assistente.');
  for (const k of [...stato.pause.keys()]) stato.riprendiChat(k);
  ai = new AIFinta();
  inviati = [];
  avvisi = [];
  cervello = new Cervello({ ai, memoria: new Memoria(null), stato });
  cervello.aggiungiNotificatore(async (t) => {
    avvisi.push(t);
    return true;
  });
});

test('risponde con l\'AI, dopo aver analizzato, e pulisce il markdown', async () => {
  cervello.ricevi(messaggio('ciao!'));
  await finito();
  assert.equal(ai.chiamate.analizza.length, 1);
  assert.equal(ai.chiamate.rispondi.length, 1);
  assert.deepEqual(inviati, ['Ciao! Come posso aiutarti?']);
  const { sistema, messaggi } = ai.chiamate.rispondi[0];
  assert.match(sistema, /Sei il mio assistente\./);
  assert.match(sistema, /WhatsApp con Mario/);
  assert.deepEqual(messaggi, [{ role: 'user', content: 'ciao!' }]);
});

test('regola con risposta fissa: nessuna chiamata all\'AI', async () => {
  cervello.ricevi(messaggio('Buongiorno, quanto costa?'));
  await finito();
  assert.deepEqual(inviati, ['Costa 10 euro.']);
  assert.equal(ai.chiamate.analizza.length + ai.chiamate.rispondi.length, 0);
});

test('regola "non rispondere"', async () => {
  cervello.ricevi(messaggio('compra bitcoin ora'));
  await finito();
  assert.deepEqual(inviati, []);
  assert.equal(stato.eventi[0].esito, 'ignorato');
});

test('regola capita dal significato: istruzioni all\'AI + avviso al proprietario', async () => {
  ai.analisi = { intento: 'vedersi', regola: 'appuntamenti', serve_risposta: true, urgenza: 'media' };
  cervello.ricevi(messaggio('possiamo vederci la settimana prossima?'));
  await finito();
  assert.match(ai.chiamate.analizza[0].sistema, /"Appuntamenti": vuole fissare un appuntamento/);
  assert.match(ai.chiamate.rispondi[0].sistema, /Chiedi giorno e ora\./);
  assert.equal(inviati.length, 1);
  assert.equal(avvisi.length, 1);
  assert.match(avvisi[0], /Mario su WhatsApp/);
  assert.deepEqual(stato.eventi[0].regole, ['Appuntamenti']);
});

test('avvisa quando l\'analisi dice che servi tu', async () => {
  ai.analisi = { intento: 'emergenza', serve_umano: true, serve_risposta: true, urgenza: 'alta' };
  cervello.ricevi(messaggio('è urgentissimo chiamami'));
  await finito();
  assert.equal(avvisi.length, 1);
  assert.match(avvisi[0], /Urgenza: alta/);
});

test('non risponde a un semplice "ok" se l\'analisi dice che non serve', async () => {
  ai.analisi = { intento: 'conferma', serve_risposta: false };
  cervello.ricevi(messaggio('ok 👍'));
  await finito();
  assert.deepEqual(inviati, []);
});

test('più messaggi di fila ricevono una sola risposta', async () => {
  impostazioniTest({ attesa_raggruppa_messaggi_sec: 0.05 });
  cervello.ricevi(messaggio('ciao'));
  cervello.ricevi(messaggio('volevo chiederti una cosa'));
  await new Promise((r) => setTimeout(r, 80));
  await finito();
  assert.equal(inviati.length, 1);
  assert.deepEqual(ai.chiamate.rispondi[0].messaggi, [
    { role: 'user', content: 'ciao\nvolevo chiederti una cosa' },
  ]);
});

test('se rispondi tu, il bot si ferma in quella chat', async () => {
  const m = messaggio('ci sei?');
  cervello.messaggioMio(m.chiave, 'sì dimmi');
  cervello.ricevi(m);
  await finito();
  assert.deepEqual(inviati, []);
  assert.ok(stato.chatInPausa(m.chiave));
  stato.riprendiChat(m.chiave);
  cervello.ricevi(messaggio('allora?'));
  await finito();
  assert.equal(inviati.length, 1);
  // il bot vede anche quello che hai scritto tu
  const roles = ai.chiamate.rispondi[0].messaggi.map((x) => x.role);
  assert.deepEqual(roles, ['assistant', 'user']);
});

test('gruppi: risponde solo se menzionato', async () => {
  const gruppo = { isGruppo: true, chiave: 'whatsapp:123@g.us', chatId: '123@g.us', nomeChat: 'Amici' };
  cervello.ricevi(messaggio('ciao a tutti', gruppo));
  await finito();
  assert.deepEqual(inviati, []);
  cervello.ricevi(messaggio('@bot tu che dici?', { ...gruppo, menzionato: true }));
  await finito();
  assert.equal(inviati.length, 1);
  assert.match(ai.chiamate.rispondi[0].sistema, /in un gruppo su WhatsApp \("Amici"\)/);
  // nei gruppi il nome di chi scrive è nel testo
  assert.match(ai.chiamate.rispondi[0].messaggi.at(-1).content, /Mario: @bot tu che dici\?/);
});

test('bot spento, contatti esclusi e messaggi vecchi vengono ignorati', async () => {
  impostazioniTest({ attivo: false });
  cervello.ricevi(messaggio('ciao'));
  impostazioniTest({ contatti: { modalita: 'tutti_tranne_lista', lista: ['393331234567'] } });
  cervello.ricevi(messaggio('ciao'));
  impostazioniTest({ contatti: { modalita: 'solo_lista', lista: ['393330000000'] } });
  cervello.ricevi(messaggio('ciao'));
  impostazioniTest();
  cervello.ricevi(messaggio('ciao', { ora: Date.now() - 60 * 60_000 }));
  await finito();
  assert.deepEqual(inviati, []);
  assert.equal(ai.chiamate.rispondi.length, 0);
});

test('vocali trascritti e foto descritte', async () => {
  const scaricaMedia = async () => ({ buffer: Buffer.from('x'), mime: 'audio/ogg' });
  cervello.ricevi(messaggio('', { tipoMedia: 'audio', scaricaMedia }));
  await finito();
  assert.equal(ai.chiamate.trascrivi, 1);
  assert.match(ai.chiamate.rispondi[0].messaggi.at(-1).content, /\[messaggio vocale\] ci vediamo domani/);

  cervello.ricevi(messaggio('guarda', { tipoMedia: 'immagine', scaricaMedia }));
  await finito();
  assert.equal(ai.chiamate.immagini, 1);
  assert.match(ai.chiamate.rispondi[1].messaggi.at(-1).content, /\[foto: un gatto su un divano\] guarda/);
});

test('se l\'analisi fallisce risponde lo stesso', async () => {
  ai.analizza = async () => {
    throw new Error('rete giù');
  };
  cervello.ricevi(messaggio('ciao'));
  await finito();
  assert.equal(inviati.length, 1);
});

test('prova dal pannello', async () => {
  const r = await cervello.prova('ciao');
  assert.equal(r.risposta, 'Ciao! Come posso aiutarti?');
  assert.equal(r.esito, 'risposto');
});

test('fascia oraria, anche a cavallo della mezzanotte', () => {
  const sera = { attivo: true, dalle: '20:00', alle: '08:00' };
  assert.equal(dentroOrario(sera, null, 21 * 60), true);
  assert.equal(dentroOrario(sera, null, 7 * 60), true);
  assert.equal(dentroOrario(sera, null, 12 * 60), false);
  const giorno = { attivo: true, dalle: '09:00', alle: '18:00' };
  assert.equal(dentroOrario(giorno, null, 10 * 60), true);
  assert.equal(dentroOrario(giorno, null, 19 * 60), false);
  assert.equal(dentroOrario({ attivo: false }, null, 0), true);
});
