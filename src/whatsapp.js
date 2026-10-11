// Collegamento a WhatsApp tramite Baileys (come "dispositivo collegato",
// esattamente come WhatsApp Web). La prima volta scansioni un QR code.
import fs from 'node:fs';
import path from 'node:path';
import pino from 'pino';
import qrcodeTerminale from 'qrcode-terminal';
import QRCode from 'qrcode';
import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  Browsers,
  downloadMediaMessage,
  getContentType,
  normalizeMessageContent,
  jidNormalizedUser,
  areJidsSameUser,
  isJidGroup,
  isJidBroadcast,
  isJidStatusBroadcast,
  isJidNewsletter,
  generateMessageIDV2,
} from '@whiskeysockets/baileys';
import { ENV, PERCORSI, impostazioni, salvaImpostazioni } from './config.js';

const TIPI_MEDIA = {
  imageMessage: 'immagine',
  audioMessage: 'audio',
  videoMessage: 'video',
  ptvMessage: 'video',
  stickerMessage: 'sticker',
  documentMessage: 'documento',
  locationMessage: 'posizione',
  liveLocationMessage: 'posizione',
  contactMessage: 'contatto',
  contactsArrayMessage: 'contatto',
};

function comeNumero(ts) {
  if (ts == null) return Date.now() / 1000;
  return typeof ts === 'object' && typeof ts.toNumber === 'function' ? ts.toNumber() : Number(ts);
}

function testoDi(contenuto) {
  return (
    contenuto?.conversation ||
    contenuto?.extendedTextMessage?.text ||
    contenuto?.imageMessage?.caption ||
    contenuto?.videoMessage?.caption ||
    contenuto?.documentMessage?.caption ||
    ''
  ).trim();
}

// Numero di telefono da un jid ("393331234567@s.whatsapp.net" -> "393331234567")
function numeroDa(jid, alternativo) {
  const scelto = alternativo && alternativo.endsWith('@s.whatsapp.net') ? alternativo : jid;
  return String(scelto || '').split('@')[0].split(':')[0];
}

export class WhatsApp {
  constructor({ cervello, stato }) {
    this.cervello = cervello;
    this.stato = stato;
    this.logger = pino({ level: process.env.LOG_WHATSAPP || 'silent' });
    this.cartellaSessione = path.join(PERCORSI.dati, 'whatsapp-sessione');
    this.inviatiDalBot = new Set();
    this.cacheMessaggi = new Map();
    this.nomiGruppi = new Map();
    this.sock = null;
    this.mioJid = null;
    this.mioLid = null;
    this.tentativi = 0;
  }

  // Chiamato quando la connessione è aperta (o dai test)
  impostaUtente(user) {
    this.mioJid = jidNormalizedUser(user.id);
    this.mioLid = user.lid ? jidNormalizedUser(user.lid) : null;
  }

  ricordaInviato(id, messaggio) {
    this.inviatiDalBot.add(id);
    if (messaggio) this.cacheMessaggi.set(id, messaggio);
    if (this.inviatiDalBot.size > 2000) this.inviatiDalBot.delete(this.inviatiDalBot.values().next().value);
    if (this.cacheMessaggi.size > 500) this.cacheMessaggi.delete(this.cacheMessaggi.keys().next().value);
  }

  async invia(jid, testo, opzioni = {}) {
    const messageId = generateMessageIDV2(this.sock.user?.id);
    this.inviatiDalBot.add(messageId); // prima di inviare: l'eco del messaggio arriva subito
    const inviato = await this.sock.sendMessage(jid, { text: testo }, { ...opzioni, messageId });
    this.ricordaInviato(inviato?.key?.id || messageId, inviato?.message);
    return inviato;
  }

  eMio(jid) {
    if (!jid || !this.mioJid) return false;
    return areJidsSameUser(jid, this.mioJid) || Boolean(this.mioLid && areJidsSameUser(jid, this.mioLid));
  }

  async nomeGruppo(jid) {
    if (this.nomiGruppi.has(jid)) return this.nomiGruppi.get(jid);
    try {
      const meta = await this.sock.groupMetadata(jid);
      this.nomiGruppi.set(jid, meta.subject);
      return meta.subject;
    } catch {
      return null;
    }
  }

  // Comandi che puoi scrivere nella chat "Tu" (messaggi a te stesso)
  async comandoProprietario(jid, testo) {
    const comando = testo.trim().toLowerCase();
    const imp = impostazioni();
    let risposta;
    if (comando === '!pausa') {
      salvaImpostazioni({ ...imp, attivo: false });
      risposta = '⏸ Bot in pausa: non risponde a nessuno finché non scrivi !riprendi';
    } else if (comando === '!riprendi') {
      salvaImpostazioni({ ...imp, attivo: true });
      risposta = '▶️ Bot attivo: risponde di nuovo automaticamente';
    } else if (comando === '!stato') {
      const s = this.stato.statistiche;
      risposta =
        `🤖 Bot ${imp.attivo ? 'ATTIVO' : 'IN PAUSA'}\n` +
        `Ricevuti: ${s.ricevuti} · Risposti: ${s.risposti} · Ignorati: ${s.ignorati} · Errori: ${s.errori}\n` +
        `Chat in pausa: ${this.stato.elencoPause().length}`;
    } else if (comando === '!aiuto') {
      risposta = 'Comandi: !pausa · !riprendi · !stato';
    } else {
      return;
    }
    await this.invia(jid, risposta);
  }

  async gestisci(m) {
    const jid = m.key?.remoteJid;
    if (!m.message || !jid) return;
    if (isJidStatusBroadcast(jid) || isJidBroadcast(jid) || isJidNewsletter(jid)) return;

    const contenuto = normalizeMessageContent(m.message);
    const tipo = getContentType(contenuto);
    const testo = testoDi(contenuto);
    const tipoMedia = TIPI_MEDIA[tipo];
    if (!testo && !tipoMedia) return; // reazioni, eliminazioni, sondaggi...

    const ora = comeNumero(m.messageTimestamp) * 1000;
    const isGruppo = Boolean(isJidGroup(jid));
    const chiave = `whatsapp:${jid}`;

    // Messaggi inviati da te (dal telefono) o dal bot
    if (m.key.fromMe) {
      if (this.inviatiDalBot.has(m.key.id)) return;
      if (this.eMio(jid)) {
        if (testo.startsWith('!')) await this.comandoProprietario(jid, testo);
        return;
      }
      // hai risposto tu di persona: il bot si fa da parte in questa chat
      if (Date.now() - ora < 5 * 60_000) {
        this.cervello.messaggioMio(chiave, testo || `[${tipoMedia}]`);
      }
      return;
    }
    if (this.eMio(jid)) return;

    const mittente = isGruppo ? m.key.participant : jid;
    const numero = numeroDa(mittente, isGruppo ? m.key.participantPn : m.key.senderPn);
    const info = contenuto[tipo]?.contextInfo;
    const menzionato =
      isGruppo &&
      Boolean(
        info?.mentionedJid?.some((j) => this.eMio(j)) ||
          (info?.participant && this.eMio(info.participant)) ||
          (this.mioJid && testo.includes(`@${numeroDa(this.mioJid)}`)),
      );

    this.cervello.ricevi({
      piattaforma: 'whatsapp',
      chiave,
      chatId: jid,
      idContatto: numero,
      nomeContatto: m.pushName || numero,
      nomeChat: isGruppo ? await this.nomeGruppo(jid) : null,
      isGruppo,
      menzionato,
      testo,
      tipoMedia,
      ora,
      scaricaMedia: async () => ({
        buffer: await downloadMediaMessage(
          m,
          'buffer',
          {},
          { logger: this.logger, reuploadRequest: this.sock.updateMediaMessage },
        ),
        mime: contenuto[tipo]?.mimetype,
      }),
      invia: (risposta) => this.invia(jid, risposta, isGruppo ? { quoted: m } : {}),
      staScrivendo: () => this.sock.sendPresenceUpdate('composing', jid),
      segnaLetto: () => this.sock.readMessages([m.key]),
    });
  }

  async connetti() {
    const { state, saveCreds } = await useMultiFileAuthState(this.cartellaSessione);
    let version;
    try {
      ({ version } = await fetchLatestBaileysVersion());
    } catch {
      // si usa la versione predefinita della libreria
    }
    const sock = makeWASocket({
      auth: state,
      ...(version ? { version } : {}),
      logger: this.logger,
      browser: Browsers.ubuntu('Chrome'),
      markOnlineOnConnect: false, // così il telefono continua a ricevere le notifiche
      syncFullHistory: false,
      getMessage: async (key) => this.cacheMessaggi.get(key.id),
    });
    this.sock = sock;
    let codiceRichiesto = false;

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
      if (this.sock !== sock) return;
      if (qr) {
        if (ENV.whatsappNumero) {
          if (codiceRichiesto) return;
          codiceRichiesto = true;
          try {
            const codice = await sock.requestPairingCode(ENV.whatsappNumero);
            const leggibile = codice.match(/.{1,4}/g).join('-');
            console.log(
              `\n📱 WhatsApp > Dispositivi collegati > Collega un dispositivo > "Collega con numero di telefono"\n   Inserisci questo codice: ${leggibile}\n`,
            );
            this.stato.impostaPiattaforma('whatsapp', { stato: 'codice', codice: leggibile, qr: null });
          } catch (err) {
            console.error('❌ Impossibile ottenere il codice di collegamento:', err.message);
          }
        } else {
          console.log('\n📱 Scansiona questo QR con WhatsApp > Dispositivi collegati > Collega un dispositivo');
          console.log('   (oppure aprilo dal pannello web)\n');
          qrcodeTerminale.generate(qr, { small: true });
          this.stato.impostaPiattaforma('whatsapp', { stato: 'qr', qr: await QRCode.toDataURL(qr) });
        }
      }
      if (connection === 'open') {
        this.tentativi = 0;
        this.impostaUtente(sock.user);
        console.log(`✅ WhatsApp collegato (${numeroDa(this.mioJid)})`);
        this.stato.impostaPiattaforma('whatsapp', {
          stato: 'connesso',
          numero: numeroDa(this.mioJid),
          qr: null,
          codice: null,
          errore: null,
        });
      }
      if (connection === 'close') {
        const codice = lastDisconnect?.error?.output?.statusCode;
        if (codice === DisconnectReason.loggedOut) {
          console.log('⚠️  WhatsApp scollegato dal telefono: serve un nuovo collegamento.');
          fs.rmSync(this.cartellaSessione, { recursive: true, force: true });
          this.stato.impostaPiattaforma('whatsapp', { stato: 'scollegato', numero: null });
          setTimeout(() => this.avvia(), 2000);
          return;
        }
        this.tentativi++;
        const riavvio = codice === DisconnectReason.restartRequired;
        const attesa = riavvio ? 500 : Math.min(60_000, 2000 * 2 ** Math.min(this.tentativi, 5));
        if (!riavvio) {
          console.log(
            `⚠️  WhatsApp disconnesso (${codice ?? lastDisconnect?.error?.message}), riconnessione tra ${Math.round(attesa / 1000)}s...`,
          );
        }
        this.stato.impostaPiattaforma('whatsapp', { stato: 'riconnessione' });
        setTimeout(() => this.avvia(), attesa);
      }
    });

    sock.ev.on('messages.upsert', ({ messages }) => {
      for (const m of messages) {
        this.gestisci(m).catch((err) => console.error('❌ WhatsApp, errore nel messaggio:', err));
      }
    });
  }

  avvia() {
    this.connetti().catch((err) => {
      console.error('❌ Avvio di WhatsApp non riuscito:', err);
      this.stato.impostaPiattaforma('whatsapp', { stato: 'errore', errore: err.message });
    });
  }

  async esci() {
    try {
      await this.sock?.logout();
    } catch {
      // già scollegato
    }
  }
}

export function avviaWhatsApp({ cervello, stato }) {
  const wa = new WhatsApp({ cervello, stato });

  // Avvisi al proprietario: arrivano nella chat "Tu" (messaggi a te stesso)
  cervello.aggiungiNotificatore(async (testo) => {
    if (!wa.sock || !wa.mioJid || stato.piattaforme.whatsapp.stato !== 'connesso') return false;
    await wa.invia(wa.mioJid, testo);
    return true;
  });

  stato.impostaPiattaforma('whatsapp', { stato: 'avvio' });
  wa.avvia();
  return wa;
}
