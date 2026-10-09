# ORION // SPY OSINT CINEMA PRO — by MAIKGOST

Gioco / demo d'interfaccia in stile "film di spionaggio": scrivi un nome e ORION
"costruisce" un dossier con identità, social, mappa, grafo delle relazioni,
timeline e galleria foto.

> ⚠️ **SIMULAZIONE.** Nessuna ricerca reale: tutti i dati sono generati a caso
> (in modo deterministico) dal testo digitato. I ritratti sono silhouette
> generate dal codice oppure volti creati da IA: **non sono persone reali**.

![Schermata INTELLIGENCE](docs/02_intelligence.jpg)

## Avvio

```bash
pip install Pillow            # obbligatorio
pip install opencv-python     # opzionale: video d'avvio personalizzato
python gf.py
```

Requisiti: Python 3.8+ con tkinter (incluso nell'installer ufficiale di Windows).

## Cosa c'è

- **Interfaccia HUD futuristica**: pulsanti neon con riflesso animato, pannelli
  olografici, schede con indicatore che scorre, notifiche animate, barra di stato
  con notiziario scorrevole, intestazione con equalizzatore e indicatori live.
- **Dossier**: anello di rischio, livello di minaccia luminoso, contatori animati,
  radar con fascio rotante, briefing con effetto "macchina da scrivere".
- **Social / Identità**: card per ogni piattaforma e per ogni identità (con ritratto).
- **Rete**: grafo animato target → identità → entità, con pacchetti dati.
- **Mappa**: mondo a punti (Natural Earth), rotte animate, ping, mirino col mouse;
  in più la mappa 3D Mapbox nel browser (serve un token gratuito).
- **Timeline**: eventi in sequenza con nodi colorati per gravità.
- **Galleria**: intro olografica, card con hover, scheda di dettaglio con
  scansione facciale (mesh dei punti del viso), slideshow con transizioni glitch.
- **Effetti sonori** sintetizzati (nessun file da scaricare) e **impostazioni**
  con interruttori, colore accento, durata intro, video d'avvio.
- **Globo 3D** olografico nella scheda MAPPA: ruota da solo, si trascina col mouse,
  rotella per lo zoom, rotte animate tra le posizioni.
- **Missioni** (scheda MISSIONI): 12 casi con personaggi **di fantasia**. Una talpa
  si nasconde tra i sospetti: analizza le prove (costano energia), escludi gli
  innocenti e accusa il colpevole. Le prove cifrate si sbloccano col minigioco
  **Breach Protocol**. Punti esperienza, gradi da RECLUTA a DIRETTORE ORION e
  progressi salvati.
- **ORION-AI**: assistente di deduzione locale (regole, nessuna rete). Calcola i
  sospetti ancora compatibili, le probabilità e quale indizio conviene cercare.
- **Terminale** (scheda TERMINALE): comandi da film hacker (`help`, `scan <nome>`,
  `caso 3`, `prove`, `analizza 2`, `ai`, `accusa VIPER`, `tema viola`, `matrix`…),
  cronologia con ↑/↓, completamento con Tab, e domande libere a ORION-AI
  ("chi è il più pericoloso?", "chi sospetti?").
- **Tavolozza comandi** (Ctrl+K) per trovare e lanciare qualsiasi azione.

## Comandi rapidi

| Tasto | Azione |
|---|---|
| Invio | avvia la scansione |
| Esc | ferma la scansione / chiude le finestre |
| Ctrl+G | galleria |
| Ctrl+P | slideshow |
| Ctrl+E | esporta dossier (.txt + .json) |
| Ctrl+R | bersaglio casuale |
| F5 | rigenera (variante del dossier) |
| F11 | schermo intero |
| Ctrl+, | impostazioni |
| Ctrl+K | tavolozza comandi |
| Ctrl+M | missioni |
| Ctrl+T | terminale |

## Schermate

| | |
|---|---|
| ![Avvio](docs/01_avvio.jpg) | ![Social](docs/03_social.jpg) |
| ![Rete](docs/04_rete.jpg) | ![Mappa](docs/05_mappa.jpg) |
| ![Timeline](docs/06_timeline.jpg) | ![Intro galleria](docs/07_intro.jpg) |
| ![Galleria](docs/08_galleria.jpg) | ![Slideshow](docs/09_slideshow.jpg) |
| ![Missioni](docs/10_missioni.jpg) | ![Breach Protocol](docs/11_breach.jpg) |
| ![Terminale](docs/12_terminale.jpg) | ![Globo 3D](docs/13_globo3d.jpg) |
| ![Tavolozza comandi](docs/14_comandi.jpg) | |

## File creati dall'app

Accanto a `gf.py` vengono creati `orion_settings.json` (impostazioni, compreso
l'eventuale token Mapbox), `orion_cache.db` (cache dei dossier), `orion_agent.json`
(esperienza e casi completati) e la cartella `orion_faces/` (volti IA scaricati). Sono esclusi da git tramite `.gitignore`.

---
Creato da **MAIKGOST**.
