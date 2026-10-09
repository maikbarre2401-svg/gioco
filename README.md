# gioco — Zeph, il tuo compagno 3D 🕺

Zeph è un personaggio 3D a corpo intero che **cammina, salta, balla e ti parla a voce in italiano**, gesticolando mentre lo fa. Può anche **trasformarsi nel TUO avatar** (file `.glb`, per esempio da ReadyPlayerMe). Esiste in due versioni:

1. **🖥️ Sul desktop (stile Desktop Goose)** — cammina sul bordo dello schermo, sopra le tue finestre
2. **🌐 Nel browser** — in un mondo naturale con colline, montagne, alberi e farfalle
3. **📱 Sul telefono Android** — sopra tutte le app, con la notifica fissa per controllarlo: istruzioni in [`android/README.md`](android/README.md), APK pronto nella [release «android»](https://github.com/maikbarre2401-svg/gioco/releases/tag/android)

## 💛 Un amico che si ricorda di te

Zeph (o come vuoi chiamarlo: **«ti chiamerò Leo»**) ti fa compagnia e **impara a conoscerti**, giorno dopo giorno. Tutto resta sul tuo dispositivo.

- **Raccontagli la tua giornata** — «oggi sono andato al mare con mia sorella», «stamattina ho litigato col capo»: se lo segna nel suo diario, si rallegra con te o ti consola, e ti chiede di più.
- **I tuoi programmi** — «domani ho un esame»: ti fa l'in bocca al lupo e **il giorno dopo ti chiede com'è andata**.
- **Ti conosce** — il tuo nome, l'età, il lavoro, la città, cosa ti piace e cosa no («mi piace la pizza», «non mi piacciono i broccoli»), le persone e gli animali di cui parli («mia sorella si chiama Giulia», «ho un cane che si chiama Rocky»). Ogni tanto è lui a farti una domanda per conoscerti meglio.
- **Si ricorda** — «cosa sai di me?», «cosa ti ho detto ieri?», «ti ricordi il mare?», «da quanto ci conosciamo?». Quando lo riaccendi ti saluta ricordando l'ultima volta (e se è il tuo compleanno fa festa).
- **Come stai** — «sono felice», «sono stanco», «mi sento solo»: risponde da amico, e ti incoraggia anche a sentire le persone a cui vuoi bene. Se scrivi qualcosa che fa pensare a un pericolo, ti indica subito il 112 e Telefono Amico.
- **Insegnagli a rispondere** — «se ti dico buongiorno rispondi ciao campione».
- **«dimentica tutto»** — cancella la memoria (chiede conferma).

### 🧠 Cervello AI (facoltativo)

Di base Zeph usa un cervello **offline e gratuito**. Se vuoi che chiacchieri davvero, su qualsiasi argomento, puoi dargli la **tua chiave di Claude** (si crea su [console.anthropic.com](https://console.anthropic.com/settings/keys); paghi tu a consumo: circa uno o due centesimi di dollaro a messaggio):

- **sul telefono**: nell'app, sezione «🧠 Cervello AI», incolla la chiave e premi «Salva chiave»;
- **nel browser o sul desktop**: incollala nella chat (`sk-ant-…`). «togli la chiave» per tornare offline.

Con la chiave risponde **Claude (`claude-opus-5-5`)** usando quello che Zeph sa di te; i comandi (torcia, sveglie, app, meteo…) restano al cervello veloce offline. Se il modello rifiuta una domanda, l'API la passa da sola a un modello di riserva (`fallbacks: "default"`); senza internet torna il cervello offline. La chiave resta sul dispositivo (sul telefono è esclusa anche dai backup) e viene usata solo per parlare con l'API di Anthropic.

## ⚡ Zeph 5: i poteri (sul telefono funzionano davvero)

- **⏰ Promemoria veri** — «ricordami domani alle 9 di chiamare la mamma», «lunedì alle 18 e mezza ricordami la palestra», «ricordami il 12 marzo del compleanno di Giulia», «che promemoria ho?». Sul telefono li tiene Android: suonano con la notifica anche se Zeph è spento e tornano in fila dopo un riavvio.
- **📇 Rubrica** — «chiama mia sorella» (sa chi è tua sorella!), «chiama la mamma», «scrivi a Giulia che arrivo tra 5 minuti»: trova il numero e ti prepara la chiamata o il messaggio WhatsApp (o SMS); **premi tu** il tasto verde o invia.
- **📩 Messaggi** — se gli dai l'accesso alle notifiche: «Ti ha scritto Giulia su WhatsApp!», «chi mi ha scritto?», «rispondi: arrivo subito» → ti chiede conferma e, solo dopo il tuo «sì», risponde con il pulsante della notifica. Di base dice solo chi ti ha scritto; leggere anche il testo ad alta voce è un'opzione.
- **📅 Agenda** — «che impegni ho oggi?», «cosa ho in programma domani?», «aggiungi al calendario dentista domani alle 10» (te lo prepara nel calendario, salvi tu).
- **☀️ Il buongiorno** — la prima volta che sblocchi il telefono la mattina (o quando chiedi «com'è la mia giornata?»): data, meteo della tua città, impegni, promemoria e compleanno vicino.
- **📚 Sa le cose** — «chi era Leonardo da Vinci?», «cos'è un buco nero?»: risponde con Wikipedia, gratis (con il cervello AI risponde Claude).
- **🌍 Traduttore** — «traduci buonanotte in inglese», «come si dice gatto in giapponese?» (Google Traduttore, oppure direttamente il cervello AI).
- **👁 Gli occhi** (con il cervello AI) — «cosa vedi?», «che pianta è questa?», «leggimi questo»: si apre la fotocamera, inquadri e Claude ti risponde a voce.
- **🛸 Modalità ologramma** — «modalità ologramma»: diventa una proiezione di luce azzurra con linee di scansione e un proiettore sotto i piedi («torna normale» per tornare solido).
- **📳 Scuoti il telefono** — tre scossoni e arriva di corsa.
- **📊 «Come sono stato questa settimana?»** — fa il punto del tuo umore e di quello che gli hai raccontato.
- **💾 Backup della memoria** — nell'app salvi in un file tutto quello che sa di te e lo ripristini su un altro telefono o dopo aver reinstallato.

## 📸 Il tuo avatar da una foto

Premi **«📸 Avatar dalla foto»** (nel browser) o **«Crea l'avatar con una foto»** (nell'app Android), oppure dì **«crea il mio avatar con una foto»**: fai un selfie con la faccia nell'ovale (o scegli una foto dalla galleria) e Zeph prende **i colori veri di pelle, capelli e vestiti** e mette **la tua faccia sulla sua testa** — una maschera che segue la forma della testa e **apre la bocca quando parla**. Puoi ritoccare i colori, scegliere gli occhi, togliere i capelli e dargli un nome. La foto non viene mandata a nessuno.

Vuoi un avatar **3D realistico**? Su [avaturn.me](https://avaturn.me) fai un selfie, scarichi il `.glb` e lo usi come qui sotto.

## 🧑 Usa il TUO avatar (.glb)

1. Creati un avatar gratis su [avaturn.me](https://avaturn.me) o [readyplayer.me](https://readyplayer.me) (anche dalla tua foto) e scarica il file **.glb** — va bene qualsiasi modello con scheletro umanoide in stile Mixamo.
2. **Nel browser:** premi «🧑 Il tuo avatar» e scegli il file, oppure **trascinalo dentro la pagina**.
3. **Sul desktop:** salva il file come `avatars/avatar.glb` nella cartella del progetto e riavvia Zeph: lo carica da solo.
4. Per provare subito c'è un avatar di esempio: `avatars/esempio.glb`.

L'avatar eredita tutto: camminata, salti, balli, gesti mentre parla. In più Zeph lo rende più vivo:

- **Motion capture**: se il file contiene un'animazione (gli avatar Avaturn hanno un idle registrato da una persona vera), da fermo la usa — respiro, peso che si sposta, dita naturali — e la fonde osso per osso con camminata, gesti e balli.
- **La bocca si muove quando parla**, anche se l'avatar non ha espressioni facciali: Zeph trova le labbra sulla mesh, separa il solco tra le labbra e aggiunge mascella, cavità e denti.
- **Ti guarda**: nel browser gira la testa verso di te (o verso Nina quando le passa accanto), sul desktop **segue il cursore del mouse**.
- Palpebre e bocca usano i blendshape quando il modello li ha (ReadyPlayerMe); texture più nitide con il filtro anisotropico.

Se il modello non ha uno scheletro riconoscibile, viene portato in giro «rigido» ma funziona comunque. Nel browser l'avatar scelto viene **ricordato** per la volta successiva.

> 🔒 `avatars/avatar.glb` è escluso da git (`.gitignore`): se è il tuo volto, resta solo sul tuo PC anche se il repository è pubblico.

## 🚀 Zeph assistente: apre app, siti, messaggi e promemoria

Scrivigli (in chat, browser o desktop):

- **«apri whatsapp»** — sul desktop apre la **VERA app** di WhatsApp installata (idem Spotify, Telegram, Discord); nel browser la versione web
- **«apri impostazioni»** — apre le vere Impostazioni di Windows; funziona anche per sezione: «apri impostazioni **wifi** / bluetooth / audio / schermo / batteria / aggiornamenti / privacy»
- **«apri fotocamera»**, **«apri store»** — le app native di Windows
- **«apri calcolatrice»** / blocco note, paint, esplora file, **terminale, gestione attività, pannello di controllo, strumento di cattura, Word, Excel, PowerPoint** — app del PC (versione desktop)
- **«alza il volume»** / «abbassa il volume» / «muto» — controlla davvero il volume del PC (versione desktop)
- **«quanta batteria ho?»** — ti dice a voce la percentuale e se è in carica
- **«apri youtube»** / google, gmail, maps, wikipedia, netflix… — apre il sito
- **«cerca ricette veloci»** — cerca su Google
- **«manda messaggio arrivo tra 10 minuti»** — prepara il messaggio su WhatsApp: *tu premi invia* (Zeph non manda mai nulla da solo)
- **«scrivi una mail a nome@esempio.it dicendo ci vediamo domani»** — apre la mail già compilata
- **«ricordami tra 5 minuti della pizza»** — al momento giusto salta, te lo dice a voce e (sul desktop) manda una notifica
- **«che ore sono?»**, **«che giorno è?»**
- **«salto mortale»** 🤸, **«piroetta»** 🌀 — acrobazie con scintille all'atterraggio ✨
- **«mi chiamo …»** — si ricorda il tuo nome e ti saluta per nome la volta dopo (e tanto altro: vedi «Un amico che si ricorda di te»)
- **«corri»** / **«rallenta»** (o tieni premuto **Shift**) — corsa vera, con falcata da corsa
- **«chiama il cane»** 🐶 — arriva **Rocky**: ti segue scodinzolando e abbaia (anche sul desktop!)
- **«fai notte»** 🌙 / «tramonto» / «alba» / «fai giorno» — il sole si muove davvero: stelle, luna e lucciole di notte (solo browser)
- **«fai piovere»** 🌧 / «fai nevicare» ❄ / «torna il sole» — meteo con gocce e fiocchi veri (solo browser)
- **«foto»** 📸 — si mette in posa e ti scarica una foto ricordo del mondo (solo browser)
- **«metti la musica»** 🎵 — DJ Zeph: musica generata al volo, balla a tempo con luci da discoteca («basta musica» per spegnere)
- **«lancia la palla»** ⚽ — Rocky corre a prenderla e te la riporta (solo browser)
- **«sasso carta forbice»** ✂️ e **«indovinello»** 🧩 — gioca davvero con te, con vittorie ballate
- **«quanto fa 125 per 8?»** 🧮 — calcoli a voce
- **«cambia look»** 👕 — vestiti e capelli nuovi (se lo ricorda per la prossima volta)
- **«ciclo automatico»** ⏰ — il sole gira da solo: giorno, tramonto, notte e alba in loop (solo browser)
- **Sul desktop: afferralo col mouse!** Trascinalo in aria («Ehiii! Mettimi giù!») e lascialo cadere 😄
- **«vola»** 🚀 — jetpack con scia di particelle: si alza in volo e sfreccia (anche sul desktop!); «atterra» per scendere
- **🏘 Il villaggio** — tre casette oltre la collina e **Nina**, l'amica di Zeph: avvicinati e ti saluta con la mano
- **⭐ 12 stelle nascoste** nel mondo: raggiungile per raccoglierle (anche in volo!), con suono e contatore; raccolte tutte, festa e nuova caccia
- **«camera cinema»** 🎥 — inquadratura cinematografica che orbita da sola; «camera normale» per tornare
- Ti saluta con **«Buongiorno/Buonasera»** in base all'ora, e se sa il tuo nome lo usa
- **🧠 Capisce anche i refusi**: «bala» → balla, «watshap» → WhatsApp, «yutube» → YouTube — corregge da solo e te lo dice
- **«dimmi una curiosità»** — ne sa sedici, da imparare qualcosa ogni volta
- **«il mio colore preferito è il blu»** — impara i tuoi gusti (colore, animale, cibo, numero…) e li ricorda: «qual è il mio colore preferito?»
- **«ultra hd»** / «grafica normale» 🖥 — grafica ULTRA con bagliori luminosi (bloom), luce ambientale catturata dal cielo e ombre ad alta risoluzione; se il PC arranca, Zeph abbassa la grafica da solo e ti avvisa
- **🌦 «che tempo fa a Roma?»** — meteo vero di qualsiasi città, anche «domani»; dì «la mia città è …» e lo ricorda. Nel browser il mondo si adegua: se piove davvero, piove anche nel prato
- **🧮 «10 km in miglia», «30 gradi in fahrenheit»** — conversioni; **«tira un dado»**, **«testa o croce»**, **«numero a caso da 1 a 10»**
- **📅 «quanti giorni mancano a Natale?»** (e a Pasqua, Capodanno, al tuo compleanno: «il mio compleanno è il 12 marzo»), «che giorno è domani?»
- **💛 «sono triste»**, **«fammi un complimento»** — ti tira su
- **⏯ «pausa», «prossima canzone»** — comanda la musica delle altre app (app desktop e telefono)
- **😴 Di notte si addormenta** se lo lasci tranquillo, e **soffre il solletico** (tre clic di fila)
- **📱 Solo sul telefono**: torcia, sveglie e timer veri, chiamate, «Leggi con Zeph», risposte dalla notifica — vedi [`android/README.md`](android/README.md)
- **🏆 «missioni»** — 10 obiettivi da completare (saluta Nina, raccogli le stelle, vinci a sasso carta forbice, vola…): pannello con i progressi, premi pirotecnici e salvataggio automatico
- **«fuochi d'artificio»** 🎆 — razzi veri con scia, esplosione di colori e BOTTO (meglio di notte!)
- **🐦 Suoni d'ambiente** — uccellini di giorno, grilli di notte e vento leggero, tutti sintetizzati
- **💾 Il mondo si ricorda di te** — riapri la pagina e ritrovi l'ora del giorno, il meteo, Rocky e la tua posizione

## 🖥️ Versione desktop — sullo schermo

Zeph (o il tuo avatar) passeggia lungo il bordo inferiore dello schermo in una striscia trasparente sempre in primo piano: i clic passano attraverso, ma se clicchi proprio su di lui reagisce e ti parla. Può anche **seguire il mouse**.

**Come si avvia (Windows):**

1. Installa [Node.js](https://nodejs.org) (versione LTS, gratis) — serve solo la prima volta.
2. Scarica questo repository (**Code → Download ZIP**) ed estrailo.
3. Apri la cartella `desktop` e fai **doppio clic su `avvia.bat`**.

Su macOS/Linux: `cd desktop && npm install && npm start`.

**Comandi:** in basso a destra dello schermo ci sono due pulsanti sempre visibili: **💬 apre la chat** (scrivigli e risponde a voce) e **🎤 il microfono**. Anche il clic destro su Zeph apre la chat. In più c'è l'icona di Zeph vicino all'orologio con il menu completo: Saluta, Balla, Salta, 🤸 Salto mortale, 🌀 Piroetta, Barzelletta, 🚶 Passeggia da solo, 🖱️ Segui il mouse, 🔊 Voce, ❌ Chiudi.

**Parlargli a voce:** nella **versione browser** il microfono 🎤 funziona davvero (Chrome/Edge): premi, parla, e Zeph capisce ed esegue («apri youtube», «balla»…). Nell'app desktop Electron il riconoscimento vocale di sistema non è disponibile: il pulsante 🎤 te lo spiega e ti apre la chat scritta — Zeph ti risponde comunque sempre a voce.

## 🌐 Versione browser

Fai **doppio clic su `index.html`** (Chrome o Edge consigliati per la voce). Non serve internet: è tutto incluso.

| Azione | Come |
|---|---|
| 🚶 Camminare dove vuoi tu | Clicca un punto sul terreno, oppure guidalo con **WASD / frecce** |
| 🗣️ Parlarti a voce | Scrivigli nella barra in basso |
| 👋💃🦘😂 Azioni | Pulsanti rapidi o a parole («balla!», «salta!») |
| 🧑 Avatar personalizzato | Pulsante «Il tuo avatar» o trascina il .glb |
| 🎥 Visuale libera | Trascina per ruotare, rotella/pizzico per lo zoom |

Prova a scrivergli: *ciao*, *come stai?*, *chi sei?*, *vieni qui*, *canta*, *barzelletta*, *fermati*, *seguimi*…

## Note tecniche

- `zeph-core.js` — personaggio procedurale condiviso (scheletro articolato, ~7 teste), animazioni procedurali (camminata, respiro, palpebre, sguardo, gesti sincronizzati col parlato) e **retargeting su avatar GLB**: le ossa vengono riconosciute per nome (Mixamo/ReadyPlayerMe), gli arti sono guidati per allineamento direzionale (funziona anche con modelli in T-pose), bocca e palpebre via morph target.
- Mondo: terreno collinare generato con rumore, cielo shader con sole, montagne innevate all'orizzonte, due specie di alberi, cespugli, fiori, rocce, nuvole e farfalle animate, tone mapping ACES.
- Voce tramite **Web Speech API** con voce italiana di sistema; fumetto di testo come riserva.
- Desktop: **Electron** con finestra trasparente click-through sempre in primo piano, icona nell'area di notifica, chat separata.
- Librerie incluse: Three.js r147 (`three.min.js`) + `gltf-loader.js` — nessun download necessario. Per il cervello AI facoltativo c'è l'SDK ufficiale di Anthropic `@anthropic-ai/sdk` 0.128.0 impacchettato per il browser (`anthropic-sdk.js`, licenza MIT), caricato ma usato solo se metti la tua chiave.
- Poteri: `ZephCore.parseWhen` capisce date e ore dette a voce («domani alle 18 e mezza», «lunedì», «il 12 marzo»); su Android i promemoria usano `AlarmManager` (`Reminders.java`), rubrica e agenda sono in sola lettura (`Contacts.java`), i messaggi passano da un `NotificationListenerService` limitato alle app di chat (`MessageListener.java`) e restano solo in memoria; gli occhi sono `occhi.html` / `occhi.js` con `ZephCore.ai.see` (immagine + domanda a `claude-opus-5-5`); l'ologramma è `ZephCore.createHologram` (materiali con effetto Fresnel e linee di scansione, funziona anche sugli avatar `.glb`).
- Memoria da amico: `zeph-core.js` (`ZephCore.memory`) salva nel `localStorage` fatti, gusti, persone, diario, umore e risposte insegnate; il saluto e le domande spontanee nascono da lì. Avatar dalla foto: `foto.html` / `foto.js` + `ZephCore.lookFromPhoto` / `applyLook` (la faccia è proiettata frontalmente su un guscio calcolato con raycasting su cranio, mento e capelli).
- Onestà tecnica: il fotorealismo da film non è ottenibile in tempo reale nel browser; lo stile è «realistico da videogioco», leggero e fluido ovunque.
