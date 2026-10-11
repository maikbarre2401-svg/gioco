# 🤖 Assistente AI per WhatsApp e Telegram

Un bot che **legge, analizza e risponde da solo** ai messaggi di WhatsApp e Telegram,
usando l'intelligenza artificiale di **Groq**, che si usa **gratis**.

## Cosa sa fare

- **Risponde in automatico** su WhatsApp (il tuo numero) e su Telegram, in modo naturale e nella lingua di chi scrive.
- **Analizza ogni messaggio prima di rispondere**: capisce cosa vuole la persona, il tono, l'urgenza e se serve che intervenga tu.
- **Gli insegni tu come rispondere**:
  - scrivi con parole tue chi è e cosa deve sapere (file `config/istruzioni.md`);
  - crei **regole**, ad esempio *"se mi chiedono un appuntamento, chiedi giorno e ora e avvisami"*. La regola funziona anche se usano parole diverse, perché l'AI capisce il **significato**.
- **Capisce i vocali**, perché li trascrive, e **guarda le foto**, perché le descrive.
- **Ha memoria**: ricorda la conversazione con ogni persona.
- **Sembra umano**: aspetta che la persona finisca di scrivere, mostra "sta scrivendo…" e risponde a più messaggi insieme.
- **Si fa da parte quando rispondi tu**: se scrivi di persona in una chat, il bot si ferma lì per 30 minuti.
- **Ti avvisa** su Telegram o nella tua chat WhatsApp "Tu" quando un messaggio è urgente o importante.
- **Pannello di controllo web**: mostra il QR di WhatsApp, i messaggi ricevuti con l'analisi dell'AI e un'area dove provare il bot. Da lì modifichi anche istruzioni, regole e impostazioni.
- Gruppi (risponde solo se lo menzioni), liste di contatti, fascia oraria, pausa/riprendi.

---

## 1. Cosa ti serve

1. **Node.js 20 o più recente**: scaricalo da <https://nodejs.org> (versione "LTS").
2. **Una chiave Groq gratuita**: vai su <https://console.groq.com/keys>, accedi e premi *Create API Key*.
3. *(per Telegram)* **Un bot Telegram**: su Telegram apri **@BotFather**, scrivi `/newbot` e segui le istruzioni. Alla fine ti dà un **token**.
4. *(per WhatsApp)* Il telefono con WhatsApp, per scansionare un QR code.

## 2. Installazione

Apri il terminale (su Windows: *Prompt dei comandi* o *PowerShell*) nella cartella del progetto:

```bash
npm install
```

Poi copia il file delle impostazioni segrete:

```bash
# Windows
copy .env.example .env
# Mac / Linux
cp .env.example .env
```

Apri `.env` con un editor di testo e compila:

```ini
GROQ_API_KEY=gsk_la_tua_chiave
TELEGRAM_BOT_TOKEN=123456:ABC...      # se usi Telegram
WHATSAPP_ATTIVO=true                  # false se non vuoi WhatsApp
```

## 3. Avvio

```bash
npm start
```

- **WhatsApp**: nel terminale (e nel pannello) compare un **QR code**. Sul telefono apri
  WhatsApp → ⚙️ Impostazioni → **Dispositivi collegati** → **Collega un dispositivo** e inquadralo.
  Il collegamento resta salvato, quindi lo fai solo la prima volta.
  *In alternativa al QR*, metti il tuo numero in `WHATSAPP_NUMERO=393331234567`: riceverai un codice
  da inserire in "Collega con numero di telefono".
- **Telegram**: scrivi al tuo bot. Con `/id` scopri il tuo id: mettilo in `TELEGRAM_OWNER_ID` nel file
  `.env` e riavvia. Così puoi usare i comandi da proprietario e ricevere gli avvisi.
- **Pannello di controllo**: apri <http://localhost:3000> nel browser.

> 💡 **Telegram che risponde al posto tuo nelle tue chat private.** Normalmente il bot risponde a chi
> scrive **al bot**. Se hai **Telegram Premium**, puoi collegarlo al tuo account: Impostazioni →
> **Telegram Business** → **Chatbot** → scegli il tuo bot. Da quel momento risponde lui nelle tue chat
> private, e si ferma quando scrivi tu.

---

## 4. Insegnare al bot come rispondere

### Le istruzioni generali: `config/istruzioni.md`

Scrivi con parole tue chi è il bot, che tono usare e tutto quello che deve sapere: orari, prezzi,
indirizzo, cosa fai, cosa NON deve dire. Puoi modificarle anche dal pannello, nella scheda **"Come rispondere"**.
Più informazioni metti, meglio risponde.

### Le regole: `config/regole.json`

Le regole dicono al bot cosa fare in casi precisi. Le crei comodamente dal pannello (scheda **Regole**)
oppure nel file. Ogni regola ha delle **condizioni** (quando scatta) e un'**azione** (cosa fa).

| Condizione | Significato |
|---|---|
| `"quando_contiene": ["prezzo", "quanto costa"]` | il messaggio contiene una di queste parole |
| `"quando_significa": "vuole un appuntamento"` | 🧠 l'AI capisce il **senso**, anche con parole diverse |
| `"quando_regex": "..."` | espressione regolare (per esperti) |
| *(nessuna condizione)* | vale sempre |
| `"solo_contatti": ["393331234567", "@username", "Nome"]` | solo per questi contatti |
| `"solo_piattaforma": "whatsapp"` | solo su WhatsApp (o `"telegram"`) |

| Azione | Cosa fa |
|---|---|
| `"rispondi_con": "testo"` | risponde **esattamente** con questo testo (con una lista `["a","b"]` ne sceglie una a caso) |
| `"istruzioni_per_ai": "..."` | l'AI risponde seguendo queste istruzioni |
| `"non_rispondere": true` | il bot non risponde |
| `"avvisami": true` | ricevi un avviso 🔔 |

Esempio:

```json
[
  {
    "nome": "Prezzi",
    "quando_contiene": ["prezzo", "quanto costa", "listino"],
    "rispondi_con": "Il taglio costa 15€, taglio + piega 25€ 💇"
  },
  {
    "nome": "Appuntamenti",
    "quando_significa": "la persona vuole prenotare o chiede quando può venire",
    "istruzioni_per_ai": "Chiedi giorno e ora preferiti. Non confermare: di' che confermo io.",
    "avvisami": true
  },
  {
    "nome": "Mamma",
    "solo_contatti": ["393331234567"],
    "istruzioni_per_ai": "È mia mamma: tono affettuoso, dalle del tu, rassicurala."
  },
  {
    "nome": "Spam",
    "quando_regex": "(bitcoin|guadagna subito)",
    "non_rispondere": true
  }
]
```

Le modifiche valgono **subito**, senza riavviare.

### Provalo prima di usarlo davvero

Nel pannello, scheda **"Prova il bot"**, scrivi come se fossi un contatto: vedi la risposta, l'analisi e
la regola usata, senza mandare niente a nessuno.

---

## 5. Comandi

**Su WhatsApp**, nella chat con te stesso ("Tu" / "Messaggi a te stesso"):

| Comando | |
|---|---|
| `!pausa` | ferma le risposte automatiche |
| `!riprendi` | le riattiva |
| `!stato` | statistiche |

**Su Telegram**, scrivendo al bot:

| Comando | |
|---|---|
| `/pausa`, `/riprendi`, `/stato` | come sopra (solo il proprietario, `TELEGRAM_OWNER_ID`) |
| `/reset` | azzera la conversazione |
| `/id` | mostra il tuo id |

Il pulsante **⏸ Metti in pausa** del pannello fa la stessa cosa.

---

## 6. Le impostazioni principali (`config/impostazioni.json` o pannello)

| Impostazione | Predefinito | Cosa fa |
|---|---|---|
| `nome_proprietario` | `""` | il tuo nome, così il bot sa per chi risponde |
| `analisi_prima_di_rispondere` | `true` | analizza ogni messaggio (intento, urgenza, regole) |
| `capisci_vocali` / `capisci_immagini` | `true` | trascrive i vocali / descrive le foto |
| `attesa_raggruppa_messaggi_sec` | `4` | aspetta che la persona finisca di scrivere |
| `pausa_se_rispondo_io_min` | `30` | minuti di silenzio del bot dopo che hai scritto tu |
| `rispondi_nei_gruppi` | `se_menzionato` | `mai`, `se_menzionato` o `sempre` |
| `contatti.modalita` | `tutti` | `tutti`, `solo_lista` o `tutti_tranne_lista` |
| `orario` | disattivo | risponde solo in una fascia oraria (es. 20:00 → 08:00) |
| `avvisami_se_serve_umano` | `true` | ti avvisa quando un messaggio richiede te |
| `modello` | `llama-3.3-70b-versatile` | modello Groq per le risposte |
| `modello_riserva` | `llama-3.1-8b-instant` | usato quando il principale finisce il limite gratuito |

Se Groq cambia i nomi dei modelli, all'avvio il bot ti mostra quali sono disponibili: copia il nome giusto
nelle impostazioni.

---

## 7. Tenerlo acceso 24 ore su 24 (online)

Il bot risponde solo finché il programma è acceso. Hai tre possibilità:

**A) Sul tuo computer, con pm2** (si riavvia da solo se si blocca):

```bash
npm install -g pm2
pm2 start src/index.js --name assistente
pm2 save
pm2 startup        # (Mac/Linux) per farlo partire all'accensione del computer
pm2 logs assistente  # per vedere cosa succede
```

**B) Su un server/VPS** (anche gratuito, es. Oracle Cloud "Always Free", oppure un VPS da pochi euro al
mese): copi la cartella, fai `npm install`, compili `.env` e usi pm2 come sopra. Per aprire il pannello
da fuori imposta `PANNELLO_PASSWORD` (nome utente: `admin`).

**C) Con Docker:**

```bash
docker build -t assistente .
docker run -d --name assistente --restart unless-stopped \
  --env-file .env -e PANNELLO_PASSWORD=una_password \
  -p 3000:3000 -v $(pwd)/data:/app/data -v $(pwd)/config:/app/config assistente
docker logs -f assistente   # qui vedi il QR di WhatsApp
```

> La cartella `data/` contiene il collegamento a WhatsApp e la memoria delle conversazioni: non
> cancellarla e **non condividerla con nessuno**.

---

## 8. Cose importanti da sapere ⚠️

- **WhatsApp**: il collegamento usa una libreria non ufficiale (Baileys), che funziona come WhatsApp Web.
  È molto usata, ma WhatsApp non la approva ufficialmente e in teoria **può bloccare il numero**, soprattutto
  se viene usato per spam. Questo bot risponde solo a chi ti scrive, e così il rischio si riduce. Per stare
  tranquillo puoi comunque provarlo prima con un **numero secondario**.
- **Limiti gratuiti di Groq**: il piano gratuito ha un numero massimo di richieste al minuto e al giorno.
  Per l'uso personale di solito bastano. Quando il modello principale arriva al limite, il bot passa da solo
  al modello di riserva.
- **Privacy**: il testo dei messaggi, i vocali e le foto vengono mandati a Groq per essere elaborati.
  Avvisa i tuoi contatti, se è il caso, ed evita di usare il bot per dati molto sensibili.
- Il bot **non prende impegni al posto tuo**: le istruzioni predefinite gli dicono di non inventare
  prezzi, orari o promesse. Personalizzale in base alle tue esigenze.

---

## 9. Problemi comuni

| Problema | Soluzione |
|---|---|
| `Manca GROQ_API_KEY` | non hai creato `.env` o la chiave è vuota |
| `chiave GROQ_API_KEY non valida` | ricopia la chiave da console.groq.com |
| `limite gratuito di Groq raggiunto` | aspetta qualche minuto; il bot usa intanto il modello di riserva |
| Il QR non compare / scade | riavvia con `npm start`; nel pannello il QR si aggiorna da solo |
| WhatsApp "scollegato" | hai rimosso il dispositivo dal telefono: riavvia e scansiona di nuovo |
| Il bot non risponde a qualcuno | guarda la scheda **Messaggi** del pannello: c'è scritto il motivo (in pausa, fuori orario, regola…) |
| Telegram `TELEGRAM_BOT_TOKEN non valido` | ricopia il token da @BotFather |
| Nei gruppi Telegram non vede i messaggi | normale: i bot vedono solo i messaggi che li menzionano (privacy mode di @BotFather) |

---

## Struttura del progetto

```
config/
  istruzioni.md       come deve comportarsi il bot (modificalo!)
  regole.json         le tue regole
  impostazioni.json   tutte le opzioni
src/
  index.js            avvio
  cervello.js         analisi, regole, memoria, decisione della risposta
  ai.js               collegamento a Groq (testo, analisi, vocali, foto)
  prompt.js           i testi inviati all'AI
  regole.js           gestione delle regole
  whatsapp.js         collegamento a WhatsApp (Baileys)
  telegram.js         collegamento a Telegram (grammY)
  pannello.js/.html   pannello di controllo web
test/                 test automatici (npm test)
data/                 creata in automatico: sessione WhatsApp, memoria, stato
```
