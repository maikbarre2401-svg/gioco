// Le "regole" sono il modo per dire al bot come rispondere a certe cose.
// Ogni regola ha delle CONDIZIONI (quando si applica) e delle AZIONI.
//
// Condizioni (se ne metti più di una basta che una sia vera):
//   quando_contiene:  ["parola", "frase"]   -> il messaggio contiene una di queste
//   quando_regex:     "espressione"         -> espressione regolare (per esperti)
//   quando_significa: "descrizione"         -> l'AI capisce il SIGNIFICATO del
//                                              messaggio, anche con parole diverse
//   (nessuna condizione)                    -> si applica sempre
// Limiti facoltativi:
//   solo_contatti:    ["393331234567", "@username", "Nome"]
//   solo_piattaforma: "whatsapp" | "telegram"
// Azioni:
//   rispondi_con:     "testo"   -> invia esattamente questo testo (senza AI);
//                                  con una lista ["a", "b"] ne sceglie una a caso
//   istruzioni_per_ai: "testo"  -> l'AI risponde seguendo queste istruzioni
//   non_rispondere:   true      -> il bot non risponde
//   avvisami:         true      -> ricevi un avviso (su Telegram o WhatsApp)

export function normalizza(testo) {
  return String(testo || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function comeLista(valore) {
  if (valore == null || valore === '') return [];
  return Array.isArray(valore) ? valore : [valore];
}

const regexNonValide = new Set();

function regexCorrisponde(sorgente, testo) {
  try {
    return new RegExp(sorgente, 'i').test(testo);
  } catch (err) {
    if (!regexNonValide.has(sorgente)) {
      regexNonValide.add(sorgente);
      console.error(`⚠️  Regola con quando_regex non valida "${sorgente}": ${err.message}`);
    }
    return false;
  }
}

export function contattoCorrisponde(voce, { idContatto, username, nomeContatto }) {
  const v = String(voce).trim();
  if (!v) return false;
  const cifre = v.replace(/\D/g, '');
  if (cifre && cifre.length >= 5 && idContatto && String(idContatto).replace(/\D/g, '') === cifre) {
    return true;
  }
  if (username && normalizza(v.replace(/^@/, '')) === normalizza(username.replace(/^@/, ''))) {
    return true;
  }
  return Boolean(nomeContatto) && normalizza(v) === normalizza(nomeContatto);
}

// Regole attive che valgono per questa piattaforma e questo contatto
export function regoleApplicabili(elenco, info) {
  return elenco.filter((r) => {
    if (!r || typeof r !== 'object' || r.attiva === false) return false;
    const piattaforme = comeLista(r.solo_piattaforma).map(normalizza);
    if (piattaforme.length && !piattaforme.includes(normalizza(info.piattaforma))) return false;
    const contatti = comeLista(r.solo_contatti);
    if (contatti.length && !contatti.some((c) => contattoCorrisponde(c, info))) return false;
    return true;
  });
}

export function haCondizioniTesto(r) {
  return comeLista(r.quando_contiene).length > 0 || Boolean(r.quando_regex);
}

export function eSemantica(r) {
  return Boolean(r.quando_significa && String(r.quando_significa).trim());
}

// Regole che scattano senza bisogno dell'AI (parole chiave, regex, "sempre")
export function regoleDirette(applicabili, testo) {
  const t = normalizza(testo);
  return applicabili.filter((r) => {
    if (haCondizioniTesto(r)) {
      const parole = comeLista(r.quando_contiene).map(normalizza).filter(Boolean);
      if (parole.some((p) => t.includes(p))) return true;
      if (r.quando_regex && regexCorrisponde(r.quando_regex, testo)) return true;
      return false;
    }
    // nessuna condizione sul testo e nessuna semantica = vale sempre
    return !eSemantica(r);
  });
}

// Unisce le azioni delle regole scattate in un'unica decisione
export function decidi(regoleScattate) {
  const decisione = {
    azione: 'ai',
    testoFisso: null,
    istruzioni: [],
    avvisa: false,
    nomi: regoleScattate.map((r) => r.nome || '(senza nome)'),
  };
  for (const r of regoleScattate) {
    if (r.avvisami) decisione.avvisa = true;
    if (r.istruzioni_per_ai) decisione.istruzioni.push(String(r.istruzioni_per_ai));
  }
  if (regoleScattate.some((r) => r.non_rispondere)) {
    decisione.azione = 'ignora';
  } else {
    const fissa = regoleScattate.find((r) => r.rispondi_con);
    if (fissa) {
      // se rispondi_con è una lista, sceglie una delle risposte a caso
      const varianti = comeLista(fissa.rispondi_con).map(String).filter(Boolean);
      if (varianti.length) {
        decisione.azione = 'fissa';
        decisione.testoFisso = varianti[Math.floor(Math.random() * varianti.length)];
      }
    }
  }
  return decisione;
}
