# Zeph per Android 📱

Zeph — o **il tuo avatar** — vive sullo schermo del telefono, sopra tutte le app, come su desktop.

- **Cammina** lungo il fondo dello schermo, si guarda intorno, ti saluta, balla e salta.
- **Toccalo**: reagisce. **Tienilo premuto**: si apre la chat (scrivi o parla col microfono).
  **Trascinalo**: lo sollevi, e se lo lasci cade giù.
- **Notifica fissa** con 🎤 Parla, 🙈 Nascondi / 👁 Mostra e ✖ Chiudi.
- **Resta acceso** anche se chiudi l'app, e **si riaccende** quando riaccendi il telefono
  (se era acceso; si può disattivare).
- **Parla con la voce del telefono** e **capisce la tua voce** (riconoscimento vocale di Google).
- **Apre le app vere**: «apri whatsapp», «apri impostazioni wifi / bluetooth / audio / schermo»,
  «apri fotocamera», «apri calcolatrice», «apri spotify»… Poi «alza il volume», «quanta batteria ho?»,
  «ricordami tra 10 minuti della pasta» (con notifica), «manda messaggio arrivo tra poco».
- **Il tuo avatar**: nell'app premi «Scegli il mio avatar (.glb)». Con gli avatar Avaturn usa anche
  i movimenti in motion capture e muove la bocca quando parla.
- Opzioni: grandezza (piccolo / medio / grande), **modalità fantasma** (i tocchi passano attraverso),
  esclusione dal risparmio batteria.
- **Controlla il telefono**: «accendi la torcia», «svegliami alle 7 e mezza» e «timer di 10 minuti»
  (veri, nell'app Orologio), «chiama 333 1234567» (apre il telefono col numero, la chiamata la fai tu),
  «pausa», «play», «prossima canzone» (comanda Spotify, YouTube Music…).
- **Meteo vero** di qualsiasi città: «che tempo fa a Roma», «che tempo farà domani a Milano»;
  dì «la mia città è …» e poi basta «che tempo fa?».
- **Scrivigli dalla notifica** (💬 Scrivi, anche dettando col microfono della tastiera) e aggiungi il
  pulsante **«Zeph» nelle Impostazioni rapide** per accenderlo e spegnerlo al volo.
- **Condividi → «Leggi con Zeph»** da qualsiasi app: ti legge ad alta voce messaggi, articoli, note.
- **Reagisce al telefono**: quando colleghi il caricatore, quando la batteria è scarica, quando metti le cuffie.
- **Di notte si addormenta** (seduto, con lo «Zzz…») se lo lasci tranquillo; toccalo per svegliarlo.
  Toccalo tre volte di fila: soffre il solletico!

## Il modo più facile: scarica l'APK già pronto

A ogni modifica GitHub crea l'APK da solo. Dal telefono apri:

**https://github.com/maikbarre2401-svg/gioco/releases/tag/android**

scarica `Zeph.apk` e aprilo. Android ti chiede di permettere l'installazione da questa fonte: dì di sì.

## Crearlo tu con `crea_apk.py`

Serve solo [Python 3](https://www.python.org/downloads/). Tutto il resto (Java 17, Android SDK,
Gradle) lo scarica lo script la prima volta in `android/.strumenti` (circa 1 GB, una volta sola).

```bash
cd android
python crea_apk.py                       # Zeph.apk con Zeph
python crea_apk.py --avatar avatar.glb   # Zeph.apk con il TUO avatar già dentro
python crea_apk.py --installa            # e lo installa sul telefono collegato via USB
```

Su Windows basta un doppio clic su **`crea_apk.bat`**, oppure trascinaci sopra il tuo `avatar.glb`.
Il file finito è `Zeph.apk` nella cartella principale del progetto.

## Primo avvio sul telefono

1. Apri l'app **Zeph**.
2. «Permetti di apparire sopra le altre app» → attiva Zeph nella lista.
3. «Permetti le notifiche» e «Non farlo mai chiudere dal risparmio batteria».
4. «▶ Metti Zeph sullo schermo». Ora puoi chiudere l'app: Zeph resta lì.

Su alcuni telefoni (Xiaomi, Huawei, Oppo…) c'è anche un'impostazione del produttore per
l'«avvio automatico»: attivala per Zeph se vuoi che si riaccenda da solo dopo il riavvio.

## Note tecniche

- Servizio in primo piano (`specialUse`) con finestra `TYPE_APPLICATION_OVERLAY` grande quanto il
  personaggio: per camminare, saltare o volare si sposta la finestra, i tocchi altrove passano alle app sotto.
- Il personaggio è disegnato da una WebView trasparente con `android/web/overlay.js` e lo stesso
  `zeph-core.js` del browser; i file vengono serviti in locale come `https://zeph.local/…`
  (niente esce dal telefono). Voce: `TextToSpeech` di Android; fumetto: finestra nativa sopra la testa.
- Le azioni sul telefono sono in una lista chiusa (`PhoneActions.java`): solo app, impostazioni e
  siti noti, niente comandi arbitrari.
- APK di debug firmato con una chiave di debug: se passi da un APK creato su GitHub a uno creato sul
  tuo PC (o viceversa), disinstalla prima quello vecchio.
