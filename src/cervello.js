// Il "cervello" del bot: riceve i messaggi da WhatsApp e Telegram, li
// raggruppa, applica le regole, li analizza con l'AI e decide se e come
// rispondere.
//
// Ogni piattaforma passa un oggetto messaggio fatto così:
// {
//   piattaforma: 'whatsapp' | 'telegram',
//   chiave:      identificativo unico della chat (es. "whatsapp:39333...@s.whatsapp.net")
//   idContatto:  numero di telefono o id del mittente
//   username:    username Telegram (facoltativo)
//   nomeContatto, nomeChat, isGruppo, menzionato,
//   testo:       testo o didascalia
//   tipoMedia:   'immagine' | 'audio' | 'video' | 'sticker' | 'documento' | 'posizione' | ... (facoltativo)
//   scaricaMedia: async () => ({ buffer, mime })            (facoltativo)
//   ora:         timestamp in millisecondi
//   invia:       async (testo) => {}   manda la risposta nella chat
//   staScrivendo, segnaLetto: async () => {}               (facoltativi)
// }
import { impostazioni, istruzioni, regole } from './config.js';
import {
  regoleApplicabili,
  regoleDirette,
  decidi,
  eSemantica,
  haCondizioniTesto,
  normalizza,
  contattoCorrisponde,
} from './regole.js';
import { promptAnalisi, promptRisposta, cronologiaPerAI } from './prompt.js';
import { descriviErrore } from './ai.js';

const NOMI = { whatsapp: 'WhatsApp', telegram: 'Telegram', prova: 'Prova' };
const ETICHETTE_MEDIA = {
  immagine: 'foto',
  audio: 'messaggio vocale',
  video: 'video',
  sticker: 'sticker',
  documento: 'documento',
  posizione: 'posizione',
  contatto: 'contatto',
};

const attendi = (ms) => new Promise((r) => setTimeout(r, ms));

function minutiDelGiorno(fuso) {
  const parti = new Intl.DateTimeFormat('it-IT', {
    timeZone: fuso || undefined,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date());
  const h = Number(parti.find((p) => p.type === 'hour')?.value || 0);
  const m = Number(parti.find((p) => p.type === 'minute')?.value || 0);
  return h * 60 + m;
}

function orarioInMinuti(hhmm) {
  const [h, m] = String(hhmm || '0:0').split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
}

export function dentroOrario(orario, fuso, adesso = minutiDelGiorno(fuso)) {
  if (!orario?.attivo) return true;
  const da = orarioInMinuti(orario.dalle);
  const a = orarioInMinuti(orario.alle);
  if (da === a) return true;
  return da < a ? adesso >= da && adesso < a : adesso >= da || adesso < a;
}

function pulisciRisposta(testo) {
  let t = String(testo || '').trim();
  t = t.replace(/\*\*(.+?)\*\*/g, '$1').replace(/^#+\s*/gm, '');
  if (/^".*"$/s.test(t) || /^«.*»$/s.test(t)) t = t.slice(1, -1).trim();
  return t;
}

function riassunto(testo, max = 120) {
  const t = String(testo || '').replace(/\s+/g, ' ').trim();
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

export class Cervello {
  constructor({ ai, memoria, stato }) {
    this.ai = ai;
    this.memoria = memoria;
    this.stato = stato;
    this.buffer = new Map(); // chiave -> { messaggi: [], timer }
    this.code = new Map(); // chiave -> promise (elaborazione in corso)
    this.notificatori = [];
  }

  // Le piattaforme registrano qui il modo per avvisare il proprietario
  aggiungiNotificatore(fn) {
    this.notificatori.push(fn);
  }

  async notifica(testo) {
    for (const fn of this.notificatori) {
      try {
        if (await fn(testo)) return true;
      } catch (err) {
        console.warn('⚠️  Avviso non inviato:', err.message);
      }
    }
    console.log(`🔔 ${testo}`);
    return false;
  }

  // Controlli rapidi: restituisce il motivo per non rispondere (o null)
  motivoPerIgnorare(msg, imp) {
    const etaMin = (Date.now() - (msg.ora || Date.now())) / 60_000;
    if (imp.ignora_messaggi_piu_vecchi_di_min > 0 && etaMin > imp.ignora_messaggi_piu_vecchi_di_min) {
      return { motivo: 'messaggio vecchio (arrivato mentre il bot era spento)' };
    }
    if (msg.isGruppo) {
      if (imp.rispondi_nei_gruppi === 'mai') return { motivo: 'gruppo', silenzioso: true };
      if (imp.rispondi_nei_gruppi !== 'sempre' && !msg.menzionato) {
        return { motivo: 'gruppo, non menzionato', silenzioso: true };
      }
    }
    if (!imp.attivo) return { motivo: 'bot in pausa (spento dal pannello o con /pausa)' };
    if (imp[msg.piattaforma] === false) return { motivo: `${NOMI[msg.piattaforma]} disattivato` };
    if (!dentroOrario(imp.orario, imp.fuso_orario)) return { motivo: 'fuori orario' };

    const { modalita, lista = [] } = imp.contatti || {};
    if (modalita === 'solo_lista' || modalita === 'tutti_tranne_lista') {
      const infoChat = { idContatto: msg.chatId, nomeContatto: msg.nomeChat };
      const inLista = lista.some(
        (voce) => contattoCorrisponde(voce, msg) || (msg.isGruppo && contattoCorrisponde(voce, infoChat)),
      );
      if (modalita === 'solo_lista' && !inLista) return { motivo: 'contatto non in lista' };
      if (modalita === 'tutti_tranne_lista' && inLista) return { motivo: 'contatto escluso' };
    }
    if (this.stato.chatInPausa(msg.chiave)) return { motivo: 'chat in pausa (stai rispondendo tu)' };
    return null;
  }

  testoBase(msg) {
    const parti = [];
    if (msg.tipoMedia) parti.push(`[${ETICHETTE_MEDIA[msg.tipoMedia] || msg.tipoMedia}]`);
    if (msg.testo) parti.push(msg.testo);
    const t = parti.join(' ');
    return msg.isGruppo && msg.nomeContatto ? `${msg.nomeContatto}: ${t}` : t;
  }

  // Punto di ingresso per ogni messaggio ricevuto
  ricevi(msg) {
    this.stato.statistiche.ricevuti++;
    this.stato.ricordaNome(msg.chiave, msg.isGruppo ? msg.nomeChat || msg.chiave : msg.nomeContatto);
    const imp = impostazioni();
    const ignora = this.motivoPerIgnorare(msg, imp);
    if (ignora) {
      this.memoria.aggiungi(msg.chiave, 'user', this.testoBase(msg));
      if (!ignora.silenzioso) {
        this.stato.registra({
          piattaforma: msg.piattaforma,
          chiave: msg.chiave,
          nome: msg.nomeContatto,
          messaggio: riassunto(this.testoBase(msg), 300),
          esito: 'ignorato',
          motivo: ignora.motivo,
        });
      }
      return;
    }
    console.log(`💬 [${NOMI[msg.piattaforma]}] ${msg.nomeContatto || msg.chiave}: ${riassunto(this.testoBase(msg))}`);

    // Le persone spesso mandano più messaggi di fila: aspetto qualche
    // secondo e rispondo a tutti insieme.
    const attesa = Math.max(0, Number(imp.attesa_raggruppa_messaggi_sec) || 0) * 1000;
    const b = this.buffer.get(msg.chiave) || { messaggi: [], timer: null };
    b.messaggi.push(msg);
    clearTimeout(b.timer);
    b.timer = setTimeout(() => this.svuotaBuffer(msg.chiave), attesa);
    this.buffer.set(msg.chiave, b);
  }

  svuotaBuffer(chiave) {
    const b = this.buffer.get(chiave);
    this.buffer.delete(chiave);
    if (!b?.messaggi.length) return;
    this.inCoda(chiave, () => this.elabora(b.messaggi));
  }

  // Le elaborazioni della stessa chat avvengono una alla volta, in ordine
  inCoda(chiave, lavoro) {
    const precedente = this.code.get(chiave) || Promise.resolve();
    const prossimo = precedente.then(lavoro).catch((err) => {
      console.error(`❌ Errore nella chat ${chiave}:`, err);
    });
    this.code.set(chiave, prossimo);
    prossimo.then(() => {
      if (this.code.get(chiave) === prossimo) this.code.delete(chiave);
    });
    return prossimo;
  }

  // Il proprietario ha scritto di persona in una chat: il bot si fa da parte
  messaggioMio(chiave, testo) {
    const b = this.buffer.get(chiave);
    if (b) {
      clearTimeout(b.timer);
      this.buffer.delete(chiave);
      for (const m of b.messaggi) this.memoria.aggiungi(chiave, 'user', this.testoBase(m));
    }
    if (testo) this.memoria.aggiungi(chiave, 'assistant', testo);
    const minuti = Number(impostazioni().pausa_se_rispondo_io_min) || 0;
    if (minuti > 0) {
      const fineAttuale = this.stato.pause.get(chiave);
      if (fineAttuale === undefined || fineAttuale < Date.now() + minuti * 60_000) {
        this.stato.pausaChat(chiave, minuti);
      }
    }
  }

  async trasformaInTesto(msg, imp) {
    const testo = msg.testo || '';
    if (!msg.tipoMedia) return testo;
    const etichetta = ETICHETTE_MEDIA[msg.tipoMedia] || msg.tipoMedia;
    try {
      if (msg.tipoMedia === 'audio' && imp.capisci_vocali && msg.scaricaMedia) {
        const { buffer, mime } = await msg.scaricaMedia();
        const trascritto = await this.ai.trascrivi(buffer, mime);
        return `[messaggio vocale] ${trascritto || '(incomprensibile)'}`;
      }
      if (msg.tipoMedia === 'immagine' && imp.capisci_immagini && msg.scaricaMedia) {
        const { buffer, mime } = await msg.scaricaMedia();
        const descrizione = await this.ai.descriviImmagine(buffer, mime, testo);
        return `[foto: ${descrizione}]${testo ? ` ${testo}` : ''}`;
      }
    } catch (err) {
      console.warn(`⚠️  Impossibile leggere il ${etichetta}: ${descriviErrore(err)}`);
    }
    return `[${etichetta}]${testo ? ` ${testo}` : ''}`;
  }

  async elabora(messaggi, { prova = false } = {}) {
    const imp = impostazioni();
    const ultimo = messaggi[messaggi.length - 1];
    const { chiave } = ultimo;
    const evento = {
      piattaforma: ultimo.piattaforma,
      chiave,
      nome: ultimo.nomeContatto,
    };

    if (imp.segna_come_letto && !prova) {
      for (const m of messaggi) Promise.resolve().then(() => m.segnaLetto?.()).catch(() => {});
    }

    // 1. Vocali e foto diventano testo
    const testi = [];
    for (const m of messaggi) {
      const t = await this.trasformaInTesto(m, imp);
      if (t) testi.push(m.isGruppo && m.nomeContatto ? `${m.nomeContatto}: ${t}` : t);
    }
    const testo = testi.join('\n');
    evento.messaggio = riassunto(testo, 500);
    this.memoria.aggiungi(chiave, 'user', testo);

    // se nel frattempo hai risposto tu, il bot non interviene
    if (!prova && this.stato.chatInPausa(chiave)) {
      return this.stato.registra({ ...evento, esito: 'ignorato', motivo: 'chat in pausa (stai rispondendo tu)' });
    }
    if (!testo.trim()) {
      return this.stato.registra({ ...evento, esito: 'ignorato', motivo: 'messaggio vuoto' });
    }

    // 2. Regole con parole chiave (non serve l'AI)
    const info = {
      piattaforma: ultimo.piattaforma,
      idContatto: ultimo.idContatto,
      username: ultimo.username,
      nomeContatto: ultimo.nomeContatto,
    };
    const applicabili = regoleApplicabili(regole(), info);
    const scattate = regoleDirette(applicabili, testo);
    let decisione = decidi(scattate);
    let regolaCapita = null;

    // 3. Analisi del messaggio con l'AI
    let analisi = null;
    const semantiche = applicabili.filter((r) => eSemantica(r) && !scattate.includes(r));
    if (decisione.azione === 'ai' && imp.analisi_prima_di_rispondere) {
      try {
        const cronologia = this.memoria.ultimi(chiave, 10);
        const { sistema, utente } = promptAnalisi({ msg: ultimo, cronologia, regoleSemantiche: semantiche });
        analisi = await this.ai.analizza(sistema, utente);
        const nomeRegola = analisi?.regola ? normalizza(analisi.regola) : '';
        const trovata = nomeRegola && semantiche.find((r) => normalizza(r.nome) === nomeRegola);
        if (trovata) {
          regolaCapita = trovata;
          decisione = decidi([...scattate, trovata]);
        }
      } catch (err) {
        console.warn(`⚠️  Analisi non riuscita: ${descriviErrore(err)}`);
      }
    }
    evento.analisi = analisi;
    evento.regole = decisione.nomi;

    const daAvvisare =
      decisione.avvisa || (imp.avvisami_se_serve_umano && analisi?.serve_umano === true);
    if (daAvvisare && !prova) {
      const righe = [
        `🔔 ${ultimo.nomeContatto || chiave} su ${NOMI[ultimo.piattaforma]} ti ha scritto:`,
        `"${riassunto(testo, 400)}"`,
      ];
      if (analisi?.riassunto) righe.push(`📝 ${analisi.riassunto}`);
      if (analisi?.urgenza) righe.push(`⏱ Urgenza: ${analisi.urgenza}`);
      if (decisione.nomi.length) righe.push(`📌 Regola: ${decisione.nomi.join(', ')}`);
      this.notifica(righe.join('\n'));
      evento.avvisato = true;
    }

    // 4. Decisione
    if (decisione.azione === 'ignora') {
      return this.stato.registra({ ...evento, esito: 'ignorato', motivo: `regola: ${decisione.nomi.join(', ')}` });
    }
    if (decisione.azione === 'fissa') {
      try {
        await this.invia(ultimo, decisione.testoFisso, imp, prova);
        return this.stato.registra({ ...evento, esito: 'risposta fissa', risposta: decisione.testoFisso });
      } catch (err) {
        console.error(`❌ Invio non riuscito a ${ultimo.nomeContatto || chiave}: ${err.message}`);
        return this.stato.registra({ ...evento, esito: 'errore', motivo: `invio non riuscito: ${err.message}` });
      }
    }
    // regole "sempre valide" (es. tono per un contatto) non obbligano a rispondere a un semplice "ok"
    const regoleConCondizione = scattate.some(haCondizioniTesto) || Boolean(regolaCapita);
    if (analisi?.serve_risposta === false && !regoleConCondizione) {
      return this.stato.registra({ ...evento, esito: 'ignorato', motivo: 'il messaggio non richiede risposta' });
    }

    // 5. Risposta con l'AI
    try {
      const sistema = promptRisposta({
        msg: ultimo,
        istruzioni: istruzioni(),
        imp,
        analisi,
        istruzioniRegole: decisione.istruzioni,
        regoleSemantiche: semantiche,
      });
      const cronologia = cronologiaPerAI(this.memoria.ultimi(chiave, imp.memoria_messaggi));
      const { testo: generato, modello } = await this.ai.rispondi(sistema, cronologia);
      const risposta = pulisciRisposta(generato);
      if (!risposta) throw new Error("l'AI ha restituito una risposta vuota");
      await this.invia(ultimo, risposta, imp, prova);
      return this.stato.registra({ ...evento, esito: 'risposto', risposta, modello });
    } catch (err) {
      console.error(`❌ Risposta non generata per ${ultimo.nomeContatto || chiave}: ${descriviErrore(err)}`);
      return this.stato.registra({ ...evento, esito: 'errore', motivo: descriviErrore(err) });
    }
  }

  async invia(msg, testo, imp, prova) {
    if (imp.ritardo_umano && !prova) {
      await Promise.resolve()
        .then(() => msg.staScrivendo?.())
        .catch(() => {});
      await attendi(Math.min(1200 + testo.length * 35, 8000));
    }
    await msg.invia(testo);
    this.memoria.aggiungi(msg.chiave, 'assistant', testo);
    console.log(`🤖 → ${msg.nomeContatto || msg.chiave}: ${riassunto(testo)}`);
  }

  // Usato dal pannello per provare il bot senza WhatsApp/Telegram
  async prova(testo) {
    let risposta = null;
    const msg = {
      piattaforma: 'prova',
      chiave: 'prova:pannello',
      chatId: 'pannello',
      idContatto: 'pannello',
      nomeContatto: 'Tu (prova)',
      testo,
      ora: Date.now(),
      invia: async (t) => {
        risposta = t;
      },
    };
    const evento = await this.inCoda(msg.chiave, () => this.elabora([msg], { prova: true }));
    return { ...evento, risposta };
  }
}
