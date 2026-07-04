# ◈ ORION // SPY OSINT CINEMA PRO

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

## ✨ Novità di questa versione

- **Cinematic Gallery** completamente rifatta:
  - **Intro a schermo intero non bloccante** (30 fps): pioggia "matrix",
    campo di particelle, radar rotante, titolo con effetto *glitch*,
    scrittura a macchina, boot-log tecnico e chiusura a serranda.
    Premi **Spazio/Invio** per saltare, **Esc** per uscire.
  - **Ritratti "da sorveglianza" procedurali** (Pillow): silhouette con
    capelli e *rim light*, grana CRT, *scanline*, vignettatura, cornice HUD,
    ID camera, timestamp e timbro `MATCH %`.
  - **Griglia stile Netflix** con effetto *hover* luminoso e schede cliccabili.
  - **Animazione di riconoscimento facciale** nella vista di dettaglio
    (linea di scansione + box di *lock* + esito `IDENTITY MATCH`).
- **Dati deterministici**: lo stesso nome produce sempre lo stesso dossier.
- **UI ridisegnata**: palette coerente, orologio live, titolo animato,
  metriche a schede, console colorate a tag, banner di simulazione sempre
  visibile.
- **Meno dipendenze**: rimossi `opencv`, `pygame`, `requests`, `bs4`
  (non necessari). Serve solo **Pillow**.
- Codice riorganizzato in moduli logici, animazioni tramite `after()`
  (niente `time.sleep` sul thread grafico), gestione errori robusta.

## 🚀 Avvio

```bash
pip install -r requirements.txt
python spy_osint_cinema.py
```

Requisiti: Python 3.8+, `tkinter` (incluso in Python), `Pillow`.

## 🎮 Come si usa

1. Scrivi un nome nel campo **NOME BERSAGLIO** (o usa i bersagli rapidi).
2. Premi **▶ AVVIA SCANSIONE OSINT**: la barra di progresso "raccoglie"
   il dossier simulato e popola le schede (Intelligence, Social, Identità,
   Footprint, Comportamento).
3. Premi **💀 LANCIA CINEMATIC GALLERY** per l'intro a schermo intero e la
   galleria di ritratti per identità.
4. Clicca una scheda foto per la vista di dettaglio con la scansione facciale.
