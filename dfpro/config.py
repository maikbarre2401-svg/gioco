"""Impostazioni, risoluzioni per modalità e preset.

Solo dati: nessuna dipendenza pesante, così è importabile da qualsiasi modulo.
"""
import os

try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    _HAS_PSUTIL = False


config = {
    'model_path': 'inswapper_128.onnx',
    'detector_name': 'buffalo_l',
    'det_size': 320,
    'det_thresh': 0.5,
    'display_hz': 60,
    'record_fps': 24,
    'output_dir': 'output',
    'gfpgan_model': 'GFPGANv1.4.pth',
    'occluder_model': 'face_occluder.onnx',
    # default regolazioni
    'swap_threshold': 0.35,
    'mask_size': 1.0,       # 0.6 - 1.3
    'feather': 0.06,        # 0.02 - 0.15
    'color_strength': 0.80,  # 0 - 1
    'sharpen': 0.15,        # 0 - 1
    'smooth': 0.0,          # 0 - 1
    'multi_face': True,
    'realistic_blend': True,
    'mirror': False,
    'fast_detect_stride': 2,
    'precise_mask': True,   # maschera dai landmark (segue la mascella)
    'forehead': 0.30,       # estensione maschera verso la fronte (0-0.6)
    'keep_mouth': 0.30,     # 0=bocca sorgente, 1=bocca reale (lingua/parlato)
    'stabilize': 0.40,      # anti-jitter temporale (0=off, 0.9=molto fermo)
    'color_stab': 0.60,     # anti-flicker del color-match (0=off, 0.9=molto fermo)
    'coast_frames': 9,      # frame in cui "tiene" l'ultima faccia se il detect salta
    'occlusion': 0.0,       # protezione occlusioni (0=off): ciuffi/occhiali/oggetti
    'match': False,         # sostituisci SOLO la persona-target (per identità)
    'match_thresh': 0.35,   # soglia similarità coseno (buffalo_l w600k)
}

MODE_RES = {'fast': (640, 360), 'balanced': (854, 480), 'quality': (960, 540)}


def _cpu_count():
    try:
        return psutil.cpu_count() if _HAS_PSUTIL else (os.cpu_count() or 4)
    except Exception:
        return os.cpu_count() or 4


# Preset: combinazioni collaudate applicate in un click.
PRESETS = {
    # realismo del parlato: bocca reale, maschera precisa, fronte coperta
    'talking': dict(mode='balanced', det=320, thresh=0.35, mask=1.0,
                    forehead=0.32, feather=0.09, color=0.85, sharpen=0.20,
                    smooth=0.30, keep=0.55, stab=0.55, occ=0.40, cstab=0.70,
                    precise=True, multi=False),
    # massima fedeltà (adatto a GPU tipo RTX 4070)
    'quality': dict(mode='quality', det=512, thresh=0.35, mask=1.05,
                    forehead=0.35, feather=0.07, color=0.90, sharpen=0.25,
                    smooth=0.35, keep=0.30, stab=0.50, occ=0.50, cstab=0.65,
                    precise=True, multi=True),
    # massimi FPS
    'speed': dict(mode='fast', det=256, thresh=0.40, mask=1.0,
                  forehead=0.25, feather=0.05, color=0.70, sharpen=0.10,
                  smooth=0.0, keep=0.20, stab=0.35, occ=0.0, cstab=0.50,
                  precise=True, multi=False),
}

# Parametri letti dal thread di inferenza (snapshot thread-safe dal main thread)
PARAM_KEYS = ('swap_threshold', 'mask_size', 'feather', 'color_strength',
              'sharpen', 'smooth', 'multi_face', 'realistic_blend', 'mirror',
              'precise_mask', 'keep_mouth', 'stabilize', 'forehead',
              'color_stab', 'occlusion', 'match', 'match_thresh')

BOX_COLORS = {
    'green': (0, 255, 0), 'red': (0, 0, 255), 'blue': (255, 0, 0),
    'yellow': (0, 255, 255), 'cyan': (255, 255, 0), 'magenta': (255, 0, 255),
}
