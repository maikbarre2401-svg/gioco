# gioco — CommGuard AI Builder

`commguard_builder.py` genera un progetto Android completo (CommGuard AI v3.7)
e, se sono presenti JDK 17 + Android SDK, ne compila direttamente l'APK.

## Uso

```bash
python3 commguard_builder.py
```

Il progetto viene creato in `~/Desktop/commguard_v37`. Senza Android SDK il
progetto resta pronto da aprire in Android Studio (Run) o da compilare con
`./gradlew assembleDebug`.

## Novita v3.7

- Splash screen animato con logo e firma "creator maikgost".
- Nessun login: onboarding saltabile, funziona anche senza Groq API key
  (analisi euristica offline).
- Bugfix f-string in `title()` (girava male su Python < 3.12).
- Mantenuti agente vocale, agente SMS, UI dettaglio, trascrizioni, filtro email IMAP.
