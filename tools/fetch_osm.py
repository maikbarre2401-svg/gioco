#!/usr/bin/env python3
"""
Scarica strade ed edifici VERI da OpenStreetMap e li salva in un file compatto
che il gioco 3D usa per costruire la citta'.

Uso:
    python tools/fetch_osm.py --nome losangeles --lat 34.0490 --lon -118.2560 --raggio 1300

Dati (c) OpenStreetMap contributors, licenza ODbL (https://www.openstreetmap.org/copyright).
Solo libreria standard di Python: nessuna dipendenza.
"""
import argparse
import gzip
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

QUERY = """
[out:json][timeout:600][maxsize:1073741824];
(
  way["building"]({bb});
  relation["building"]({bb});
  way["building:part"]({bb});
  relation["building:part"]({bb});
  way["highway"]({bb});
  way["leisure"~"park|garden|pitch|playground|dog_park|golf_course|stadium"]({bb});
  relation["leisure"~"park|garden"]({bb});
  way["landuse"~"grass|park|recreation_ground|forest|meadow|village_green|cemetery|railway|construction"]({bb});
  relation["landuse"~"grass|park|recreation_ground|forest"]({bb});
  way["natural"~"water|wood|scrub|grassland|bare_rock"]({bb});
  relation["natural"="water"]({bb});
  way["waterway"="riverbank"]({bb});
  way["amenity"="parking"]({bb});
  way["area:highway"]({bb});
  way["railway"~"rail|light_rail|subway|tram"]({bb});
  node["highway"~"traffic_signals|street_lamp|bus_stop"]({bb});
  node["natural"="tree"]({bb});
  node["amenity"~"police|school|hospital|fire_station|fuel|bar|restaurant|cafe|cinema|theatre"]({bb});
  way["amenity"~"police|school|hospital|fire_station|fuel|cinema|theatre|university|college"]({bb});
);
out geom tags qt;
"""


def fetch(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(3):
        for url in MIRRORS:
            try:
                print("Richiesta a", url, flush=True)
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "rick-morty-fan-game/1.0"})
                with urllib.request.urlopen(req, timeout=900) as r:
                    raw = r.read()
                print("Ricevuti %.1f MB" % (len(raw) / 1e6), flush=True)
                return json.loads(raw)
            except Exception as e:  # noqa: BLE001
                last = e
                print("  errore:", e, flush=True)
                time.sleep(20 * (attempt + 1))
    raise SystemExit("Impossibile scaricare i dati: %s" % last)


def parse_len(v):
    if v is None:
        return None
    s = str(v).strip().lower().replace(",", ".")
    try:
        if s.endswith("ft") or s.endswith("'"):
            return float(s.rstrip("ft'").strip()) * 0.3048
        if s.endswith("m"):
            s = s[:-1]
        return float(s.split(";")[0].split()[0])
    except ValueError:
        return None


def stitch(ways):
    """unisce i pezzi di un multipoligono in anelli chiusi"""
    rings = []
    pieces = [list(w) for w in ways if len(w) >= 2]
    while pieces:
        ring = pieces.pop(0)
        changed = True
        while ring[0] != ring[-1] and changed:
            changed = False
            for i, p in enumerate(pieces):
                if p[0] == ring[-1]:
                    ring += p[1:]
                elif p[-1] == ring[-1]:
                    ring += p[::-1][1:]
                elif p[-1] == ring[0]:
                    ring = p[:-1] + ring
                elif p[0] == ring[0]:
                    ring = p[::-1][:-1] + ring
                else:
                    continue
                pieces.pop(i)
                changed = True
                break
        if len(ring) >= 4 and ring[0] == ring[-1]:
            rings.append(ring)
    return rings


DEFAULT_H = {"house": 7, "detached": 7, "residential": 11, "apartments": 16, "commercial": 11, "retail": 7,
             "office": 22, "industrial": 9, "warehouse": 9, "garage": 3.2, "garages": 3.2, "shed": 3,
             "hotel": 30, "school": 10, "church": 14, "cathedral": 30, "hospital": 22, "parking": 13,
             "public": 14, "civic": 16, "government": 18, "university": 16, "train_station": 14,
             "transportation": 8, "stadium": 25, "kiosk": 3, "service": 4, "construction": 12}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nome", default="losangeles")
    ap.add_argument("--lat", type=float, default=34.0490)
    ap.add_argument("--lon", type=float, default=-118.2560)
    ap.add_argument("--raggio", type=float, default=1300.0, help="mezzo lato dell'area in metri")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "citta"))
    a = ap.parse_args()
    lat0, lon0, R = a.lat, a.lon, a.raggio
    kx = math.cos(math.radians(lat0)) * 111320.0
    ky = 110540.0
    dlat, dlon = R / ky, R / kx
    bb = "%.6f,%.6f,%.6f,%.6f" % (lat0 - dlat, lon0 - dlon, lat0 + dlat, lon0 + dlon)
    js = fetch(QUERY.replace("{bb}", bb))
    els = js.get("elements", [])
    print("Elementi:", len(els))

    def P(g):
        return [(round((p["lon"] - lon0) * kx, 1), round((p["lat"] - lat0) * ky, 1)) for p in g if p]

    def Q(pts):
        return [int(round(c * 10)) for xy in pts for c in xy]

    buildings, parts, roads, areas, rails = [], [], [], [], []
    pts = {"signals": [], "lamps": [], "trees": [], "bus": []}
    amen = []
    for e in els:
        t = e.get("tags", {})
        typ = e["type"]
        if typ == "node":
            x, y = P([e])[0]
            hw = t.get("highway")
            if hw == "traffic_signals":
                pts["signals"].append((x, y))
            elif hw == "street_lamp":
                pts["lamps"].append((x, y))
            elif hw == "bus_stop":
                pts["bus"].append((x, y))
            elif t.get("natural") == "tree":
                pts["trees"].append((x, y))
            if "amenity" in t:
                amen.append(dict(k=t["amenity"], n=t.get("name", ""), p=[x, y]))
            continue
        if typ == "way":
            geom = P(e.get("geometry", []))
            rings = [geom]
        else:
            outer = [P(m.get("geometry", [])) for m in e.get("members", []) if m.get("role", "outer") in ("outer", "") and m.get("geometry")]
            inner = [P(m.get("geometry", [])) for m in e.get("members", []) if m.get("role") == "inner" and m.get("geometry")]
            ro = stitch(outer)
            ri = stitch(inner)
            if not ro:
                continue
            rings = ro + ri
            geom = ro[0]
        if not geom or len(geom) < 2:
            continue
        if "building" in t or "building:part" in t:
            is_part = "building:part" in t and "building" not in t
            kind = t.get("building:part") if is_part else t.get("building")
            if kind in ("no",) or t.get("location") == "underground":
                continue
            h = parse_len(t.get("height"))
            lv = parse_len(t.get("building:levels"))
            if h is None and lv is not None:
                h = lv * 3.3 + (1.5 if lv > 2 else 0.5)
            mh = parse_len(t.get("min_height"))
            mlv = parse_len(t.get("building:min_level"))
            if mh is None and mlv is not None:
                mh = mlv * 3.3
            est = 0
            if h is None:
                h = DEFAULT_H.get(kind, 9.0)
                est = 1
            if kind == "roof":
                mh = mh if mh is not None else max(0.0, h - 1.0)
            rec = dict(h=round(h, 1), m=round(mh or 0.0, 1), k=kind or "yes", e=est,
                       r=[Q(r) for r in (rings if typ == "relation" else [geom]) if len(r) >= 4])
            if t.get("name"):
                rec["n"] = t["name"]
            if t.get("amenity"):
                rec["a"] = t["amenity"]
            if t.get("building:colour"):
                rec["c"] = t["building:colour"]
            if t.get("building:material"):
                rec["mat"] = t["building:material"]
            if t.get("roof:shape"):
                rec["rs"] = t["roof:shape"]
            if not rec["r"]:
                continue
            (parts if is_part else buildings).append(rec)
            continue
        if "highway" in t and typ == "way":
            hw = t["highway"]
            if t.get("area") == "yes":
                areas.append(dict(k="plaza", r=Q(geom)))
                continue
            rec = dict(k=hw, p=Q(geom))
            for tag, key in (("lanes", "l"), ("oneway", "o"), ("layer", "y"), ("bridge", "b"), ("tunnel", "t"),
                             ("name", "n"), ("width", "w"), ("service", "s"), ("sidewalk", "sw")):
                if tag in t:
                    rec[key] = t[tag]
            roads.append(rec)
            continue
        if "railway" in t and typ == "way":
            rails.append(dict(k=t["railway"], p=Q(geom), t=t.get("tunnel", ""), y=t.get("layer", "")))
            continue
        k = None
        if t.get("leisure") in ("park", "garden", "playground", "dog_park"):
            k = "park"
        elif t.get("leisure") in ("pitch", "stadium", "golf_course"):
            k = "pitch"
        elif t.get("landuse") in ("grass", "park", "recreation_ground", "meadow", "village_green", "cemetery"):
            k = "grass"
        elif t.get("landuse") == "forest" or t.get("natural") in ("wood", "scrub", "grassland"):
            k = "wood"
        elif t.get("natural") == "water" or t.get("waterway") == "riverbank":
            k = "water"
        elif t.get("amenity") == "parking":
            k = "parking"
        elif "area:highway" in t:
            k = "road_area"
        elif t.get("landuse") == "railway":
            k = "railway"
        elif t.get("landuse") == "construction":
            k = "construction"
        elif t.get("amenity"):
            amen.append(dict(k=t["amenity"], n=t.get("name", ""), p=list(geom[0])))
            continue
        if k:
            for r in rings[:1] if typ == "way" else rings:
                if len(r) >= 4:
                    rec = dict(k=k, r=Q(r))
                    if t.get("name"):
                        rec["n"] = t["name"]
                    areas.append(rec)
    out = dict(nome=a.nome, centro=[lat0, lon0], raggio=R, fonte="(c) OpenStreetMap contributors, ODbL",
               scala=0.1, edifici=buildings, parti=parts, strade=roads, aree=areas, ferrovie=rails,
               punti=pts, servizi=amen)
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, a.nome + ".json.gz")
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print("Salvato %s (%.1f MB): %d edifici, %d parti, %d strade, %d aree" % (
        path, os.path.getsize(path) / 1e6, len(buildings), len(parts), len(roads), len(areas)))


if __name__ == "__main__":
    sys.exit(main())
