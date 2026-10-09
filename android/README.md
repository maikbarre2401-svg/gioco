# Zeph per Android 📱

*creator **MaikGost***

All'apertura c'è la schermata d'avvio animata (logo, «ZEPH» e «creator MaikGost»), poi l'app; in alto
compare un pulsante viola quando su GitHub c'è una versione nuova.

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
- **📸 Avatar dalla foto**: nell'app «Crea l'avatar con una foto» (o di' «crea il mio avatar con una foto»):
  selfie con la fotocamera frontale, colori veri e la tua faccia sulla sua testa, che parla con te.
  Per un avatar 3D realistico c'è il pulsante per il sito Avaturn: poi scegli il `.glb` che scarichi.
- **Dagli un nome**: «ti chiamerò Leo» oppure dall'app; anche la notifica e il riquadro usano il nuovo nome.
- **Un amico che si ricorda di te**: raccontagli la giornata, i programmi («domani ho un esame»), cosa ti
  piace, le persone a cui vuoi bene. Il giorno dopo ti chiede com'è andata; «cosa sai di me?»,
  «cosa ti ho detto ieri?». Tutto resta sul telefono; «dimentica tutto» per cancellare.
- **🎙 Conversazione a voce mani libere**: «Parla con…» nell'app o «parliamo a voce»; ascolta, risponde e
  riascolta da solo (serve il permesso del microfono, usato solo mentre la finestra è aperta).
- **⚡ Poteri del telefono** (sezione nuova nell'app, tutti facoltativi):
  promemoria veri anche tra giorni («ricordami domani alle 9 di…», suonano anche a Zeph spento e dopo un
  riavvio), «chiama mia sorella» / «scrivi a Giulia che arrivo» (rubrica), «chi mi ha scritto?» e
  «rispondi: …» con conferma (accesso alle notifiche), «che impegni ho oggi?» e «aggiungi al calendario…»
  (agenda), il buongiorno quando sblocchi il telefono la mattina, «chi era…?» con Wikipedia, «traduci…»,
  «cosa vedi?» con la fotocamera e il cervello AI, «modalità ologramma», scuoti il telefono e arriva.
  Su Android 13+ l'accesso alle notifiche per un'app installata da file può risultare grigio: Impostazioni →
  App → Zeph → ⋮ → «Consenti impostazioni con limitazioni», poi riattivalo.
- **💾 Backup della memoria**: «Salva backup» / «Ripristina backup» nell'app (la chiave AI non viene salvata).
- **🧠 Cervello AI facoltativo**: nell'app incolla la tua chiave di Claude (console.anthropic.com, a
  consumo e a tuo carico: circa uno o due centesimi di dollaro a messaggio) e chiacchiera davvero di tutto. Senza chiave usa il cervello offline gratuito.

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
- Rete: la WebView può raggiungere solo Open-Meteo (meteo) e, se hai messo la chiave, `api.anthropic.com`
  (`LocalWeb.java`). La chiave sta in `SharedPreferences` a parte, esclusa da backup e trasferimenti
  (`res/xml/backup_rules.xml`, `data_extraction_rules.xml`), e non viene mai scritta nella pagina.
- Permessi facoltativi: `READ_CONTACTS` e `READ_CALENDAR` (sola lettura), accesso alle notifiche
  (`MessageListener`, solo app di chat; i messaggi non vengono salvati), `USE_EXACT_ALARM` per i promemoria.
  Zeph non chiama e non manda nulla da solo: la chiamata e l'invio li fai tu; l'unica eccezione è
  «rispondi: …», che parte solo dopo che hai detto «sì».
- Aggiornamenti: ogni APK di GitHub ha un numero di versione più alto. Per installarlo sopra il vecchio
  senza disinstallare serve la stessa firma: se aggiungi nei segreti del repository `ZEPH_KEYSTORE`
  (un keystore in base64 con alias `zeph`) e `ZEPH_KEYSTORE_PASSWORD`, la compilazione la usa sempre.
  Senza, prima di installare una nuova versione fai «Salva backup», disinstalla e poi «Ripristina backup».
- Avatar dalla foto: `PhotoActivity` apre `foto.html`; la fotocamera viene concessa solo a quella pagina
  e solo per il video. Il look (colori + faccia ritagliata in JPEG) è salvato in `files/look.json`.
- APK di debug firmato con una chiave di debug: se passi da un APK creato su GitHub a uno creato sul
  tuo PC (o viceversa), disinstalla prima quello vecchio.
