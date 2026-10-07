# gioco — Profilo MAIKBARRE (stile hacker 3D)

Pagina profilo in stile hacker/cyberpunk con grafica 3D in tempo reale (Three.js / WebGL).

## Cosa c'è dentro

- **Intro "breach"**: finta intrusione SSH con logo ASCII, barre di avanzamento,
  "ACCESSO NEGATO" → nuovo tentativo → **ACCESS GRANTED**. Al click lo schermo
  si spegne come un vecchio monitor CRT e la telecamera vola nello spazio (warp).
- **Pioggia Matrix** generata da uno shader su 2 livelli di profondità, che reagisce
  alla musica e al movimento del mouse.
- **Globo olografico 3D** con continenti a punti, archi di rete con pacchetti in
  viaggio, onde d'impatto, anello di scansione, satelliti e alone che pulsa con i bassi.
- **Cockpit 3D** (su schermi larghi): finestra profilo e terminale inclinate in 3D
  ai lati del globo, con HUD centrale (FPS, uptime, oscilloscopio audio, radar, log di rete).
- **Terminale interattivo**: scrivi `help` per tutti i comandi. I più belli:
  `hack`, `matrix`, `theme rosso`, `trace`, `whoami`, `social`, `copy`, `sudo`.
  Funzionano TAB (completamento) e frecce ↑ ↓ (cronologia). Sul telefono ci sono
  i bottoni dei comandi.
- **4 temi colore**: verde, ciano, rosso, viola (`theme <nome>`); il tema scelto viene ricordato.
- Effetti sonori sintetizzati, cursore a mirino con scia binaria, glitch, testo che si decifra.
- Funziona su telefono e computer; se manca un file o il WebGL, la pagina continua a funzionare.

## File necessari (nella stessa cartella di `index.html`)

| File             | Stato                                   |
|------------------|-----------------------------------------|
| `profile.jpg`    | già incluso                             |
| `audio.mp3`      | **da caricare** (musica di sottofondo)  |
| `background.mp4` | **da caricare** (video di sfondo, viene colorato col tema) |

## Modificare i link

Apri `index.html` e cerca:

- `data-social="Instagram"`: metti il tuo link Instagram dentro `href=""`.
  Finché è vuoto, il bottone e il comando `instagram` dicono "in arrivo".
- TikTok e Discord sono già impostati (anche il terminale li legge da lì).

## Pubblicare online (GitHub Pages)

1. Su GitHub: **Settings → Pages**.
2. In "Build and deployment" scegli **Deploy from a branch**, branch `main`, cartella `/ (root)`.
3. Dopo un minuto la pagina è online su `https://<tuo-utente>.github.io/gioco/`.

Nota: l'analisi della musica in tempo reale funziona quando la pagina è online
(o su un server locale). Se apri il file direttamente dal computer, il ritmo viene simulato.
