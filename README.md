# gioco — Zeph, il tuo compagno 3D 🕺

Zeph è un personaggio 3D a corpo intero con proporzioni realistiche che **cammina, salta, balla e ti parla a voce in italiano**, gesticolando mentre lo fa. Esiste in due versioni:

1. **🖥️ Sul desktop (stile Desktop Goose)** — cammina sul bordo dello schermo, sopra le tue finestre
2. **🌐 Nel browser** — nel suo prato 3D, basta un doppio clic

## 🖥️ Versione desktop — Zeph sullo schermo

Zeph passeggia lungo il bordo inferiore dello schermo in una striscia trasparente sempre in primo piano: i clic passano attraverso (non disturba il lavoro), ma se clicchi proprio su di lui reagisce e ti parla. Può anche **seguire il mouse** come un'ochetta.

**Come si avvia (Windows):**

1. Installa [Node.js](https://nodejs.org) (versione LTS, gratis) — serve solo la prima volta.
2. Scarica questo repository (**Code → Download ZIP**) ed estrailo.
3. Apri la cartella `desktop` e fai **doppio clic su `avvia.bat`**. La prima volta scarica i componenti (circa un minuto), poi Zeph appare sullo schermo.

Su macOS/Linux: `cd desktop && npm install && npm start`.

**Comandi:** clicca l'**icona di Zeph vicino all'orologio** (area di notifica) per il menu: 💬 Parla con Zeph (chat: lui risponde a voce), Saluta, Balla, Salta, Barzelletta, 🚶 Passeggia da solo, 🖱️ Segui il mouse, 🔊 Voce, ❌ Chiudi.

## 🌐 Versione browser

Fai **doppio clic su `index.html`** (Chrome o Edge consigliati per la voce). Non serve internet né installare nulla: Three.js è incluso.

| Azione | Come |
|---|---|
| 🚶 Camminare dove vuoi tu | Clicca un punto sul prato, oppure guidalo con **WASD / frecce** |
| 🗣️ Parlarti a voce | Scrivigli nella barra in basso: risponde con la voce italiana del browser |
| 👋 Salutare, 💃 ballare, 🦘 saltare | Pulsanti rapidi, oppure scriviglielo («balla!», «salta!») |
| 🌼 Passeggiare da solo | Attiva «Passeggia da solo» |
| 🎥 Visuale libera | Trascina per ruotare la camera, rotella/pizzico per lo zoom |

Prova a scrivergli: *ciao*, *come stai?*, *chi sei?*, *vieni qui*, *canta*, *barzelletta*, *fermati*, *seguimi*…

## Note tecniche

- `zeph-core.js` — il personaggio condiviso: costruito proceduralmente (niente modelli esterni), scheletro articolato (spalle, gomiti, anche, ginocchia, piedi, collo, occhi con iridi e palpebre), proporzioni umane realistiche (~7 teste).
- Animazioni procedurali: ciclo di camminata con appoggio del tallone, respiro, sbattito di palpebre, sguardo che vaga, gesti sincronizzati col parlato, bocca in sincrono con la voce.
- Voce tramite **Web Speech API** con voce italiana di sistema; se la voce non è disponibile resta il fumetto di testo.
- Versione desktop: **Electron** con finestra trasparente click-through sempre in primo piano (`setIgnoreMouseEvents` + hit-test sul personaggio), icona nell'area di notifica, chat in finestra separata.
- Un'onesta precisazione: il fotorealismo da film non è ottenibile in tempo reale con questa tecnica — lo stile è «realistico da videogioco», leggero abbastanza da girare fluido ovunque.
