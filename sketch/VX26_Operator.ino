/*
  ================================================================
   VX-26 OPERATOR - Interfaccia HUD futuristica stile post-apocalittico (2026)
   Scheda: ESP32-2432S028R "Cheap Yellow Display" (320x240 + touch)
  ================================================================

  LIBRERIE (Library Manager):
    - TFT_eSPI (Bodmer)               -> usa il file User_Setup.h fornito
    - XPT2046_Touchscreen (Paul Stoffregen)
    (WiFi, BLE, Preferences sono gia' incluse nel core ESP32)

  IMPOSTAZIONI SCHEDA (menu Strumenti):
    - Scheda: "ESP32 Dev Module"
    - Partition Scheme: "Huge APP (3MB No OTA/1MB SPIFFS)"   <-- OBBLIGATORIO (WiFi+BT sono grandi)

  FUNZIONI:
    STAT  : STATO (figura animata + sensori) | SISTEMA (info chip, rete) | CONFIG (tema, luminosita', suono, CRT, WiFi)
    INV   : ARMI | ATTREZZI | AIUTI
    DATA  : ORA (orologio NTP) | MISSIONI | LOG eventi
    MAP   : radar animato con reti WiFi e dispositivi Bluetooth reali (TUTTI | WIFI | BT)
    RADIO : WIFI (scansione + connessione con tastiera) | BLUETOOTH (scansione BLE)
*/

#include <SPI.h>
#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>
#include <WiFi.h>
#include <Preferences.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <time.h>

// ---------------- PIN CYD ----------------
#define XPT2046_IRQ  36
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK  25
#define XPT2046_CS   33
#define LDR_PIN      34
#define LED_R 4
#define LED_G 16
#define LED_B 17
#define SPK_PIN 26
#define BL_PIN  21

// Calibrazione touch (aggiusta se i tocchi risultano spostati)
#define TS_MINX 200
#define TS_MAXX 3700
#define TS_MINY 240
#define TS_MAXY 3800

// Fuso orario (Italia) e server NTP
#define TZ_INFO "CET-1CEST,M3.5.0,M10.5.0/3"
#define NTP1 "pool.ntp.org"
#define NTP2 "time.google.com"

// ---------------- OGGETTI ----------------
TFT_eSPI tft;
TFT_eSprite spr(&tft);           // framebuffer 4 bit (16 colori) -> niente sfarfallio
SPIClass touchSPI(VSPI);
XPT2046_Touchscreen ts(XPT2046_CS, XPT2046_IRQ);
Preferences prefs;

// Indici della palette (0-7 normali, 8-15 versioni scure per le scanline)
enum { BG = 0, C_FAINT, C_DARK, C_DIM2, C_DIM, C_MID, C_MAIN, C_HI };
uint16_t pal[16];

struct Theme { const char* name; uint8_t r, g, b; };
Theme THEMES[] = {
  {"VERDE",  30, 255,  70},
  {"AMBRA", 255, 170,  20},
  {"CIANO",   0, 230, 255},
  {"BIANCO",225, 255, 235},
  {"ROSSO", 255,  60,  40},
};
const int THEME_N = sizeof(THEMES) / sizeof(THEMES[0]);

struct Config {
  int theme = 0;
  int bright = 220;
  bool sound = true;
  bool crt = true;
  String ssid, pass;
} cfg;

// ---------------- NAVIGAZIONE ----------------
const char* TABS[5] = {"STAT", "INV", "DATA", "MAP", "RADIO"};
const char* SUBS[5][3] = {
  {"STATO", "SISTEMA", "CONFIG"},
  {"ARMI", "ATTREZZI", "AIUTI"},
  {"ORA", "MISSIONI", "LOG"},
  {"TUTTI", "WIFI", "BT"},
  {"WIFI", "BLUETOOTH", nullptr},
};
const int SUBN[5] = {3, 3, 3, 3, 2};
int tab = 0, sub[5] = {0, 0, 0, 0, 0};
int subX0[3], subX1[3];

enum Modal { M_NONE, M_KB, M_CONN, M_MSG };
Modal modal = M_NONE;
String msgL1, msgL2;

bool dirty = true;
unsigned long lastFrame = 0, lastStats = 0;
unsigned long glitchUntil = 0;   // disturbo al cambio scheda
uint8_t vigInset[240];            // angoli arrotondati del tubo catodico

// ---------------- INVENTARIO ----------------
struct Item { const char* name; float w; int v; const char* d1; const char* d2; };
Item ARMI[] = {
  {"Tubo di piombo", 3.0,   8, "Pesante e",      "affidabile."},
  {"Fionda",         0.5,   5, "Munizioni:",     "sassi. Tanti."},
  {"Pistola laser",  2.0, 120, "Cella al 60%.",  "Non guardare."},
  {"Mazza chiodata", 4.0,  25, "Fatta in casa.", "Con amore."},
  {"Coltello",       0.5,  12, "Taglia anche",   "il pane."},
};
Item ATTREZZI[] = {
  {"Nastro adesivo", 0.2, 12, "Ripara tutto.",  "Quasi."},
  {"Chiave inglese", 2.0, 15, "Arma o utensile","a seconda."},
  {"Cella energia",  0.3, 30, "Carica: 87%",    "Non leccare."},
  {"Parti radio",    0.8, 22, "Utili per il",   "trasmettitore."},
  {"Torcia",         0.6, 18, "Batteria quasi", "scarica."},
};
Item AIUTI[] = {
  {"Medkit",          0.5, 40, "Ripristina la", "salute."},
  {"Fagioli in latta",1.0,  5, "Scaduti nel",   "2031. Forse."},
  {"Acqua pulita",    1.0, 20, "Rara come",     "l'oro."},
  {"Antiradiazioni",  0.1, 60, "Sapore di",     "metallo."},
  {"Caffe' solubile", 0.2, 10, "Per i turni",   "di notte."},
};
Item* INV[3] = {ARMI, ATTREZZI, AIUTI};
const int INV_N = 5;
int invSel[3] = {0, 0, 0};

// ---------------- MISSIONI / LOG ----------------
const char* QUESTS[5] = {"Trovare acqua pulita", "Riparare la radio", "Mappare le reti vicine",
                         "Contattare altri sopravvissuti", "Tornare al rifugio"};
bool qDone[5] = {true, false, false, false, false};
String logs[8];
int logN = 0;

// ---------------- SENSORI ----------------
int sRam = 0, sLight = 0, sSig = 0;
float sTemp = 0;

// ---------------- WIFI ----------------
#define MAXNETS 20
struct Net { String ssid; int rssi; int ch; bool enc; };
Net nets[MAXNETS];
int netCount = 0, netScroll = 0;
bool wifiScanning = false;
String connSsid, connPass;
unsigned long connStart = 0;

// ---------------- BLUETOOTH ----------------
#define MAXBT 30
struct BDev { char name[24]; char addr[18]; int rssi; };
BDev bdevs[MAXBT];
volatile int bdevCount = 0;
volatile bool btScanning = false;
bool bleReady = false;
int btScroll = 0, btSel = -1;
portMUX_TYPE btMux = portMUX_INITIALIZER_UNLOCKED;

// ---------------- TASTIERA ----------------
const char* KB_L[4] = {"1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm._@"};
const char* KB_U[4] = {"!#$%&*()+=", "QWERTYUIOP", "ASDFGHJKL_", "ZXCVBNM,?/"};
bool kbShift = false;
String kbText, kbSsid;
int kbFlash = -1;
unsigned long kbFlashT = 0;
#define KB_Y 54
#define KB_H 32
struct KSpec { int x, w; const char* l; };
KSpec KSPEC[5] = {{0, 62, "SHIFT"}, {64, 94, "SPAZIO"}, {160, 62, "CANC"}, {224, 46, "ESC"}, {272, 47, "OK"}};

// Prototipi
void startWifiScan();
void startBtScan();
void arrowBtnH(int x, int y, int w, int h, bool left);

// =================================================================
//  UTILITA'
// =================================================================
String two(int v) { return (v < 10 ? "0" : "") + String(v); }

String uptimeStr() {
  unsigned long s = millis() / 1000;
  return two(s / 3600) + ":" + two((s / 60) % 60) + ":" + two(s % 60);
}

bool getNow(struct tm& ti) {
  time_t t = time(nullptr);
  if (t < 1700000000) return false;
  localtime_r(&t, &ti);
  return true;
}

String shortTime() {
  struct tm ti;
  if (getNow(ti)) return two(ti.tm_hour) + ":" + two(ti.tm_min);
  unsigned long s = millis() / 1000;
  return two((s / 60) % 100) + ":" + two(s % 60);
}

uint32_t hashStr(const char* s) {
  uint32_t h = 5381;
  while (*s) h = h * 33 + (uint8_t)*s++;
  return h;
}

void addLog(const String& s) {
  String e = "[" + shortTime() + "] " + s;
  if (logN < 8) logs[logN++] = e;
  else { for (int i = 0; i < 7; i++) logs[i] = logs[i + 1]; logs[7] = e; }
  Serial.println(e);
  dirty = true;
}

void click() {
  if (!cfg.sound) return;
  for (int i = 0; i < 12; i++) {
    digitalWrite(SPK_PIN, HIGH); delayMicroseconds(180);
    digitalWrite(SPK_PIN, LOW);  delayMicroseconds(180);
  }
}

bool inRect(int x, int y, int rx, int ry, int rw, int rh) {
  return x >= rx && x < rx + rw && y >= ry && y < ry + rh;
}

void saveConfig() {
  prefs.putInt("theme", cfg.theme);
  prefs.putInt("bright", cfg.bright);
  prefs.putBool("sound", cfg.sound);
  prefs.putBool("crt", cfg.crt);
  prefs.putString("ssid", cfg.ssid);
  prefs.putString("pass", cfg.pass);
}

void loadConfig() {
  cfg.theme  = constrain(prefs.getInt("theme", 0), 0, THEME_N - 1);
  cfg.bright = constrain(prefs.getInt("bright", 220), 20, 255);
  cfg.sound  = prefs.getBool("sound", true);
  cfg.crt    = prefs.getBool("crt", true);
  cfg.ssid   = prefs.getString("ssid", "");
  cfg.pass   = prefs.getString("pass", "");
}

void applyTheme() {
  const float f[8] = {0.04, 0.10, 0.18, 0.30, 0.45, 0.62, 0.85, 1.0};
  Theme& t = THEMES[cfg.theme];
  for (int i = 0; i < 8; i++) {
    float k = f[i], d = f[i] * 0.72;
    pal[i]     = tft.color565((uint8_t)(t.r * k), (uint8_t)(t.g * k), (uint8_t)(t.b * k));
    pal[i + 8] = tft.color565((uint8_t)(t.r * d), (uint8_t)(t.g * d), (uint8_t)(t.b * d));
  }
  spr.createPalette(pal, 16);
}

void applyBrightness() { analogWrite(BL_PIN, cfg.bright); }

// =================================================================
//  PRIMITIVE GRAFICHE
// =================================================================
void txt(const String& s, int x, int y, uint8_t c, uint8_t datum = TL_DATUM, uint8_t font = 2) {
  spr.setTextColor(c);
  spr.setTextDatum(datum);
  spr.drawString(s, x, y, font);
}

// testo con alone luminoso (effetto fosforo)
void txtG(const String& s, int x, int y, uint8_t c, uint8_t datum = TL_DATUM, uint8_t font = 2) {
  if (cfg.crt) {
    txt(s, x - 1, y, C_DIM2, datum, font);
    txt(s, x + 1, y, C_DIM2, datum, font);
    txt(s, x, y - 1, C_DIM2, datum, font);
    txt(s, x, y + 1, C_DIM2, datum, font);
  }
  txt(s, x, y, c, datum, font);
}

void dotted(int x0, int y0, int x1, int y1, uint8_t c) {
  int n = max(abs(x1 - x0), abs(y1 - y0));
  for (int i = 0; i <= n; i += 3) spr.drawPixel(x0 + (x1 - x0) * i / max(n, 1), y0 + (y1 - y0) * i / max(n, 1), c);
}

// pannello con angoli smussati (stile HUD)
void chamfer(int x, int y, int w, int h, int c, uint8_t col) {
  spr.drawFastHLine(x + c, y, w - 2 * c, col);
  spr.drawFastHLine(x + c, y + h - 1, w - 2 * c, col);
  spr.drawFastVLine(x, y + c, h - 2 * c, col);
  spr.drawFastVLine(x + w - 1, y + c, h - 2 * c, col);
  spr.drawLine(x, y + c, x + c, y, col);
  spr.drawLine(x + w - 1 - c, y, x + w - 1, y + c, col);
  spr.drawLine(x, y + h - 1 - c, x + c, y + h - 1, col);
  spr.drawLine(x + w - 1 - c, y + h - 1, x + w - 1, y + h - 1 - c, col);
}

void chamferFill(int x, int y, int w, int h, int c, uint8_t col) {
  spr.fillRect(x, y + c, w, h - 2 * c, col);
  for (int i = 0; i < c; i++) {
    spr.drawFastHLine(x + c - i, y + i, w - 2 * (c - i), col);
    spr.drawFastHLine(x + c - i, y + h - 1 - i, w - 2 * (c - i), col);
  }
}

// staffe agli angoli di un'area
void brackets(int x, int y, int w, int h, int l, uint8_t col) {
  spr.drawFastHLine(x, y, l, col);             spr.drawFastVLine(x, y, l, col);
  spr.drawFastHLine(x + w - l, y, l, col);     spr.drawFastVLine(x + w - 1, y, l, col);
  spr.drawFastHLine(x, y + h - 1, l, col);     spr.drawFastVLine(x, y + h - l, l, col);
  spr.drawFastHLine(x + w - l, y + h - 1, l, col); spr.drawFastVLine(x + w - 1, y + h - l, l, col);
}

// indicatore circolare a tacche (270 gradi)
void ring(int cx, int cy, int r, int pct) {
  const int N = 36;
  int on = (constrain(pct, 0, 100) * N + 50) / 100;
  for (int i = 0; i < N; i++) {
    float a = (135 + i * 270.0 / (N - 1)) * DEG_TO_RAD;
    uint8_t c = i < on ? (i == on - 1 ? C_HI : C_MAIN) : C_DARK;
    spr.drawLine(cx + cos(a) * (r - 5), cy + sin(a) * (r - 5), cx + cos(a) * r, cy + sin(a) * r, c);
  }
  spr.drawCircle(cx, cy, r - 8, C_FAINT);
}

// griglia di punti sullo sfondo
void bgGrid() {
  for (int y = 55; y < 215; y += 20)
    for (int x = 10; x < 320; x += 20) spr.drawPixel(x, y, C_DIM2);
}

void chirp() {
  if (!cfg.sound) return;
  for (int f = 2600; f > 900; f -= 170) {
    int half = 500000 / f;
    for (int i = 0; i < 3; i++) {
      digitalWrite(SPK_PIN, HIGH); delayMicroseconds(half);
      digitalWrite(SPK_PIN, LOW);  delayMicroseconds(half);
    }
  }
}

void initVignette() {
  const int R = 26;
  for (int y = 0; y < 240; y++) {
    int d = y < R ? R - y : (y > 239 - R ? y - (239 - R) : 0);
    vigInset[y] = d ? (uint8_t)(R - sqrtf((float)(R * R - d * d))) : 0;
  }
}

void button(int x, int y, int w, int h, const char* label, bool active = false) {
  if (active) {
    chamferFill(x, y, w, h, 4, C_MAIN);
    txt(label, x + w / 2, y + h / 2 + 1, BG, MC_DATUM);
  } else {
    chamfer(x, y, w, h, 4, C_MAIN);
    txt(label, x + w / 2, y + h / 2 + 1, C_MAIN, MC_DATUM);
  }
}

void arrowBtn(int x, int y, int w, int h, bool up) {
  chamfer(x, y, w, h, 4, C_MAIN);
  int cx = x + w / 2, cy = y + h / 2;
  if (up) spr.fillTriangle(cx, cy - 5, cx - 6, cy + 4, cx + 6, cy + 4, C_MAIN);
  else    spr.fillTriangle(cx, cy + 5, cx - 6, cy - 4, cx + 6, cy - 4, C_MAIN);
}

void segBar(int x, int y, int w, int h, int pct, int segs = 20) {
  int sw = w / segs;
  int on = (constrain(pct, 0, 100) * segs + 50) / 100;
  for (int i = 0; i < segs; i++)
    spr.fillRect(x + i * sw, y, sw - 2, h, i < on ? C_MAIN : C_DARK);
}

void rssiBars(int x, int yBottom, int rssi) {
  int lvl = rssi > -55 ? 4 : rssi > -67 ? 3 : rssi > -78 ? 2 : 1;
  for (int b = 0; b < 4; b++) {
    int h = (b + 1) * 3;
    spr.fillRect(x + b * 6, yBottom - h, 4, h, b < lvl ? C_MAIN : C_DARK);
  }
}

void drawLock(int x, int y, uint8_t c) {
  spr.drawRoundRect(x + 1, y, 6, 8, 3, c);
  spr.fillRect(x, y + 5, 8, 6, c);
}

void scanAnim(int cy, const char* label) {
  txt(label, 160, cy - 14, C_MAIN, MC_DATUM);
  int p = (millis() / 70) % 24;
  for (int i = 0; i < 20; i++) {
    int d = abs(i - (p - 2));
    uint8_t c = d == 0 ? C_HI : d == 1 ? C_MAIN : d == 2 ? C_DIM : C_DARK;
    spr.fillRect(60 + i * 10, cy, 8, 8, c);
  }
}

// Effetto CRT: scanline + glitch casuale, poi invio al display
static inline uint8_t brighten(uint8_t c) { return (c > 0 && c < 7) ? c + 1 : c; }

// Effetto monitor CRT: banda di refresh, rumore, disturbi, scanline, angoli curvi, sfarfallio
// Effetto olografico: interlacciatura leggera, linea di scansione, glitch digitale al cambio scheda
void present() {
  if (cfg.crt) {
    uint8_t* buf = (uint8_t*)spr.getPointer();
    unsigned long now = millis();
    bool gl = now < glitchUntil;

    int sy = (int)((now / 6) % 400);                    // linea di scansione olografica
    if (sy < 240) {
      uint8_t* row = buf + sy * 160;
      for (int i = 0; i < 160; i++) {
        uint8_t b = row[i], h = b >> 4, l = b & 15;
        if (h < 7) h = h ? h + 2 : 2;
        if (l < 7) l = l ? l + 2 : 2;
        row[i] = (min((int)h, 7) << 4) | min((int)l, 7);
      }
    }

    if (gl) {                                           // glitch digitale a blocchi
      for (int k = 0; k < 10; k++) {
        int y0 = random(0, 230), hh = random(2, 12), sh = random(2, 20);
        for (int y = y0; y < min(240, y0 + hh); y++) {
          uint8_t* row = buf + y * 160;
          memmove(row + sh, row, 160 - sh);
          memset(row, 0, sh);
        }
      }
      for (int k = 0; k < 6; k++) spr.fillRect(random(320), random(240), random(4, 30), random(1, 4), random(2, 7));
    }

    for (int y = 1; y < 240; y += 2) {                  // interlacciatura leggera
      uint8_t* row = buf + y * 160;
      for (int i = 0; i < 160; i++) {
        uint8_t b = row[i], h = b >> 4, l = b & 15;
        if (h > 0 && h < 8) h += 8;
        if (l > 0 && l < 8) l += 8;
        row[i] = (h << 4) | l;
      }
    }
  }
  spr.pushSprite(0, 0);
}

// =================================================================
//  HEADER / SOTTOSCHEDE / FOOTER
// =================================================================
void drawHeader() {
  for (int i = 0; i < 5; i++) {
    int cx = i * 64 + 32;
    if (i == tab) {
      int x0 = i * 64 + 4, x1 = x0 + 56;
      spr.fillTriangle(x0 + 6, 3, x1, 3, x0, 20, C_MAIN);
      spr.fillTriangle(x1, 3, x1 - 6, 20, x0, 20, C_MAIN);
      txt(TABS[i], cx, 12, BG, MC_DATUM);
    } else {
      txt(TABS[i], cx, 12, C_DIM, MC_DATUM);
      spr.drawFastHLine(cx - 4, 20, 9, C_DIM2);
    }
  }
  spr.drawFastHLine(8, 23, 304, C_MID);
  spr.drawFastHLine(8, 24, 304, C_DIM2);
  spr.fillTriangle(0, 21, 0, 26, 5, 23, C_MAIN);
  spr.fillTriangle(319, 21, 319, 26, 314, 23, C_MAIN);
}

void drawSubtabs() {
  int n = SUBN[tab], gap = 20, tot = 0, w[3];
  for (int i = 0; i < n; i++) { w[i] = spr.textWidth(SUBS[tab][i], 2); tot += w[i]; }
  tot += gap * (n - 1);
  int x = 160 - tot / 2;
  for (int i = 0; i < n; i++) {
    int d = abs(i - sub[tab]);
    txt(SUBS[tab][i], x, 27, d == 0 ? C_HI : d == 1 ? C_DIM : C_DIM2);
    if (d == 0) spr.drawFastHLine(x, 43, w[i], C_MID);
    subX0[i] = x - gap / 2;
    subX1[i] = x + w[i] + gap / 2;
    x += w[i] + gap;
  }
}

void tag(int x, int w, const char* s, bool on, bool blink) {
  bool lit = on || (blink && (millis() / 300) % 2);
  if (lit) { spr.fillRect(x, 223, w, 14, C_MAIN); txt(s, x + w / 2, 230, C_DARK, MC_DATUM, 1); }
  else     { spr.drawRect(x, 223, w, 14, C_DIM2); txt(s, x + w / 2, 230, C_DIM2, MC_DATUM, 1); }
}

void drawFooter() {
  struct tm ti;
  String clk = getNow(ti) ? two(ti.tm_hour) + ":" + two(ti.tm_min) + ":" + two(ti.tm_sec) : uptimeStr();
  bool wc = WiFi.status() == WL_CONNECTED;
  chamferFill(0, 219, 92, 21, 5, C_DARK);
  txtG(clk, 46, 230, C_HI, MC_DATUM);
  chamferFill(95, 219, 130, 21, 5, C_DARK);
  tag(101, 36, "WIFI", wc, wifiScanning || modal == M_CONN);
  tag(141, 24, "BT", false, btScanning);
  txt("RAM " + String(sRam) + "%", 196, 230, C_MAIN, MC_DATUM, 1);
  chamferFill(228, 219, 92, 21, 5, C_DARK);
  String ip = wc ? WiFi.localIP().toString() : String("OFFLINE");
  txt(ip, 274, 230, wc ? C_MAIN : C_DIM, MC_DATUM, ip.length() > 12 ? 1 : 2);
}

// =================================================================
//  STAT
// =================================================================
void updateStats() {
  sRam = (int)((uint64_t)ESP.getFreeHeap() * 100 / ESP.getHeapSize());
  sTemp = temperatureRead();
  sLight = constrain(100 - analogRead(LDR_PIN) * 100 / 4095, 0, 100);
  sSig = WiFi.status() == WL_CONNECTED ? constrain(map(WiFi.RSSI(), -100, -40, 0, 100), 0, 100) : 0;
}

// Sopravvissuto in tuta con casco (disegno originale) + barre condizione con linee guida
void drawFigure(int cx, int cy) {
  int b = (int)(sin(millis() / 450.0) * 2.0);   // respiro
  int a = (int)(sin(millis() / 700.0) * 3);     // oscillazione braccia
  cy += b;
  int hy = cy - 56, ty = cy - 38;

  // casco e visiera
  spr.drawCircle(cx, hy, 13, C_MAIN);
  spr.drawCircleHelper(cx, hy - 1, 16, 1 | 2, C_MAIN);
  spr.drawCircleHelper(cx, hy - 1, 15, 1 | 2, C_MID);
  spr.drawFastHLine(cx - 16, hy - 1, 33, C_MAIN);
  spr.fillRect(cx - 2, hy - 17, 5, 3, C_MAIN);
  spr.drawRoundRect(cx - 10, hy + 1, 21, 7, 3, C_HI);
  spr.fillRect(cx - 7, hy + 3, 4, 3, C_MID);
  // respiratore e collo
  spr.drawRect(cx - 4, hy + 9, 9, 4, C_MAIN);
  spr.drawFastVLine(cx - 4, hy + 13, 4, C_MAIN);
  spr.drawFastVLine(cx + 4, hy + 13, 4, C_MAIN);

  // busto (tuta)
  spr.drawLine(cx - 20, ty + 4, cx - 6, ty, C_MAIN);
  spr.drawLine(cx + 20, ty + 4, cx + 6, ty, C_MAIN);
  spr.drawFastHLine(cx - 6, ty, 13, C_MAIN);
  spr.drawLine(cx - 20, ty + 4, cx - 15, ty + 38, C_MAIN);
  spr.drawLine(cx + 20, ty + 4, cx + 15, ty + 38, C_MAIN);
  spr.drawFastVLine(cx, ty + 1, 29, C_DIM);
  spr.drawRect(cx - 14, ty + 9, 9, 8, C_DIM);
  spr.drawFastHLine(cx + 5, ty + 11, 9, C_DIM);
  spr.drawFastHLine(cx + 5, ty + 14, 9, C_DIM);
  spr.fillRect(cx - 16, ty + 30, 33, 5, C_MAIN);
  spr.fillRect(cx - 3, ty + 30, 7, 5, C_HI);

  // braccia (doppia linea) e guanti
  for (int k = 0; k < 2; k++) {
    uint8_t c = k ? C_MID : C_MAIN;
    spr.drawLine(cx - 20 - k, ty + 5, cx - 29 - k, ty + 22 + a, c);
    spr.drawLine(cx - 29 - k, ty + 22 + a, cx - 27 - k, ty + 38 + a, c);
    spr.drawLine(cx + 20 + k, ty + 5, cx + 29 + k, ty + 22 - a, c);
    spr.drawLine(cx + 29 + k, ty + 22 - a, cx + 27 + k, ty + 38 - a, c);
  }
  spr.fillCircle(cx - 28, ty + 41 + a, 4, C_MAIN);
  spr.fillCircle(cx + 28, ty + 41 - a, 4, C_MAIN);

  // gambe e stivali
  for (int k = 0; k < 2; k++) {
    uint8_t c = k ? C_MID : C_MAIN;
    spr.drawLine(cx - 11 - k, ty + 35, cx - 13 - k, cy + 38 - b, c);
    spr.drawLine(cx - 3 + k, ty + 35, cx - 5 + k, cy + 38 - b, c);
    spr.drawLine(cx + 11 + k, ty + 35, cx + 13 + k, cy + 38 - b, c);
    spr.drawLine(cx + 3 - k, ty + 35, cx + 5 - k, cy + 38 - b, c);
  }
  spr.fillRoundRect(cx - 18, cy + 37 - b, 14, 7, 2, C_MAIN);
  spr.fillRoundRect(cx + 4, cy + 37 - b, 14, 7, 2, C_MAIN);

  // barre condizione: posizione barra, punto dell'arto collegato, valore
  int bars[6][5] = {
    {cx - 12, hy - 30, cx,      hy - 18,      22},
    {cx - 64, ty + 14, cx - 30, ty + 20 + a,  18},
    {cx + 40, ty + 14, cx + 30, ty + 20 - a,  22},
    {cx - 60, cy + 24, cx - 13, cy + 22,      14},
    {cx + 36, cy + 24, cx + 13, cy + 22,      20},
    {cx - 12, cy + 52, cx,      ty + 36,      22},
  };
  // piattaforma olografica e scansione
  spr.drawEllipse(cx, cy + 47 - b, 34, 6, C_MID);
  spr.drawEllipse(cx, cy + 47 - b, 24, 4, C_DIM2);
  int scan = 48 + (int)((millis() / 14) % 140);
  spr.drawFastHLine(6, scan, 124, C_HI);
  spr.drawFastHLine(6, scan - 1, 124, C_MID);
  spr.drawFastHLine(6, scan - 3, 124, C_DIM2);
  for (int i = 0; i < 6; i++) {
    int bx = bars[i][0], by = bars[i][1];
    spr.drawRect(bx, by, 24, 5, C_DIM);
    spr.fillRect(bx + 1, by + 1, bars[i][4], 3, C_MAIN);
    if (i == 1 || i == 3) dotted(bx + 25, by + 2, bars[i][2], bars[i][3], C_DIM2);
    if (i == 2 || i == 4) dotted(bx - 2, by + 2, bars[i][2], bars[i][3], C_DIM2);
  }
}

void drawStato() {
  brackets(2, 46, 132, 146, 8, C_DIM);
  drawFigure(68, 130);
  const char* lb[4] = {"MEMORIA", "CPU", "LUCE", "SEGNALE"};
  String sv[4] = {String(sRam) + "%", String((int)sTemp) + "C", String(sLight) + "%",
                  WiFi.status() == WL_CONNECTED ? String(WiFi.RSSI()) : String("--")};
  int sp[4] = {sRam, constrain((int)sTemp, 0, 100), sLight, sSig};
  for (int i = 0; i < 4; i++) {
    int gx = 182 + (i % 2) * 90, gy = 80 + (i / 2) * 70;
    ring(gx, gy, 26, sp[i]);
    txtG(sv[i], gx, gy + 1, C_HI, MC_DATUM);
    txt(lb[i], gx, gy + 28, C_DIM, MC_DATUM, 1);
  }
  unsigned long s = millis() / 1000;
  int hp = sTemp > 70 ? constrain(100 - (int)((sTemp - 70) * 3), 10, 100) : 100;
  chamferFill(0, 195, 100, 20, 5, C_DARK);
  txtG("HP " + String(hp) + "/100", 50, 205, C_HI, MC_DATUM);
  chamferFill(103, 195, 114, 20, 5, C_DARK);
  txtG("LIV " + String(1 + s / 300), 110, 205, C_HI, ML_DATUM);
  segBar(160, 201, 54, 8, (s % 300) * 100 / 300, 6);
  chamferFill(220, 195, 100, 20, 5, C_DARK);
  txtG("UP " + String(s / 3600) + "h" + two((s / 60) % 60), 270, 205, C_HI, MC_DATUM);
}

void drawSistema() {
  bool wc = WiFi.status() == WL_CONNECTED;
  String L[9] = {"CHIP", "CPU", "FLASH", "RAM LIBERA", "RAM MINIMA", "MAC", "IP", "RETE", "SDK"};
  String V[9] = {
    String(ESP.getChipModel()) + " r" + String(ESP.getChipRevision()),
    String(ESP.getChipCores()) + " core @ " + String(getCpuFrequencyMhz()) + "MHz",
    String(ESP.getFlashChipSize() / 1048576) + " MB",
    String(ESP.getFreeHeap() / 1024) + " KB",
    String(ESP.getMinFreeHeap() / 1024) + " KB",
    WiFi.macAddress(),
    wc ? WiFi.localIP().toString() : String("-"),
    wc ? WiFi.SSID().substring(0, 16) + " " + String(WiFi.RSSI()) : String("non connesso"),
    String(ESP.getSdkVersion()).substring(0, 18),
  };
  for (int i = 0; i < 9; i++) {
    int y = 47 + i * 18;
    txt(L[i], 8, y, C_DIM);
    txt(V[i], 314, y, C_MAIN, TR_DATUM);
    spr.drawFastHLine(8, y + 16, 306, C_FAINT);
  }
}

void drawConfig() {
  const char* L[5] = {"TEMA", "LUMINOSITA'", "SUONO", "EFFETTO OLO", "WIFI SALVATO"};
  for (int i = 0; i < 5; i++) {
    int y = 50 + i * 32;
    txt(L[i], 8, y + 13, C_MAIN, ML_DATUM);
    spr.drawFastHLine(8, y + 28, 306, C_FAINT);
  }
  int y = 50;
  arrowBtnH(176, y, 30, 24, true);
  txt(THEMES[cfg.theme].name, 248, y + 13, C_HI, MC_DATUM);
  arrowBtnH(290, y, 30, 24, false);
  y += 32;
  button(176, y, 30, 24, "-");
  segBar(212, y + 8, 74, 8, (cfg.bright - 20) * 100 / 235, 8);
  button(290, y, 30, 24, "+");
  y += 32;
  button(230, y, 90, 24, cfg.sound ? "ON" : "OFF", cfg.sound);
  y += 32;
  button(230, y, 90, 24, cfg.crt ? "ON" : "OFF", cfg.crt);
  y += 32;
  String s = cfg.ssid.length() ? cfg.ssid.substring(0, 12) : String("-");
  txt(s, 120, y + 13, C_DIM, ML_DATUM);
  button(230, y, 90, 24, "DIMENTICA");
}

// freccia sinistra/destra (per il tema)
void arrowBtnH(int x, int y, int w, int h, bool left) {
  chamfer(x, y, w, h, 4, C_MAIN);
  int cx = x + w / 2, cy = y + h / 2;
  if (left) spr.fillTriangle(cx - 5, cy, cx + 4, cy - 6, cx + 4, cy + 6, C_MAIN);
  else      spr.fillTriangle(cx + 5, cy, cx - 4, cy - 6, cx - 4, cy + 6, C_MAIN);
}

// =================================================================
//  INV
// =================================================================
void drawInv() {
  int c = sub[1];
  Item* list = INV[c];
  for (int i = 0; i < INV_N; i++) {
    int y = 50 + i * 26;
    bool s = (i == invSel[c]);
    if (s) {
      spr.fillRect(4, y, 164, 22, C_MAIN);
      txt(list[i].name, 10, y + 12, BG, ML_DATUM);
    } else {
      txt(list[i].name, 10, y + 12, C_MAIN, ML_DATUM);
    }
  }
  Item& it = list[invSel[c]];
  chamfer(176, 48, 140, 164, 8, C_DIM);
  txt("PESO", 184, 56, C_DIM);
  txt("VALORE", 184, 76, C_DIM);
  txt(String(it.w, 1), 308, 56, C_HI, TR_DATUM);
  txt(String(it.v), 308, 76, C_HI, TR_DATUM);
  spr.drawFastHLine(182, 98, 128, C_DIM2);
  txt(it.d1, 184, 106, C_MAIN);
  txt(it.d2, 184, 124, C_MAIN);
  // icona generica animata
  int bx = 224, by = 150, k = (millis() / 150) % 44;
  brackets(bx - 4, by - 4, 52, 52, 8, C_MAIN);
  spr.drawCircle(bx + 22, by + 22, 16, C_DIM);
  spr.drawCircle(bx + 22, by + 22, 6, C_MAIN);
  spr.drawLine(bx, by + 22, bx + 43, by + 22, C_DIM2);
  spr.drawLine(bx + 22, by, bx + 22, by + 43, C_DIM2);
  spr.drawFastHLine(bx + 1, by + k, 42, C_MID);
}

// =================================================================
//  DATA
// =================================================================
const char* GIORNI[7] = {"DOMENICA", "LUNEDI'", "MARTEDI'", "MERCOLEDI'", "GIOVEDI'", "VENERDI'", "SABATO"};
const char* MESI[12] = {"GEN", "FEB", "MAR", "APR", "MAG", "GIU", "LUG", "AGO", "SET", "OTT", "NOV", "DIC"};

void drawOra() {
  struct tm ti;
  if (getNow(ti)) {
    txtG(two(ti.tm_hour) + ":" + two(ti.tm_min) + ":" + two(ti.tm_sec), 160, 92, C_HI, MC_DATUM, 7);
    txtG(GIORNI[ti.tm_wday], 160, 136, C_MAIN, MC_DATUM, 4);
    txt(String(ti.tm_mday) + " " + MESI[ti.tm_mon] + " " + String(ti.tm_year + 1900), 160, 162, C_MAIN, MC_DATUM, 2);
    txt("SINCRONIZZATO VIA NTP", 160, 196, C_DIM, MC_DATUM);
  } else {
    txtG(uptimeStr(), 160, 92, C_HI, MC_DATUM, 7);
    txt("TEMPO DALL'ACCENSIONE", 160, 140, C_MAIN, MC_DATUM);
    txt("CONNETTI IL WIFI PER L'ORA ESATTA", 160, 180, C_DIM, MC_DATUM);
  }
}

void drawMissioni() {
  int done = 0;
  for (int i = 0; i < 5; i++) {
    int y = 52 + i * 26;
    spr.drawRect(10, y, 14, 14, C_MAIN);
    if (qDone[i]) { spr.fillRect(13, y + 3, 8, 8, C_HI); done++; }
    txt(QUESTS[i], 34, y + 7, qDone[i] ? C_DIM2 : C_MAIN, ML_DATUM);
    if (qDone[i]) spr.drawFastHLine(34, y + 8, spr.textWidth(QUESTS[i], 2), C_DIM2);
  }
  txt("COMPLETATE " + String(done) + "/5", 10, 190, C_DIM);
  segBar(150, 194, 166, 8, done * 20, 10);
}

void drawLog() {
  if (logN == 0) { txt("NESSUN EVENTO", 160, 120, C_DIM, MC_DATUM); return; }
  for (int i = 0; i < logN; i++) {
    String s = logs[i];
    if (s.length() > 40) s = s.substring(0, 40);
    txt(s, 6, 48 + i * 20, i == logN - 1 ? C_HI : C_MAIN);
  }
}

// =================================================================
//  MAP - radar
// =================================================================
void drawRadar() {
  const int cx = 214, cy = 130, R = 80;
  int f = sub[3];
  brackets(128, 47, 174, 168, 10, C_DIM2);
  for (int r = R / 4; r <= R; r += R / 4) spr.drawCircle(cx, cy, r, r == R ? C_DIM2 : C_FAINT);
  spr.drawFastHLine(cx - R, cy, 2 * R, C_FAINT);
  spr.drawFastVLine(cx, cy - R, 2 * R, C_FAINT);
  for (int d = 0; d < 360; d += 30) {
    float a = d * DEG_TO_RAD;
    spr.drawLine(cx + cos(a) * (R - 5), cy + sin(a) * (R - 5), cx + cos(a) * R, cy + sin(a) * R, C_DIM);
  }
  float sw = (millis() % 3000) / 3000.0 * TWO_PI;
  const uint8_t trail[8] = {C_HI, C_MAIN, C_MID, C_MID, C_DIM, C_DIM2, C_DIM2, C_DARK};
  for (int k = 7; k >= 0; k--) {
    float a = sw - k * 0.05;
    spr.drawLine(cx, cy, cx + cos(a) * R, cy + sin(a) * R, trail[k]);
  }

  auto plot = [&](const char* key, int rssi, bool isBt, const String& label) {
    uint32_t h = hashStr(key);
    float a = (h % 360) * DEG_TO_RAD;
    int d = map(constrain(rssi, -95, -35), -35, -95, 12, R - 4);
    int x = cx + cos(a) * d, y = cy + sin(a) * d;
    float behind = sw - a;
    while (behind < 0) behind += TWO_PI;
    uint8_t c = behind < 0.4 ? C_HI : behind < 1.4 ? C_MAIN : behind < 3.0 ? C_MID : C_DIM;
    if (isBt) spr.fillTriangle(x, y - 3, x - 3, y + 3, x + 3, y + 3, c);
    else      spr.fillRect(x - 2, y - 2, 5, 5, c);
    if (behind < 0.9) txt(label.substring(0, 10), x + 5, y - 4, C_MAIN, TL_DATUM, 1);
  };

  if (f != 2) for (int i = 0; i < netCount; i++) plot(nets[i].ssid.c_str(), nets[i].rssi, false, nets[i].ssid);
  if (f != 1) {
    static BDev snap[MAXBT];
    int n;
    portENTER_CRITICAL(&btMux);
    n = bdevCount;
    memcpy(snap, bdevs, sizeof(BDev) * n);
    portEXIT_CRITICAL(&btMux);
    for (int i = 0; i < n; i++) plot(snap[i].addr, snap[i].rssi, true, String(snap[i].name[0] ? snap[i].name : snap[i].addr));
  }

  txt("RETI WIFI", 6, 50, C_DIM);
  txt(String(netCount), 6, 66, C_HI, TL_DATUM, 4);
  txt("DISP. BT", 6, 98, C_DIM);
  txt(String((int)bdevCount), 6, 114, C_HI, TL_DATUM, 4);
  spr.fillRect(8, 152, 5, 5, C_MAIN); txt("WIFI", 20, 148, C_MAIN);
  spr.fillTriangle(10, 166, 7, 172, 13, 172, C_MAIN); txt("BT", 20, 162, C_MAIN);
  bool sc = wifiScanning || btScanning;
  button(6, 190, 84, 22, sc ? "SCAN..." : "SCAN", sc && (millis() / 300) % 2);
  if (netCount == 0 && bdevCount == 0 && !sc) txt("PREMI SCAN", cx, cy + 30, C_DIM, MC_DATUM, 1);
}

// =================================================================
//  RADIO - WIFI / BLUETOOTH
// =================================================================
void drawWifi() {
  bool wc = WiFi.status() == WL_CONNECTED;
  String cur = wc ? WiFi.SSID() : "";
  if (wifiScanning) scanAnim(120, "SCANSIONE FREQUENZE...");
  else if (netCount == 0) txt("NESSUNA RETE - PREMI SCAN", 160, 115, C_DIM, MC_DATUM);
  else {
    for (int r = 0; r < 7; r++) {
      int i = netScroll + r;
      if (i >= netCount) break;
      int y = 46 + r * 20;
      bool isCur = wc && nets[i].ssid == cur;
      if (isCur) spr.fillRect(2, y, 316, 19, C_DARK);
      String s = nets[i].ssid.length() ? nets[i].ssid : String("<nascosta>");
      if (s.length() > 22) s = s.substring(0, 21) + "~";
      txt((isCur ? String("> ") : String("  ")) + s, 4, y + 10, isCur ? C_HI : C_MAIN, ML_DATUM);
      if (nets[i].enc) drawLock(222, y + 4, C_DIM);
      txt("C" + String(nets[i].ch), 262, y + 10, C_DIM, MR_DATUM);
      rssiBars(292, y + 16, nets[i].rssi);
    }
  }
  button(4, 190, 70, 22, "SCAN", wifiScanning && (millis() / 300) % 2);
  if (wc) button(80, 190, 110, 22, "DISCONNETTI");
  else txt(String(netCount) + " RETI", 135, 201, C_DIM, MC_DATUM);
  arrowBtn(232, 190, 40, 22, true);
  arrowBtn(276, 190, 40, 22, false);
}

void drawBt() {
  BDev local[MAXBT];
  int n;
  portENTER_CRITICAL(&btMux);
  n = bdevCount;
  memcpy(local, bdevs, sizeof(BDev) * n);
  portEXIT_CRITICAL(&btMux);

  if (btScanning && n == 0) scanAnim(120, "RICERCA DISPOSITIVI...");
  else if (n == 0) txt("NESSUN DISPOSITIVO - PREMI SCAN", 160, 115, C_DIM, MC_DATUM);
  else {
    for (int r = 0; r < 7; r++) {
      int i = btScroll + r;
      if (i >= n) break;
      int y = 46 + r * 20;
      bool s = (i == btSel);
      if (s) spr.fillRect(2, y, 316, 19, C_DARK);
      String nm = local[i].name[0] ? String(local[i].name) : String(local[i].addr);
      if (nm.length() > 24) nm = nm.substring(0, 23) + "~";
      txt(nm, 6, y + 10, s ? C_HI : (local[i].name[0] ? C_MAIN : C_DIM), ML_DATUM);
      txt(String(local[i].rssi), 280, y + 10, C_DIM, MR_DATUM);
      rssiBars(292, y + 16, local[i].rssi);
    }
  }
  button(4, 190, 70, 22, btScanning ? "..." : "SCAN", btScanning && (millis() / 300) % 2);
  if (btSel >= 0 && btSel < n) txt(local[btSel].addr, 153, 201, C_MAIN, MC_DATUM, 1);
  else txt(String(n) + " DISPOSITIVI", 153, 201, C_DIM, MC_DATUM);
  arrowBtn(232, 190, 40, 22, true);
  arrowBtn(276, 190, 40, 22, false);
}

// =================================================================
//  WIFI - logica
// =================================================================
void startWifiScan() {
  if (wifiScanning || modal == M_CONN) return;
  WiFi.scanDelete();
  WiFi.scanNetworks(true);
  wifiScanning = true;
}

void pollWifiScan() {
  if (!wifiScanning) return;
  int n = WiFi.scanComplete();
  if (n == WIFI_SCAN_RUNNING) return;
  wifiScanning = false;
  if (n < 0) { addLog("SCAN WIFI FALLITA"); return; }
  netCount = min(n, MAXNETS);
  for (int i = 0; i < netCount; i++)
    nets[i] = {WiFi.SSID(i), WiFi.RSSI(i), WiFi.channel(i), WiFi.encryptionType(i) != WIFI_AUTH_OPEN};
  for (int i = 0; i < netCount; i++)            // ordina per segnale
    for (int j = i + 1; j < netCount; j++)
      if (nets[j].rssi > nets[i].rssi) { Net t = nets[i]; nets[i] = nets[j]; nets[j] = t; }
  WiFi.scanDelete();
  netScroll = 0;
  addLog("WIFI: " + String(n) + " reti trovate");
}

void startConnect(const String& ssid, const String& pass) {
  WiFi.scanDelete();
  wifiScanning = false;
  WiFi.disconnect();
  delay(100);
  WiFi.begin(ssid.c_str(), pass.c_str());
  connSsid = ssid; connPass = pass;
  connStart = millis();
  modal = M_CONN;
}

void handleConnecting() {
  if (modal != M_CONN) return;
  wl_status_t st = WiFi.status();
  if (st == WL_CONNECTED) {
    cfg.ssid = connSsid; cfg.pass = connPass;
    saveConfig();
    msgL1 = "CONNESSO A " + connSsid.substring(0, 16);
    msgL2 = "IP " + WiFi.localIP().toString();
    modal = M_MSG;
  } else if (millis() - connStart > 15000 || st == WL_CONNECT_FAILED) {
    WiFi.disconnect();
    msgL1 = "CONNESSIONE FALLITA";
    msgL2 = "Password errata o segnale debole";
    addLog("WIFI: connessione fallita");
    modal = M_MSG;
  }
}

void checkWifiStatus() {
  static bool was = false;
  bool c = WiFi.status() == WL_CONNECTED;
  if (c != was) {
    was = c;
    if (c) {
      configTzTime(TZ_INFO, NTP1, NTP2);
      addLog("WIFI OK " + WiFi.localIP().toString());
    } else addLog("WIFI DISCONNESSO");
  }
}

void selectNet(int i) {
  Net& n = nets[i];
  if (n.ssid.length() == 0) return;
  if (n.ssid == cfg.ssid && cfg.pass.length()) { startConnect(n.ssid, cfg.pass); return; }
  if (!n.enc) { startConnect(n.ssid, ""); return; }
  kbSsid = n.ssid;
  kbText = "";
  kbShift = false;
  modal = M_KB;
}

// =================================================================
//  BLUETOOTH - logica (scansione in un task separato)
// =================================================================
class AdvCB : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice d) {
    String a = d.getAddress().toString().c_str();
    String nm = d.haveName() ? String(d.getName().c_str()) : String("");
    int rssi = d.getRSSI();
    portENTER_CRITICAL(&btMux);
    int idx = -1;
    for (int i = 0; i < bdevCount; i++) if (strcmp(bdevs[i].addr, a.c_str()) == 0) { idx = i; break; }
    if (idx < 0 && bdevCount < MAXBT) idx = bdevCount++;
    if (idx >= 0) {
      strncpy(bdevs[idx].addr, a.c_str(), 17); bdevs[idx].addr[17] = 0;
      if (nm.length()) { strncpy(bdevs[idx].name, nm.c_str(), 23); bdevs[idx].name[23] = 0; }
      bdevs[idx].rssi = rssi;
    }
    portEXIT_CRITICAL(&btMux);
  }
};

void btTask(void*) {
  BLEScan* s = BLEDevice::getScan();
  s->start(6, false);
  s->clearResults();
  btScanning = false;
  vTaskDelete(NULL);
}

void startBtScan() {
  if (btScanning) return;
  if (!bleReady) {
    BLEDevice::init("RetroTerm");
    BLEScan* s = BLEDevice::getScan();
    s->setAdvertisedDeviceCallbacks(new AdvCB(), false);
    s->setActiveScan(true);
    s->setInterval(100);
    s->setWindow(99);
    bleReady = true;
    addLog("BT: modulo avviato");
  }
  portENTER_CRITICAL(&btMux);
  bdevCount = 0;
  memset(bdevs, 0, sizeof(bdevs));
  portEXIT_CRITICAL(&btMux);
  btSel = -1; btScroll = 0;
  btScanning = true;
  xTaskCreatePinnedToCore(btTask, "btscan", 6144, NULL, 1, NULL, 0);
}

void checkBtDone() {
  static bool was = false;
  if (was && !btScanning) {
    // ordina per segnale
    portENTER_CRITICAL(&btMux);
    for (int i = 0; i < bdevCount; i++)
      for (int j = i + 1; j < bdevCount; j++)
        if (bdevs[j].rssi > bdevs[i].rssi) { BDev t = bdevs[i]; bdevs[i] = bdevs[j]; bdevs[j] = t; }
    portEXIT_CRITICAL(&btMux);
    addLog("BT: " + String((int)bdevCount) + " dispositivi");
    if (!qDone[2] && netCount > 0) qDone[2] = true;
  }
  was = btScanning;
}

// =================================================================
//  TASTIERA E FINESTRE
// =================================================================
void drawKeyboard() {
  txt("> CONNETTI A:", 4, 4, C_DIM);
  txt(kbSsid.substring(0, 20), 112, 4, C_HI);
  spr.drawRect(2, 24, 316, 24, C_MAIN);
  String t = kbText;
  while (t.length() && spr.textWidth(t, 2) > 290) t = t.substring(1);
  txt(t, 8, 36, C_HI, ML_DATUM);
  if ((millis() / 400) % 2) spr.fillRect(10 + spr.textWidth(t, 2), 29, 7, 14, C_MAIN);

  const char** L = kbShift ? KB_U : KB_L;
  bool flashing = millis() - kbFlashT < 120;
  for (int r = 0; r < 4; r++)
    for (int c = 0; c < 10; c++) {
      int x = c * 32 + 1, y = KB_Y + r * KB_H, id = r * 10 + c;
      char ch[2] = {L[r][c], 0};
      if (flashing && id == kbFlash) {
        spr.fillRoundRect(x, y, 30, KB_H - 3, 3, C_HI);
        txt(ch, x + 15, y + 15, BG, MC_DATUM);
      } else {
        spr.drawRoundRect(x, y, 30, KB_H - 3, 3, C_DIM);
        txt(ch, x + 15, y + 15, C_MAIN, MC_DATUM);
      }
    }
  int y = KB_Y + 4 * KB_H;
  for (int k = 0; k < 5; k++) {
    bool act = (k == 0 && kbShift) || (flashing && kbFlash == 40 + k);
    if (act) { spr.fillRoundRect(KSPEC[k].x, y, KSPEC[k].w, KB_H - 3, 3, C_MAIN); txt(KSPEC[k].l, KSPEC[k].x + KSPEC[k].w / 2, y + 15, BG, MC_DATUM); }
    else     { spr.drawRoundRect(KSPEC[k].x, y, KSPEC[k].w, KB_H - 3, 3, C_MAIN); txt(KSPEC[k].l, KSPEC[k].x + KSPEC[k].w / 2, y + 15, C_MAIN, MC_DATUM); }
  }
  txt("INSERISCI LA PASSWORD - OK PER CONNETTERE", 160, 228, C_DIM2, MC_DATUM, 1);
}

void kbTouch(int x, int y) {
  if (y >= KB_Y && y < KB_Y + 4 * KB_H) {
    int r = (y - KB_Y) / KB_H, c = min(x / 32, 9);
    if (kbText.length() < 63) kbText += (kbShift ? KB_U : KB_L)[r][c];
    kbFlash = r * 10 + c;
  } else if (y >= KB_Y + 4 * KB_H && y < KB_Y + 5 * KB_H) {
    for (int k = 0; k < 5; k++) {
      if (x >= KSPEC[k].x && x < KSPEC[k].x + KSPEC[k].w) {
        kbFlash = 40 + k;
        if (k == 0) kbShift = !kbShift;
        else if (k == 1 && kbText.length() < 63) kbText += ' ';
        else if (k == 2 && kbText.length()) kbText.remove(kbText.length() - 1);
        else if (k == 3) modal = M_NONE;
        else if (k == 4) startConnect(kbSsid, kbText);
      }
    }
  }
  kbFlashT = millis();
}

void drawModalBox() {
  chamferFill(24, 68, 272, 104, 10, BG);
  chamfer(24, 68, 272, 104, 10, C_MAIN);
  chamfer(28, 72, 264, 96, 8, C_DIM2);
  if (modal == M_CONN) {
    txtG("CONNESSIONE IN CORSO", 160, 90, C_HI, MC_DATUM);
    txt(connSsid.substring(0, 24), 160, 112, C_MAIN, MC_DATUM);
    int p = constrain((int)((millis() - connStart) * 100 / 15000), 0, 100);
    segBar(50, 138, 220, 10, p, 20);
  } else {
    txtG(msgL1, 160, 94, C_HI, MC_DATUM);
    txt(msgL2, 160, 118, C_MAIN, MC_DATUM);
    if ((millis() / 500) % 2) txt("[ TOCCA PER CONTINUARE ]", 160, 152, C_DIM, MC_DATUM, 1);
  }
}

// =================================================================
//  RENDER
// =================================================================
void drawContent() {
  switch (tab) {
    case 0: if (sub[0] == 0) drawStato(); else if (sub[0] == 1) drawSistema(); else drawConfig(); break;
    case 1: drawInv(); break;
    case 2: if (sub[2] == 0) drawOra(); else if (sub[2] == 1) drawMissioni(); else drawLog(); break;
    case 3: drawRadar(); break;
    case 4: if (sub[4] == 0) drawWifi(); else drawBt(); break;
  }
}

void render() {
  spr.fillSprite(BG);
  if (modal == M_KB) drawKeyboard();
  else {
    bgGrid();
    drawHeader();
    drawSubtabs();
    drawContent();
    drawFooter();
    if (modal == M_CONN || modal == M_MSG) drawModalBox();
  }
  present();
}

// =================================================================
//  TOUCH
// =================================================================
bool getTouch(int& x, int& y) {
  static bool was = false;
  bool now = ts.tirqTouched() && ts.touched();
  if (now && !was) {
    was = true;
    TS_Point p = ts.getPoint();
    x = constrain(map(p.x, TS_MINX, TS_MAXX, 0, 320), 0, 319);
    y = constrain(map(p.y, TS_MINY, TS_MAXY, 0, 240), 0, 239);
    return true;
  }
  if (!now) was = false;
  return false;
}

void touchConfig(int x, int y) {
  if (y < 50 || y >= 210) return;
  int row = (y - 50) / 32;
  switch (row) {
    case 0:
      if (x >= 176 && x < 206) cfg.theme = (cfg.theme + THEME_N - 1) % THEME_N;
      else if (x >= 290) cfg.theme = (cfg.theme + 1) % THEME_N;
      else return;
      applyTheme(); break;
    case 1:
      if (x >= 176 && x < 206) cfg.bright = max(20, cfg.bright - 30);
      else if (x >= 290) cfg.bright = min(255, cfg.bright + 30);
      else return;
      applyBrightness(); break;
    case 2: if (x >= 230) cfg.sound = !cfg.sound; else return; break;
    case 3: if (x >= 230) cfg.crt = !cfg.crt; else return; break;
    case 4:
      if (x >= 230) { cfg.ssid = ""; cfg.pass = ""; WiFi.disconnect(); addLog("WIFI: credenziali cancellate"); }
      else return;
      break;
  }
  saveConfig();
}

void onTouch(int x, int y) {
  click();
  if (modal == M_KB)  { kbTouch(x, y); return; }
  if (modal == M_MSG) { modal = M_NONE; return; }
  if (modal == M_CONN) return;

  if (y < 24) {
    int nt = constrain(x / 64, 0, 4);
    if (nt != tab) { tab = nt; glitchUntil = millis() + 160; chirp(); }
    return;
  }
  if (y < 45) {
    for (int i = 0; i < SUBN[tab]; i++)
      if (x >= subX0[i] && x < subX1[i] && sub[tab] != i) { sub[tab] = i; glitchUntil = millis() + 90; }
    return;
  }

  switch (tab) {
    case 0:
      if (sub[0] == 2) touchConfig(x, y);
      break;
    case 1:
      if (x < 170 && y >= 50 && y < 50 + INV_N * 26) invSel[sub[1]] = (y - 50) / 26;
      break;
    case 2:
      if (sub[2] == 1 && y >= 50 && y < 180) {
        int i = (y - 50) / 26;
        if (i >= 0 && i < 5) qDone[i] = !qDone[i];
      }
      break;
    case 3:
      if (inRect(x, y, 6, 186, 90, 28)) { startWifiScan(); startBtScan(); }
      break;
    case 4:
      if (sub[4] == 0) {
        if (inRect(x, y, 0, 186, 76, 30)) startWifiScan();
        else if (inRect(x, y, 78, 186, 114, 30) && WiFi.status() == WL_CONNECTED) WiFi.disconnect();
        else if (inRect(x, y, 230, 186, 44, 30)) netScroll = max(0, netScroll - 3);
        else if (inRect(x, y, 274, 186, 46, 30)) netScroll = constrain(netScroll + 3, 0, max(0, netCount - 7));
        else if (y >= 46 && y < 186 && !wifiScanning) {
          int i = netScroll + (y - 46) / 20;
          if (i < netCount) selectNet(i);
        }
      } else {
        int n = bdevCount;
        if (inRect(x, y, 0, 186, 76, 30)) startBtScan();
        else if (inRect(x, y, 230, 186, 44, 30)) btScroll = max(0, btScroll - 3);
        else if (inRect(x, y, 274, 186, 46, 30)) btScroll = constrain(btScroll + 3, 0, max(0, n - 7));
        else if (y >= 46 && y < 186) {
          int i = btScroll + (y - 46) / 20;
          if (i < n) btSel = (btSel == i) ? -1 : i;
        }
      }
      break;
  }
}

// =================================================================
//  AVVIO
// =================================================================
// logo esagonale che si costruisce
void drawHexLogo(int cx, int cy, int r, int edges, float rot) {
  for (int i = 0; i < edges && i < 6; i++) {
    float a0 = (i * 60 - 90) * DEG_TO_RAD, a1 = ((i + 1) * 60 - 90) * DEG_TO_RAD;
    for (int k = 0; k < 3; k++)
      spr.drawLine(cx + cos(a0) * (r - k), cy + sin(a0) * (r - k), cx + cos(a1) * (r - k), cy + sin(a1) * (r - k), k == 1 ? C_HI : C_MAIN);
  }
  if (edges >= 6) {
    for (int i = 0; i < 3; i++) {
      float a = (i * 120 - 90) * DEG_TO_RAD;
      spr.drawLine(cx, cy, cx + cos(a) * (r - 10), cy + sin(a) * (r - 10), C_MAIN);
    }
    spr.fillCircle(cx, cy, 4, C_HI);
    for (int i = 0; i < 24; i++) {
      if (i % 3 == 0) continue;
      float a = rot + i * TWO_PI / 24;
      spr.drawLine(cx + cos(a) * (r + 6), cy + sin(a) * (r + 6), cx + cos(a) * (r + 10), cy + sin(a) * (r + 10), C_DIM);
    }
  }
}

void bootSequence() {
  // accensione: linea che si espande
  for (int w = 4; w <= 320; w += 28) { spr.fillSprite(BG); spr.fillRect(160 - w / 2, 119, w, 2, C_HI); spr.pushSprite(0, 0); }
  // flusso dati
  for (int f = 0; f < 22; f++) {
    spr.fillSprite(BG);
    for (int r = 0; r < 14; r++) {
      char line[48];
      snprintf(line, sizeof(line), "%04X  %02X %02X %02X %02X %02X %02X %02X %02X", (unsigned)((f + r) * 16) & 0xFFFF,
               (int)random(256), (int)random(256), (int)random(256), (int)random(256),
               (int)random(256), (int)random(256), (int)random(256), (int)random(256));
      txt(line, 8, 4 + r * 15, r == 13 ? C_HI : C_DIM2);
    }
    present();
  }
  // logo
  for (int f = 0; f < 56; f++) {
    spr.fillSprite(BG);
    bgGrid();
    drawHexLogo(160, 80, 34, f / 4, f * 0.05);
    if (f == 26) glitchUntil = millis() + 180;
    if (f > 26) {
      txtG("VX-26", 160, 140, C_HI, MC_DATUM, 4);
      txt("OPERATOR SYSTEM  //  2026", 160, 166, C_MAIN, MC_DATUM);
    }
    if (f > 40) txt("INTERFACCIA OLOGRAFICA PERSONALE", 160, 198, C_DIM, MC_DATUM, 1);
    present();
  }
  chirp();
  const char* lines[] = {
    "VX-26 OPERATOR SYSTEM  v4.0",
    "BUILD 2026.10 // CORE XTENSA LX6",
    "",
    "> MEMORIA",
    "> SENSORI",
    "> MODULO WIFI",
    "> MODULO BLUETOOTH",
    "> INTERFACCIA OLOGRAFICA",
  };
  const int N = sizeof(lines) / sizeof(lines[0]);
  for (int l = 0; l < N; l++) {
    int len = strlen(lines[l]);
    for (int c = 0; c <= len; c += 3) {
      spr.fillSprite(BG);
      for (int k = 0; k < l; k++) {
        txt(lines[k], 14, 12 + k * 20, C_MAIN);
        if (k >= 3) txt("[ OK ]", 306, 12 + k * 20, C_HI, TR_DATUM);
      }
      String part = String(lines[l]).substring(0, c);
      txtG(part, 14, 12 + l * 20, C_HI);
      spr.fillRect(16 + spr.textWidth(part, 2), 14 + l * 20, 7, 13, C_MAIN);
      present();
    }
    click();
  }
  for (int p = 0; p <= 100; p += 4) {
    spr.fillRect(0, 178, 320, 62, BG);
    chamfer(14, 184, 292, 18, 5, C_MAIN);
    segBar(20, 189, 282, 8, p, 28);
    txt("CARICAMENTO " + String(p) + "%", 160, 216, C_DIM, MC_DATUM);
    present();
  }
  glitchUntil = millis() + 200;
  for (int f = 0; f < 20; f++) {
    spr.fillSprite(BG);
    bgGrid();
    brackets(30, 80, 260, 80, 14, C_MAIN);
    txtG("ACCESSO CONSENTITO", 160, 112, C_HI, MC_DATUM, 4);
    txt("BENVENUTO, OPERATORE", 160, 140, C_MAIN, MC_DATUM);
    present();
  }
  delay(400);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_R, OUTPUT); pinMode(LED_G, OUTPUT); pinMode(LED_B, OUTPUT);
  digitalWrite(LED_R, HIGH); digitalWrite(LED_G, HIGH); digitalWrite(LED_B, HIGH);  // LED RGB spento
  pinMode(SPK_PIN, OUTPUT);
  analogSetPinAttenuation(LDR_PIN, ADC_0db);

  prefs.begin("retroterm", false);
  loadConfig();

  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  applyBrightness();

  touchSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
  ts.begin(touchSPI);
  ts.setRotation(1);

  spr.setColorDepth(4);
  if (!spr.createSprite(320, 240)) {
    tft.setTextColor(TFT_RED);
    tft.drawString("ERRORE: memoria insufficiente", 10, 10, 2);
    while (true) delay(1000);
  }
  applyTheme();
  initVignette();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  randomSeed(analogRead(LDR_PIN) ^ micros());

  bootSequence();
  updateStats();
  addLog("SISTEMA AVVIATO");

  if (cfg.ssid.length()) {
    WiFi.begin(cfg.ssid.c_str(), cfg.pass.c_str());
    addLog("WIFI: connessione a " + cfg.ssid.substring(0, 14));
  }
}

void loop() {
  int x, y;
  if (getTouch(x, y)) { onTouch(x, y); dirty = true; }

  pollWifiScan();
  handleConnecting();
  checkWifiStatus();
  checkBtDone();

  unsigned long now = millis();
  if (now - lastStats >= 1000) { lastStats = now; updateStats(); }

  bool anim = cfg.crt || tab == 3 || (tab == 0 && sub[0] == 0) || tab == 1 ||
              wifiScanning || btScanning || modal != M_NONE;
  unsigned long iv = anim ? 40 : 250;
  if (dirty || now - lastFrame >= iv) {
    lastFrame = now;
    dirty = false;
    render();
  }
}
