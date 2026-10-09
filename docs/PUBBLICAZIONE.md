# Pubblicare Maik Subs su App Store e Google Play

## 1. Account

| | Costo | Link |
| --- | --- | --- |
| Apple Developer Program | 99 $ l'anno | https://developer.apple.com/programs/ |
| Google Play Console | 25 $ una tantum | https://play.google.com/console |
| Expo (EAS, build nel cloud) | gratis per iniziare | https://expo.dev/signup |
| RevenueCat | gratis fino a 2.500 $ di ricavi al mese | https://app.revenuecat.com |

Per costruire l'app per iPhone **non serve un Mac**: EAS fa la build nel cloud.

## 2. Identificativi

In `app.json` sono già impostati:

- iOS `bundleIdentifier`: `com.maik.subs`
- Android `package`: `com.maik.subs`

Se sono già occupati sugli store, cambiali (es. `com.tuonome.maiksubs`) **prima** della prima build.

```bash
npx eas-cli@latest login
npx eas-cli@latest init        # collega il progetto a Expo
```

## 3. Prodotti in-app

Crea gli stessi tre prodotti su entrambi gli store:

| Prodotto | Tipo | Prezzo suggerito |
| --- | --- | --- |
| `maik_premium_monthly` | abbonamento auto-rinnovabile, 1 mese | 2,99 € |
| `maik_premium_yearly` | abbonamento auto-rinnovabile, 1 anno | 19,99 € |
| `maik_premium_lifetime` | acquisto non consumabile | 49,99 € |

- **App Store Connect** → la tua app → Abbonamenti → crea un gruppo "Premium" con mensile e annuale; Acquisti in-app → crea il "lifetime".
- **Play Console** → Monetizza → Prodotti → Abbonamenti (mensile, annuale) e Prodotti in-app (lifetime).

## 4. RevenueCat

1. Crea un progetto e aggiungi un'app **App Store** e una **Play Store** (servono la chiave App Store Connect API e il service account di Google: RevenueCat spiega i passaggi).
2. **Entitlements** → crea `premium` (l'app usa esattamente questo nome) e collega i tre prodotti.
3. **Offerings** → `default` con tre pacchetti: `$rc_monthly`, `$rc_annual`, `$rc_lifetime`.
4. **API keys** → copia le chiavi pubbliche (`appl_…`, `goog_…`) in `.env` oppure come variabili d'ambiente EAS:

```bash
npx eas-cli@latest env:create --name EXPO_PUBLIC_REVENUECAT_IOS_KEY --value appl_xxx --environment production
npx eas-cli@latest env:create --name EXPO_PUBLIC_REVENUECAT_ANDROID_KEY --value goog_xxx --environment production
```

Il paywall legge automaticamente prezzi e valute dagli store; "Ripristina acquisti" è già presente (Apple lo richiede).

## 5. Build

```bash
# Prova interna su telefono (APK Android installabile direttamente)
npx eas-cli@latest build --profile preview --platform android

# Build per gli store
npx eas-cli@latest build --profile production --platform ios
npx eas-cli@latest build --profile production --platform android
```

## 6. Test

### Google Play: test chiuso obbligatorio

Con un **account personale creato dopo il 13 novembre 2023**, Google richiede un test chiuso con **almeno 12 tester iscritti per 14 giorni consecutivi** prima di poter chiedere l'accesso alla produzione.

1. Play Console → Test → Test chiuso → crea una traccia.
2. Carica l'AAB (`npx eas-cli@latest submit --platform android`).
3. Aggiungi i tester (lista di email Gmail o un Google Group) e manda loro il link di iscrizione.
4. Tieni almeno 12 tester iscritti per 14 giorni di fila. Chiedi di aprire l'app più volte e di lasciare feedback.
5. Dopo 14 giorni: Dashboard → "Richiedi accesso alla produzione" e rispondi al questionario.

Consiglio: recluta 15-20 persone (amici, famiglia, gruppi di "test reciproco" su Reddit o Telegram), perché qualcuno si disiscrive sempre.

### iPhone: TestFlight

```bash
npx eas-cli@latest submit --platform ios
```

In App Store Connect → TestFlight aggiungi tester interni (subito) o esterni (dopo una breve revisione).

## 7. Scheda dello store

- **Icona**: generata da `assets/brand/maik-icon.svg` (`assets/images/icon.png`, 1024×1024).
- **Screenshot**: servono almeno quelli per iPhone 6,9" (1320×2868) e per telefono Android. Fai gli screenshot dal simulatore o dal telefono dopo aver toccato "Carica dati di esempio" in Profilo → Dati.
- **Testi** in italiano e inglese: [SCHEDA_STORE.md](SCHEDA_STORE.md).
- **Informativa privacy**: pubblica [PRIVACY.md](PRIVACY.md) su una pagina web (GitHub Pages, Notion, Google Sites) e inserisci il link in entrambe le console.
- **Apple, Privacy dell'app**: "Dati non raccolti".
- **Google, Sicurezza dei dati**: nessun dato raccolto né condiviso; gli acquisti passano da Google Play.
- **Classificazione dei contenuti**: questionario, risulta "3+ / PEGI 3".
- **Categoria**: Finanza.

## 8. Revisione

- Apple: di solito 24-48 ore. Nelle note per il revisore spiega che l'app funziona offline e che il Premium si prova con un account sandbox.
- Google: da poche ore a 7 giorni.

## 9. Aggiornamenti

- Correzioni solo JavaScript: `npx eas-cli@latest update` (aggiornamento OTA, senza passare dalla revisione).
- Nuove librerie native o cambi in `app.json`: nuova build e nuova revisione.
