# Ghostlink

App per il telefono in stile hacker futuristico (ispirata all'interfaccia di Watch Dogs). Esiste in due forme:

- **APK Android**: un'app vera da installare sul telefono (cartella `android/`).
- **PWA**: la stessa app aperta dal browser e aggiunta alla schermata Home, anche su iPhone.

## Installare l'APK su Android

1. Scarica `apk/ghostlink.apk` da questo repository, oppure l'ultima versione dalla pagina **Releases** (release "ultima-versione").
2. Aprilo dal telefono. Se Android lo chiede, consenti l'installazione da questa fonte (Impostazioni → App → Accesso speciale → Installa app sconosciute).
3. Premi **Installa**. Play Protect può mostrare un avviso perché l'app non viene dal Play Store: scegli **Installa comunque**.

Nell'APK la torcia usa il LED vero, la vibrazione e la condivisione sono quelle di Android, e tutto funziona offline.

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

## Progetto Android

```
android/
  app/build.gradle                   versione, SDK, firma
  app/src/main/AndroidManifest.xml   permessi (posizione, microfono, vibrazione)
  app/src/main/java/.../MainActivity.java
                                     WebView a schermo intero, permessi, torcia LED,
                                     vibrazione, appunti e condivisione
  app/src/main/res/                  icone, nome, colori, tema
  keystore/ghostlink.jks             chiave di firma di sviluppo
```

Il codice web (index.html, css, js…) resta nella cartella principale: Gradle lo copia dentro l'APK a ogni compilazione, quindi basta modificarlo una volta sola.

- **Android Studio:** apri la cartella `android/` e premi Run, oppure *Build → Build APK(s)*.
- **Da terminale:** `cd android && ./gradlew assembleRelease` → `android/app/build/outputs/apk/release/app-release.apk`.
- **GitHub Actions:** a ogni push che tocca l'app, il workflow *APK Android* ricompila l'APK e lo pubblica nella release "ultima-versione".

Prima di pubblicare una nuova versione aumenta `versionCode` in `android/app/build.gradle`.

La chiave in `android/keystore/` è nel repository per far sì che ogni compilazione si installi sopra la precedente. Chi ha accesso al repository può firmare APK con la stessa chiave: per pubblicare sul Play Store crea una chiave privata e non metterla nel repository.

## Metterla online come PWA (una volta sola)

1. Su GitHub apri il repository **gioco** e vai in **Settings → Pages**.
2. In **Build and deployment → Source** scegli **Deploy from a branch**.
3. Scegli il branch dove si trova l'app (per esempio `main` dopo il merge) e la cartella **/ (root)**, poi premi **Save**.
4. Dopo un minuto circa l'app è online su `https://maikbarre2401-svg.github.io/gioco/`.

## Installarla sul telefono

- **Android (Chrome):** apri il link e premi il pulsante **Installa l'app sul telefono** in fondo alla home, oppure menu ⋮ → **Installa app**.
- **iPhone (Safari):** apri il link, tocca **Condividi** e poi **Aggiungi alla schermata Home**.

Tenendo premuta l'icona su Android compaiono le scorciatoie per Cifratore, Torcia e Scanner.

## Provarla sul computer

Serve un piccolo server locale, perché il service worker e i sensori non funzionano aprendo il file direttamente:

```bash
python3 -m http.server 8000
# poi apri http://localhost:8000
```

Sensori, microfono e torcia funzionano solo su `https` o su `localhost`.

## Struttura

```
index.html            tutte le schermate
css/style.css         grafica
css/fonts.css         font
js/app.js             avvio, navigazione, profiler, registro
js/device.js          lettura delle informazioni del dispositivo
js/scan.js            Scanner
js/cipher.js          Cifratore (AES-GCM + PBKDF2)
js/password.js        Password
js/sensors.js         Sensori
js/audio.js           Fonometro
js/torch.js           Torcia e Morse
js/ui.js              funzioni comuni e ponte verso Android
fonts/                font inclusi (SIL Open Font License)
sw.js                 funzionamento offline
manifest.webmanifest  dati per l'installazione
icons/                icone dell'app
android/              progetto Android (APK)
apk/ghostlink.apk     APK pronto da installare
```
