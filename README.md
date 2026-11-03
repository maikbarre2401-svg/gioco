# OJO DE DEUS v100 · Global Intelligence Monitor 3D

Monitor di intelligence globale in un'unica pagina web, con **globo 3D vero** (CesiumJS) e **solo dati pubblici reali**, etichettati onestamente.

**Apri `index.html`** (è un file unico, autonomo). Consigliato servirlo via http(s), per esempio con GitHub Pages o con:

```bash
python3 -m http.server 8000
```

e poi vai su `http://localhost:8000`. Aperto come file locale (`file://`) funziona quasi tutto, ma i video YouTube possono mostrare “Errore 153” perché YouTube richiede un'origine web.

---

## Cosa fa

### Globo 3D reale
- **CesiumJS**: globo WGS84, modalità 3D / 2.5D / 2D, rotazione automatica, vista orbitale.
- **Terreno 3D gratuito** (tile Terrarium di AWS Open Data, decodificati al volo) con esagerazione del rilievo regolabile; con un token Cesium ion: terreno mondiale HD.
- **Sole reale**: illuminazione giorno/notte calcolata sull'ora esatta, atmosfera, e **luci notturne delle città NASA** che compaiono solo sul lato in ombra.
- Basi cartografiche: satellite Esri, **immagini NASA di ieri** (VIIRS/MODIS), scura, topografica, OpenStreetMap, luci notturne. Le varianti NASA vengono verificate all'avvio: si usa solo quella che risponde davvero.
- **Visori**: NVG (visore notturno), FLIR (termico), CRT (contorni tattici): shader GPU veri, non filtri finti.
- Con token Cesium ion (gratuito): **edifici 3D OSM** e **città fotorealistiche 3D**.

### Dati live (tutti reali)
| Layer | Fonte |
|---|---|
| ✈ Aerei ADS-B alla **quota reale**, con stima della posizione tra un aggiornamento e l'altro | adsb.lol, airplanes.live, adsb.fi (area inquadrata + militari globali), OpenSky (globale, con quota giornaliera rispettata) |
| 🛰 Satelliti **in orbita** propagati con SGP4 ogni secondo (ISS, Tiangong, GPS, Galileo, GLONASS, meteo, militari, Starlink…), orbita, impronta, passaggi sopra di te | CelesTrak + satellite.js |
| 🌍 Terremoti come colonne 3D proporzionali alla magnitudo, impulsi sugli eventi forti | USGS |
| 🌋 Eventi naturali aperti (incendi, vulcani, tempeste, alluvioni…) | NASA EONET |
| 🔥 Punti di incendio satellitari (con chiave gratuita) | NASA FIRMS |
| 🌌 Ovale dell'aurora in 3D a 110 km di quota, Kp, vento solare, IMF, brillamenti | NOAA SWPC |
| 🌧 Radar pioggia | RainViewer |
| 📰 Notizie da 12 fonti RSS + GDELT, **geolocalizzate automaticamente** sul globo | BBC, Al Jazeera, ANSA, RaiNews, DW, Guardian, France 24, NYT, NPR, Sky, Defense News, Times of Israel |
| 📈 Indici, materie prime, titoli difesa, crypto, valute | Yahoo Finance/Stooq, CoinGecko/Binance, BCE (Frankfurter) |
| 🌦 Meteo, qualità dell'aria, quota, luogo | Open-Meteo, BigDataCloud |

### Intelligenza (trasparente, a regole)
- **Indice OJO** 0-100 → livello di allerta 1-5 (calcolato, **non** ufficiale, non è DEFCON): zone calde + emergenze in volo + meteo spaziale + grandi sismi. La formula è mostrata nel briefing.
- **Zone calde** (Ucraina, Israele/Gaza, Libano/Siria, Iran, Yemen/Mar Rosso, Sudan, Taiwan, Corea del Nord, Baltico, Sahel) con punteggio live = base storica + notizie reali + attività militare ADS-B nell'area, e **dossier** per ciascuna.
- **Rilevamento anomalie**: squawk 7500/7600/7700, aerei ISR/rifornitori/droni vicino alle zone calde, concentrazioni di aerei militari, terremoti forti o con allerta tsunami, tempeste geomagnetiche, brillamenti di classe X, notizie urgenti. Con voce italiana opzionale.
- **Briefing automatico** in italiano, leggibile ad alta voce.
- **Analisi di un punto** (clic sul globo): luogo, quota, meteo, aria, ora locale, sole, luna, zone in cui ricade, aerei/sismi/notizie vicini.

### Strumenti
- Pannello bersaglio per ogni oggetto: **segui**, **cockpit** (vista dal muso dell'aereo), rotta e foto dell'aereo, orbita e passaggi del satellite.
- **Ricerca universale** (`/`): luoghi, voli, satelliti, basi, coordinate, comandi.
- Terminale con comandi (`help`), TV live dai canali ufficiali (la diretta *attuale*, non ID che scadono), webcam e canali **modificabili**, Windy centrato sulla vista, IP/DNS GeoTrace con arco sul globo.
- Pannello **📊 Stato feed**: per ogni fonte dice se è LIVE, in errore o in attesa, da dove arriva (diretta o proxy) e con che latenza.
- Mappa 2D di riserva (Leaflet) automatica se il computer non ha WebGL. Layout responsive per telefono.

## Onestà dei dati
`LIVE` dato reale · `CALC` calcolato da dati reali · `REF` riferimento statico pubblico · `STIMA` area indicativa · `KEY` richiede chiave.
Se una fonte non risponde, l'app lo dice: **nessun dato viene inventato**. Molti voli militari non trasmettono ADS-B: l'assenza di un aereo non significa assenza di attività.

## Chiavi opzionali (salvate solo nel tuo browser)
- **Cesium ion token** — <https://ion.cesium.com/signup> → terreno HD, edifici 3D, città fotorealistiche, Bing Aerial.
- **NASA FIRMS map key** — <https://firms.modaps.eosdis.nasa.gov/api/map_key/> → punti di incendio.
- **Proxy CORS personale** — molte fonti (RSS, Yahoo, adsb.lol) non permettono la lettura diretta dal browser. L'app usa proxy pubblici gratuiti, che però sono lenti o a volte giù. Per avere tutto affidabile, pubblica in 5 minuti [`proxy/cloudflare-worker.js`](proxy/cloudflare-worker.js) (piano gratuito Cloudflare) e incolla l'indirizzo in ⚙ Impostazioni. Il Worker inoltra solo verso gli host usati da OJO.

## Scorciatoie
`/` ricerca · `1` `2` `3` 3D/2.5D/2D · `L` layer · `S` stato feed · `B` briefing · `T` voce · `F` mappa intera · `H` orbita · `R` rotazione · `G` la mia posizione · `V` visore · `A` aerei · `Esc` chiudi/smetti di seguire · `?` aiuto

## Cosa è stato corretto rispetto alla v92
- L'avvio partiva da solo dopo 400 ms: era impossibile inserire il token. Ora si avvia quando premi il pulsante (avvio automatico attivabile nelle impostazioni).
- La casella del token e il pulsante di avvio non avevano stile (gli ID nel CSS non corrispondevano).
- La chiave FIRMS veniva chiesta ma mai usata; i layer “Incendi” e “War Sim” erano nel menu ma non esistevano.
- Gli endpoint ADS-B `/v2/all` non fanno parte delle API pubbliche documentate di adsb.lol/adsb.fi: ora si usano area inquadrata + `/v2/mil`, con più fonti di riserva.
- Coordinate sbagliate: la centrale di **Zaporizhzhia** era vicino a Donetsk (ora 47,51 N 34,59 E), la base di **Hmeimim** era vicino a Sochi, **Ramstein** e **Camp Lemonnier** erano spostate di decine di km.
- I pulsanti NRM/NVG/THERM non facevano nulla; i filtri notizie 🇬🇧/🇫🇷/📡 non filtravano; i pulsanti Windy “vento” e “onde” non erano definiti.
- La scheda paese e il lettore TV grande non si aprivano mai (stile `display:none` mai rimosso); “Modifica ID” non era collegato; il pannello di stato era vuoto.
- Testo a 5-7 px illeggibile; varie classi CSS usate ma mai definite; contenuti esterni inseriti con `innerHTML` (rischio XSS): ora tutto il testo esterno è inserito in modo sicuro.
- Il “DEFCON” era manuale e senza significato: sostituito dall'indice OJO calcolato e spiegato.

## Struttura e sviluppo
```
index.html            ← file unico generato (aprilo nel browser)
src/index.html        ← struttura della pagina
src/css/ojo.css       ← stile
src/js/00-core.js     ← utility, rete con proxy adattivi, stato feed, voce, suoni, geodesia
src/js/10-data.js     ← dati di riferimento (basi, siti nucleari, gazetteer, canali)
src/js/20-globe3d.js  ← motore 3D Cesium (terreno, sole, aerei, satelliti, shader)
src/js/25-map2d.js    ← mappa 2D di riserva + gestione layer
src/js/30-feeds.js    ← tutti i feed di dati reali
src/js/40-intel.js    ← indice, zone calde, anomalie, briefing
src/js/50-ui.js       ← interfaccia, pannelli, ricerca, terminale, avvio
proxy/cloudflare-worker.js ← proxy CORS personale opzionale
tests/                ← test end-to-end (Chromium headless + API simulate)
```
Dopo aver modificato i file in `src/`:
```bash
node build.mjs
```
Test (scarica Cesium, Leaflet, satellite.js e Playwright in `tests/node_modules`):
```bash
cd tests && npm install && npx playwright install chromium && npm run test:all
```
I test avviano l'app in Chromium con WebGL software, simulano tutte le API (anche fonti senza CORS, per verificare i proxy di riserva) e controllano feed, pannelli, picking 3D, cockpit, visori, layer, terminale, ricerca, modali, versione 2D e mobile.
