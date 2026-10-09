"""Dati, calcolo dei rinnovi e salvataggio su file JSON (resta tutto sul telefono)."""
import calendar
import json
import os
import random
import string
import time
from datetime import date, timedelta

FREE_LIMIT = 8

# (id, nome, colore, categoria, prezzo indicativo, unità, ogni)
CATALOG = [
    ("netflix", "Netflix", "#E50914", "streaming", 13.99, "month", 1),
    ("disney", "Disney+", "#0E47A1", "streaming", 9.99, "month", 1),
    ("prime", "Amazon Prime", "#00A8E1", "streaming", 4.99, "month", 1),
    ("now", "NOW", "#00C9B1", "streaming", 9.99, "month", 1),
    ("dazn", "DAZN", "#1A1A1A", "streaming", 34.99, "month", 1),
    ("appletv", "Apple TV+", "#2C2C2E", "streaming", 9.99, "month", 1),
    ("paramount", "Paramount+", "#0064FF", "streaming", 7.99, "month", 1),
    ("crunchyroll", "Crunchyroll", "#F47521", "streaming", 5.99, "month", 1),
    ("spotify", "Spotify", "#1DB954", "music", 11.99, "month", 1),
    ("applemusic", "Apple Music", "#FA243C", "music", 10.99, "month", 1),
    ("youtube", "YouTube Premium", "#FF0000", "music", 13.99, "month", 1),
    ("audible", "Audible", "#F8991C", "music", 9.99, "month", 1),
    ("gamepass", "Xbox Game Pass", "#107C10", "gaming", 14.99, "month", 1),
    ("psplus", "PlayStation Plus", "#003791", "gaming", 8.99, "month", 1),
    ("nintendo", "Nintendo Online", "#E60012", "gaming", 19.99, "year", 1),
    ("chatgpt", "ChatGPT Plus", "#10A37F", "work", 23.0, "month", 1),
    ("claude", "Claude Pro", "#D97757", "work", 18.0, "month", 1),
    ("m365", "Microsoft 365", "#D83B01", "work", 99.0, "year", 1),
    ("adobe", "Adobe CC", "#FA0F00", "work", 61.99, "month", 1),
    ("canva", "Canva Pro", "#00C4CC", "work", 11.99, "month", 1),
    ("icloud", "iCloud+", "#3693F3", "cloud", 0.99, "month", 1),
    ("googleone", "Google One", "#4285F4", "cloud", 1.99, "month", 1),
    ("dropbox", "Dropbox", "#0061FF", "cloud", 11.99, "month", 1),
    ("gym", "Palestra", "#00B894", "sport", 39.0, "month", 1),
    ("strava", "Strava", "#FC4C02", "sport", 7.99, "month", 1),
    ("phone", "Telefono", "#5B8DEF", "home", 9.99, "month", 1),
    ("internet", "Internet casa", "#F2994A", "home", 27.9, "month", 1),
    ("electricity", "Luce e gas", "#E6B800", "home", 85.0, "month", 1),
    ("carinsurance", "Assicurazione auto", "#6C5CE7", "home", 480.0, "year", 1),
    ("glovo", "Glovo Prime", "#FFC244", "food", 5.99, "month", 1),
    ("duolingo", "Duolingo Super", "#58CC02", "education", 12.99, "month", 1),
    ("train", "Abbonamento treno", "#00A8A8", "transport", 60.0, "month", 1),
]

POPULAR = ["netflix", "spotify", "prime", "disney", "youtube", "gym", "icloud", "chatgpt"]

CATEGORIES = {
    "streaming": ("Streaming", "#E50914"),
    "music": ("Musica", "#1DB954"),
    "gaming": ("Giochi", "#7B61FF"),
    "work": ("Lavoro", "#FF8A00"),
    "cloud": ("Cloud e app", "#2D9CDB"),
    "sport": ("Sport e salute", "#00B894"),
    "home": ("Casa e bollette", "#E6B800"),
    "food": ("Cibo", "#FF5E7E"),
    "education": ("Studio", "#5B8DEF"),
    "transport": ("Trasporti", "#00A8A8"),
    "other": ("Altro", "#A0A4AB"),
}

CYCLES = [("week", 1, "Settimanale"), ("month", 1, "Mensile"), ("month", 3, "Trimestrale"),
          ("month", 6, "Semestrale"), ("year", 1, "Annuale")]

CURRENCIES = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF"}

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
MONTHS_LONG = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
               "agosto", "settembre", "ottobre", "novembre", "dicembre"]
WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def find_service(service_id):
    for s in CATALOG:
        if s[0] == service_id:
            return s
    return None


def cycle_label(unit, every):
    for u, e, label in CYCLES:
        if u == unit and e == every:
            return label
    names = {"day": "giorni", "week": "settimane", "month": "mesi", "year": "anni"}
    return "Ogni %d %s" % (every, names.get(unit, unit))


# ---------------------------------------------------------------- date

def parse_date(s):
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


def add_months(d, n, anchor_day=None):
    """Aggiunge mesi tenendo il giorno originale quando possibile (31 gen -> 29 feb -> 31 mar)."""
    anchor_day = anchor_day or d.day
    total = d.month - 1 + n
    y = d.year + total // 12
    m = total % 12 + 1
    return date(y, m, min(anchor_day, calendar.monthrange(y, m)[1]))


def occurrence(start, unit, every, k):
    every = max(1, every)
    if unit == "day":
        return start + timedelta(days=k * every)
    if unit == "week":
        return start + timedelta(days=7 * k * every)
    if unit == "month":
        return add_months(start, k * every, start.day)
    return add_months(start, 12 * k * every, start.day)


def _approx_days(unit, every):
    return {"day": 1, "week": 7, "month": 30.436875, "year": 365.2425}[unit] * max(1, every)


def first_index_on_or_after(start, unit, every, when):
    if when <= start:
        return 0
    k = max(0, int((when - start).days / _approx_days(unit, every)) - 1)
    while occurrence(start, unit, every, k) < when:
        k += 1
    while k > 0 and occurrence(start, unit, every, k - 1) >= when:
        k -= 1
    return k


def next_renewal(sub, today=None):
    if sub["status"] != "active":
        return None
    today = today or date.today()
    start = parse_date(sub["start"])
    return occurrence(start, sub["unit"], sub["every"], first_index_on_or_after(start, sub["unit"], sub["every"], today))


def upcoming(sub, count, today=None):
    if sub["status"] != "active":
        return []
    today = today or date.today()
    start = parse_date(sub["start"])
    k0 = first_index_on_or_after(start, sub["unit"], sub["every"], today)
    return [occurrence(start, sub["unit"], sub["every"], k0 + i) for i in range(count)]


def charges_between(sub, a, b):
    start = parse_date(sub["start"])
    end = b
    if sub["status"] != "active" and sub.get("status_date"):
        end = min(b, parse_date(sub["status_date"]) - timedelta(days=1))
    out = []
    if end < a:
        return out
    k = first_index_on_or_after(start, sub["unit"], sub["every"], a)
    while len(out) < 2000:
        d = occurrence(start, sub["unit"], sub["every"], k)
        if d > end:
            break
        out.append(d)
        k += 1
    return out


def charges_per_month(unit, every):
    every = max(1, every)
    return {"day": 30.436875, "week": 30.436875 / 7, "month": 1.0, "year": 1 / 12}[unit] / every


def monthly_cost(sub):
    return sub["price"] * charges_per_month(sub["unit"], sub["every"])


def spent_so_far(sub):
    return len(charges_between(sub, parse_date(sub["start"]), date.today())) * sub["price"]


def saved_since_cancel(sub):
    if sub["status"] != "cancelled" or not sub.get("status_date"):
        return 0.0
    days = max(0, (date.today() - parse_date(sub["status_date"])).days)
    return monthly_cost(sub) * days / 30.436875


def is_trial(sub):
    return sub.get("trial") and sub["status"] == "active" and parse_date(sub["start"]) > date.today()


def days_text(days):
    if days <= 0:
        return "Oggi"
    if days == 1:
        return "Domani"
    return "tra %d giorni" % days


def fmt_date(d, long=False):
    if long:
        return "%s %d %s %d" % (WEEKDAYS[d.weekday()], d.day, MONTHS_LONG[d.month - 1], d.year)
    return "%d %s" % (d.day, MONTHS_SHORT[d.month - 1])


def parse_price(text):
    t = "".join(c for c in (text or "") if c.isdigit() or c in ",.")
    if not t:
        return None
    sep = max(t.rfind(","), t.rfind("."))
    if sep == -1:
        return float(t)
    whole = t[:sep].replace(",", "").replace(".", "") or "0"
    return float(whole + "." + t[sep + 1:])


def money(value, currency="EUR", decimals=2):
    """Formato italiano: 1.234,56 €"""
    s = "{:,.{}f}".format(value, decimals).replace(",", "X").replace(".", ",").replace("X", ".")
    sym = CURRENCIES.get(currency, currency)
    return "%s %s" % (s, sym) if currency in ("EUR", "CHF") else "%s%s" % (sym, s)


def new_id():
    return "%x%s" % (int(time.time() * 1000), "".join(random.choice(string.ascii_lowercase) for _ in range(5)))


# ---------------------------------------------------------------- store

DEFAULT_SETTINGS = {
    "dark": False,
    "currency": "EUR",
    "budget": 0.0,
    "default_reminder": 3,
    "notifications": True,
    "premium": False,
    "onboarded": False,
}


class Store:
    def __init__(self, folder):
        self.path = os.path.join(folder, "maik_subs.json")
        self.subs = []
        self.settings = dict(DEFAULT_SETTINGS)
        self.notified = {}
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.subs = [s for s in data.get("subs", []) if isinstance(s, dict) and "name" in s]
            self.settings.update(data.get("settings", {}))
            self.notified = data.get("notified", {})
        except (OSError, ValueError):
            pass

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"subs": self.subs, "settings": self.settings, "notified": self.notified}, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    # --- abbonamenti
    def active(self):
        return [s for s in self.subs if s["status"] == "active"]

    def inactive(self):
        return [s for s in self.subs if s["status"] != "active"]

    def can_add(self):
        return self.settings["premium"] or len([s for s in self.subs if s["status"] != "cancelled"]) < FREE_LIMIT

    def get(self, sub_id):
        for s in self.subs:
            if s["id"] == sub_id:
                return s
        return None

    def add(self, sub):
        self.subs.insert(0, sub)
        self.save()

    def update(self, sub_id, **patch):
        s = self.get(sub_id)
        if not s:
            return
        if "price" in patch and patch["price"] != s["price"]:
            s.setdefault("history", []).append([date.today().isoformat(), s["price"]])
        s.update(patch)
        self.save()

    def remove(self, sub_id):
        s = self.get(sub_id)
        if s:
            self.subs.remove(s)
            self.save()
        return s

    def month_total(self):
        return sum(monthly_cost(s) for s in self.active())

    def by_category(self):
        totals = {}
        for s in self.active():
            totals[s["category"]] = totals.get(s["category"], 0.0) + monthly_cost(s)
        return sorted(totals.items(), key=lambda kv: -kv[1])

    def months_forecast(self, past=False):
        base = date.today().replace(day=1)
        out = []
        for i in range(12):
            m = add_months(base, i - 11 if past else i, 1)
            end = add_months(m, 1, 1) - timedelta(days=1)
            value = sum(len(charges_between(s, m, end)) * s["price"] for s in self.subs)
            out.append((MONTHS_SHORT[m.month - 1][0].upper(), value))
        return out

    def due_reminders(self):
        """Promemoria da mostrare oggi: (chiave, titolo, testo)."""
        out = []
        today = date.today()
        for s in self.active():
            nxt = next_renewal(s)
            days = (nxt - today).days
            for r in s.get("reminders", [3]):
                if days <= r:
                    key = "%s|%s" % (s["id"], nxt.isoformat())
                    if key in self.notified:
                        break
                    when = "oggi" if days == 0 else "domani" if days == 1 else "tra %d giorni" % days
                    if is_trial(s):
                        title = "La prova di %s termina %s" % (s["name"], when)
                        body = "Poi pagherai %s. Disdici ora se non ti serve." % money(s["price"], self.settings["currency"])
                    else:
                        title = "%s si rinnova %s" % (s["name"], when)
                        body = "%s · %s" % (money(s["price"], self.settings["currency"]), cycle_label(s["unit"], s["every"]))
                    out.append((key, title, body))
                    break
        return out

    def load_sample(self):
        t = date.today()

        def mk(sid, start, **extra):
            _, name, color, cat, price, unit, every = find_service(sid)
            d = dict(id=new_id(), service=sid, name=name, color=color, category=cat, price=price, unit=unit,
                     every=every, start=start.isoformat(), trial=False, status="active", status_date=None,
                     reminders=[3], notes="", history=[])
            d.update(extra)
            return d

        self.subs = [
            mk("netflix", add_months(t + timedelta(days=3), -14), history=[[add_months(t, -5).isoformat(), 12.99]]),
            mk("spotify", add_months(t + timedelta(days=9), -20)),
            mk("gym", add_months(t + timedelta(days=1), -7)),
            mk("icloud", add_months(t + timedelta(days=17), -30), price=2.99),
            mk("m365", add_months(t + timedelta(days=46), -12)),
            mk("disney", t + timedelta(days=5), trial=True, reminders=[2]),
            mk("dazn", add_months(t, -8), status="cancelled", status_date=add_months(t, -2).isoformat()),
        ]
        self.save()

    def reset(self):
        self.subs = []
        self.notified = {}
        self.save()
