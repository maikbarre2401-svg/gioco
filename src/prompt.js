// Costruzione dei testi (prompt) inviati all'AI.

const NOMI_PIATTAFORMA = { whatsapp: 'WhatsApp', telegram: 'Telegram', prova: 'il pannello di prova' };

export function dataOra(fuso) {
  try {
    return new Date().toLocaleString('it-IT', {
      timeZone: fuso || undefined,
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return new Date().toLocaleString('it-IT');
  }
}

function descriviChat(msg) {
  const dove = NOMI_PIATTAFORMA[msg.piattaforma] || msg.piattaforma;
  const chi = msg.nomeContatto || 'una persona';
  return msg.isGruppo
    ? `in un gruppo su ${dove}${msg.nomeChat ? ` ("${msg.nomeChat}")` : ''}; l'ultimo messaggio è di ${chi}`
    : `in una chat privata su ${dove} con ${chi}`;
}

export function cronologiaComeTesto(cronologia, nomeContatto) {
  return cronologia
    .map((m) => `${m.ruolo === 'assistant' ? 'TU' : nomeContatto || 'LUI/LEI'}: ${m.testo}`)
    .join('\n');
}

export function promptAnalisi({ msg, cronologia, regoleSemantiche }) {
  const elencoRegole = regoleSemantiche.length
    ? regoleSemantiche.map((r) => `- "${r.nome}": ${r.quando_significa}`).join('\n')
    : '(nessuna)';
  const sistema = `Sei un analizzatore di messaggi. Ricevi una conversazione ${descriviChat(msg)}.
Analizza SOLO l'ultimo messaggio ricevuto (usando la conversazione come contesto) e rispondi
esclusivamente con un oggetto JSON con questi campi:
{
  "lingua": "codice della lingua del messaggio, es. it, en, es",
  "intento": "cosa vuole la persona, massimo 10 parole",
  "sentimento": "positivo" | "neutro" | "negativo",
  "urgenza": "bassa" | "media" | "alta",
  "riassunto": "il messaggio riassunto in una frase",
  "regola": "nome ESATTO della regola che corrisponde al significato del messaggio, oppure null",
  "serve_umano": true se serve l'intervento personale del proprietario (emergenze, soldi, decisioni importanti, domande a cui un assistente non può rispondere con certezza), altrimenti false,
  "serve_risposta": false SOLO se il messaggio non richiede alcuna replica (es. "ok", "👍", "va bene grazie, ciao" che chiudono il discorso), altrimenti true
}

Regole disponibili (scegline una solo se il significato del messaggio corrisponde davvero, anche con parole diverse):
${elencoRegole}`;
  const contesto = cronologia.slice(0, -1);
  const ultimo = cronologia[cronologia.length - 1];
  const utente =
    (contesto.length
      ? `CONVERSAZIONE PRECEDENTE:\n${cronologiaComeTesto(contesto.slice(-8), msg.nomeContatto)}\n\n`
      : '') + `ULTIMO MESSAGGIO DA ANALIZZARE:\n${ultimo ? ultimo.testo : msg.testo}`;
  return { sistema, utente };
}

export function promptRisposta({ msg, istruzioni, imp, analisi, istruzioniRegole, regoleSemantiche }) {
  const parti = [istruzioni || 'Sei un assistente che risponde ai messaggi in modo cordiale e breve.'];

  const contesto = [`Stai rispondendo ${descriviChat(msg)}.`, `Data e ora attuali: ${dataOra(imp.fuso_orario)}.`];
  if (imp.nome_proprietario) {
    contesto.push(`Il proprietario dell'account, per cui rispondi, si chiama ${imp.nome_proprietario}.`);
  }
  parti.push(`=== CONTESTO ===\n${contesto.join('\n')}`);

  if (analisi) {
    const righe = [
      analisi.intento && `- Cosa vuole: ${analisi.intento}`,
      analisi.sentimento && `- Tono: ${analisi.sentimento}`,
      analisi.urgenza && `- Urgenza: ${analisi.urgenza}`,
      analisi.lingua && `- Lingua: ${analisi.lingua} (rispondi in questa lingua)`,
    ].filter(Boolean);
    if (righe.length) parti.push(`=== ANALISI DEL MESSAGGIO ===\n${righe.join('\n')}`);
  }

  if (istruzioniRegole?.length) {
    parti.push(
      `=== ISTRUZIONI SPECIALI PER QUESTO MESSAGGIO (hanno la priorità) ===\n${istruzioniRegole
        .map((i) => `- ${i}`)
        .join('\n')}`,
    );
  }

  // senza analisi preventiva l'AI valuta da sola le regole "quando_significa"
  if (!analisi && regoleSemantiche?.length) {
    const condizionali = regoleSemantiche
      .filter((r) => r.istruzioni_per_ai)
      .map((r) => `- Se ${r.quando_significa}: ${r.istruzioni_per_ai}`);
    if (condizionali.length) parti.push(`=== REGOLE ===\n${condizionali.join('\n')}`);
  }

  parti.push(`=== FORMATO ===
- Scrivi solo il testo del messaggio da inviare, senza virgolette e senza premesse.
- Niente markdown (niente **, #, tabelle): è una chat.
- Breve e naturale, come una persona vera in chat.
- I messaggi tra parentesi quadre (es. [messaggio vocale], [foto]) sono trascrizioni o descrizioni automatiche di vocali e immagini.`);

  return parti.join('\n\n');
}

export function cronologiaPerAI(cronologia) {
  return cronologia.map((m) => ({
    role: m.ruolo === 'assistant' ? 'assistant' : 'user',
    content: m.testo,
  }));
}
