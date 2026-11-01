# guardia

Sala operativa radio self-hosted in **un solo file** (`guardia.py`): scanner SDR →
squelch per canale → trascrizione vocale → mappa 3D nel browser, anche dal telefono.

```bash
python guardia.py            # 1a volta: crea la venv e installa le dipendenze
python guardia.py            # poi: avvia (passa in demo se il dongle non risponde)
```

All'avvio stampa l'indirizzo con il token, es. `http://192.168.1.20:8080/?t=ab12cd34`.

## Modi

| comando | cosa fa |
|---|---|
| `python guardia.py` | radio reale; se il dongle manca ricade in demo |
| `--sim` | catena radio completa su un **dongle simulato** (prova tutto senza hardware) |
| `--demo` | solo interfaccia, traffico finto |
| `--selftest` | test interni: DSP, squelch, regex, DB, API. Nessun hardware |
| `--check` | diagnostica: pacchetti, binari, dongle, sink audio |
| `--install` | (Linux) `apt`, sink PulseAudio, build di dsd-fme |
| `--service` | (Linux) scrive la unit systemd |

Opzioni utili: `--freqs 151175000:CC:digital,160900000:PL:analog`, `--gain 24`, `--ppm 42`,
`--squelch -45` (soglia fissa in dBFS), `--dwell 4`, `--model medium`, `--no-stt`, `-v`.
Tutto finisce in `guardia.json` e da lì si può modificare a mano.

## Come funziona

**Ricezione.** Un dongle non può stare su frequenze lontane, ma può stare su tutte quelle
che entrano nei suoi ~1.9 MHz di banda. I canali vengono quindi raggruppati: ogni gruppo è
ascoltato **in parallelo** con un canalizzatore FFT (una FFT per blocco, N canali estratti,
overlap-save), i gruppi restanti a rotazione (`dwell`). Con i canali di default 4 frequenze
diventano 2 gruppi invece di 4 turni.

**Squelch.** Il livello è misurato **dopo** il filtro di canale, non sulla banda larga, e in
modo `auto` la soglia segue il rumore di fondo del singolo canale (`squelch_margin` dB sopra),
con calibrazione iniziale sul minimo e isteresi in chiusura. La stima sopravvive ai cambi di
turno. In `manual` si usa `squelch` in dBFS.

**Segmentazione.** Pre-roll di 0.3 s (non si perde la prima sillaba), chiusura dopo `hang`
secondi di silenzio, taglio a `max_seg`, scarto delle tratte sotto `min_voice`. Il guadagno
di normalizzazione è **uno per tratta**, quindi niente pumping.

**Trascrizione.** faster-whisper in italiano, con confidenza ricavata da `avg_logprob`. Le
righe nascono `pending` e diventano `done` / `empty` / `error` / `nostt`: le tratte in sospeso
vengono riprese al riavvio e se whisper non c'è l'audio resta comunque ascoltabile.

**Mappa.** La base è uno stile scuro disegnato sulle tile **vettoriali** di OpenFreeMap:
nessuna API key, stesso fornitore degli edifici 3D. (Le raster di CARTO oggi rispondono con
tile "API KEY REQUIRED".) Se OpenFreeMap non risponde entro qualche secondo entra da sola una
base OSM scurita. Con `--basemap osm`, o `basemap` in `guardia.json` impostato a un tuo
template raster (`https://.../{z}/{x}/{y}.png`), si usa direttamente quella.

Il primo toponimo riconosciuto (`via`, `piazza`, `lungotevere`, …) viene geocodificato
su Nominatim con cache su DB, cache dei "buchi" (TTL 6 h) e rate-limit globale di 1 req/s.
Le unità sono modelli 3D (Three.js su MapLibre, fallback a marker 2D), gli elicotteri arrivano
da ADS-B.

**Modo `digital`.** L'audio demodulato va in UDP a `127.0.0.1:7355` e si registra il sink
PulseAudio `dsd_out`: serve dsd-fme in ascolto (`--install`). Se manca, il canale viene
trattato come analogico e il log lo dice; un canale digitale per volta.

## Note

- Dati e audio restano in locale: `guardia.db`, `audio/`, cancellati dopo `retention_hours`.
- L'interfaccia richiede il token (cookie o `?t=`), header di sicurezza e CSP attivi, e le API
  non espongono path del filesystem.
- Windows + SDR reale: serve [Zadig](https://zadig.akeo.ie) per mettere WinUSB sul dongle.
- Ascolto e registrazione di comunicazioni radio sono regolati dalla legge locale: usalo sulle
  frequenze che ti è consentito ricevere.
