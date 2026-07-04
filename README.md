# gioco — Deepfake Ultra Pro 7.2 🎭

Face-swap in tempo reale (webcam **o file video**) basato su **insightface** +
`inswapper_128.onnx`, con interfaccia Tkinter. Versione ottimizzata: **più
veloce**, **più realistica** e **più potente**, con pannello di regolazioni live.

> ⚠️ **Uso responsabile.** Usa solo volti per cui hai il consenso. Non creare
> contenuti ingannevoli, diffamatori o che ledano le persone. Molti paesi
> regolano l'uso dei deepfake: sei responsabile di come usi questo strumento.

## ⚠️ Cosa questo strumento NON può fare (leggi prima)

`inswapper_128` è un modello con due limiti **fisici**, che nessuna impostazione
elimina:

1. **Non scambia i capelli / la testa.** Sostituisce solo il **volto interno**
   (sopracciglia→mento). Capelli, attaccatura, orecchie e forma della testa
   restano di chi è ripreso. Lo swap di capelli/testa richiede un'altra classe
   di modelli (full-head / reenactment), molto più pesanti e **non real-time**.
2. **Lavora a 128×128.** Quando muovi la lingua o parli, la bocca si "impasta"
   e sembra un'altra faccia. Si mitiga con **Keep mouth** (mostra la tua bocca
   reale) e con l'**enhancer GFPGAN** (più dettaglio), ma non si azzera.

Ciò che la 7.0 aggiunge lavora *entro* questi limiti — è lo stesso approccio dei
tool open-source "seri" (es. FaceFusion).

## Novità della 7.0 (realismo del volto)

- **Maschera precisa dai landmark 2D-106**: la maschera segue la vera forma di
  mascella e mento invece di un'ellisse fissa → bordi più naturali, meno
  effetto "faccia incollata" (toggle *Precise mask*).
- **Keep mouth** (slider): lascia trasparire la **bocca reale**. Alzalo quando
  parli / muovi la lingua → l'espressione torna naturale. Default 0.30.
- **Stabilize** (slider): anti-jitter temporale. Leviga bbox/landmark tra frame
  (con tracking multi-volto) → lo swap smette di "tremolare", che è uno dei
  segnali che tradiscono il fake. Nei test riduce il tremolìo del ~77%.
- **Preset rapidi**: pulsanti **🗣 Talking / 💎 Quality / ⚡ Speed** che tarano
  tutti gli slider in un colpo.

### Fix realismo (sopracciglia/fronte + scatti)

- **Forehead** (nuovo slider): con *precise mask* i landmark si fermano alle
  sopracciglia, quindi **fronte e sopracciglia** restavano dell'originale e si
  vedeva lo stacco. Ora la maschera si **estende verso la fronte** seguendo
  l'inclinazione della testa → niente più bordo sulle sopracciglia. Default 0.30
  (alza fino a ~0.45 se hai la fronte alta/scoperta).
- **Coasting anti-scatto**: quando il detector "salta" un frame, prima lo swap
  si spegneva per un istante → effetto "a trattini". Ora la posizione viene
  **tenuta per qualche frame** (config `coast_frames`), così il volto non
  sfarfalla. Se combinato con **Stabilize** il movimento diventa fluido.
- **Enhancer sul crop (GPU)**: l'enhancer ora lavora solo sul ritaglio del volto
  (upscale 512 → restore → blend), non su tutto il frame. Su **RTX 4070** gira
  in tempo reale e dà il dettaglio vero a denti/pelle/bocca. Il modello si
  scarica da solo al primo click.
- **Occlusion** (nuovo slider): dove nell'area del volto **non c'è pelle**
  (ciuffi di capelli, occhiali, un microfono, oggetti scuri che ci passano
  davanti) lo swap si ritira e mostra l'immagine reale → niente più faccia
  "spalmata" sopra le cose. Basato su rilevamento pelle YCrCb. *Limite:* le mani
  sono color pelle, quindi non vengono protette. Default 0 (attivo nei preset
  Talking/Quality).

## Novità della 6.0

**Più impostazioni (regolabili dal vivo)**
- Slider: **soglia swap, dimensione maschera, feather, color-match, sharpen,
  skin-smooth**.
- **Det_size** selezionabile (256/320/512/640), applicato a caldo.
- Toggle: blend realistico, multi-face, mirror, enhancer, bbox, FPS + colore box.

**Più realismo**
- Blending ellittico con feather regolabile + color transfer LAB regolabile.
- **Skin-smooth** (bilateral) e **sharpen** (unsharp) sulla faccia sostituita.
- **Enhancer opzionale GFPGAN** (se installato) per volti ad alta fedeltà.

**Più potenza**
- **Multi-face**: sostituisce *tutti* i volti sopra soglia, non solo il migliore.
- Input da **file video** oltre alla webcam (playback in loop).
- **Snapshot** (PNG) e **registrazione** (MP4) dell'output, in `output/`.

## Base (dalla 5.0)
- **Auto-selezione provider ONNX** (CUDA/CoreML/DirectML/CPU): usa la GPU quando
  c'è → il guadagno più grande.
- **Detector "detection-only"** per il live (salta recognition/landmark/genderage).
- **Un solo thread di inferenza** (niente più N thread che si contendono il lock).
- Cache `id(frame)` rotta rimossa; in FAST si rileva 1 frame su N.

## Requisiti

```bash
pip install -r requirements.txt
```

### Setup GPU NVIDIA (RTX 4070) — consigliato
1. Installa CUDA 12.x + cuDNN 9.x.
2. `requirements.txt` usa già `onnxruntime-gpu`.
3. Verifica: `python -c "import onnxruntime as o; print(o.get_available_providers())"`
   deve elencare `CUDAExecutionProvider`. All'avvio lo status mostra
   **`✅ Ready · CUDA (GPU)`**.
4. Per l'enhancer: `pip install gfpgan` + torch/torchvision build CUDA
   (`--index-url https://download.pytorch.org/whl/cu121`).

Con la 4070 puoi tenere **Quality (det 512) + Enhancer + Stabilize** e restare
fluido.

## Modello

Scarica `inswapper_128.onnx` dalle release di insightface e mettilo nella
stessa cartella dello script:

- https://github.com/deepinsight/insightface/releases

Al primo avvio insightface scarica automaticamente il pacchetto detector
`buffalo_l`.

## Avvio

```bash
python deepfake_ultra_pro.py
```

1. Attendi `✅ Ready` (mostra anche il provider attivo, es. CUDA/CPU).
2. **LOAD FACE IMAGE** → foto frontale nitida del volto sorgente.
3. **SWAP ON** (o barra spaziatrice).

### Scorciatoie
| Tasto | Azione |
|-------|--------|
| `Spazio` | Attiva/disattiva swap |
| `m` | Multi-face on/off |
| `s` | Snapshot (PNG) |
| `v` | Avvia/ferma registrazione |
| `f` | Schermo intero |
| `r` | Reinizializza camera |
| `Esc` | Esci |

### Modalità
- **FAST** — risoluzione ridotta + detect ogni 2 frame → massimi FPS.
- **BALANCED** — compromesso predefinito.
- **QUALITY** — risoluzione maggiore, detect ogni frame.

### Enhancer GFPGAN (opzionale, alta fedeltà)
`pip install gfpgan` e metti `GFPGANv1.4.pth` nella cartella dello script, poi
attiva il toggle **Enhancer GFPGAN**. Migliora molto la qualità dei volti ma è
**lento**: usalo su GPU o per registrare/esportare, non per il massimo dei FPS.

## Ricetta per il massimo realismo (RTX 4070)
Scorciatoia: premi **💎 Quality** (o **🗣 Talking**) e sei quasi a posto. A mano:
1. **Precise mask** ON + **Forehead** 0.30–0.45 → copre bene fronte e sopracciglia.
2. **Feather** ~0.08 → bordi morbidi che seguono la mascella.
3. **Keep mouth** 0.3–0.6 → parlato e lingua naturali (usa la tua bocca reale).
4. **Stabilize** 0.4–0.6 → togli il tremolìo/gli scatti (fondamentale nei video).
5. **Color match** 0.8–1.0 → l'illuminazione combacia con la scena.
6. **Skin smooth** 0.2–0.4 + **Sharpen** 0.2 → pelle uniforme ma nitida.
7. **Enhancer** ON → denti/pelle/bocca ad alta fedeltà (sulla 4070 è real-time).
8. **Occlusion** 0.4–0.6 → capelli/occhiali/oggetti davanti al viso non vengono
   coperti dallo swap.
9. Foto sorgente **frontale, nitida, ben illuminata**, sfondo semplice.

Se vedi ancora lo stacco sulle sopracciglia → alza **Forehead**. Se scatta →
alza **Stabilize** e usa **det 512** in modalità Quality. Se un ciuffo/occhiali
vengono "spalmati" dallo swap → alza **Occlusion**.

### Se vuoi VERAMENTE anche i capelli
Serve un'altra pipeline (non questo modello): approcci full-head / reenactment
o hair-transfer. Sono pesanti, richiedono GPU e in genere non girano in
real-time. Se ti interessa, dimmelo e ti indico la direzione.

## Suggerimenti performance
- Su GPU installa `onnxruntime-gpu`: è la differenza più grande.
- CPU debole → modalità **FAST** e det_size `256`.
- L'enhancer GFPGAN è **lento**: tienilo per registrazioni/export, non per i FPS.
- Più volti nella scena → attiva **Multi-face**.
