"""FaceEngine: caricamento modelli, rilevamento, swap e blending.

Codice spostato dal monolite senza modifiche funzionali: la pipeline di
inferenza è quella già verificata.
"""
import os
import threading

import cv2
import numpy as np

from .config import config


class FaceEngine:
    """Carica i modelli e fornisce rilevamento, swap, blending ed enhance."""

    def __init__(self, model_path):
        self.model_path = model_path
        self.detector = None      # detection-only (live)
        self.app = None           # completo (embedding sorgente)
        self.swapper = None
        self.enhancer = None
        self.enhancer_ready = False
        self.matcher = None            # detector con recognition (match identità)
        self.matcher_ready = False
        self.occluder = None           # modello neurale di occlusione (mani/oggetti)
        self.occluder_ready = False
        self.occluder_in = None
        self._occ_size = 256
        self._occ_nchw = False
        self.loaded = False

        self.providers = []
        self.provider_name = 'CPU'
        self.ctx_id = -1

        self._lock = threading.Lock()
        self._last_faces = []
        self._frame_idx = 0
        self._color_ema = {}      # track_id -> (lab_mean, lab_std) anti-flicker

    # ---- providers ----------------------------------------------------------
    def _select_providers(self):
        try:
            import onnxruntime as ort
            avail = ort.get_available_providers()
        except Exception:
            avail = ['CPUExecutionProvider']
        preferred = ['CUDAExecutionProvider', 'CoreMLExecutionProvider',
                     'DmlExecutionProvider', 'CPUExecutionProvider']
        self.providers = [p for p in preferred if p in avail] or ['CPUExecutionProvider']
        top = self.providers[0]
        self.provider_name = {
            'CUDAExecutionProvider': 'CUDA (GPU)',
            'CoreMLExecutionProvider': 'CoreML (Apple)',
            'DmlExecutionProvider': 'DirectML (GPU)',
            'CPUExecutionProvider': 'CPU',
        }.get(top, top)
        self.ctx_id = 0 if top == 'CUDAExecutionProvider' else -1
        return self.providers

    # ---- load ---------------------------------------------------------------
    def load(self):
        try:
            import insightface
            from insightface.app import FaceAnalysis
        except Exception as e:
            print(f"❌ insightface non disponibile: {e}")
            return False

        self._select_providers()
        print(f"⚡ Execution provider: {self.provider_name}")

        det = (config['det_size'], config['det_size'])
        # detection + landmark_2d_106 per la maschera precisa (niente recognition)
        self.detector = FaceAnalysis(name=config['detector_name'],
                                     allowed_modules=['detection', 'landmark_2d_106'],
                                     providers=self.providers)
        self.detector.prepare(ctx_id=self.ctx_id, det_size=det,
                              det_thresh=config['det_thresh'])

        self.app = FaceAnalysis(name=config['detector_name'],
                                allowed_modules=['detection', 'recognition'],
                                providers=self.providers)
        self.app.prepare(ctx_id=self.ctx_id, det_size=(320, 320),
                         det_thresh=config['det_thresh'])

        if not os.path.exists(self.model_path):
            print(f"❌ Modello non trovato: {self.model_path}")
            return False
        self.swapper = insightface.model_zoo.get_model(self.model_path,
                                                       providers=self.providers)
        self.loaded = True
        return True

    GFPGAN_URL = ('https://github.com/TencentARC/GFPGAN/releases/download/'
                  'v1.3.0/GFPGANv1.4.pth')

    def try_load_enhancer(self):
        """Carica GFPGAN. Usa il file locale se c'è, altrimenti lo scarica.
        Ritorna (ok, messaggio)."""
        if self.enhancer_ready:
            return True, "enhancer già pronto"
        try:
            from gfpgan import GFPGANer
        except Exception:
            return False, "pacchetto 'gfpgan' non installato (pip install gfpgan)"
        local = config['gfpgan_model']
        model = local if os.path.exists(local) else self.GFPGAN_URL
        try:
            self.enhancer = GFPGANer(model_path=model, upscale=1, arch='clean',
                                     channel_multiplier=2, bg_upsampler=None)
            self.enhancer_ready = True
            src = "file locale" if model == local else "download automatico"
            return True, f"GFPGAN pronto ({src})"
        except Exception as e:
            return False, f"errore GFPGAN: {str(e)[:80]}"

    def enhance_crop(self, crop):
        """Migliora SOLO il crop del volto (aligned): veloce, adatto al live su
        GPU. Upscale a 512, restore, torna alla dimensione originale."""
        if not self.enhancer_ready:
            return crop
        try:
            a = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_LINEAR)
            _, restored, _ = self.enhancer.enhance(a, has_aligned=True,
                                                   paste_back=False)
            if restored:
                return cv2.resize(restored[0], (crop.shape[1], crop.shape[0]),
                                  interpolation=cv2.INTER_AREA)
        except Exception:
            pass
        return crop

    def set_det_size(self, n):
        with self._lock:
            self.detector.prepare(ctx_id=self.ctx_id, det_size=(int(n), int(n)),
                                  det_thresh=config['det_thresh'])

    # ---- detection ----------------------------------------------------------
    def detect_source(self, img):
        faces = self.app.get(img)
        if not faces:
            return None
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    def detect(self, frame):
        """Rilevamento diretto (no stride/cache) — per l'export offline."""
        with self._lock:
            return self.detector.get(frame)

    def ensure_matcher(self):
        """Costruisce (lazy) un detector con detection+landmark+recognition,
        usato per il match d'identità. Ritorna (ok, messaggio)."""
        if self.matcher_ready:
            return True, "matcher pronto"
        try:
            from insightface.app import FaceAnalysis
            self.matcher = FaceAnalysis(
                name=config['detector_name'],
                allowed_modules=['detection', 'landmark_2d_106', 'recognition'],
                providers=self.providers)
            self.matcher.prepare(ctx_id=self.ctx_id,
                                 det_size=(config['det_size'], config['det_size']),
                                 det_thresh=config['det_thresh'])
            self.matcher_ready = True
            return True, "match identità pronto"
        except Exception as e:
            return False, f"errore matcher: {str(e)[:80]}"

    def detect_match(self, frame):
        """Rilevamento con embedding (per il match d'identità)."""
        with self._lock:
            return self.matcher.get(frame)

    OCCLUDER_URLS = [
        'https://github.com/facefusion/facefusion-assets/releases/download/'
        'models/face_occluder.onnx',
        'https://huggingface.co/facefusion/models/resolve/main/face_occluder.onnx',
    ]

    @staticmethod
    def _download_first(urls, dest):
        import urllib.request
        d = os.path.dirname(dest)
        if d:
            os.makedirs(d, exist_ok=True)
        for u in urls:
            try:
                urllib.request.urlretrieve(u, dest)
                if os.path.exists(dest) and os.path.getsize(dest) > 10000:
                    return True
            except Exception:
                continue
        return False

    def try_load_occluder(self):
        """Carica il modello neurale di occlusione (gestisce anche le MANI).
        Scarica il file se manca. Ritorna (ok, messaggio)."""
        if self.occluder_ready:
            return True, "occluder pronto"
        try:
            import onnxruntime as ort
        except Exception:
            return False, "onnxruntime non disponibile"
        path = config['occluder_model']
        if not os.path.exists(path):
            if not self._download_first(self.OCCLUDER_URLS, path):
                return False, f"scarica 'face_occluder.onnx' e mettilo come {path}"
        try:
            so = ort.SessionOptions()
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.occluder = ort.InferenceSession(path, sess_options=so,
                                                 providers=self.providers)
            inp = self.occluder.get_inputs()[0]
            self.occluder_in = inp.name
            shape = inp.shape  # [1,3,H,W] (NCHW) oppure [1,H,W,3] (NHWC)
            self._occ_nchw = len(shape) == 4 and shape[1] == 3
            dim = shape[2] if self._occ_nchw else shape[1]
            self._occ_size = int(dim) if isinstance(dim, int) and dim > 0 else 256
            self.occluder_ready = True
            return True, f"occluder AI pronto ({'NCHW' if self._occ_nchw else 'NHWC'}"\
                         f" {self._occ_size})"
        except Exception as e:
            return False, f"errore occluder: {str(e)[:80]}"

    def occlusion_mask_crop(self, crop):
        """Maschera 'faccia visibile' (1=faccia, 0=occluso) sul crop allineato.
        Dove c'è una mano/oggetto davanti, il modello restituisce ~0."""
        if not self.occluder_ready:
            return None
        try:
            s = self._occ_size
            img = cv2.resize(crop, (s, s))[:, :, ::-1].astype(np.float32) / 255.0
            blob = np.transpose(img, (2, 0, 1))[None] if self._occ_nchw else img[None]
            out = self.occluder.run(None, {self.occluder_in: blob})[0]
            m = np.asarray(out, np.float32).squeeze()
            if m.ndim == 3:
                m = m[0] if m.shape[0] < m.shape[-1] else m[..., 0]
            m = np.clip(m, 0.0, 1.0)
            return cv2.resize(m, (crop.shape[1], crop.shape[0]))
        except Exception:
            return None

    def detect_live(self, frame, stride=1):
        self._frame_idx += 1
        if stride > 1 and self._last_faces and (self._frame_idx % stride) != 0:
            return self._last_faces
        with self._lock:
            faces = self.detector.get(frame)
        self._last_faces = faces
        return faces

    # ---- blending -----------------------------------------------------------
    @staticmethod
    def _lab_stats(img):
        """Media e deviazione standard per canale LAB."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        mean = np.array([lab[..., i].mean() for i in range(3)], np.float32)
        std = np.array([lab[..., i].std() for i in range(3)], np.float32)
        return mean, std

    @staticmethod
    def _apply_color(src, ref_mean, ref_std):
        """Porta src alle statistiche di colore (ref_mean/ref_std) indicate."""
        s = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
        out = s.copy()
        for i in range(3):
            sm = float(s[..., i].mean())
            ss = float(s[..., i].std()) + 1e-6
            out[..., i] = (s[..., i] - sm) * (float(ref_std[i]) / ss) + float(ref_mean[i])
        return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)

    def _ref_color_stats(self, aimg, face, strength):
        """Statistiche di colore della scena, LEVIGATE NEL TEMPO per traccia.
        Senza questo il color-match si ricalcola da zero ogni frame e il volto
        "pulsa" di tinta — uno dei segnali che tradiscono il fake."""
        mean, std = self._lab_stats(aimg)
        a = float(np.clip(strength, 0.0, 0.95))
        if a <= 0:
            return mean, std
        key = getattr(face, 'track_id', 0)
        prev = self._color_ema.get(key)
        if prev is not None and prev[0].shape == mean.shape:
            mean = a * prev[0] + (1.0 - a) * mean
            std = a * prev[1] + (1.0 - a) * std
        self._color_ema[key] = (mean, std)
        if len(self._color_ema) > 16:          # non far crescere la cache
            for k in list(self._color_ema)[:-8]:
                self._color_ema.pop(k, None)
        return mean, std

    @staticmethod
    def _sharpen(img, amount):
        if amount <= 0:
            return img
        blur = cv2.GaussianBlur(img, (0, 0), 3)
        return cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)

    @staticmethod
    def _smooth(img, amount):
        if amount <= 0:
            return img
        sm = cv2.bilateralFilter(img, 7, 45, 45)
        return cv2.addWeighted(img, 1.0 - amount, sm, amount, 0)

    @staticmethod
    def _ellipse_mask_full(M, size, w, h, ms):
        ax = int(np.clip(size * 0.42 * ms, 4, size // 2))
        ay = int(np.clip(size * 0.50 * ms, 4, size // 2))
        mask = np.zeros((size, size), np.float32)
        cv2.ellipse(mask, (size // 2, size // 2), (ax, ay), 0, 0, 360, 1.0, -1)
        IM = cv2.invertAffineTransform(M)
        return cv2.warpAffine(mask, IM, (w, h), borderValue=0)

    @staticmethod
    def _landmark_mask_full(face, w, h, ms, forehead, M):
        """Maschera che segue la reale forma del volto (convex hull dei 106
        landmark) ED estesa verso la FRONTE lungo l'asse 'su' della testa —
        così sopracciglia e fronte vengono coperte dallo swap (niente stacco)."""
        pts = getattr(face, 'landmark_2d_106', None)
        if pts is None:
            return None
        try:
            pts = np.asarray(pts, dtype=np.float32)
            allpts = pts
            if forehead > 0:
                # direzione "su" del volto in coordinate frame (dal crop allineato)
                IM = cv2.invertAffineTransform(M)
                up = -IM[:, 1].astype(np.float32)
                up = up / (float(np.linalg.norm(up)) + 1e-6)
                fh = float(pts[:, 1].max() - pts[:, 1].min())
                shift = up * (fh * float(forehead))
                allpts = np.vstack([pts, pts + shift])
            hull = cv2.convexHull(allpts.astype(np.int32))
            mask = np.zeros((h, w), np.float32)
            cv2.fillConvexPoly(mask, hull, 1.0)
            fw = float(face.bbox[2] - face.bbox[0])
            k = max(1, int(fw * 0.05 * ms))
            mask = cv2.dilate(mask, np.ones((k, k), np.uint8))
            return mask
        except Exception:
            return None

    @staticmethod
    def _mouth_mask_full(face, w, h):
        """Ellisse morbida sulla bocca (dai keypoint) per far trasparire la
        bocca reale: espressioni e lingua restano naturali."""
        kps = getattr(face, 'kps', None)
        if kps is None or len(kps) < 5:
            return None
        lm = np.asarray(kps[3], np.float32)
        rm = np.asarray(kps[4], np.float32)
        cx, cy = (lm + rm) / 2.0
        wd = float(np.linalg.norm(rm - lm)) + 1e-6
        ang = float(np.degrees(np.arctan2(rm[1] - lm[1], rm[0] - lm[0])))
        m = np.zeros((h, w), np.float32)
        cv2.ellipse(m, (int(cx), int(cy)),
                    (int(wd * 0.85), int(wd * 0.60)), ang, 0, 360, 1.0, -1)
        b = max(3, int(wd * 0.4))
        b = b + 1 if b % 2 == 0 else b
        return cv2.GaussianBlur(m, (b, b), 0)

    @staticmethod
    def _skin_prob(bgr):
        """Probabilità di pelle (YCrCb). Serve a NON coprire con lo swap ciò
        che non è pelle dentro l'area del volto (ciuffi, occhiali, oggetti).
        Nota: le mani sono color pelle, quindi non vengono protette."""
        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        lower = np.array([0, 133, 77], np.uint8)
        upper = np.array([255, 173, 127], np.uint8)
        m = cv2.inRange(ycrcb, lower, upper).astype(np.float32) / 255.0
        return cv2.GaussianBlur(m, (7, 7), 0)

    def _blend(self, frame, bgr_fake, M, face, p, skin=None):
        h, w = frame.shape[:2]
        # enhancer sul crop (denti/pelle/bocca ad alta fedeltà) prima del blend
        if p.get('enhance') and self.enhancer_ready:
            bgr_fake = self.enhance_crop(bgr_fake)
        size = bgr_fake.shape[0]

        # NB: warpAffine NON implementa INTER_AREA (lo ignora e usa il bilineare,
        # verificato: output bit-identico). INTER_AREA esiste solo in resize().
        # Qui aimg serve per le statistiche di colore e per l'occluder, dove il
        # bilineare va benissimo: non "ottimizzare" mettendo INTER_AREA.
        aimg = cv2.warpAffine(frame, M, (size, size), flags=cv2.INTER_LINEAR)
        cs = float(p['color_strength'])
        if cs > 0:
            rm, rs = self._ref_color_stats(aimg, face, float(p.get('color_stab', 0.0)))
            ct = self._apply_color(bgr_fake, rm, rs)
            fake = cv2.addWeighted(bgr_fake, 1.0 - cs, ct, cs, 0)
        else:
            fake = bgr_fake
        fake = self._smooth(fake, float(p['smooth']))
        fake = self._sharpen(fake, float(p['sharpen']))

        IM = cv2.invertAffineTransform(M)
        # Paste-back: INTER_LINEAR è la scelta MISURATA come migliore.
        # Test con ground truth (volto hi-res -> 128 -> riportato su): PSNR
        # LINEAR 28.24 dB, CUBIC 28.06, LANCZOS4 27.97; e l'errore sui bordi
        # PEGGIORA col cubico. Il cubico "sembra" più nitido solo perché i suoi
        # lobi negativi fanno overshoot e amplificano il rumore (su crop
        # rumoroso: varianza Laplace 71->85 ma PSNR 27.47->27.04).
        # Non sostituire con CUBIC/LANCZOS4: è un peggioramento reale.
        fake_full = cv2.warpAffine(fake, IM, (w, h), flags=cv2.INTER_LINEAR,
                                   borderValue=0)

        ms = float(p['mask_size'])
        mask_full = None
        if p.get('precise_mask'):
            mask_full = self._landmark_mask_full(face, w, h, ms,
                                                 float(p.get('forehead', 0.0)), M)
        if mask_full is None:
            mask_full = self._ellipse_mask_full(M, size, w, h, ms)

        km = float(p.get('keep_mouth', 0.0))
        if km > 0:
            mm = self._mouth_mask_full(face, w, h)
            if mm is not None:
                mask_full = mask_full * (1.0 - km * mm)

        # occlusione neurale (mani/oggetti): il modello dice dov'è la faccia vera
        if p.get('occluder') and self.occluder_ready:
            occm = self.occlusion_mask_crop(aimg)
            if occm is not None:
                occ_full = cv2.warpAffine(occm, IM, (w, h), borderValue=1.0)
                mask_full = mask_full * occ_full

        # occlusione "leggera": dove NON c'è pelle nell'area del volto, originale
        occ = float(p.get('occlusion', 0.0))
        if occ > 0:
            # riusa la mappa pelle calcolata una volta per frame (multi-face)
            sk = skin if skin is not None else self._skin_prob(frame)
            mask_full = mask_full * (1.0 - occ * (1.0 - sk))

        scale = float(np.sqrt(M[0, 0] ** 2 + M[0, 1] ** 2)) + 1e-6
        face_px = size / scale
        blur = int(max(3, face_px * float(p['feather'])))
        blur = blur + 1 if blur % 2 == 0 else blur
        mask_full = cv2.GaussianBlur(mask_full, (blur, blur), 0)
        mask_full = np.clip(mask_full, 0.0, 1.0)[..., None]

        out = fake_full.astype(np.float32) * mask_full + \
            frame.astype(np.float32) * (1.0 - mask_full)
        return out.astype(np.uint8)

    def swap_one(self, frame, target, source, p, skin=None):
        if not self.loaded or target is None or source is None:
            return frame
        with self._lock:
            if p['realistic_blend']:
                try:
                    bgr_fake, M = self.swapper.get(frame, target, source, paste_back=False)
                except Exception:
                    return self.swapper.get(frame, target, source, paste_back=True) or frame
            else:
                return self.swapper.get(frame, target, source, paste_back=True) or frame
        # blend fuori dal lock (solo numpy/cv2)
        return self._blend(frame, bgr_fake, M, target, p, skin=skin)

    @staticmethod
    def best_face(faces):
        return max(faces, key=lambda f: f.det_score) if faces else None
