# gioco — Zeph, il tuo compagno 3D 🕺

Zeph è un personaggio 3D a corpo intero che **cammina, salta, balla e ti parla a voce in italiano**, gesticolando mentre lo fa. Può anche **trasformarsi nel TUO avatar** (file `.glb`, per esempio da ReadyPlayerMe). Esiste in due versioni:

1. **🖥️ Sul desktop (stile Desktop Goose)** — cammina sul bordo dello schermo, sopra le tue finestre
2. **🌐 Nel browser** — in un mondo naturale con colline, montagne, alberi e farfalle

## 🧑 Usa il TUO avatar (.glb)

1. Creati un avatar gratis su [readyplayer.me](https://readyplayer.me) e scarica il file **.glb** (va bene anche qualsiasi modello con scheletro umanoide in stile Mixamo).
2. **Nel browser:** premi «🧑 Il tuo avatar» e scegli il file, oppure **trascinalo dentro la pagina**.
3. **Sul desktop:** salva il file come `avatars/avatar.glb` nella cartella del progetto e riavvia Zeph: lo carica da solo.
4. Per provare subito c'è un avatar di esempio: `avatars/esempio.glb`.

L'avatar eredita tutto: camminata, salti, balli, gesti mentre parla, e — se il modello ha i morph facciali (ReadyPlayerMe li ha) — anche bocca e palpebre animate. Se il modello non ha uno scheletro riconoscibile, viene portato in giro «rigido» ma funziona comunque. Nel browser l'avatar scelto viene **ricordato** per la volta successiva.

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
- **«mi chiamo …»** — si ricorda il tuo nome e ti saluta per nome la volta dopo
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
- Librerie incluse: Three.js r147 (`three.min.js`) + `gltf-loader.js` — nessun download necessario.
- Onestà tecnica: il fotorealismo da film non è ottenibile in tempo reale nel browser; lo stile è «realistico da videogioco», leggero e fluido ovunque.
