#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎭 DEEPFAKE ULTRA PRO 8.0  ⚡  (real-time face swap)

Entry point. Il progetto è organizzato in moduli dentro `dfpro/`:

    dfpro/config.py    impostazioni, preset, costanti (solo dati)
    dfpro/theme.py     palette, font, helper di disegno  (solo tkinter)
    dfpro/widgets.py   widget custom su Canvas           (solo tkinter)
    dfpro/tracking.py  monitor prestazioni + stabilizzatore volti
    dfpro/engine.py    FaceEngine: modelli, rilevamento, swap, blending
    dfpro/app.py       finestra principale + pipeline

theme/widgets non importano cv2 né insightface: la UI è testabile da sola.

LIMITI DEL MODELLO (inswapper_128) — onestà tecnica
  * NON scambia i capelli / la testa: solo il volto interno.
  * Lavora a 128x128: il dettaglio di denti/lingua è limitato.
    "Keep mouth" e l'enhancer mitigano, non azzerano.

Uso etico: usa solo volti per cui hai il consenso. Non creare contenuti
ingannevoli o che ledano le persone.

Requisiti: vedi requirements.txt · Modello: inswapper_128.onnx
"""
import warnings
warnings.filterwarnings('ignore')

import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ.setdefault('OMP_NUM_THREADS', str(max(1, (os.cpu_count() or 4))))

from dfpro.app import main

if __name__ == '__main__':
    main()
