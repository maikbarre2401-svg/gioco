# gioco — Deepfake Ultra Pro 6.0 🎭

Face-swap in tempo reale (webcam **o file video**) basato su **insightface** +
`inswapper_128.onnx`, con interfaccia Tkinter. Versione ottimizzata: **più
veloce**, **più realistica** e **più potente**, con pannello di regolazioni live.

> ⚠️ **Uso responsabile.** Usa solo volti per cui hai il consenso. Non creare
> contenuti ingannevoli, diffamatori o che ledano le persone. Molti paesi
> regolano l'uso dei deepfake: sei responsabile di come usi questo strumento.

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

Per GPU NVIDIA: in `requirements.txt` usa `onnxruntime-gpu` al posto di
`onnxruntime` (serve CUDA/cuDNN installati).

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

## Suggerimenti
- Su GPU installa `onnxruntime-gpu`: è la differenza più grande.
- CPU debole → modalità **FAST** e det_size `256`.
- Realismo: tieni **Realistic blend** attivo, alza un po' **Color match** e
  **Feather**, aggiungi un filo di **Skin smooth**; foto sorgente frontale e
  ben illuminata.
- Più volti nella scena → attiva **Multi-face**.
