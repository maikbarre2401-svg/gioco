# OJO DE DEUS v92 — Global Intelligence Monitor

Dashboard OSINT a pagina singola (`index.html`, nessuna build necessaria): globo 3D Mapbox,
tracciamento voli ADS-B live, navi AIS, terremoti USGS, ISS, meteo spaziale NOAA, mercati,
crypto, feed RSS, TV in diretta e simulazione di conflitti WAR4D.

## Uso
Apri `index.html` in un browser moderno (Chrome/Edge/Firefox). Serve una connessione internet
per i dati live e le mappe.

## Impostazioni & API keys
Clicca **⚙ SETTINGS** in alto a destra (o premi `S`). Le chiavi sono salvate solo nel tuo
browser (localStorage) e non vengono mai inviate a server esterni.

- **Mapbox token** (gratis, consigliato) — globo satellitare 3D con terreno. Crea il token su
  [mapbox.com](https://account.mapbox.com/access-tokens/) (inizia con `pk.`). Senza token viene
  usato un token demo con qualità limitata.
- **NASA FIRMS** (opzionale) — incendi attivi ad alta risoluzione.
- **AISHub** (opzionale) — posizioni navi AIS reali; senza chiave viene usata una simulazione realistica.
- **Finnhub** (opzionale) — prezzi azionari live.

## Novità v92
- **Mappa satellitare gratis di default**: senza token Mapbox l'app parte in modalità MAPS (satellite ESRI, nessuna chiave) così **aerei ADS-B, navi AIS e la simulazione WAR4D sono subito visibili**. Col token Mapbox si passa al globo 3D.
- **Aerei reali** via ADS-B (adsb.lol → adsb.fi → OpenSky) disegnati sia sul globo 3D sia sulla mappa 2D.
- **WAR4D** (fronte, missili, droni, tank) ora renderizzato anche sulla mappa 2D, non solo sul globo.
- **Live TV via HLS** (`.m3u8` in un player video nativo con hls.js e fallback proxy CORS) — molto più affidabile degli embed.
- **Webcam** città via layer webcam di Windy (iframe affidabile).
- **Street View nel pannello**: clic sulla mappa → 🚶 Street View a 360° dentro l'app (richiede una Google Maps Embed API key, gratuita, in Impostazioni). Niente più redirect a Google Earth.
- Pannello **Impostazioni** con gestione API keys (Mapbox, NASA FIRMS, AISHub, Finnhub, Google), qualità grafica e sistema.
- **Terminatore Giorno/Notte 4D**: ombra notturna reale calcolata dalla posizione del sole, con marcatore subsolare.
- Rotazione automatica del globo, esagerazione terreno regolabile, scelta stile mappa, toggle effetti (atmosfera, scanline, cursore).
- Mercati e feed instradati tramite proxy CORS selezionabile per maggiore affidabilità.

## Scorciatoie
`1/2/3` modalità mappa · `W` WAR4D · `A` ADS-B · `T` voce (TTS) · `S` impostazioni · `L` layer · `/` terminale · `ESC` chiudi.
