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

**Cinematic Gallery**
- **Intro a schermo intero non bloccante e più corta (~2.6 s)**: pioggia
  "matrix", particelle, radar rotante, titolo con *glitch*, scrittura a
  macchina, boot-log, chiusura a serranda. **Spazio/Invio** = salta,
  **Esc** = esci.
- **Ritratti "da sorveglianza" procedurali** (Pillow): silhouette con capelli
  e *rim light*, grana CRT, *scanline*, vignettatura, cornice HUD, ID camera,
  coordinate GPS, mini-barcode, barra **REDACTED**, glitch, timbro `MATCH %` e
  watermark **MAIKGOST**.
- **Griglia stile Netflix** con *hover* luminoso e schede cliccabili.
- **Riconoscimento facciale animato** nella vista di dettaglio.
- **🎞 Slideshow** automatico a schermo intero (← → per navigare).

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
