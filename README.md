# guardia

Sala operativa radio self-hosted: **scanner SDR → squelch per canale → trascrizione vocale
→ mappa 3D nel browser**, anche dal telefono. Tutto in locale, niente servizi a pagamento,
niente chiavi API.

```bash
python guardia.py            # 1a volta: crea la venv e installa le dipendenze
python guardia.py            # poi: avvia (passa in demo se il dongle non risponde)
```

All'avvio stampa l'indirizzo con il token, per esempio `http://192.168.1.20:8080/?t=ab12cd34`.

## Modi

| comando | cosa fa |
|---|---|
| `python guardia.py` | radio reale; se il dongle manca ricade in demo |
| `--sim` | catena radio completa su un **dongle simulato**: prova tutto senza hardware |
| `--demo` | solo interfaccia, traffico finto |
| `--selftest` | 16 prove interne: DSP, squelch, database, API, WebSocket. Nessun hardware |
| `--check` | diagnostica: pacchetti, binari, dongle, sink audio |
| `--install` | (Linux) `apt`, sink PulseAudio, build di dsd-fme |
| `--service` | (Linux) scrive la unit systemd |

Opzioni principali: `--freqs 151175000:CC:digital,160900000:PL:analog`, `--gain 24`,
`--ppm 42`, `--squelch -45`, `--dwell 4`, `--model medium`, `--no-stt`, `--port 8081`,
`--basemap osm`, `--config CARTELLA`, `--log-file guardia.log`, `-v`, `-q`.
Tutto finisce in `guardia.json`, modificabile a mano; le variabili d'ambiente
`GUARDIA_PORT`, `GUARDIA_TOKEN`, `GUARDIA_CITY`… hanno la precedenza sul file, e la riga
di comando su tutto (ma non viene salvata).

## Come funziona

**Ricezione.** Un dongle non può stare su frequenze lontane, ma può stare su tutte quelle
che entrano nei suoi ~1.9 MHz di banda. I canali vengono raggruppati: ogni gruppo è
ascoltato **in parallelo** con un canalizzatore FFT (una FFT per blocco, N canali estratti,
overlap-save), i gruppi restanti a rotazione (`dwell`). Con i canali di default 4 frequenze
diventano 2 gruppi invece di 4 turni. Il DSP è solo numpy — niente scipy da installare.

**Squelch.** Il livello è misurato **dopo** il filtro di canale, non sulla banda larga, e in
modo `auto` la soglia segue il rumore di fondo del singolo canale (`squelch_margin` dB
sopra), con calibrazione iniziale sul minimo e isteresi in chiusura. La stima sopravvive ai
cambi di turno. I canali che tacciono non vengono nemmeno demodulati: il livello costa una
IFFT, la demodulazione molto di più.

**Segmentazione.** Pre-roll di 0.3 s (non si perde la prima sillaba), chiusura dopo `hang`
secondi di silenzio, taglio a `max_seg`, scarto sotto `min_voice`. Il guadagno di
normalizzazione è **uno per tratta**, quindi niente pumping.

**Trascrizione.** faster-whisper in italiano, con confidenza ricavata da `avg_logprob`. Le
righe nascono `pending` e diventano `done` / `empty` / `error` / `nostt`: le tratte in
sospeso vengono riprese al riavvio e, se whisper non c'è, l'audio resta comunque
ascoltabile.

**Mappa.** Base scura disegnata sulle tile **vettoriali** di OpenFreeMap (nessuna API key,
strade su tre livelli con bordo, acqua, verde, ferrovie, etichette, edifici estrusi). Se
non risponde entro qualche secondo entra da sola una base OSM scurita; con `--basemap osm`
o un tuo template raster si usa direttamente quella. Il primo toponimo riconosciuto nel
parlato (`via`, `piazza`, `lungotevere`…) viene geocodificato su Nominatim con cache su
database, cache dei "buchi" e rate-limit globale di 1 richiesta al secondo.

**Modo `digital`.** L'audio demodulato va in UDP a `127.0.0.1:7355` e si registra il sink
PulseAudio `dsd_out`: serve dsd-fme in ascolto (`--install`). Se manca, il canale viene
trattato come analogico e il log lo dice; un canale digitale per volta.

## L'interfaccia

- **Mezzi 3D** con lampeggiante, alone a terra e targhetta che li segue. La dimensione è
  costante sullo schermo (~11 px): a mappa larga non spariscono, a mappa stretta tornano a
  misura reale. Chi sta trasmettendo in questo momento pulsa in verde.
- **Scie** degli ultimi passaggi e **anello** che si espande su ogni chiamata nuova.
- **Unità in onda**: un clic insegue l'unità con la telecamera, un altro la libera.
- **Livelli canali**: segnale, rumore di fondo e soglia di ogni canale, dal vivo. È il
  cruscotto che serve per regolare squelch e guadagno senza indovinare.
- **Dati**: chiamate per ora e per unità nelle ultime 24 ore, spazio occupato.
- **Impostazioni**: squelch, tempi, parole d'allarme e conservazione si cambiano mentre il
  programma gira, con effetto immediato e salvataggio automatico.
- **Registro** con ricerca nel parlato e nei luoghi, filtro per unità, solo-avvisi,
  caricamento progressivo scorrendo ed esportazione CSV. Un clic vola sul punto e riproduce
  l'audio.
- **Parole d'allarme**: la riga si accende e, se le attivi, arriva una notifica di sistema.
- **AUTO** inquadra da sola le chiamate nuove, ma sta ferma 25 secondi dopo che hai mosso tu
  la mappa. Scorciatoie: `/` cerca, `L` livelli, `D` dati, `spazio` riascolta l'ultima,
  `Esc` chiude.
- Installabile dal telefono (PWA), e funziona anche se il WebSocket è bloccato: ricade sul
  polling da sola.

## API

Tutto richiede il token (`?t=`, cookie, `X-Token:` o `Authorization: Bearer`).

| percorso | cosa dà |
|---|---|
| `GET /api/state` | unità, aeromobili, livelli dei canali |
| `GET /api/events` | registro, con `limit`, `since_id`, `before`, `unit`, `q` |
| `GET /api/stats?ore=24` | conteggi per unità e per ora, spazio su disco |
| `GET /api/audio/{id}` | il WAV della tratta |
| `GET /api/export.csv?ore=168` | registro in CSV |
| `GET` / `POST /api/settings` | le impostazioni modificabili dal vivo |
| `GET /health` | stato del processo, radio, trascrizione, database |
| `WS /ws` | push di `event`, `capture`, `levels`, `state`, `settings` |

## Architettura

`guardia.py` è solo l'avvio; il codice sta nel pacchetto accanto, un modulo per
responsabilità:

```
guardia/
  config.py   percorsi, default, caricamento, validazione      bus.py     eventi → interfaccia
  bootstrap.py venv, dipendenze, diagnostica (solo stdlib)      web.py     API, WebSocket, pagina
  db.py       schema, migrazioni, query di dominio             app.py     avvio e ciclo di vita
  dsp.py      canalizzatore FFT, squelch, scrittura WAV        selftest.py 16 prove
  sources.py  dongle reale e dongle simulato                   geo.py     toponimi e geocodifica
  radio.py    sintonia, gate per canale, registrazione         stt.py     trascrizione
  adsb.py     elicotteri nelle vicinanze                       demo.py    traffico finto
  maintenance.py  pulizia di disco e database
  ui/         index.html, css/, js/ (sei moduli ES)
```

## Note

- Dati e audio restano in locale: `guardia.db`, `audio/`, cancellati dopo
  `retention_hours` **e** quando l'audio supera `max_audio_mb` (su scheda SD è quello che
  conta). `--config CARTELLA` li sposta altrove.
- L'interfaccia richiede il token, ha header di sicurezza e CSP, non espone percorsi del
  filesystem e frena i tentativi a forza bruta.
- **Windows + SDR reale**: servono due cose distinte, il driver
  ([Zadig](https://zadig.akeo.ie) → *Options > List All Devices* → `Bulk-In, Interface (0)`
  → WinUSB) e la libreria (`librtlsdr.dll` e `libusb-1.0.dll` da
  [rtl-sdr-blog](https://github.com/rtlsdrblog/rtl-sdr-blog/releases), copiate accanto a
  `guardia.py`). `--check` dice cosa manca.
- **La porta è occupata?** Probabilmente un'altra istanza è ancora aperta: il programma lo
  dice invece di dare un errore di rete.
- Ascolto e registrazione di comunicazioni radio sono regolati dalla legge locale: usalo
  sulle frequenze che ti è consentito ricevere.
