# Ghostlink

App per il telefono in stile hacker futuristico (ispirata all'interfaccia di Watch Dogs). All'avvio c'è un'intro animata con hacker incappucciato, pioggia di dati, suoni e voce; al primo avvio scegli il tuo nome in codice e sali di livello usando gli strumenti. Esiste in due forme:

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
| **Agente** (home) | Il tuo nome in codice, livello ed esperienza (XP). Usando gli strumenti sali di grado, da "Script kiddie" a "Leggenda della rete". Accanto c'è un hacker animato che reagisce e parla. |
| **Mappa ctOS** | Mappa scura della tua zona con telecamere, semafori, antenne, hotspot Wi-Fi, defibrillatori e colonnine di ricarica **reali**, presi da OpenStreetMap. Tocca un oggetto per analizzarne i dati pubblici con un'animazione da hacking. |
| **Profiler AR** | Fotocamera con mirino ctOS: inquadra e "scansiona" per generare un profilo (nome, età, lavoro, curiosità). I profili sono **inventati**, come nel gioco: nessun dato reale sulle persone. |
| **Scanner** | Impronta digitale del telefono, dispositivo, rete, IP pubblico, zona e operatore, permessi concessi. |
| **Velocità** | Test reale della connessione (ping, jitter, download, upload) con tachimetro animato, sui server Cloudflare. |
| **Terminale** | Riga di comando con comandi veri e scherzosi: `ip`, `ping`, `hash`, `base64`, `bin`, `morse`, `matrix`, `hack`, e altri. |
| **Cifratore** | Messaggi cifrati AES-256 da mandare in chat: solo chi ha la stessa chiave può leggerli. |
| **Password** | Genera password forti o frasi di parole italiane e analizza quanto resistono. |
| **Sensori** | Bussola, GPS, livella a bolla e rilevatore di scossoni. |
| **Fonometro** | Livello del suono in decibel e spettro delle frequenze. |
| **Torcia** | LED o schermo, con luce fissa, strobo, SOS e messaggi in Morse. |
| **Impostazioni** | Nome in codice, effetti sonori, voce, vibrazione, tipo di intro e la tua carriera. |

I suoni e la musica dell'intro sono creati dall'app al momento (sintetizzati), non sono presi dal videogioco. Le uniche richieste a internet sono la mappa, la ricerca dell'IP e il test di velocità.

## Progetto Android

```
android/
  app/build.gradle                   versione, SDK, firma
  app/src/main/AndroidManifest.xml   permessi (posizione, fotocamera, microfono, vibrazione)
  app/src/main/java/.../MainActivity.java
                                     WebView a schermo intero, permessi, torcia LED,
                                     vibrazione, voce (TextToSpeech), appunti e condivisione
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
js/app.js             avvio, navigazione, agente, livelli
js/intro.js           intro animata (hacker, pioggia di dati, voce)
js/hacker.js          hacker incappucciato animato su canvas
js/sfx.js             suoni sintetizzati e voce
js/prefs.js           nome in codice, impostazioni, esperienza
js/map.js             Mappa ctOS (Leaflet + OpenStreetMap)
js/profiler.js        Profiler AR (fotocamera)
js/speed.js           test di velocità
js/terminal.js        terminale
js/settings.js        impostazioni
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
vendor/leaflet/       libreria della mappa (BSD)
android/              progetto Android (APK)
apk/ghostlink.apk     APK pronto da installare
```
