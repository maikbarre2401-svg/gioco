# gioco — Profilo MAIKBARRE 3D

Pagina profilo in stile cyberpunk con scena 3D in tempo reale (Three.js / WebGL).

## Cosa c'è dentro

- **Schermata di avvio** con log di sistema animato e "CLICK TO ENTER".
- **Effetto warp**: entrando, la camera vola nello spazio tra le stelle.
- **Scena 3D**: nucleo energetico che si deforma a ritmo di musica, gusci wireframe,
  anello galattico, forme fluttuanti e pavimento a griglia synthwave.
- **Card olografica 3D**: si inclina seguendo il mouse (o il giroscopio sul telefono),
  con strati a profondità diverse, bordo al neon animato e riflesso olografico.
- **Avatar** con orbite 3D, alone che pulsa con i bassi ed effetto glitch.
- **Player audio** con play/pausa, volume ed equalizzatore in tempo reale.
- Copia dello username Discord con un click, cursore personalizzato, effetto ripple.
- Funziona su telefono e computer; se un file manca la pagina continua a funzionare.

## File necessari (nella stessa cartella di `index.html`)

| File             | Stato                                   |
|------------------|-----------------------------------------|
| `profile.jpg`    | già incluso                             |
| `audio.mp3`      | **da caricare** (musica di sottofondo)  |
| `background.mp4` | **da caricare** (video di sfondo)       |

## Modificare i link

Apri `index.html` e cerca:

- `data-social="Instagram"`: metti il tuo link Instagram dentro `href=""`.
  Finché è vuoto, il bottone mostra "Link Instagram in arrivo!".
- TikTok e Discord sono già impostati.

## Pubblicare online (GitHub Pages)

1. Su GitHub: **Settings → Pages**.
2. In "Build and deployment" scegli **Deploy from a branch**, branch `main`, cartella `/ (root)`.
3. Dopo un minuto la pagina è online su `https://<tuo-utente>.github.io/gioco/`.

Nota: l'analisi della musica in tempo reale funziona quando la pagina è online
(o su un server locale). Se apri il file direttamente dal computer, il ritmo viene simulato.
