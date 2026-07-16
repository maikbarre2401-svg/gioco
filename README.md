# gioco — Zeph, il tuo compagno 3D 🕺

Un personaggio 3D a corpo intero che vive nel browser: **cammina, salta, balla e ti parla a voce** (in italiano), gesticolando mentre lo fa. Costruito con [Three.js](https://threejs.org/), tutto in un solo file: `index.html`.

## Come si avvia sul PC

1. Scarica il repository (pulsante verde **Code → Download ZIP**) oppure clonalo.
2. Fai **doppio clic su `index.html`**: si apre nel browser (Chrome o Edge consigliati per la voce).
3. Serve la connessione a internet (la pagina scarica la libreria Three.js).

In alternativa puoi pubblicarlo con GitHub Pages (Settings → Pages → branch) e aprirlo da qualsiasi dispositivo, anche dal telefono.

## Cosa sa fare Zeph

| Azione | Come |
|---|---|
| 🚶 Camminare dove vuoi tu | Clicca un punto sul prato, oppure guidalo con **WASD / frecce** |
| 🗣️ Parlarti a voce | Scrivigli nella barra in basso: risponde con la voce italiana del browser, muove la bocca e gesticola |
| 👋 Salutare, 💃 ballare, 🦘 saltare | Pulsanti rapidi, oppure scriviglielo («balla!», «salta!») |
| 😂 Raccontare barzellette | Chiedigli «raccontami una barzelletta» |
| 🌼 Passeggiare da solo | Attiva «Passeggia da solo»: esplora il prato e commenta |
| 🎥 Visuale libera | Trascina per ruotare la camera, rotella/pizzico per lo zoom |

Prova a scrivergli: *ciao*, *come stai?*, *chi sei?*, *vieni qui*, *canta*, *fermati*, *cosa sai fare?*…

## Note tecniche

- Personaggio costruito proceduralmente (niente modelli esterni): scheletro articolato con spalle, gomiti, anche, ginocchia, piedi, testa e occhi animati.
- Animazioni procedurali: ciclo di camminata, respiro, sbattito di palpebre, sguardo che vaga, gesti sincronizzati col parlato, bocca in sincrono con la voce.
- Voce tramite **Web Speech API** (`speechSynthesis`) con voce italiana; se la voce non è disponibile compare comunque il fumetto di testo.
- Nessuna dipendenza oltre a Three.js (r150, caricato da CDN).
