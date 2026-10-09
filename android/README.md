# Maik Subs per Android (cartella `android/`)

Progetto Android normale (Java + Gradle) che contiene l'app **Maik Subs** già compilata. Si crea l'APK con un doppio clic.

## Crearlo subito su Windows

1. Installa **Python 3** da https://www.python.org/downloads/ (spunta **"Add python.exe to PATH"**).
2. Apri la cartella `android` e fai doppio clic su **`crea_apk.bat`**.
3. Aspetta. La prima volta scarica da solo Java 17, Android SDK e Gradle (circa 1 GB, solo la prima volta) e ci mette 5-10 minuti. Le volte dopo basta 1 minuto.
4. Alla fine trovi **`MaikSubs.apk`** nella cartella principale del progetto.
5. Copialo sul telefono (cavo, Drive, WhatsApp a te stesso…) e aprilo. Android ti chiede di permettere l'installazione da questa fonte.

Hai il telefono collegato via USB con il debug USB attivo? Allora usa **`installa_sul_telefono.bat`**: crea l'APK e lo installa direttamente.

Su macOS o Linux: `python3 android/crea_apk.py`

### Senza creare niente

A ogni modifica GitHub crea l'APK da solo e lo mette nella pagina **Releases** del repository, con il tag `maik-subs`. Puoi scaricarlo direttamente dal telefono.

## Com'è fatta

| File | A cosa serve |
| --- | --- |
| `app/src/main/assets/www/` | L'app già compilata (Expo / React Native Web) |
| `MainActivity.java` | Mostra l'app a schermo intero, gestisce il tasto indietro, apre i link nel browser, importa ed esporta i backup |
| `LocalWeb.java` | Serve i file dell'app dall'APK: funziona offline |
| `Reminders.java` | **Notifiche vere** di Android (AlarmManager): arrivano anche ad app chiusa |
| `BootReceiver.java` | Rimette in fila i promemoria dopo un riavvio del telefono |
| `res/` | Icona adattiva con il logo Maik, schermata di avvio, icona delle notifiche |
| `crea_apk.py` / `crea_apk.bat` | Scaricano gli strumenti e creano l'APK |

L'app web e Android parlano tramite `window.MaikAndroid` (vedi `src/lib/android-bridge.ts`):

- **Promemoria**: ogni volta che cambi un abbonamento, l'app manda ad Android la lista aggiornata, per esempio "Netflix si rinnova tra 3 giorni · 13,99 €" alle 9:00. Android li programma; toccando la notifica si apre quell'abbonamento.
- **Esporta backup / CSV**: si apre la finestra "Salva con nome" di Android.
- **Importa backup**: scegli il file `.json`.
- **Condividi riepilogo**: si apre la condivisione di Android (WhatsApp, Telegram…).
- **Vibrazione leggera** ai tocchi, e barre di sistema colorate come il tema chiaro o scuro.

I dati restano sul telefono, nello spazio privato dell'app.

## Se modifichi l'app (cartella `src/`)

Serve Node.js. Ricompila l'app e poi l'APK:

```
crea_apk.bat --web
```

Oppure a mano: `npm install`, `npm run build:android`, poi `crea_apk.bat`.

## Note

- Il Premium qui è in **modalità demo** (si attiva gratis). Per i pagamenti veri su Google Play serve la build nativa di Expo con RevenueCat: vedi `docs/PUBBLICAZIONE.md`.
- `targetSdk` è 34: va benissimo per installare l'APK a mano. Per pubblicare su Google Play porta `compileSdk` e `targetSdk` al valore minimo richiesto da Google in quel momento.
- Ogni APK di debug ha una firma diversa sul PC e su GitHub. Se Android dice "app non installata", disinstalla prima la vecchia versione (perdi i dati: fai prima un backup dal Profilo). Oppure configura una firma fissa con i segreti `MAIK_KEYSTORE` e `MAIK_KEYSTORE_PASSWORD`.
