// Simula messaggi di WhatsApp e Telegram (senza connettersi davvero) e
// controlla che arrivino al cervello nel modo giusto.
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

const { salvaImpostazioni, impostazioni, IMPOSTAZIONI_PREDEFINITE } = await import('../src/config.js');
const { WhatsApp } = await import('../src/whatsapp.js');
const { creaBotTelegram } = await import('../src/telegram.js');

let ricevuti;
let mie;
const cervello = {
  ricevi: (m) => ricevuti.push(m),
  messaggioMio: (chiave, testo) => mie.push({ chiave, testo }),
  aggiungiNotificatore: () => {},
};
const stato = {
  statistiche: { ricevuti: 0, risposti: 0, ignorati: 0, errori: 0 },
  piattaforme: { whatsapp: { stato: 'connesso' }, telegram: { stato: 'connesso' } },
  elencoPause: () => [],
  impostaPiattaforma: () => {},
};
const memoria = { cancellate: [], cancella(k) { this.cancellate.push(k); } };

beforeEach(() => {
  ricevuti = [];
  mie = [];
  salvaImpostazioni({ ...IMPOSTAZIONI_PREDEFINITE });
});

// ------------------------------ WhatsApp ------------------------------

const MIO = '393330000000';
function creaWhatsApp() {
  const wa = new WhatsApp({ cervello, stato });
  const inviati = [];
  wa.sock = {
    user: { id: `${MIO}:5@s.whatsapp.net`, lid: '777:5@lid' },
    sendMessage: async (jid, contenuto, opzioni) => {
      inviati.push({ jid, testo: contenuto.text, opzioni });
      return { key: { id: opzioni.messageId, remoteJid: jid, fromMe: true }, message: { conversation: contenuto.text } };
    },
    groupMetadata: async () => ({ subject: 'Amici' }),
    sendPresenceUpdate: async () => {},
    readMessages: async () => {},
  };
  wa.impostaUtente(wa.sock.user);
  return { wa, inviati };
}
const adesso = () => Math.floor(Date.now() / 1000);

test('WhatsApp: messaggio privato in arrivo', async () => {
  const { wa, inviati } = creaWhatsApp();
  await wa.gestisci({
    key: { remoteJid: '393331234567@s.whatsapp.net', fromMe: false, id: 'A1' },
    message: { conversation: 'ciao' },
    messageTimestamp: adesso(),
    pushName: 'Mario',
  });
  assert.equal(ricevuti.length, 1);
  const m = ricevuti[0];
  assert.equal(m.chiave, 'whatsapp:393331234567@s.whatsapp.net');
  assert.equal(m.idContatto, '393331234567');
  assert.equal(m.nomeContatto, 'Mario');
  assert.equal(m.testo, 'ciao');
  assert.equal(m.isGruppo, false);

  // la risposta del bot parte e la sua "eco" non viene scambiata per un tuo messaggio
  await m.invia('Ciao Mario!');
  assert.deepEqual(inviati.map((x) => [x.jid, x.testo]), [['393331234567@s.whatsapp.net', 'Ciao Mario!']]);
  await wa.gestisci({
    key: { remoteJid: '393331234567@s.whatsapp.net', fromMe: true, id: inviati[0].opzioni.messageId },
    message: { conversation: 'Ciao Mario!' },
    messageTimestamp: adesso(),
  });
  assert.equal(mie.length, 0);
});

test('WhatsApp: se scrivi tu dal telefono il bot lo sa', async () => {
  const { wa } = creaWhatsApp();
  await wa.gestisci({
    key: { remoteJid: '393331234567@s.whatsapp.net', fromMe: true, id: 'DAL-TELEFONO' },
    message: { conversation: 'arrivo tra 5 minuti' },
    messageTimestamp: adesso(),
  });
  assert.deepEqual(mie, [{ chiave: 'whatsapp:393331234567@s.whatsapp.net', testo: 'arrivo tra 5 minuti' }]);
  assert.equal(ricevuti.length, 0);
});

test('WhatsApp: gruppo con menzione, contatto @lid e foto con didascalia', async () => {
  const { wa } = creaWhatsApp();
  await wa.gestisci({
    key: { remoteJid: '120363@g.us', fromMe: false, id: 'G1', participant: '393339999999@s.whatsapp.net' },
    message: {
      extendedTextMessage: {
        text: `@${MIO} che ne pensi?`,
        contextInfo: { mentionedJid: [`${MIO}@s.whatsapp.net`] },
      },
    },
    messageTimestamp: adesso(),
    pushName: 'Luca',
  });
  await wa.gestisci({
    key: { remoteJid: '120363@g.us', fromMe: false, id: 'G2', participant: '393339999999@s.whatsapp.net' },
    message: { conversation: 'chiacchiere' },
    messageTimestamp: adesso(),
    pushName: 'Luca',
  });
  await wa.gestisci({
    key: { remoteJid: '55555@lid', fromMe: false, id: 'L1', senderPn: '393331112222@s.whatsapp.net' },
    message: { ephemeralMessage: { message: { imageMessage: { caption: 'guarda', mimetype: 'image/jpeg' } } } },
    messageTimestamp: adesso(),
    pushName: 'Sara',
  });
  const [menzione, normale, foto] = ricevuti;
  assert.equal(menzione.isGruppo, true);
  assert.equal(menzione.menzionato, true);
  assert.equal(menzione.nomeChat, 'Amici');
  assert.equal(menzione.idContatto, '393339999999');
  assert.equal(normale.menzionato, false);
  assert.equal(foto.idContatto, '393331112222');
  assert.equal(foto.tipoMedia, 'immagine');
  assert.equal(foto.testo, 'guarda');
});

test('WhatsApp: stati, reazioni e messaggi a te stesso non arrivano al bot', async () => {
  const { wa } = creaWhatsApp();
  await wa.gestisci({ key: { remoteJid: 'status@broadcast', id: 'S1' }, message: { conversation: 'stato' } });
  await wa.gestisci({
    key: { remoteJid: '393331234567@s.whatsapp.net', id: 'R1' },
    message: { reactionMessage: { text: '👍' } },
  });
  await wa.gestisci({
    key: { remoteJid: `${MIO}@s.whatsapp.net`, fromMe: true, id: 'N1' },
    message: { conversation: 'nota per me' },
    messageTimestamp: adesso(),
  });
  assert.equal(ricevuti.length + mie.length, 0);
});

test('WhatsApp: comandi nella chat "Tu"', async () => {
  const { wa, inviati } = creaWhatsApp();
  await wa.gestisci({
    key: { remoteJid: `${MIO}@s.whatsapp.net`, fromMe: true, id: 'C1' },
    message: { conversation: '!pausa' },
    messageTimestamp: adesso(),
  });
  assert.equal(impostazioni().attivo, false);
  assert.match(inviati[0].testo, /in pausa/);
  await wa.gestisci({
    key: { remoteJid: '777@lid', fromMe: true, id: 'C2' },
    message: { conversation: '!riprendi' },
    messageTimestamp: adesso(),
  });
  assert.equal(impostazioni().attivo, true);
});

// ------------------------------ Telegram ------------------------------

const BOT_INFO = {
  id: 999,
  is_bot: true,
  first_name: 'Assistente',
  username: 'mio_assistente_bot',
  can_join_groups: true,
  can_read_all_group_messages: false,
  supports_inline_queries: false,
  can_connect_to_business: true,
  has_main_web_app: false,
};

function creaTelegram() {
  const chiamate = [];
  const bot = creaBotTelegram({ cervello, stato, memoria, token: '1:finto', proprietario: '42', botInfo: BOT_INFO });
  bot.api.config.use(async (prec, metodo, dati) => {
    chiamate.push({ metodo, dati });
    if (metodo === 'getBusinessConnection') {
      return {
        ok: true,
        result: { id: dati.business_connection_id, user: { id: 42, is_bot: false, first_name: 'Io' }, user_chat_id: 42, date: 0, is_enabled: true },
      };
    }
    return { ok: true, result: true };
  });
  return { bot, chiamate };
}

let idUpdate = 1;
const utente = (id, nome, username) => ({ id, is_bot: false, first_name: nome, username });
function messaggioTg(testo, { chat, from, extra = {} } = {}) {
  const m = {
    message_id: idUpdate,
    date: adesso(),
    chat: chat || { id: 7, type: 'private', first_name: 'Anna' },
    from: from || utente(7, 'Anna', 'anna'),
    text: testo,
    ...extra,
  };
  if (testo.startsWith('/')) m.entities = [{ type: 'bot_command', offset: 0, length: testo.split(' ')[0].length }];
  return m;
}

test('Telegram: messaggio al bot e risposta', async () => {
  const { bot, chiamate } = creaTelegram();
  await bot.handleUpdate({ update_id: idUpdate++, message: messaggioTg('ciao') });
  assert.equal(ricevuti.length, 1);
  const m = ricevuti[0];
  assert.equal(m.chiave, 'telegram:7');
  assert.equal(m.nomeContatto, 'Anna');
  assert.equal(m.username, 'anna');
  await m.invia('Ciao Anna!');
  const invio = chiamate.find((c) => c.metodo === 'sendMessage');
  assert.equal(invio.dati.chat_id, 7);
  assert.equal(invio.dati.text, 'Ciao Anna!');
});

test('Telegram: comandi /id e /reset non vanno all\'AI', async () => {
  const { bot, chiamate } = creaTelegram();
  await bot.handleUpdate({ update_id: idUpdate++, message: messaggioTg('/id') });
  await bot.handleUpdate({ update_id: idUpdate++, message: messaggioTg('/reset') });
  assert.equal(ricevuti.length, 0);
  assert.match(chiamate[0].dati.text, /id Telegram è: 7/);
  assert.deepEqual(memoria.cancellate.slice(-1), ['telegram:7']);
});

test('Telegram: /pausa solo per il proprietario', async () => {
  const { bot, chiamate } = creaTelegram();
  await bot.handleUpdate({ update_id: idUpdate++, message: messaggioTg('/pausa') });
  assert.match(chiamate[0].dati.text, /riservato al proprietario/);
  assert.equal(impostazioni().attivo, true);
  await bot.handleUpdate({
    update_id: idUpdate++,
    message: messaggioTg('/pausa', { chat: { id: 42, type: 'private', first_name: 'Io' }, from: utente(42, 'Io') }),
  });
  assert.equal(impostazioni().attivo, false);
});

test('Telegram Business: risponde al posto tuo e si ferma se scrivi tu', async () => {
  const { bot, chiamate } = creaTelegram();
  const chat = { id: 8, type: 'private', first_name: 'Luca' };
  const business = (testo, from, extra = {}) => ({
    update_id: idUpdate++,
    business_message: { ...messaggioTg(testo, { chat, from, extra }), business_connection_id: 'bc1' },
  });

  await bot.handleUpdate(business('ehi ci sei?', utente(8, 'Luca')));
  assert.equal(ricevuti.length, 1);
  assert.equal(ricevuti[0].chiave, 'telegram:business:8');
  await ricevuti[0].invia('Ora non può rispondere, ti scrive appena può');
  const invio = chiamate.find((c) => c.metodo === 'sendMessage');
  assert.equal(invio.dati.business_connection_id, 'bc1');

  // messaggio scritto da te (titolare dell'account)
  await bot.handleUpdate(business('eccomi!', utente(42, 'Io')));
  assert.deepEqual(mie, [{ chiave: 'telegram:business:8', testo: 'eccomi!' }]);

  // messaggio inviato dal bot per conto tuo: ignorato
  await bot.handleUpdate(business('risposta del bot', utente(42, 'Io'), { sender_business_bot: BOT_INFO }));
  assert.equal(mie.length, 1);
  assert.equal(ricevuti.length, 1);
});

test('Telegram: nei gruppi capisce se è menzionato', async () => {
  const { bot } = creaTelegram();
  const chat = { id: -100, type: 'supergroup', title: 'Calcetto' };
  await bot.handleUpdate({ update_id: idUpdate++, message: messaggioTg('chi viene stasera?', { chat }) });
  await bot.handleUpdate({ update_id: idUpdate++, message: messaggioTg('@Mio_Assistente_Bot tu vieni?', { chat }) });
  assert.equal(ricevuti[0].menzionato, false);
  assert.equal(ricevuti[1].menzionato, true);
  assert.equal(ricevuti[1].nomeChat, 'Calcetto');
  assert.equal(ricevuti[1].isGruppo, true);
});
