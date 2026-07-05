# ◈ ORION // SPY OSINT CINEMA PRO — created by MAIKGOST

Un **simulatore d'intelligence dall'estetica cinematografica** (interfaccia
in stile film di spionaggio) scritto in Python + Tkinter.

> ## ⚠️ È UN GIOCO / SIMULAZIONE
> Questo programma **non esegue nessuna ricerca reale**, **non si connette a
> internet** e **non raccoglie dati su nessuna persona**.
> Tutti i dati mostrati — nomi, foto, email, profili social, "identità
> multiple", metriche — sono **generati in modo casuale e deterministico** a
> partire dal testo digitato, esclusivamente a scopo di intrattenimento e
> dimostrazione di interfaccia. I "ritratti" sono silhouette astratte generate
> dal codice: **non sono persone reali**.

## ✨ Funzionalità

**🎬 Splash d'avvio (video)**
- All'apertura parte uno **splash a schermo intero**: se imposti un **tuo
  video** viene riprodotto (a schermo intero, OpenCV) con in sovrimpressione
  **CREATED BY MAIKGOST**, l'HUD ORION e il banner SIMULAZIONE.
- Il video si sceglie in **⚙ Impostazioni → VIDEO D'AVVIO** (bottone
  *Sfoglia…*), oppure basta mettere un file **`intro.mp4`** nella cartella del
  programma (auto-rilevato). Formati: mp4/mov/avi/mkv/webm/m4v.
- Se non c'è nessun video (o manca OpenCV) parte un **emblema ORION animato**
  (matrix + boot-log, niente teschio). Click / **⎵** per entrare.
- Il video richiede `opencv-python` (in `requirements.txt`). *Nota:* la
  riproduzione via OpenCV è **senza audio**.

**🌍 Mappa 3D Mapbox REALE**
- Nella scheda **🗺 MAPPA** il bottone *"APRI MAPPA 3D MAPBOX"* apre nel
  browser un **globo 3D** (Mapbox GL JS v3) con **terreno**, atmosfera, e i
  **marker** delle identità su **coordinate reali**, con tour cinematografico
  automatico e popup.
- Richiede **il tuo token Mapbox** (`pk.…`): si imposta in ⚙ Impostazioni
  o nella variabile d'ambiente `MAPBOX_TOKEN`. Il token resta **locale**
  (non finisce su GitHub). La mappa canvas interna usa comunque le
  coordinate reali proiettate.

**Cinematic Gallery**
- **Intro a schermo intero non bloccante e regolabile** (Corta/Media/Lunga):
  pioggia "matrix", particelle, radar rotante, titolo con *glitch*, scrittura
  a macchina, boot-log, chiusura a serranda. **Spazio/Invio** = salta,
  **Esc** = esci.
- **Ritratti "da sorveglianza" procedurali** (Pillow): silhouette con capelli
  e *rim light*, grana CRT, *scanline*, vignettatura, cornice HUD, ID camera,
  coordinate GPS, mini-barcode, barra **REDACTED**, glitch, timbro `MATCH %` e
  watermark **MAIKGOST**.
- **Griglia stile Netflix** con *hover* luminoso e schede cliccabili.
- **Riconoscimento facciale animato** nella vista di dettaglio.
- **🎞 Slideshow** a schermo intero con **crossfade**, comandi play/pausa
  (⎵), avanti/indietro (← →) e velocità regolabile (+/−).

**⚙ Impostazioni** (pannello dedicato, salvate in `orion_settings.json`)
- **Intro**: salta intro oppure velocità **Corta / Media / Lunga**
  (~1.9 / 3.2 / 4.8 s).
- **Slideshow**: secondi per foto (1.5–8 s).
- **Grafica**: animazioni di sfondo on/off, barra **REDACTED** on/off, suono.
- **Colore accento**: Ciano / Verde / Magenta / Ambra (cambia HUD, mirini,
  grafici, ritratti…).

**Strumenti (pannello 🧰)**
- **📄 Esporta dossier** in `.txt` e `.json`.
- **📋 Copia sommario** negli appunti.
- **🎲 Target casuale** e **🔁 Rigenera** (ignora la cache).

**Schede intelligence**
- 📊 Intelligence con **radar/spider chart** delle metriche e KPI a tile.
- 👥 Social · 🕵 Identità multiple · 🕐 **Timeline eventi**.
- 🕸 **Rete**: grafo relazioni animato (target ▸ identità ▸ entità).
- 🗺 **Mappa**: ping geolocalizzati animati con archi tra le posizioni.
- 🌐 Footprint · 📈 Comportamento.

**Sotto il cofano**
- **Firma del creatore `MAIKGOST` presente ovunque** (titolo, logo, intro,
  ritratti, report, console, gallery).
- **Dati deterministici**: lo stesso nome produce sempre lo stesso dossier.
- Logo con *glow*, palette coerente, orologio live, banner di simulazione
  sempre visibile.
- Animazioni via `after()` (niente `time.sleep` sul thread grafico),
  animatori canvas interrompibili, gestione errori robusta.
- **Poche dipendenze**: solo **Pillow** (rimossi `opencv`, `pygame`,
  `requests`, `bs4`).

## 🚀 Avvio

```bash
pip install -r requirements.txt
python spy_osint_cinema.py
```

Requisiti: Python 3.8+, `tkinter` (incluso in Python), `Pillow`.

## 🎮 Come si usa

1. Scrivi un nome nel campo **NOME BERSAGLIO** (o usa i bersagli rapidi /
   🎲 casuale).
2. Premi **▶ AVVIA SCANSIONE OSINT**: si popolano tutte le schede (radar,
   rete, mappa, timeline, ecc.).
3. Premi **💀 GALLERY** per l'intro cinematica e la galleria per identità,
   oppure **🎞 SLIDESHOW** per la presentazione automatica.
4. Clicca una scheda foto per il dettaglio con la scansione facciale.
5. **📄 Esporta** o **📋 Copia** il dossier quando vuoi.

---
*created by **MAIKGOST** · progetto dimostrativo/gioco.*
