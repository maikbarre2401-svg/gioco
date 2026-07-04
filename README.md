# gioco — Deepfake Ultra Pro 5.0 🎭

Face-swap in tempo reale (webcam) basato su **insightface** + `inswapper_128.onnx`,
con interfaccia Tkinter. Versione ottimizzata: **più veloce** e **più realistica**.

> ⚠️ **Uso responsabile.** Usa solo volti per cui hai il consenso. Non creare
> contenuti ingannevoli, diffamatori o che ledano le persone. Molti paesi
> regolano l'uso dei deepfake: sei responsabile di come usi questo strumento.

## Cosa è cambiato rispetto alla 4.1

**Velocità**
- **Auto-selezione del provider ONNX**: usa la GPU (CUDA / CoreML / DirectML)
  quando disponibile, invece del solo CPU. → il guadagno più grande.
- **Detector "detection-only"** per il flusso live: salta i modelli di
  recognition/landmark/genderage che il face-swap non usa.
- **Un solo thread di inferenza** al posto di N thread che condividevano lo
  stesso lock (di fatto serializzavano tutto e generavano contesa).
- **Cache di rilevamento corretta**: la 4.1 usava `id(frame)` come chiave —
  non colpiva mai e poteva restituire dati obsoleti dopo il garbage collector.
  Ora in modalità FAST si può saltare il detect ogni N frame riusando l'ultimo.
- **Sessione ONNX** con ottimizzazione del grafo e thread intra-op.

**Realismo**
- **Blending ellittico con bordi sfumati** (feather) invece del crop quadrato.
- **Color transfer LAB**: la faccia sostituita adotta luce/tinta della scena.
- **Faccia sorgente** scelta per dimensione (il soggetto), non solo per score.

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
| `f` | Schermo intero |
| `r` | Reinizializza camera |
| `Esc` | Esci |

### Modalità
- **FAST** — risoluzione ridotta + detect ogni 2 frame → massimi FPS.
- **BALANCED** — compromesso predefinito.
- **QUALITY** — risoluzione maggiore, detect ogni frame.

## Suggerimenti performance
- Su GPU installa `onnxruntime-gpu`: è la differenza più grande.
- Se hai una CPU debole, usa la modalità **FAST** e abbassa `det_size` a `256`
  in `config`.
- Per il massimo realismo tieni attivo **Realistic blend** e usa una foto
  sorgente ben illuminata e frontale.
