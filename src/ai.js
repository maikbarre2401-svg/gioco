// Collegamento a Groq (API gratuita): risposte, analisi dei messaggi,
// descrizione delle foto e trascrizione dei messaggi vocali.
import Groq, { toFile } from 'groq-sdk';
import { impostazioni } from './config.js';

const MAX_IMMAGINE_BYTE = 3 * 1024 * 1024; // in base64 diventa ~4 MB (limite Groq)
const MAX_AUDIO_BYTE = 25 * 1024 * 1024; // limite piano gratuito

// Errori per cui ha senso riprovare con il modello di riserva
function erroreRecuperabile(err) {
  const s = err?.status;
  if (!s) return true; // problema di rete / timeout
  if (s === 429 || s >= 500 || s === 404) return true;
  return s === 400 && /model/i.test(err.message || '');
}

export function descriviErrore(err) {
  const s = err?.status;
  if (!s && /connection|timed? ?out|fetch failed|ENOTFOUND|ECONN/i.test(err?.message || '')) {
    return 'impossibile raggiungere Groq (controlla la connessione a internet)';
  }
  if (s === 401) return 'chiave GROQ_API_KEY non valida';
  if (s === 429) return 'limite gratuito di Groq raggiunto, riprova tra poco';
  if (s === 404 || (s === 400 && /model/i.test(err.message || ''))) {
    return `modello non disponibile (${err.message})`;
  }
  return err?.message || String(err);
}

function estraiJson(testo) {
  const t = String(testo || '');
  try {
    return JSON.parse(t);
  } catch {
    const inizio = t.indexOf('{');
    const fine = t.lastIndexOf('}');
    if (inizio !== -1 && fine > inizio) return JSON.parse(t.slice(inizio, fine + 1));
    throw new Error('risposta di analisi non in formato JSON');
  }
}

function estensioneAudio(mime = '') {
  if (/mpeg|mp3/.test(mime)) return 'mp3';
  if (/mp4|m4a|aac/.test(mime)) return 'm4a';
  if (/wav/.test(mime)) return 'wav';
  if (/webm/.test(mime)) return 'webm';
  if (/flac/.test(mime)) return 'flac';
  return 'ogg'; // vocali di WhatsApp e Telegram (ogg/opus)
}

export class AI {
  constructor(apiKey) {
    this.client = new Groq({ apiKey, maxRetries: 1, timeout: 45_000 });
  }

  async completa({ messaggi, modelli, json = false, temperatura, maxToken }) {
    const imp = impostazioni();
    const elenco = [...new Set(modelli.filter(Boolean))];
    let ultimoErrore;
    for (const modello of elenco) {
      try {
        const r = await this.client.chat.completions.create({
          model: modello,
          messages: messaggi,
          temperature: temperatura ?? imp.temperatura,
          max_completion_tokens: maxToken ?? imp.lunghezza_massima_risposta,
          ...(json ? { response_format: { type: 'json_object' } } : {}),
        });
        return { testo: (r.choices?.[0]?.message?.content || '').trim(), modello };
      } catch (err) {
        ultimoErrore = err;
        if (!erroreRecuperabile(err)) break;
        console.warn(`⚠️  Groq (${modello}): ${descriviErrore(err)}`);
      }
    }
    throw ultimoErrore;
  }

  // Genera la risposta da inviare. messaggi = [{role, content}, ...]
  async rispondi(sistema, messaggi) {
    const imp = impostazioni();
    return this.completa({
      messaggi: [{ role: 'system', content: sistema }, ...messaggi],
      modelli: [imp.modello, imp.modello_riserva],
    });
  }

  // Analizza il messaggio e restituisce un oggetto
  async analizza(sistema, contenuto) {
    const imp = impostazioni();
    const { testo } = await this.completa({
      messaggi: [
        { role: 'system', content: sistema },
        { role: 'user', content: contenuto },
      ],
      modelli: [imp.modello_analisi, imp.modello_riserva, imp.modello],
      json: true,
      temperatura: 0,
      maxToken: 400,
    });
    return estraiJson(testo);
  }

  async descriviImmagine(buffer, mime = 'image/jpeg', didascalia = '') {
    if (buffer.length > MAX_IMMAGINE_BYTE) return 'una foto (troppo grande per essere analizzata)';
    const imp = impostazioni();
    const richiesta =
      'Descrivi in italiano, in modo conciso (massimo 3 frasi), cosa si vede in questa immagine. ' +
      'Se contiene del testo scritto, riportalo.' +
      (didascalia ? ` La persona ha scritto insieme alla foto: "${didascalia}".` : '');
    const { testo } = await this.completa({
      messaggi: [
        {
          role: 'user',
          content: [
            { type: 'text', text: richiesta },
            {
              type: 'image_url',
              image_url: { url: `data:${mime};base64,${buffer.toString('base64')}` },
            },
          ],
        },
      ],
      modelli: [imp.modello_immagini],
      temperatura: 0.2,
      maxToken: 300,
    });
    return testo;
  }

  async trascrivi(buffer, mime = 'audio/ogg') {
    if (buffer.length > MAX_AUDIO_BYTE) throw new Error('audio troppo lungo');
    const imp = impostazioni();
    const r = await this.client.audio.transcriptions.create({
      file: await toFile(buffer, `vocale.${estensioneAudio(mime)}`),
      model: imp.modello_audio,
      ...(imp.lingua_audio ? { language: imp.lingua_audio } : {}),
      response_format: 'json',
    });
    return (r.text || '').trim();
  }

  // Controlla all'avvio che la chiave funzioni e che i modelli esistano
  async verifica() {
    const imp = impostazioni();
    const r = await this.client.models.list();
    const disponibili = new Set((r.data || []).map((m) => m.id));
    const mancanti = [
      imp.modello,
      imp.modello_riserva,
      imp.modello_analisi,
      imp.modello_immagini,
      imp.modello_audio,
    ].filter((m) => m && !disponibili.has(m));
    return { disponibili: [...disponibili].sort(), mancanti: [...new Set(mancanti)] };
  }
}
