"""Monitor prestazioni e stabilizzatore temporale dei volti."""
import time

import numpy as np

from .config import _HAS_PSUTIL

if _HAS_PSUTIL:
    import psutil


class PerformanceMonitor:
    def __init__(self):
        self.max_history = 100
        self.fps_history = []
        self.frame_count = 0
        self.last_time = time.time()
        self.current_fps = 0
        self._cpu = 0.0
        self._ram = 0.0

    def update_fps(self):
        self.frame_count += 1
        now = time.time()
        if now - self.last_time >= 0.5:
            self.current_fps = int(self.frame_count / (now - self.last_time))
            self.frame_count = 0
            self.last_time = now
            self.fps_history.append(self.current_fps)
            if len(self.fps_history) > self.max_history:
                self.fps_history.pop(0)
            if _HAS_PSUTIL:
                self._cpu = psutil.cpu_percent()
                self._ram = psutil.virtual_memory().percent
        return self.current_fps

    def get_stats(self):
        avg = int(np.mean(self.fps_history)) if self.fps_history else 0
        return {"fps": self.current_fps, "cpu": self._cpu, "ram": self._ram, "avg_fps": avg}


class FaceStabilizer:
    """Leviga bbox/keypoint/landmark nel tempo per togliere il tremolìo dello
    swap. Associa i volti tra frame consecutivi per centroide (greedy)."""

    _KEYS = ('bbox', 'kps', 'landmark_2d_106')

    def __init__(self):
        self.tracks = {}   # id -> {'c':centroid, 'geo':{key:array}, 'age':int}
        self._next = 0

    @staticmethod
    def _centroid(face):
        b = np.asarray(face.bbox, np.float32)
        return np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0], np.float32)

    @staticmethod
    def _face_w(face):
        b = np.asarray(face.bbox, np.float32)
        return float(b[2] - b[0])

    def update(self, faces, strength):
        """strength in [0,0.95]: quota del valore precedente da mantenere.
        0 = nessuna levigatura, 0.9 = molto fermo (più latenza)."""
        if not faces:
            self.tracks.clear()
            return faces
        s = float(np.clip(strength, 0.0, 0.95))

        cents = [self._centroid(f) for f in faces]
        used = set()
        assigned = {}
        # greedy match: per ogni volto, la traccia più vicina entro soglia
        for i, f in enumerate(faces):
            best_id, best_d = None, None
            thr = max(40.0, 0.6 * self._face_w(f))
            for tid, t in self.tracks.items():
                if tid in used:
                    continue
                d = float(np.linalg.norm(cents[i] - t['c']))
                if d <= thr and (best_d is None or d < best_d):
                    best_id, best_d = tid, d
            if best_id is not None:
                used.add(best_id)
                assigned[i] = best_id

        new_tracks = {}
        for i, f in enumerate(faces):
            tid = assigned.get(i)
            geo = {}
            for k in self._KEYS:
                cur = getattr(f, k, None)
                if cur is None:
                    continue
                cur = np.asarray(cur, np.float32)
                if s > 0 and tid is not None and k in self.tracks[tid]['geo']:
                    prev = self.tracks[tid]['geo'][k]
                    if prev.shape == cur.shape:
                        cur = s * prev + (1.0 - s) * cur
                        setattr(f, k, cur)
                geo[k] = cur
            nid = tid if tid is not None else self._new_id()
            # l'id di traccia serve anche al color-match temporale (anti-flicker)
            try:
                setattr(f, 'track_id', nid)
            except Exception:
                pass
            new_tracks[nid] = {'c': self._centroid(f), 'geo': geo, 'age': 0}
        self.tracks = new_tracks
        return faces

    def _new_id(self):
        self._next += 1
        return self._next
