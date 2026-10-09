# Ghostlink

App per il telefono in stile hacker futuristico (ispirata all'interfaccia di Watch Dogs). È una **PWA**: si installa sulla schermata Home come un'app normale, si apre a schermo intero e funziona anche offline. Va bene sia su Android sia su iPhone.

## Cosa fa

| Modulo | Funzione |
| --- | --- |
| **Profiler** (home) | Dà un codice al tuo telefono, mostra sistema, browser, schermo e quanto sei riconoscibile online. Ha un registro di sistema in tempo reale (batteria, rete, connessione persa o ritrovata). |
| **Scanner** | Ti mostra tutto quello che un sito può leggere dal tuo telefono senza chiedere niente: impronta digitale, processore, RAM, scheda grafica, rete, IP pubblico, zona e operatore, permessi concessi. |
| **Cifratore** | Cifra un messaggio con una chiave segreta (AES-256). Lo mandi su WhatsApp o Telegram e solo chi ha Ghostlink e la stessa chiave può leggerlo. |
| **Password** | Genera password casuali o frasi di parole italiane e analizza le tue: quanto sono forti e quanto tempo servirebbe per craccarle. |
| **Sensori** | Bussola, coordinate GPS con velocità e altitudine, livella a bolla e rilevatore di scossoni. |
| **Fonometro** | Misura il rumore in decibel con il microfono e mostra lo spettro delle frequenze. |
| **Torcia** | Accende il LED posteriore (Android con Chrome) oppure lo schermo. Ha le modalità fissa, strobo e SOS, e può trasmettere qualsiasi messaggio in codice Morse. |

Tutto avviene sul telefono: l'unica richiesta a internet è quella per scoprire l'IP pubblico nello Scanner.

## Metterla online (una volta sola)

1. Su GitHub apri il repository **gioco** e vai in **Settings → Pages**.
2. In **Build and deployment → Source** scegli **Deploy from a branch**.
3. Scegli il branch dove si trova l'app (per esempio `main` dopo il merge) e la cartella **/ (root)**, poi premi **Save**.
4. Dopo un minuto circa l'app è online su `https://maikbarre2401-svg.github.io/gioco/`.

## Installarla sul telefono

- **Android (Chrome):** apri il link e premi il pulsante **Installa l'app sul telefono** in fondo alla home, oppure menu ⋮ → **Installa app**.
- **iPhone (Safari):** apri il link, tocca **Condividi** e poi **Aggiungi alla schermata Home**.

Tenendo premuta l'icona su Android compaiono le scorciatoie per Cifratore, Torcia e Scanner.

## Provarla sul computer

Serve un piccolo server locale, perché i moduli JavaScript e il service worker non funzionano aprendo il file direttamente:

```bash
python3 -m http.server 8000
# poi apri http://localhost:8000
```

Sensori, microfono e torcia funzionano solo su `https` o su `localhost`.

## Struttura

```
index.html            tutte le schermate
css/style.css         grafica
js/app.js             avvio, navigazione, profiler, registro
js/device.js          lettura delle informazioni del dispositivo
js/scan.js            Scanner
js/cipher.js          Cifratore (AES-GCM + PBKDF2)
js/password.js        Password
js/sensors.js         Sensori
js/audio.js           Fonometro
js/torch.js           Torcia e Morse
js/ui.js              funzioni comuni
sw.js                 funzionamento offline
manifest.webmanifest  dati per l'installazione
icons/                icone dell'app
```
