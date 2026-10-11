// Pannello di controllo web: stato, QR di WhatsApp, messaggi ricevuti con
// l'analisi dell'AI, prova del bot, modifica di istruzioni/regole/impostazioni.
import path from 'node:path';
import crypto from 'node:crypto';
import express from 'express';
import {
  ENV,
  PERCORSI,
  impostazioni,
  salvaImpostazioni,
  regole,
  salvaRegole,
  istruzioni,
  salvaIstruzioni,
} from './config.js';

function confrontoSicuro(a, b) {
  const ha = crypto.createHash('sha256').update(String(a)).digest();
  const hb = crypto.createHash('sha256').update(String(b)).digest();
  return crypto.timingSafeEqual(ha, hb);
}

export function avviaPannello({ cervello, stato, memoria, whatsapp }) {
  const app = express();
  app.disable('x-powered-by');
  app.use(express.json({ limit: '1mb' }));

  if (ENV.pannelloPassword) {
    app.use((req, res, next) => {
      const [tipo, valore] = (req.headers.authorization || '').split(' ');
      if (tipo === 'Basic' && valore) {
        const [, ...resto] = Buffer.from(valore, 'base64').toString().split(':');
        if (confrontoSicuro(resto.join(':'), ENV.pannelloPassword)) return next();
      }
      res.set('WWW-Authenticate', 'Basic realm="Pannello assistente", charset="UTF-8"');
      res.status(401).send('Password richiesta');
    });
  }

  const gestisci = (fn) => async (req, res) => {
    try {
      res.json((await fn(req)) ?? { ok: true });
    } catch (err) {
      res.status(400).json({ errore: err.message });
    }
  };

  app.get('/', (req, res) => res.sendFile(path.join(PERCORSI.radice, 'src', 'pannello.html')));

  app.get(
    '/api/stato',
    gestisci(() => ({
      attivo: impostazioni().attivo,
      piattaforme: stato.piattaforme,
      statistiche: stato.statistiche,
      pause: stato.elencoPause(),
    })),
  );

  app.get('/api/eventi', gestisci(() => stato.eventi.slice(0, 150)));

  app.get(
    '/api/config',
    gestisci(() => ({ impostazioni: impostazioni(), regole: regole(), istruzioni: istruzioni() })),
  );

  app.put(
    '/api/impostazioni',
    gestisci((req) => {
      if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) {
        throw new Error('Impostazioni non valide');
      }
      salvaImpostazioni(req.body);
    }),
  );

  app.put('/api/regole', gestisci((req) => salvaRegole(req.body)));

  app.put(
    '/api/istruzioni',
    gestisci((req) => {
      if (typeof req.body?.testo !== 'string') throw new Error('Testo mancante');
      salvaIstruzioni(req.body.testo);
    }),
  );

  app.post(
    '/api/attivo',
    gestisci((req) => salvaImpostazioni({ ...impostazioni(), attivo: Boolean(req.body?.attivo) })),
  );

  app.post(
    '/api/pausa',
    gestisci((req) => {
      if (!req.body?.chiave) throw new Error('Chat mancante');
      const minuti = req.body.minuti == null ? null : Number(req.body.minuti);
      stato.pausaChat(req.body.chiave, minuti);
    }),
  );

  app.post(
    '/api/riprendi',
    gestisci((req) => {
      if (!req.body?.chiave) throw new Error('Chat mancante');
      stato.riprendiChat(req.body.chiave);
    }),
  );

  app.post(
    '/api/prova',
    gestisci(async (req) => {
      const testo = String(req.body?.testo || '').trim();
      if (!testo) throw new Error('Scrivi un messaggio');
      return cervello.prova(testo);
    }),
  );

  app.post('/api/prova/reset', gestisci(() => memoria.cancella('prova:pannello')));

  app.post(
    '/api/whatsapp/scollega',
    gestisci(async () => {
      if (!whatsapp) throw new Error('WhatsApp non è attivo');
      await whatsapp.esci();
    }),
  );

  // senza password il pannello è raggiungibile solo da questo computer
  const host = ENV.pannelloPassword ? '0.0.0.0' : '127.0.0.1';
  const server = app.listen(ENV.pannelloPorta, host, () => {
    console.log(`🖥  Pannello di controllo: http://localhost:${ENV.pannelloPorta}`);
    if (!ENV.pannelloPassword) {
      console.log('   (visibile solo da questo computer: imposta PANNELLO_PASSWORD per aprirlo da altri dispositivi)');
    }
  });
  server.on('error', (err) => {
    console.error(`❌ Pannello non avviato sulla porta ${ENV.pannelloPorta}: ${err.message}`);
  });
  return server;
}
