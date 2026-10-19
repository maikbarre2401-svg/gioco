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

  FUNZIONI (v6.0):
    STAT  : STATO (figura animata + sensori + livello) | SISTEMA (info chip, rete) | GRAFICI (storico sensori)
            | CONFIG (2 pagine: tema, luminosita' manuale/automatica, suono, effetto olo, LED RGB,
              salvaschermo, calibrazione touch, WiFi salvato, riavvio)
    INV   : ARMI | ATTREZZI | AIUTI
    DATA  : ORA (orologio NTP) | METEO (Open-Meteo, previsioni 3 giorni) | TIMER (conto alla rovescia
            e cronometro) | MISSIONI | LOG eventi
    MAP   : radar animato con reti WiFi e dispositivi Bluetooth reali (TUTTI | WIFI | BT)
    RADIO : WIFI (scansione + connessione con tastiera) | BLUETOOTH (scansione BLE)
            | CANALI (analizzatore dei canali WiFi) | LINK (pannello web + hotspot + codice QR)
    GIOCO : TERMINALE (trova la password) | SERPENTE | DIFESA (difendi i rifugi dai missili)
    Extra : livelli ed esperienza, pannello web con schermo dal vivo e tocco a distanza,
            messaggi dal telefono, salvaschermo, suoni non bloccanti, LED di stato
*/

#include <SPI.h>
#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>
#include <WiFi.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <ESPmDNS.h>
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
  bool autoBright = false;
  bool led = true;
  int saver = 2;                    // indice in SAVER_MIN
  bool ap = false;                  // hotspot VX26 per il pannello web
  int tminx = TS_MINX, tmaxx = TS_MAXX, tminy = TS_MINY, tmaxy = TS_MAXY;
  String ssid, pass;
} cfg;

// ---------------- NAVIGAZIONE ----------------
#define NTABS 6
#define TAB_W 53
const char* TABS[NTABS] = {"STAT", "INV", "DATA", "MAP", "RADIO", "GIOCO"};
const char* SUBS[NTABS][5] = {
  {"STATO", "SISTEMA", "GRAFICI", "CONFIG", nullptr},
  {"ARMI", "ATTREZZI", "AIUTI", nullptr, nullptr},
  {"ORA", "METEO", "TIMER", "MISSIONI", "LOG"},
  {"TUTTI", "WIFI", "BT", nullptr, nullptr},
  {"WIFI", "BLUETOOTH", "CANALI", "LINK", nullptr},
  {"TERMINALE", "SERPENTE", "DIFESA", nullptr, nullptr},
};
const int SUBN[NTABS] = {4, 3, 5, 3, 4, 3};
int tab = 0, sub[NTABS] = {0, 0, 0, 0, 0, 0};
int subX0[5], subX1[5];
// sottoschede usate nel codice
enum { S_ORA, S_METEO, S_TIMER, S_MISSIONI, S_LOG };
enum { S_WIFI, S_BT, S_CANALI, S_LINK };
enum { S_TERM, S_SNAKE, S_DIFESA };

enum Modal { M_NONE, M_KB, M_CONN, M_MSG, M_CAL, M_RX };
Modal modal = M_NONE;
String msgL1, msgL2;
String rxText;                    // messaggio arrivato dal pannello web
unsigned long toastUntil = 0;     // avviso temporaneo in alto (livello raggiunto ecc.)
String toastText;

bool dirty = true;
unsigned long lastFrame = 0, lastStats = 0;
unsigned long glitchUntil = 0;   // disturbo al cambio scheda
unsigned long lastInput = 0;     // ultimo tocco (per il salvaschermo)
bool saverOn = false;
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

// ---------------- CONFIG (paginata) ----------------
enum { CI_THEME, CI_BRIGHT, CI_AUTO, CI_SOUND, CI_CRT, CI_LED, CI_SAVER, CI_CAL, CI_WIFI, CI_SYS, CI_N };
const char* CI_LBL[CI_N] = {"TEMA", "LUMINOSITA'", "LUCE AUTOMATICA", "SUONO", "EFFETTO OLO",
                            "LED RGB", "SALVASCHERMO", "TOUCH", "WIFI SALVATO", "SISTEMA"};
#define CFG_ROWS 5
int cfgPage = 0;
int blAuto = 160;                 // luminosita' calcolata dal sensore di luce

// ---------------- SUONO E LED (PWM hardware, non bloccante) ----------------
#define SPK_CH   0                // analogWrite usa i canali dal 15 in giu'
#define LED_CH_R 2
#define LED_CH_G 3
#define LED_CH_B 4
struct Note { uint16_t f, ms; };
#define TONE_Q 32
Note toneQ[TONE_Q];
int toneHead = 0, toneLen = 0;
unsigned long toneEnd = 0;
bool toneOn = false;

// ---------------- GRAFICI ----------------
#define HIST 120
uint8_t hist[4][HIST];
int histN = 0, histPos = 0;

// ---------------- METEO ----------------
struct Weather { bool ok; char city[24]; float t, wind; int hum, code; int dCode[4]; float dMax[4], dMin[4]; char upd[6]; };
Weather wx = {};
volatile int wxState = 0;         // 0 attesa, 1 caricamento, 2 ok, 3 errore
unsigned long wxLast = 0;
float geoLat = NAN, geoLon = NAN;
char geoCity[24] = "";
portMUX_TYPE wxMux = portMUX_INITIALIZER_UNLOCKED;

// ---------------- SALVASCHERMO ----------------
const int SAVER_MIN[4] = {0, 1, 3, 10};
const char* SAVER_LBL[4] = {"OFF", "1 MIN", "3 MIN", "10 MIN"};
#define DROPS 54
struct Drop { int16_t y; uint8_t sp, len; };
Drop drops[DROPS];

// ---------------- CALIBRAZIONE TOUCH ----------------
int calStep = 0, calRaw[2][2];
int rawX = 0, rawY = 0;

// ---------------- GIOCO: TERMINALE ----------------
const char* WORDS[] = {
  "PIANO", "FUOCO", "TERRA", "PORTA", "RADIO", "CORDA", "MONTE", "FERRO", "VETRO", "CARTA",
  "NOTTE", "PONTE", "CAMPO", "TORRE", "FORZA", "LEGNO", "SEGNO", "VENTO", "LAMPO", "TUONO",
  "SPADA", "SCUDO", "BORSA", "CASCO", "ROCCA", "PORTO", "BANCO", "DENTE", "FANGO", "ZAINO",
  "MAPPA", "BUSTA", "FIUME", "SERRA", "VALLE", "COLLE", "BOSCO", "PRATO", "SASSO", "BOMBA",
  "TENDA", "FORNO", "ACQUA", "LATTA", "GRANO", "CARNE", "PESCE", "GATTO", "RATTO", "CORVO",
};
const int WORDS_N = sizeof(WORDS) / sizeof(WORDS[0]);
#define TW_N 12
int twW[TW_N];
bool twUsed[TW_N];
char twJunk[TW_N][2];
int twAns = 0, twTries = 4, twLogN = 0, twState = 0;   // 0 in gioco, 1 vinto, 2 bloccato
int twLogW[4], twLogL[4];
unsigned twAddr = 0xF4A0;
unsigned long twLockUntil = 0;

// ---------------- GIOCO: SERPENTE ----------------
#define SN_COLS 38
#define SN_ROWS 18
#define SN_X0 8
#define SN_Y0 58
#define SN_CELL 8
int8_t snX[SN_COLS * SN_ROWS], snY[SN_COLS * SN_ROWS];
int snLen = 0, snDx = 1, snDy = 0, snNdx = 1, snNdy = 0;
int snFx = 0, snFy = 0, snScore = 0, snHi = 0, snState = 0;   // 0 pronto, 1 in corsa, 2 fine, 3 pausa
unsigned long snLast = 0, snDeadT = 0;

// ---------------- LIVELLI / ESPERIENZA ----------------
long xp = 0;

// ---------------- TIMER / CRONOMETRO ----------------
int tmMode = 0;                   // 0 conto alla rovescia, 1 cronometro
long tmSet = 300000;              // durata impostata (ms)
long tmLeft = 300000;             // tempo rimasto quando e' fermo
unsigned long tmStart = 0;        // millis() all'avvio
bool tmRun = false, tmAlarm = false;
unsigned long tmAlarmT = 0;
long crBase = 0;                  // cronometro: tempo accumulato
unsigned long crStart = 0;
bool crRun = false;
long crLap[3] = {-1, -1, -1};
int crLapN = 0;

// ---------------- PANNELLO WEB / HOTSPOT ----------------
#define AP_SSID "VX26-OPERATOR"
#define AP_PASS "vx26-2026"
#define MDNS_NAME "vx26"
WebServer web(80);
bool mdnsOn = false;
int qrShowWifi = 0;               // 0 = indirizzo del pannello, 1 = credenziali hotspot
unsigned long webHits = 0, webLastHit = 0;

// ---------------- GIOCO: DIFESA ----------------
#define DF_EN 18
#define DF_SH 6
#define DF_EX 16
#define DF_GROUND 206
struct DfMissile { float sx, sy, x, y, vx, vy; int target; bool on, split; };
struct DfShot { float x, y, vx, vy, tx, ty; int n; bool on; };
struct DfBoom { float x, y; int age, maxR; bool on, player; };
DfMissile dfEn[DF_EN];
DfShot dfSh[DF_SH];
DfBoom dfEx[DF_EX];
const int DF_CITY_X[4] = {38, 102, 218, 282};
bool dfCity[4];
int dfState = 0;                  // 0 pronto, 1 in gioco, 2 fine, 3 pausa, 4 fine ondata
int dfWave = 1, dfScore = 0, dfHi = 0, dfAmmo = 0, dfToSpawn = 0, dfSpawnT = 0, dfBonus = 0;
unsigned long dfLast = 0, dfStateT = 0;

// Prototipi
void startWifiScan();
void startBtScan();
void arrowBtnH(int x, int y, int w, int h, bool left);
void addXp(int n);
void ledRGB(int r, int g, int b);

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

void queueTone(uint16_t f, uint16_t ms) {
  if (!cfg.sound || toneLen >= TONE_Q) return;
  toneQ[(toneHead + toneLen) % TONE_Q] = {f, ms};
  toneLen++;
}

// suona la coda di note senza mai bloccare il programma (f = 0 -> pausa)
void pollSound() {
  unsigned long now = millis();
  if (toneOn && now < toneEnd) return;
  if (toneLen == 0) {
    if (toneOn) { ledcWriteTone(SPK_CH, 0); toneOn = false; }
    return;
  }
  Note n = toneQ[toneHead];
  toneHead = (toneHead + 1) % TONE_Q;
  toneLen--;
  ledcWriteTone(SPK_CH, n.f);
  toneOn = true;
  toneEnd = now + n.ms;
}

void click()  { queueTone(3200, 5); }
void sndOk()  { queueTone(1320, 70); queueTone(1760, 70); queueTone(2640, 120); }
void sndErr() { queueTone(330, 120); queueTone(0, 40); queueTone(220, 200); }
void sndEat() { queueTone(1900, 25); queueTone(2500, 25); }

bool inRect(int x, int y, int rx, int ry, int rw, int rh) {
  return x >= rx && x < rx + rw && y >= ry && y < ry + rh;
}

void saveConfig() {
  prefs.putInt("theme", cfg.theme);
  prefs.putInt("bright", cfg.bright);
  prefs.putBool("sound", cfg.sound);
  prefs.putBool("crt", cfg.crt);
  prefs.putBool("auto", cfg.autoBright);
  prefs.putBool("led", cfg.led);
  prefs.putInt("saver", cfg.saver);
  prefs.putBool("ap", cfg.ap);
  prefs.putInt("tminx", cfg.tminx);
  prefs.putInt("tmaxx", cfg.tmaxx);
  prefs.putInt("tminy", cfg.tminy);
  prefs.putInt("tmaxy", cfg.tmaxy);
  prefs.putString("ssid", cfg.ssid);
  prefs.putString("pass", cfg.pass);
}

void loadConfig() {
  cfg.theme  = constrain(prefs.getInt("theme", 0), 0, THEME_N - 1);
  cfg.bright = constrain(prefs.getInt("bright", 220), 20, 255);
  cfg.sound  = prefs.getBool("sound", true);
  cfg.crt    = prefs.getBool("crt", true);
  cfg.autoBright = prefs.getBool("auto", false);
  cfg.led    = prefs.getBool("led", true);
  cfg.saver  = constrain(prefs.getInt("saver", 2), 0, 3);
  cfg.ap     = prefs.getBool("ap", false);
  cfg.tminx  = prefs.getInt("tminx", TS_MINX);
  cfg.tmaxx  = prefs.getInt("tmaxx", TS_MAXX);
  cfg.tminy  = prefs.getInt("tminy", TS_MINY);
  cfg.tmaxy  = prefs.getInt("tmaxy", TS_MAXY);
  if (cfg.tminx == cfg.tmaxx || cfg.tminy == cfg.tmaxy) {
    cfg.tminx = TS_MINX; cfg.tmaxx = TS_MAXX; cfg.tminy = TS_MINY; cfg.tmaxy = TS_MAXY;
  }
  cfg.ssid   = prefs.getString("ssid", "");
  cfg.pass   = prefs.getString("pass", "");
  uint8_t q  = prefs.getUChar("quests", 1);
  for (int i = 0; i < 5; i++) qDone[i] = (q >> i) & 1;
  snHi       = prefs.getInt("snhi", 0);
  dfHi       = prefs.getInt("dfhi", 0);
  xp         = prefs.getLong("xp", 0);
  blAuto     = cfg.bright;
}

void saveQuests() {
  uint8_t q = 0;
  for (int i = 0; i < 5; i++) if (qDone[i]) q |= 1 << i;
  prefs.putUChar("quests", q);
}

void completeQuest(int i) {
  if (qDone[i]) return;
  qDone[i] = true;
  saveQuests();
  addLog("MISSIONE OK: " + String(QUESTS[i]).substring(0, 20));
  sndOk();
  addXp(100);
}

// livello n richiede 40*(n-1)^2 punti esperienza
int levelOf(long x) { int l = 1; while (40L * l * l <= x) l++; return l; }
long xpFor(int l) { return 40L * (l - 1) * (l - 1); }

void toast(const String& s) { toastText = s; toastUntil = millis() + 2600; }

void addXp(int n) {
  if (n <= 0) return;
  int before = levelOf(xp);
  xp += n;
  prefs.putLong("xp", xp);
  int after = levelOf(xp);
  if (after > before) {
    toast("LIVELLO " + String(after) + " RAGGIUNTO");
    addLog("LIVELLO " + String(after));
    queueTone(880, 60); queueTone(1175, 60); queueTone(1568, 60); queueTone(2093, 160);
    glitchUntil = millis() + 150;
  }
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

int blTarget() { return cfg.autoBright ? blAuto : cfg.bright; }

void applyBrightness() {
  int b = blTarget();
  if (saverOn) b = max(10, b / 5);       // in standby lo schermo si abbassa
  analogWrite(BL_PIN, b);
}

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

void chirp() { for (int f = 2600; f > 900; f -= 280) queueTone(f, 7); }

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
  pollSound();
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
  for (int i = 0; i < NTABS; i++) {
    int x0 = i * TAB_W + 2, x1 = x0 + TAB_W - 4, cx = (x0 + x1) / 2;
    if (i == tab) {
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
  int n = SUBN[tab], gap = 18, tot = 0, w[5];
  for (int i = 0; i < n; i++) { w[i] = spr.textWidth(SUBS[tab][i], 2); tot += w[i]; }
  if (n > 1) gap = constrain((312 - tot) / (n - 1), 8, 18);
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

  uint8_t v[4] = {(uint8_t)sRam, (uint8_t)constrain((int)sTemp, 0, 100), (uint8_t)sLight, (uint8_t)sSig};
  for (int k = 0; k < 4; k++) hist[k][histPos] = v[k];
  histPos = (histPos + 1) % HIST;
  if (histN < HIST) histN++;

  if (cfg.autoBright) {
    int target = map(sLight, 0, 100, 25, 255);
    blAuto += (target - blAuto) / 3;     // transizione morbida
    applyBrightness();
  }
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
  int lv = levelOf(xp);
  long x0 = xpFor(lv), x1 = xpFor(lv + 1);
  chamferFill(103, 195, 114, 20, 5, C_DARK);
  txtG("LIV " + String(lv), 110, 205, C_HI, ML_DATUM);
  segBar(160, 201, 54, 8, (int)((xp - x0) * 100 / max(1L, x1 - x0)), 6);
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
  for (int r = 0; r < CFG_ROWS; r++) {
    int id = cfgPage * CFG_ROWS + r;
    if (id >= CI_N) break;
    int y = 48 + r * 28, by = y + 2;
    txt(CI_LBL[id], 8, y + 13, C_MAIN, ML_DATUM);
    spr.drawFastHLine(8, y + 27, 306, C_FAINT);
    switch (id) {
      case CI_THEME:
        arrowBtnH(176, by, 30, 22, true);
        txt(THEMES[cfg.theme].name, 248, y + 13, C_HI, MC_DATUM);
        arrowBtnH(290, by, 30, 22, false);
        break;
      case CI_BRIGHT:
        button(176, by, 30, 22, "-");
        segBar(212, y + 9, 74, 8, (blTarget() - 20) * 100 / 235, 8);
        button(290, by, 30, 22, "+");
        break;
      case CI_AUTO:  button(230, by, 90, 22, cfg.autoBright ? "ON" : "OFF", cfg.autoBright); break;
      case CI_SOUND: button(230, by, 90, 22, cfg.sound ? "ON" : "OFF", cfg.sound); break;
      case CI_CRT:   button(230, by, 90, 22, cfg.crt ? "ON" : "OFF", cfg.crt); break;
      case CI_LED:   button(230, by, 90, 22, cfg.led ? "ON" : "OFF", cfg.led); break;
      case CI_SAVER:
        arrowBtnH(176, by, 30, 22, true);
        txt(SAVER_LBL[cfg.saver], 248, y + 13, C_HI, MC_DATUM);
        arrowBtnH(290, by, 30, 22, false);
        break;
      case CI_CAL:   button(230, by, 90, 22, "CALIBRA"); break;
      case CI_WIFI: {
        String s = cfg.ssid.length() ? cfg.ssid.substring(0, 10) : String("-");
        txt(s, 112, y + 13, C_DIM, ML_DATUM);
        button(230, by, 90, 22, "DIMENTICA");
      } break;
      case CI_SYS:   button(230, by, 90, 22, "RIAVVIA"); break;
    }
  }
  int pages = (CI_N + CFG_ROWS - 1) / CFG_ROWS;
  arrowBtnH(4, 190, 40, 22, true);
  txt("PAGINA " + String(cfgPage + 1) + "/" + String(pages), 160, 201, C_DIM, MC_DATUM);
  arrowBtnH(276, 190, 40, 22, false);
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
  addXp(5);
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
      if (!mdnsOn && MDNS.begin(MDNS_NAME)) { MDNS.addService("http", "tcp", 80); mdnsOn = true; }
      addLog("WIFI OK " + WiFi.localIP().toString());
      completeQuest(1);
      if (wxState != 1) wxState = 0;        // meteo subito alla connessione
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
    addXp(5);
    if (netCount > 0) completeQuest(2);
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
  } else if (modal == M_RX) {
    txtG("TRASMISSIONE IN ARRIVO", 160, 86, C_HI, MC_DATUM);
    String rest = rxText;
    for (int line = 0; line < 3 && rest.length(); line++) {      // a capo automatico
      int cut = rest.length();
      while (cut > 1 && spr.textWidth(rest.substring(0, cut), 2) > 250) {
        int sp = rest.lastIndexOf(' ', cut - 1);
        cut = sp > 0 ? sp : cut - 1;
      }
      txt(rest.substring(0, cut), 160, 108 + line * 17, C_MAIN, MC_DATUM);
      rest = rest.substring(cut);
      rest.trim();
    }
    if ((millis() / 500) % 2) txt("[ TOCCA PER CONTINUARE ]", 160, 160, C_DIM, MC_DATUM, 1);
  } else {
    txtG(msgL1, 160, 94, C_HI, MC_DATUM);
    txt(msgL2, 160, 118, C_MAIN, MC_DATUM);
    if ((millis() / 500) % 2) txt("[ TOCCA PER CONTINUARE ]", 160, 152, C_DIM, MC_DATUM, 1);
  }
}

// =================================================================
//  GRAFICI - storico sensori (ultimi 2 minuti)
// =================================================================
void drawGrafici() {
  const char* L[4] = {"MEMORIA LIBERA", "TEMPERATURA CPU", "LUCE AMBIENTE", "SEGNALE WIFI"};
  const char* U[4] = {"%", "C", "%", "%"};
  for (int k = 0; k < 4; k++) {
    int px = 4 + (k % 2) * 158, py = 48 + (k / 2) * 84, pw = 154, ph = 80;
    chamfer(px, py, pw, ph, 6, C_DIM2);
    txt(L[k], px + 6, py + 5, C_DIM, TL_DATUM, 1);
    int gx = px + 6, gy = py + 18, gw = pw - 12, gh = ph - 32;
    for (int i = 1; i < 4; i++) dotted(gx, gy + gh * i / 4, gx + gw, gy + gh * i / 4, C_FAINT);
    if (histN == 0) { txt("IN ATTESA...", px + pw / 2, gy + gh / 2, C_DIM2, MC_DATUM, 1); continue; }
    int lo = 100, hi = 0, prevX = -1, prevY = 0;
    for (int i = 0; i < histN; i++) {
      int v = hist[k][(histPos - histN + i + HIST) % HIST];
      lo = min(lo, v); hi = max(hi, v);
    }
    // scala automatica: almeno 20 punti di escursione, con un po' di margine
    int a = max(0, lo - 4), b = min(100, hi + 4);
    if (b - a < 20) { b = min(100, (a + b) / 2 + 10); a = max(0, b - 20); b = a + 20; }
    for (int i = 0; i < histN; i++) {
      int v = hist[k][(histPos - histN + i + HIST) % HIST];
      int x = gx + (HIST - histN + i) * gw / (HIST - 1);
      int y = gy + gh - (constrain(v, a, b) - a) * gh / (b - a);
      spr.drawFastVLine(x, y, gy + gh - y, C_FAINT);
      if (prevX >= 0) spr.drawLine(prevX, prevY, x, y, C_MAIN);
      prevX = x; prevY = y;
    }
    spr.fillCircle(prevX, prevY, 2, C_HI);
    int last = hist[k][(histPos + HIST - 1) % HIST];
    txtG(String(last) + U[k], px + pw - 6, py + 2, C_HI, TR_DATUM);
    txt("MIN " + String(lo) + "   MAX " + String(hi), gx, py + ph - 11, C_DIM2, TL_DATUM, 1);
  }
}

// =================================================================
//  METEO - Open-Meteo (nessuna chiave API), posizione stimata dall'IP
// =================================================================
int wxIcon(int c) {
  if (c == 0) return 0;
  if (c <= 2) return 1;
  if (c == 3) return 2;
  if (c == 45 || c == 48) return 3;
  if ((c >= 71 && c <= 77) || c == 85 || c == 86) return 5;
  if (c >= 95) return 6;
  if (c >= 51) return 4;
  return 2;
}

const char* wxText(int c) {
  if (c == 0) return "SERENO";
  if (c == 1) return "PREVAL. SERENO";
  if (c == 2) return "POCO NUVOLOSO";
  if (c == 3) return "COPERTO";
  if (c == 45 || c == 48) return "NEBBIA";
  if (c >= 51 && c <= 57) return "PIOGGERELLA";
  if (c >= 61 && c <= 67) return "PIOGGIA";
  if (c >= 71 && c <= 77) return "NEVE";
  if (c >= 80 && c <= 82) return "ROVESCI";
  if (c == 85 || c == 86) return "ROVESCI DI NEVE";
  if (c == 95) return "TEMPORALE";
  if (c >= 96) return "TEMPORALE+GRANDINE";
  return "--";
}

// nuvola: g = spessore aggiuntivo (per il bordo)
void cloudShape(int x, int y, float s, int g, uint8_t c) {
  spr.fillCircle(x - 11 * s, y + 3 * s, 8 * s + g, c);
  spr.fillCircle(x + 1 * s, y - 4 * s, 11 * s + g, c);
  spr.fillCircle(x + 13 * s, y + 3 * s, 8 * s + g, c);
  spr.fillRect(x - 11 * s, y + 3 * s, 24 * s + 1, 8 * s + g + 1, c);
}

void sunShape(int x, int y, float s, uint8_t c) {
  float rot = millis() / 2500.0;
  spr.fillCircle(x, y, 8 * s, c);
  for (int i = 0; i < 8; i++) {
    float a = rot + i * PI / 4;
    spr.drawLine(x + cos(a) * 12 * s, y + sin(a) * 12 * s, x + cos(a) * 17 * s, y + sin(a) * 17 * s, c);
  }
}

void drawWxIcon(int x, int y, float s, int type) {
  unsigned long t = millis();
  int fall = (int)(14 * s) + 1;
  switch (type) {
    case 0: sunShape(x, y, s, C_HI); break;
    case 1:
      sunShape(x + 8 * s, y - 7 * s, s * 0.8, C_HI);
      cloudShape(x - 2 * s, y + 5 * s, s * 0.85, 1, C_MAIN);
      cloudShape(x - 2 * s, y + 5 * s, s * 0.85, 0, C_DARK);
      break;
    case 3:
      for (int i = 0; i < 4; i++) {
        int o = (int)(sin(t / 500.0 + i) * 3 * s);
        spr.drawFastHLine(x - 18 * s + o, y - 9 * s + i * 6 * s, 36 * s, i % 2 ? C_MID : C_MAIN);
      }
      break;
    default:
      cloudShape(x, y - 4 * s, s, 1, C_MAIN);
      cloudShape(x, y - 4 * s, s, 0, type == 6 ? C_DIM2 : C_DARK);
      if (type == 4)
        for (int i = 0; i < 5; i++) {
          int dy = (t / 40 + i * 7) % fall, xx = x - 12 * s + i * 6 * s;
          spr.drawLine(xx, y + 9 * s + dy, xx - 2, y + 9 * s + dy + 4 * s, C_HI);
        }
      if (type == 5)
        for (int i = 0; i < 5; i++) {
          int dy = (t / 70 + i * 5) % fall;
          spr.fillCircle(x - 12 * s + i * 6 * s, y + 10 * s + dy, max(1, (int)(1.5 * s)), C_HI);
        }
      if (type == 6 && (t / 150) % 8 < 3) {
        int ly = y + 6 * s;
        spr.fillTriangle(x + 2 * s, ly, x - 5 * s, ly + 10 * s, x + 1 * s, ly + 9 * s, C_HI);
        spr.fillTriangle(x + 1 * s, ly + 7 * s, x + 5 * s, ly + 8 * s, x - 3 * s, ly + 18 * s, C_HI);
      }
  }
}

String httpGet(const char* url) {
  HTTPClient http;
  http.setConnectTimeout(6000);
  http.setTimeout(8000);
  if (!http.begin(url)) return String();
  int code = http.GET();
  String body = code == 200 ? http.getString() : String();
  http.end();
  return body;
}

float jNum(const String& s, const char* key, int from) {
  int i = s.indexOf(key, from);
  return i < 0 ? NAN : atof(s.c_str() + i + strlen(key));
}

int jArr(const String& s, const char* key, int from, float* out, int n) {
  int i = s.indexOf(key, from);
  if (i < 0) return 0;
  i = s.indexOf('[', i);
  if (i < 0) return 0;
  const char* p = s.c_str() + i + 1;
  int k = 0;
  while (k < n && *p && *p != ']') {
    out[k++] = atof(p);
    while (*p && *p != ',' && *p != ']') p++;
    if (*p == ',') p++;
  }
  return k;
}

// legge una stringa JSON: key e' tipo "\"city\":" (tollera spazi prima delle virgolette)
void jStr(const String& s, const char* key, char* out, int n) {
  out[0] = 0;
  int i = s.indexOf(key);
  if (i < 0) return;
  i += strlen(key);
  while (i < (int)s.length() && (s[i] == ' ' || s[i] == '"')) i++;
  int k = 0;
  while (k < n - 1 && i < (int)s.length() && s[i] != '"') {
    uint8_t c = s[i++];
    if (c >= 32 && c < 127) out[k++] = toupper(c);
    else if (c == 0xC3 && i < (int)s.length()) {       // vocali accentate UTF-8 -> lettera base
      uint8_t b = (uint8_t)s[i++] & 0xDF;              // minuscole e maiuscole insieme
      char m = b <= 0x85 ? 'A' : (b >= 0x88 && b <= 0x8B) ? 'E' : (b >= 0x8C && b <= 0x8F) ? 'I'
             : (b >= 0x92 && b <= 0x96) ? 'O' : (b >= 0x99 && b <= 0x9C) ? 'U' : 0;
      if (m) out[k++] = m;
    }
  }
  out[k] = 0;
}

void wxTask(void*) {
  Weather w = {};
  bool good = false;
  if (isnan(geoLat)) {                       // posizione approssimativa dall'IP
    String g = httpGet("http://ip-api.com/json/?fields=status,city,lat,lon");
    if (g.indexOf("\"success\"") >= 0) {
      geoLat = jNum(g, "\"lat\":", 0);
      geoLon = jNum(g, "\"lon\":", 0);
      jStr(g, "\"city\":", geoCity, sizeof(geoCity));
    } else {                                 // servizio di riserva (HTTPS)
      g = httpGet("https://ipapi.co/json/");
      geoLat = jNum(g, "\"latitude\":", 0);
      geoLon = jNum(g, "\"longitude\":", 0);
      jStr(g, "\"city\":", geoCity, sizeof(geoCity));
    }
  }
  if (!isnan(geoLat) && !isnan(geoLon)) {
    String r;
    int c = -1, d = -1;
    const char* proto[2] = {"http", "https"};  // prima HTTP (piu' leggero), poi HTTPS
    for (int k = 0; k < 2 && (c < 0 || d < 0); k++) {
      char url[330];
      snprintf(url, sizeof(url),
               "%s://api.open-meteo.com/v1/forecast?latitude=%.3f&longitude=%.3f"
               "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
               "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=4",
               proto[k], geoLat, geoLon);
      r = httpGet(url);
      c = r.indexOf("\"current\":{");
      d = r.indexOf("\"daily\":{");
    }
    if (c >= 0 && d >= 0) {
      w.t = jNum(r, "\"temperature_2m\":", c);
      w.hum = (int)jNum(r, "\"relative_humidity_2m\":", c);
      w.wind = jNum(r, "\"wind_speed_10m\":", c);
      w.code = (int)jNum(r, "\"weather_code\":", c);
      float codes[4] = {0, 0, 0, 0};
      jArr(r, "\"weather_code\":", d, codes, 4);
      for (int i = 0; i < 4; i++) w.dCode[i] = (int)codes[i];
      jArr(r, "\"temperature_2m_max\":", d, w.dMax, 4);
      jArr(r, "\"temperature_2m_min\":", d, w.dMin, 4);
      strncpy(w.city, geoCity, sizeof(w.city) - 1);
      strncpy(w.upd, shortTime().c_str(), 5);
      w.ok = !isnan(w.t);
      good = w.ok;
    }
  }
  if (good) {
    portENTER_CRITICAL(&wxMux);
    wx = w;
    portEXIT_CRITICAL(&wxMux);
  }
  wxState = good ? 2 : 3;
  vTaskDelete(NULL);
}

void startWeather() {
  if (wxState == 1 || WiFi.status() != WL_CONNECTED) return;
  wxState = 1;
  wxLast = millis();
  if (xTaskCreatePinnedToCore(wxTask, "meteo", 16384, NULL, 1, NULL, 0) != pdPASS) wxState = 3;
}

void pollWeather() {
  static int was = 0;
  int st = wxState;
  if (st != was) {
    if (st == 2) addLog("METEO AGGIORNATO");
    else if (st == 3) addLog("METEO: ERRORE DI RICEZIONE");
    was = st;
  }
  if (WiFi.status() != WL_CONNECTED || st == 1) return;
  unsigned long iv = st == 3 ? 60000UL : 900000UL;
  if (st == 0 || millis() - wxLast > iv) startWeather();
}

void drawMeteo() {
  Weather w;
  portENTER_CRITICAL(&wxMux);
  w = wx;
  portEXIT_CRITICAL(&wxMux);
  bool wc = WiFi.status() == WL_CONNECTED;
  if (!w.ok) {
    if (wxState == 1) scanAnim(120, "CONTATTO STAZIONE METEO...");
    else if (!wc) {
      drawWxIcon(160, 86, 1.2, 2);
      txt("STAZIONE METEO NON RAGGIUNGIBILE", 160, 140, C_MAIN, MC_DATUM);
      txt("CONNETTI IL WIFI DA RADIO > WIFI", 160, 162, C_DIM, MC_DATUM);
    } else {
      txt(wxState == 3 ? "ERRORE DI RICEZIONE" : "IN ATTESA DATI", 160, 110, C_MAIN, MC_DATUM);
      txt("TOCCA PER RIPROVARE", 160, 134, C_DIM, MC_DATUM);
    }
    return;
  }
  brackets(4, 48, 94, 92, 8, C_DIM);
  drawWxIcon(51, 92, 1.4, wxIcon(w.code));
  String tt = String((int)lroundf(w.t));
  txtG(tt, 106, 52, C_HI, TL_DATUM, 7);
  int tw = spr.textWidth(tt, 7);
  spr.drawCircle(112 + tw, 58, 3, C_HI);
  txt("C", 118 + tw, 54, C_HI, TL_DATUM, 4);
  txt(w.city[0] ? String(w.city).substring(0, 14) : String("POSIZIONE IP"), 314, 50, C_DIM, TR_DATUM);
  txt("UMIDITA' " + String(w.hum) + "%", 314, 70, C_MAIN, TR_DATUM);
  txt("VENTO " + String((int)lroundf(w.wind)) + " KM/H", 314, 88, C_MAIN, TR_DATUM);
  txtG(wxText(w.code), 106, 106, C_MAIN);
  if (wxState == 1) { if ((millis() / 300) % 2) txt("AGGIORNAMENTO IN CORSO...", 106, 128, C_DIM, TL_DATUM, 1); }
  else txt("AGG. " + String(w.upd) + "  (TOCCA = AGGIORNA)", 106, 128, C_DIM2, TL_DATUM, 1);

  struct tm ti;
  bool hasDay = getNow(ti);
  for (int i = 0; i < 3; i++) {
    int x = 4 + i * 106;
    chamfer(x, 146, 100, 66, 6, i == 0 ? C_DIM : C_DIM2);
    String dn = i == 0 ? String("OGGI") : hasDay ? String(GIORNI[(ti.tm_wday + i) % 7]).substring(0, 3) : "+" + String(i) + "G";
    txt(dn, x + 8, 150, i == 0 ? C_HI : C_MAIN);
    drawWxIcon(x + 28, 188, 0.6, wxIcon(w.dCode[i]));
    txt(String((int)lroundf(w.dMax[i])), x + 94, 166, C_HI, TR_DATUM, 4);
    txt(String((int)lroundf(w.dMin[i])), x + 94, 194, C_DIM, TR_DATUM);
  }
}

// =================================================================
//  GIOCO - TERMINALE (trova la password tra le parole)
// =================================================================
int likeness(const char* a, const char* b) {
  int n = 0;
  for (int i = 0; a[i] && b[i]; i++) if (a[i] == b[i]) n++;
  return n;
}

void newTerminal() {
  const char* J = "!@#$%&*<>?/|;:+=-_[]{}";
  int jn = strlen(J);
  for (int i = 0; i < TW_N; i++) {
    int w;
    bool dup;
    do {
      w = random(WORDS_N);
      dup = false;
      for (int j = 0; j < i; j++) if (twW[j] == w) dup = true;
    } while (dup);
    twW[i] = w;
    twUsed[i] = false;
    twJunk[i][0] = J[random(jn)];
    twJunk[i][1] = J[random(jn)];
  }
  twAns = random(TW_N);
  twTries = 4;
  twLogN = 0;
  twState = 0;
  twAddr = (0xF000 + random(0x0F00)) & 0xFFF0;
}

void drawTerminal() {
  txt("TERMLINK VX-26 // PROTETTO", 6, 48, C_DIM, TL_DATUM, 1);
  txt("TENTATIVI", 214, 48, C_DIM, TL_DATUM, 1);
  for (int i = 0; i < 4; i++) spr.fillRect(272 + i * 11, 48, 8, 8, i < twTries ? C_HI : C_DARK);
  for (int i = 0; i < TW_N; i++) {
    int x = 4 + (i / 6) * 104, y = 62 + (i % 6) * 21;
    char ad[6];
    snprintf(ad, sizeof(ad), "%04X", (unsigned)(twAddr + i * 12));
    txt(ad, x, y + 5, C_DIM2, TL_DATUM, 1);
    char j1[2] = {twJunk[i][0], 0}, j2[2] = {twJunk[i][1], 0};
    const char* word = WORDS[twW[i]];
    int cx = x + 27;
    txt(j1, cx, y + 1, C_DIM2);
    cx += spr.textWidth(j1, 2) + 1;
    int ww = spr.textWidth(word, 2);
    if (twState != 0 && i == twAns) {
      spr.fillRect(cx - 1, y, ww + 2, 17, C_MAIN);
      txt(word, cx, y + 1, BG);
    } else txt(word, cx, y + 1, twUsed[i] ? C_DIM2 : C_MAIN);
    txt(j2, cx + ww + 1, y + 1, C_DIM2);
  }
  chamfer(212, 60, 106, 152, 6, C_DIM2);
  int ly = 66;
  for (int i = 0; i < twLogN; i++) {
    txt(String("> ") + WORDS[twW[twLogW[i]]], 218, ly, twLogW[i] == twAns ? C_HI : C_MAIN);
    ly += 15;
    txt("ESATTE " + String(twLogL[i]) + "/5", 228, ly, C_DIM, TL_DATUM, 1);
    ly += 13;
  }
  if (twState == 0) {
    if ((millis() / 400) % 2) txt(">_", 218, ly, C_HI);
    txt("TOCCA LA PASSWORD GIUSTA", 6, 196, C_DIM2, TL_DATUM, 1);
  } else if (twState == 1) {
    txtG("ACCESSO", 265, 184, C_HI, MC_DATUM);
    txtG("CONSENTITO", 265, 200, C_HI, MC_DATUM);
    txt("TOCCA = NUOVO TERMINALE", 6, 196, C_DIM, TL_DATUM, 1);
  } else {
    long left = (long)twLockUntil - (long)millis();
    if ((millis() / 300) % 2) txtG("BLOCCATO", 265, 184, C_HI, MC_DATUM);
    if (left > 0) txt("SBLOCCO TRA " + String(left / 1000 + 1) + "s", 265, 202, C_MAIN, MC_DATUM, 1);
    else txt("TOCCA = NUOVO", 265, 202, C_MAIN, MC_DATUM, 1);
  }
}

void termTouch(int x, int y) {
  if (twState == 1 || (twState == 2 && millis() > twLockUntil)) { newTerminal(); glitchUntil = millis() + 120; return; }
  if (twState != 0 || x >= 212 || y < 60 || y >= 60 + 6 * 21) return;
  int i = (x < 108 ? 0 : 6) + (y - 60) / 21;
  if (i >= TW_N || twUsed[i]) return;
  twUsed[i] = true;
  twLogW[twLogN] = i;
  twLogL[twLogN] = likeness(WORDS[twW[i]], WORDS[twW[twAns]]);
  twLogN++;
  if (i == twAns) {
    twState = 1;
    glitchUntil = millis() + 200;
    sndOk();
    addLog("TERMINALE: ACCESSO OTTENUTO");
    completeQuest(3);
    addXp(60);
  } else if (--twTries == 0) {
    twState = 2;
    twLockUntil = millis() + 10000;
    glitchUntil = millis() + 300;
    sndErr();
    addLog("TERMINALE BLOCCATO");
  } else queueTone(600, 60);
}

// =================================================================
//  GIOCO - SERPENTE
// =================================================================
void snPlaceFood() {
  for (int t = 0; t < 500; t++) {
    int fx = random(SN_COLS), fy = random(SN_ROWS);
    bool hit = false;
    for (int i = 0; i < snLen; i++) if (snX[i] == fx && snY[i] == fy) { hit = true; break; }
    if (!hit) { snFx = fx; snFy = fy; return; }
  }
}

void snReset() {
  snLen = 4;
  for (int i = 0; i < snLen; i++) { snX[i] = 10 - i; snY[i] = SN_ROWS / 2; }
  snDx = snNdx = 1;
  snDy = snNdy = 0;
  snScore = 0;
  snPlaceFood();
}

void snStep() {
  snDx = snNdx; snDy = snNdy;
  int nx = snX[0] + snDx, ny = snY[0] + snDy;
  bool dead = nx < 0 || ny < 0 || nx >= SN_COLS || ny >= SN_ROWS;
  for (int i = 0; i < snLen - 1 && !dead; i++) if (snX[i] == nx && snY[i] == ny) dead = true;
  if (dead) {
    snState = 2;
    snDeadT = millis();
    glitchUntil = millis() + 220;
    sndErr();
    if (snScore > snHi) {
      snHi = snScore;
      prefs.putInt("snhi", snHi);
      addLog("SERPENTE: RECORD " + String(snHi));
    }
    addXp(snScore * 3);
    return;
  }
  bool eat = nx == snFx && ny == snFy;
  if (eat && snLen < SN_COLS * SN_ROWS) snLen++;
  memmove(snX + 1, snX, snLen - 1);
  memmove(snY + 1, snY, snLen - 1);
  snX[0] = nx; snY[0] = ny;
  if (eat) { snScore++; sndEat(); snPlaceFood(); }
}

void snakeTouch(int x, int y) {
  if (snState == 2 && millis() - snDeadT < 700) return;
  if (snState == 0 || snState == 2) { snReset(); snState = 1; snLast = millis(); return; }
  if (snState == 3) { snState = 1; snLast = millis(); return; }
  int hx = SN_X0 + snX[0] * SN_CELL + 4, hy = SN_Y0 + snY[0] * SN_CELL + 4;
  if (snDx != 0) { snNdx = 0; snNdy = y < hy ? -1 : 1; }
  else           { snNdy = 0; snNdx = x < hx ? -1 : 1; }
}

void drawSnake() {
  txt("PUNTI " + String(snScore), 8, 47, C_HI, TL_DATUM, 1);
  txt("RECORD " + String(snHi), 312, 47, C_DIM, TR_DATUM, 1);
  chamfer(SN_X0 - 3, SN_Y0 - 3, SN_COLS * SN_CELL + 6, SN_ROWS * SN_CELL + 6, 4, C_DIM);
  for (int gy = 0; gy < SN_ROWS; gy += 2)
    for (int gx = 0; gx < SN_COLS; gx += 2) spr.drawPixel(SN_X0 + gx * SN_CELL + 4, SN_Y0 + gy * SN_CELL + 4, C_FAINT);
  int fx = SN_X0 + snFx * SN_CELL, fy = SN_Y0 + snFy * SN_CELL;
  spr.fillRect(fx + 2, fy + 2, 4, 4, C_HI);
  if ((millis() / 200) % 2) spr.drawRect(fx, fy, 8, 8, C_MAIN);
  for (int i = snLen - 1; i >= 0; i--) {
    int px = SN_X0 + snX[i] * SN_CELL, py = SN_Y0 + snY[i] * SN_CELL;
    spr.fillRect(px + 1, py + 1, 6, 6, i == 0 ? C_HI : (i < snLen / 2 ? C_MAIN : C_MID));
  }
  if (snState != 1) {
    chamferFill(70, 98, 180, 60, 8, BG);
    chamfer(70, 98, 180, 60, 8, C_MAIN);
    const char* t1 = snState == 0 ? "SERPENTE" : snState == 2 ? "GAME OVER" : "PAUSA";
    txtG(t1, 160, 118, C_HI, MC_DATUM, 4);
    if ((millis() / 500) % 2) txt(snState == 3 ? "TOCCA PER RIPRENDERE" : "TOCCA PER INIZIARE", 160, 146, C_DIM, MC_DATUM, 1);
  }
  txt("TOCCA SOPRA/SOTTO O A SX/DX DELLA TESTA", 160, 210, C_DIM2, MC_DATUM, 1);
}

// =================================================================
//  SALVASCHERMO - pioggia di codice + orologio che si sposta
// =================================================================
void initSaver() {
  for (int i = 0; i < DROPS; i++) {
    drops[i].y = random(-240, 0);
    drops[i].sp = random(2, 7);
    drops[i].len = random(5, 16);
  }
}

void drawSaver() {
  static const char G[] = "0123456789ABCDEF<>#$%&*+=?";
  unsigned long t = millis();
  for (int i = 0; i < DROPS; i++) {
    Drop& d = drops[i];
    for (int k = 0; k < d.len; k++) {
      int cy = d.y - k * 9;
      if (cy < -8 || cy >= 240) continue;
      uint32_t h = ((uint32_t)i * 2654435761u) ^ ((uint32_t)(cy / 9 + 64) * 40503u) ^ (t / 350);
      char ch[2] = {G[h % (sizeof(G) - 1)], 0};
      uint8_t c = k == 0 ? C_HI : k < 3 ? C_MAIN : k < d.len / 2 ? C_MID : k < d.len - 2 ? C_DIM : C_DIM2;
      txt(ch, i * 6, cy, c, TL_DATUM, 1);
    }
    d.y += d.sp;
    if (d.y - d.len * 9 > 240) { d.y = random(-60, 0); d.sp = random(2, 7); d.len = random(5, 16); }
  }
  struct tm ti;
  String clk = getNow(ti) ? two(ti.tm_hour) + ":" + two(ti.tm_min) : uptimeStr().substring(0, 5);
  int ox = 160 + (int)(sin(t / 7000.0) * 60), oy = 120 + (int)(sin(t / 5300.0) * 38);
  chamferFill(ox - 90, oy - 40, 180, 80, 10, BG);
  chamfer(ox - 90, oy - 40, 180, 80, 10, C_MAIN);
  txtG(clk, ox, oy - 8, C_HI, MC_DATUM, 6);
  txt("VX-26 IN STANDBY", ox, oy + 26, C_DIM, MC_DATUM, 1);
}

// =================================================================
//  CALIBRAZIONE TOUCH
// =================================================================
const int CAL_PT[2][2] = {{24, 24}, {296, 216}};

void startCalib() { calStep = 0; modal = M_CAL; }

void drawCalib() {
  txtG("CALIBRAZIONE TOUCH", 160, 100, C_HI, MC_DATUM);
  txt("TOCCA IL CENTRO DEL MIRINO  " + String(calStep + 1) + "/2", 160, 122, C_MAIN, MC_DATUM);
  txt("usa un pennino o la punta dell'unghia", 160, 142, C_DIM, MC_DATUM, 1);
  int x = CAL_PT[calStep][0], y = CAL_PT[calStep][1];
  spr.drawCircle(x, y, 6 + (millis() / 60) % 10, C_DIM);
  spr.drawCircle(x, y, 5, C_HI);
  spr.drawFastHLine(x - 14, y, 29, C_HI);
  spr.drawFastVLine(x, y - 14, 29, C_HI);
}

void calTouch() {
  calRaw[calStep][0] = rawX;
  calRaw[calStep][1] = rawY;
  if (++calStep < 2) return;
  float kx = (calRaw[1][0] - calRaw[0][0]) / (float)(CAL_PT[1][0] - CAL_PT[0][0]);
  float ky = (calRaw[1][1] - calRaw[0][1]) / (float)(CAL_PT[1][1] - CAL_PT[0][1]);
  if (fabs(kx) < 4 || fabs(ky) < 4) {
    msgL1 = "CALIBRAZIONE NON VALIDA";
    msgL2 = "Riprova toccando i mirini";
    modal = M_MSG;
    sndErr();
    return;
  }
  cfg.tminx = calRaw[0][0] - kx * CAL_PT[0][0];
  cfg.tmaxx = cfg.tminx + kx * 320;
  cfg.tminy = calRaw[0][1] - ky * CAL_PT[0][1];
  cfg.tmaxy = cfg.tminy + ky * 240;
  saveConfig();
  msgL1 = "TOUCH CALIBRATO";
  msgL2 = "Impostazioni salvate";
  modal = M_MSG;
  sndOk();
  addLog("TOUCH CALIBRATO");
}

// =================================================================
//  CODICE QR (versione 3, correzione L: fino a 53 caratteri)
// =================================================================
#define QR_N 29
uint8_t qrMod[QR_N][QR_N];        // 1 = modulo scuro
uint8_t qrFun[QR_N][QR_N];        // 1 = modulo di servizio (non mascherabile)
char qrCached[64] = "";

static uint8_t gfMul(uint8_t x, uint8_t y) {
  int z = 0;
  for (int i = 7; i >= 0; i--) {
    z = (z << 1) ^ ((z >> 7) * 0x11D);
    z ^= ((y >> i) & 1) * x;
  }
  return (uint8_t)z;
}

static void qrSetF(int x, int y, bool dark) { qrMod[y][x] = dark; qrFun[y][x] = 1; }

static void qrFinder(int cx, int cy) {
  for (int dy = -4; dy <= 4; dy++)
    for (int dx = -4; dx <= 4; dx++) {
      int x = cx + dx, y = cy + dy;
      if (x < 0 || y < 0 || x >= QR_N || y >= QR_N) continue;
      int d = max(abs(dx), abs(dy));
      qrSetF(x, y, d != 2 && d != 4);
    }
}

static void qrFormat(int mask) {
  int data = (1 << 3) | mask;                    // livello L = 01
  int rem = data;
  for (int i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >> 9) * 0x537);
  int bits = ((data << 10) | rem) ^ 0x5412;
  auto bit = [&](int i) { return ((bits >> i) & 1) != 0; };
  for (int i = 0; i <= 5; i++) qrSetF(8, i, bit(i));
  qrSetF(8, 7, bit(6));
  qrSetF(8, 8, bit(7));
  qrSetF(7, 8, bit(8));
  for (int i = 9; i < 15; i++) qrSetF(14 - i, 8, bit(i));
  for (int i = 0; i < 8; i++) qrSetF(QR_N - 1 - i, 8, bit(i));
  for (int i = 8; i < 15; i++) qrSetF(8, QR_N - 15 + i, bit(i));
  qrSetF(8, QR_N - 8, true);                     // modulo scuro fisso
}

static bool qrMaskBit(int m, int x, int y) {
  switch (m) {
    case 0: return (x + y) % 2 == 0;
    case 1: return y % 2 == 0;
    case 2: return x % 3 == 0;
    case 3: return (x + y) % 3 == 0;
    case 4: return (x / 3 + y / 2) % 2 == 0;
    case 5: return x * y % 2 + x * y % 3 == 0;
    case 6: return (x * y % 2 + x * y % 3) % 2 == 0;
    default: return ((x + y) % 2 + x * y % 3) % 2 == 0;
  }
}

static void qrApplyMask(int m) {
  for (int y = 0; y < QR_N; y++)
    for (int x = 0; x < QR_N; x++)
      if (!qrFun[y][x] && qrMaskBit(m, x, y)) qrMod[y][x] ^= 1;
}

// penalita' semplificata (righe/colonne uniformi, blocchi 2x2, bilanciamento)
static long qrPenalty() {
  long p = 0;
  int dark = 0;
  for (int pass = 0; pass < 2; pass++)
    for (int a = 0; a < QR_N; a++) {
      int run = 1;
      for (int b = 1; b < QR_N; b++) {
        bool c = pass ? qrMod[b][a] : qrMod[a][b], pc = pass ? qrMod[b - 1][a] : qrMod[a][b - 1];
        if (c == pc) { if (++run == 5) p += 3; else if (run > 5) p++; }
        else run = 1;
      }
    }
  for (int y = 0; y < QR_N - 1; y++)
    for (int x = 0; x < QR_N - 1; x++) {
      int c = qrMod[y][x];
      if (c == qrMod[y][x + 1] && c == qrMod[y + 1][x] && c == qrMod[y + 1][x + 1]) p += 3;
    }
  for (int y = 0; y < QR_N; y++) for (int x = 0; x < QR_N; x++) dark += qrMod[y][x];
  int k = abs(dark * 20 - QR_N * QR_N * 10) / (QR_N * QR_N);
  return p + k * 10;
}

void qrMake(const char* text) {
  if (strcmp(text, qrCached) == 0) return;
  strncpy(qrCached, text, sizeof(qrCached) - 1);
  const int DATA = 55, ECC = 15;
  uint8_t cw[DATA + ECC];
  memset(cw, 0, sizeof(cw));
  int len = min((int)strlen(text), 53), bitPos = 0;
  auto put = [&](int val, int n) {
    for (int i = n - 1; i >= 0; i--, bitPos++)
      if ((val >> i) & 1) cw[bitPos >> 3] |= 0x80 >> (bitPos & 7);
  };
  put(4, 4);                                     // modalita' byte
  put(len, 8);
  for (int i = 0; i < len; i++) put((uint8_t)text[i], 8);
  put(0, min(4, DATA * 8 - bitPos));             // terminatore
  bitPos = (bitPos + 7) & ~7;
  for (int i = bitPos / 8, k = 0; i < DATA; i++, k++) cw[i] = k % 2 ? 0x11 : 0xEC;

  uint8_t gen[ECC], root = 1;                    // Reed-Solomon
  memset(gen, 0, sizeof(gen));
  gen[ECC - 1] = 1;
  for (int i = 0; i < ECC; i++) {
    for (int j = 0; j < ECC; j++) {
      gen[j] = gfMul(gen[j], root);
      if (j + 1 < ECC) gen[j] ^= gen[j + 1];
    }
    root = gfMul(root, 2);
  }
  uint8_t* ec = cw + DATA;
  for (int i = 0; i < DATA; i++) {
    uint8_t f = cw[i] ^ ec[0];
    memmove(ec, ec + 1, ECC - 1);
    ec[ECC - 1] = 0;
    for (int j = 0; j < ECC; j++) ec[j] ^= gfMul(gen[j], f);
  }

  memset(qrMod, 0, sizeof(qrMod));               // moduli di servizio
  memset(qrFun, 0, sizeof(qrFun));
  for (int i = 0; i < QR_N; i++) { qrSetF(6, i, i % 2 == 0); qrSetF(i, 6, i % 2 == 0); }
  qrFinder(3, 3); qrFinder(QR_N - 4, 3); qrFinder(3, QR_N - 4);
  for (int dy = -2; dy <= 2; dy++)
    for (int dx = -2; dx <= 2; dx++) qrSetF(22 + dx, 22 + dy, max(abs(dx), abs(dy)) != 1);
  qrFormat(0);

  int i = 0;                                     // dati a zig-zag
  for (int right = QR_N - 1; right >= 1; right -= 2) {
    if (right == 6) right = 5;
    for (int v = 0; v < QR_N; v++)
      for (int j = 0; j < 2; j++) {
        int x = right - j, y = ((right + 1) & 2) == 0 ? QR_N - 1 - v : v;
        if (!qrFun[y][x] && i < (DATA + ECC) * 8) { qrMod[y][x] = (cw[i >> 3] >> (7 - (i & 7))) & 1; i++; }
      }
  }

  int best = 0;
  long bestP = -1;
  for (int m = 0; m < 8; m++) {                  // sceglie la maschera migliore
    qrApplyMask(m); qrFormat(m);
    long p = qrPenalty();
    if (bestP < 0 || p < bestP) { bestP = p; best = m; }
    qrApplyMask(m);
  }
  qrApplyMask(best); qrFormat(best);
}
// =================================================================
//  TIMER - conto alla rovescia e cronometro
// =================================================================
long timerLeft() { return tmRun ? max(0L, tmLeft - (long)(millis() - tmStart)) : tmLeft; }
long cronoNow() { return crRun ? crBase + (long)(millis() - crStart) : crBase; }

// minuti:secondi (up = arrotonda per eccesso, per il conto alla rovescia)
String mmss(long ms, bool up) {
  long s = up ? (ms + 999) / 1000 : ms / 1000;
  return two((s / 60) % 100) + ":" + two(s % 60);
}

String crStr(long ms) { return mmss(ms, false) + "." + two((ms / 10) % 100); }

void pollTimer() {
  if (tmRun && timerLeft() == 0) {
    tmRun = false;
    tmLeft = 0;
    tmAlarm = true;
    tmAlarmT = millis();
    lastInput = millis();
    if (saverOn) { saverOn = false; applyBrightness(); }
    if (!(tab == 2 && sub[2] == S_TIMER) && modal == M_NONE) {
      msgL1 = "TEMPO SCADUTO";
      msgL2 = "Timer da " + mmss(tmSet, true);
      modal = M_MSG;
    }
    addLog("TIMER: TEMPO SCADUTO");
  }
  if (tmAlarm) {
    unsigned long e = millis() - tmAlarmT;
    if (e > 20000) tmAlarm = false;
    else if (toneLen == 0 && (e / 600) % 2 == 0) { queueTone(2400, 80); queueTone(0, 50); queueTone(2400, 80); queueTone(0, 50); }
  }
}

void drawTimer() {
  button(60, 48, 96, 20, "TIMER", tmMode == 0);
  button(164, 48, 96, 20, "CRONO", tmMode == 1);
  if (tmMode == 0) {
    long l = timerLeft();
    if (!(tmAlarm && (millis() / 250) % 2)) txtG(mmss(l, true), 160, 104, C_HI, MC_DATUM, 7);
    segBar(40, 140, 240, 8, tmSet > 0 ? (int)(l * 100 / tmSet) : 0, 24);
    if (tmAlarm) txtG("TEMPO SCADUTO - TOCCA", 160, 166, C_HI, MC_DATUM);
    else txt(tmRun ? "IN CORSO" : l == tmSet ? "IMPOSTA LA DURATA E PREMI AVVIA" : "IN PAUSA", 160, 166, C_DIM, MC_DATUM, 1);
    button(4, 190, 50, 22, "-1M");
    button(58, 190, 50, 22, "+1M");
    button(112, 190, 50, 22, "+5M");
    button(166, 190, 80, 22, tmRun ? "PAUSA" : "AVVIA", tmRun);
    button(250, 190, 66, 22, "AZZERA");
  } else {
    long c = cronoNow();
    String m = mmss(c, false);
    int w = spr.textWidth(m, 7), x0 = 160 - (w + 40) / 2;
    txtG(m, x0, 78, C_HI, TL_DATUM, 7);
    txt("." + two((c / 10) % 100), x0 + w + 4, 100, C_MAIN, TL_DATUM, 4);
    if (crLap[0] < 0) txt("GIRO: SALVA UN TEMPO PARZIALE", 160, 150, C_DIM, MC_DATUM, 1);
    for (int i = 0; i < 3; i++) {
      if (crLap[i] < 0) break;
      txt("GIRO " + String(crLapN - i), 96, 136 + i * 16, i == 0 ? C_MAIN : C_DIM);
      txt(crStr(crLap[i]), 224, 136 + i * 16, i == 0 ? C_HI : C_DIM, TR_DATUM);
    }
    button(4, 190, 100, 22, crRun ? "PAUSA" : "AVVIA", crRun);
    button(110, 190, 100, 22, "GIRO");
    button(216, 190, 100, 22, "AZZERA");
  }
}

void timerTouch(int x, int y) {
  if (y >= 44 && y < 72) {
    if (x >= 56 && x < 160) tmMode = 0;
    else if (x >= 160 && x < 264) tmMode = 1;
    return;
  }
  if (y < 186 || y >= 216) return;
  if (tmMode == 0) {
    long d = 0;
    if (x < 56) d = -60000;
    else if (x < 110) d = 60000;
    else if (x < 164) d = 300000;
    else if (x < 248) {
      if (tmRun) { tmLeft = timerLeft(); tmRun = false; }
      else {
        if (tmLeft == 0) tmLeft = tmSet;
        tmStart = millis();
        tmRun = true;
        addLog("TIMER AVVIATO " + mmss(tmLeft, true));
      }
      return;
    } else { tmRun = false; tmLeft = tmSet; return; }
    if (tmRun) { tmLeft = constrain(timerLeft() + d, 1000L, 5999000L); tmStart = millis(); }
    else { tmSet = constrain(tmSet + d, 60000L, 5940000L); tmLeft = tmSet; }
  } else {
    if (x < 107) {
      if (crRun) { crBase = cronoNow(); crRun = false; }
      else { crStart = millis(); crRun = true; }
    } else if (x < 213) {
      if (crRun) { crLap[2] = crLap[1]; crLap[1] = crLap[0]; crLap[0] = cronoNow(); crLapN++; }
    } else { crRun = false; crBase = 0; crLap[0] = crLap[1] = crLap[2] = -1; crLapN = 0; }
  }
}

// =================================================================
//  CANALI - analizzatore dello spettro WiFi a 2,4 GHz
// =================================================================
void drawCanali() {
  const int gx = 30, gy = 50, gw = 284, gh = 118;
  auto X = [&](float ch) { return gx + (int)((ch + 1) * gw / 16.0f); };
  auto Y = [&](int rssi) { return gy + (constrain(-30 - rssi, 0, 70)) * gh / 70; };
  for (int db = -30; db >= -90; db -= 20) {
    dotted(gx, Y(db), gx + gw, Y(db), C_FAINT);
    txt(String(db), gx - 4, Y(db) - 3, C_DIM2, TR_DATUM, 1);
  }
  spr.drawFastHLine(gx, gy + gh, gw, C_DIM);
  for (int c = 1; c <= 13; c++) {
    spr.drawFastVLine(X(c), gy + gh, 3, C_DIM);
    txt(String(c), X(c), gy + gh + 5, c == 1 || c == 6 || c == 11 ? C_MAIN : C_DIM2, TC_DATUM, 1);
  }
  if (wifiScanning) { scanAnim(108, "ANALISI SPETTRO..."); }
  else if (netCount == 0) txt("NESSUN DATO - PREMI SCAN", 160, 100, C_DIM, MC_DATUM);
  else {
    String cur = WiFi.status() == WL_CONNECTED ? WiFi.SSID() : String("");
    int lx[6], ly[6], ln = 0;
    for (int i = netCount - 1; i >= 0; i--) {         // i piu' forti disegnati per ultimi (sopra)
      int ch = constrain(nets[i].ch, 1, 13);
      bool isCur = cur.length() && nets[i].ssid == cur;
      uint8_t c = isCur ? C_HI : i < 3 ? C_MAIN : i < 6 ? C_MID : C_DIM;
      int top = Y(nets[i].rssi), base = gy + gh, px = -1, py = 0;
      for (int k = -20; k <= 20; k++) {
        float t = k / 10.0f;
        int x = X(ch + t), y = base - (int)((base - top) * (1 - t * t / 4));
        if (isCur && (k & 1) == 0) spr.drawFastVLine(x, y, base - y, C_DARK);
        if (px >= 0) spr.drawLine(px, py, x, y, c);
        px = x; py = y;
      }
    }
    for (int i = 0; i < netCount && ln < 6; i++) {    // etichette dei piu' forti senza sovrapporle
      int x = X(constrain(nets[i].ch, 1, 13)), y = Y(nets[i].rssi) - 10;
      bool clash = false;
      for (int k = 0; k < ln; k++) if (abs(lx[k] - x) < 46 && abs(ly[k] - y) < 10) clash = true;
      if (clash || y < gy - 2) continue;
      String s = nets[i].ssid.length() ? nets[i].ssid.substring(0, 9) : String("?");
      txt(s, x, y, i == 0 ? C_HI : C_MAIN, TC_DATUM, 1);
      lx[ln] = x; ly[ln] = y; ln++;
    }
  }
  // canale consigliato tra 1, 6, 11 (meno interferenze pesate per segnale)
  int best = 0;
  long load[3] = {0, 0, 0};
  const int CH3[3] = {1, 6, 11};
  for (int k = 0; k < 3; k++) {
    for (int i = 0; i < netCount; i++) {
      int d = abs(nets[i].ch - CH3[k]);
      if (d < 5) load[k] += (long)(5 - d) * (nets[i].rssi + 100);
    }
    if (load[k] < load[best]) best = k;
  }
  button(4, 190, 70, 22, "SCAN", wifiScanning && (millis() / 300) % 2);
  if (netCount) {
    txt("CANALE MIGLIORE", 84, 201, C_DIM, ML_DATUM, 1);
    txtG(String(CH3[best]), 186, 201, C_HI, ML_DATUM, 4);
    txt(String(netCount) + " RETI", 314, 201, C_DIM, MR_DATUM);
  } else txt("TOCCA SCAN PER ANALIZZARE", 196, 201, C_DIM, MC_DATUM, 1);
}

// =================================================================
//  LINK - pannello web, hotspot e codice QR
// =================================================================
String linkUrl() {
  if (WiFi.status() == WL_CONNECTED) return "http://" + WiFi.localIP().toString() + "/";
  if (cfg.ap) return "http://" + WiFi.softAPIP().toString() + "/";
  return "";
}

void applyAp() {
  if (cfg.ap) {
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(AP_SSID, AP_PASS);
    if (!mdnsOn && MDNS.begin(MDNS_NAME)) { MDNS.addService("http", "tcp", 80); mdnsOn = true; }
    addLog("HOTSPOT " + WiFi.softAPIP().toString());
  } else {
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
  }
}

void drawLink() {
  bool wc = WiFi.status() == WL_CONNECTED;
  String url = linkUrl();
  bool wifiQr = cfg.ap && qrShowWifi;
  const int bx = 6, by = 48, bs = QR_N * 4 + 16;
  if (url.length() || wifiQr) {
    qrMake(wifiQr ? "WIFI:T:WPA;S:" AP_SSID ";P:" AP_PASS ";;" : url.c_str());
    spr.fillRect(bx, by, bs, bs, C_HI);
    for (int y = 0; y < QR_N; y++)
      for (int x = 0; x < QR_N; x++)
        if (qrMod[y][x]) spr.fillRect(bx + 8 + x * 4, by + 8 + y * 4, 4, 4, BG);
  } else {
    chamfer(bx, by, bs, bs, 8, C_DIM2);
    txt("OFFLINE", bx + bs / 2, by + bs / 2 - 8, C_DIM, MC_DATUM);
    txt("niente da inquadrare", bx + bs / 2, by + bs / 2 + 10, C_DIM2, MC_DATUM, 1);
  }

  const int rx = bx + bs + 8;
  txt("PANNELLO WEB", rx, 48, C_DIM, TL_DATUM, 1);
  if (wc) {
    txtG(WiFi.localIP().toString(), rx, 58, C_HI);
    txt(mdnsOn ? "o  " MDNS_NAME ".local" : "dalla stessa rete WiFi", rx, 76, C_MAIN, TL_DATUM, 1);
  } else {
    txt(cfg.ap ? "SOLO VIA HOTSPOT" : "WIFI NON CONNESSO", rx, 58, C_MAIN);
    txt(cfg.ap ? "collegati alla rete qui sotto" : "connetti il WiFi o l'hotspot", rx, 76, C_DIM, TL_DATUM, 1);
  }
  spr.drawFastHLine(rx, 89, 316 - rx, C_FAINT);
  txt("HOTSPOT", rx, 107, C_MAIN, ML_DATUM);
  button(232, 96, 84, 22, cfg.ap ? "ON" : "OFF", cfg.ap);
  if (cfg.ap) {
    txt("RETE " AP_SSID, rx, 124, C_MAIN, TL_DATUM, 1);
    txt("PASS " AP_PASS, rx, 136, C_MAIN, TL_DATUM, 1);
    txt("IP " + WiFi.softAPIP().toString() + "  CLIENT " + String(WiFi.softAPgetStationNum()), rx, 148, C_DIM, TL_DATUM, 1);
  } else txt("rete propria " AP_SSID, rx, 124, C_DIM2, TL_DATUM, 1);
  spr.drawFastHLine(rx, 161, 316 - rx, C_FAINT);
  String last = webHits ? String((millis() - webLastHit) / 1000) + "s FA" : String("MAI");
  txt("RICHIESTE " + String(webHits), rx, 166, C_DIM, TL_DATUM, 1);
  txt("ULTIMA " + last, rx, 177, webHits && millis() - webLastHit < 3000 ? C_HI : C_DIM, TL_DATUM, 1);

  if (cfg.ap) button(4, 190, 148, 22, wifiQr ? "QR: HOTSPOT" : "QR: PANNELLO");
  else { txt("INQUADRA IL QR", 74, 196, C_DIM2, MC_DATUM, 1); txt("COL TELEFONO", 74, 207, C_DIM2, MC_DATUM, 1); }
  txt(wifiQr ? "1) ENTRA NELLA RETE" : "APRE IL PANNELLO", 238, 196, C_DIM, MC_DATUM, 1);
  txt(wifiQr ? "2) POI QR: PANNELLO" : "SCHERMO + COMANDI", 238, 207, C_DIM, MC_DATUM, 1);
}

void linkTouch(int x, int y) {
  if (inRect(x, y, 226, 90, 94, 34)) {
    cfg.ap = !cfg.ap;
    qrShowWifi = cfg.ap ? 1 : 0;
    applyAp();
    saveConfig();
  } else if (cfg.ap && inRect(x, y, 0, 186, 156, 30)) qrShowWifi ^= 1;
}

// ---------------- server web ----------------
const char PAGE[] PROGMEM = R"rawliteral(<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>VX-26 LINK</title><style>
:root{--c:#1eff46;--bg:#050805}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--c);
font:14px/1.4 ui-monospace,Menlo,Consolas,monospace}main{max-width:700px;margin:auto;padding:12px}
h1{font-size:18px;letter-spacing:3px;margin:4px 0 10px;display:flex;justify-content:space-between}
#dot{width:10px;height:10px;border-radius:50%;background:var(--c);display:inline-block;box-shadow:0 0 8px var(--c)}
.off #dot{background:#555;box-shadow:none}.scr{position:relative;border:2px solid var(--c);border-radius:14px;
padding:6px;background:#000;box-shadow:0 0 18px color-mix(in srgb,var(--c) 35%,transparent)}
#s{width:100%;display:block;image-rendering:pixelated;border-radius:8px;cursor:crosshair;aspect-ratio:4/3;background:#000}
.row{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}button,select,input{font:inherit;color:var(--c);
background:transparent;border:1px solid var(--c);border-radius:4px;padding:7px 10px}button:active{background:var(--c);color:#000}
.tabs button{flex:1}.on{background:var(--c);color:#000}.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:6px}
.k{border:1px solid color-mix(in srgb,var(--c) 40%,transparent);border-radius:4px;padding:6px 8px}
.k b{display:block;font-size:11px;opacity:.65;font-weight:normal}.bar{height:6px;border:1px solid var(--c);margin-top:4px}
.bar i{display:block;height:100%;background:var(--c)}input[type=text]{flex:1;min-width:0}
input[type=range]{flex:1;accent-color:var(--c)}h2{font-size:13px;opacity:.7;margin:16px 0 4px;letter-spacing:2px}
small{opacity:.6}</style></head><body><main id="m"><h1><span>VX-26 // LINK</span><span><span id="dot"></span></span></h1>
<div class="scr"><img id="s" alt="schermo"></div>
<div class="row"><button id="live" class="on">LIVE</button><small id="hint">Tocca l'immagine per toccare lo schermo vero.</small></div>
<div class="row tabs" id="tabs"></div>
<h2>STATO</h2><div class="g" id="st"></div>
<h2>TRASMETTI UN MESSAGGIO</h2><div class="row"><input type="text" id="msg" maxlength="96" placeholder="Scrivi qui...">
<button id="send">INVIA</button></div>
<h2>CONTROLLI</h2><div class="row"><select id="tema"></select><button id="suono">SUONO</button>
<button id="olo">OLO</button><button id="led">LED</button></div>
<div class="row"><span>LUCE</span><input type="range" id="luce" min="20" max="255"></div>
<small>VX-26 Operator v6.0 - pannello locale, nessun dato esce dalla tua rete.</small></main><script>
const $=i=>document.getElementById(i);let live=1,S={};
const T=['STAT','INV','DATA','MAP','RADIO','GIOCO'];
T.forEach((t,i)=>{const b=document.createElement('button');b.textContent=t;b.onclick=()=>fetch('/api/vai?tab='+i).then(st);$('tabs').appendChild(b)});
function shot(){if(!live)return;const n=new Image();n.onload=()=>{$('s').src=n.src;setTimeout(shot,250)};
n.onerror=()=>setTimeout(shot,1500);n.src='/screen.bmp?t='+Date.now()}
$('s').onclick=e=>{const r=e.target.getBoundingClientRect();const x=Math.round((e.clientX-r.left)*320/r.width),
y=Math.round((e.clientY-r.top)*240/r.height);fetch('/api/tap?x='+x+'&y='+y)};
$('live').onclick=()=>{live^=1;$('live').classList.toggle('on',!!live);if(live)shot()};
function k(l,v,p){return'<div class="k"><b>'+l+'</b>'+v+(p!=null?'<div class="bar"><i style="width:'+p+'%"></i></div>':'')+'</div>'}
function st(){fetch('/api/stato').then(r=>r.json()).then(d=>{S=d;document.body.classList.remove('off');
document.documentElement.style.setProperty('--c',d.colore);
const lp=Math.round((d.xp-d.xpDa)*100/Math.max(1,d.xpA-d.xpDa));
$('st').innerHTML=k('LIVELLO',d.liv+' <small>'+d.xp+' XP</small>',lp)+k('MEMORIA LIBERA',d.ram+'%',d.ram)+
k('CPU',d.temp+' C',Math.min(100,d.temp))+k('LUCE AMBIENTE',d.luce+'%',d.luce)+
k('WIFI',d.wifi?d.ssid+' <small>'+d.rssi+' dBm</small>':'non connesso')+k('HOTSPOT',d.ap?'attivo, '+d.apClienti+' client':'spento')+
k('METEO',d.meteo?d.t+' C '+d.cond+' <small>'+d.citta+'</small>':'--')+k('ACCESO DA',d.up)+
k('TIMER',d.timer+(d.timerOn?' <small>in corso</small>':''))+k('RADAR',d.reti+' reti, '+d.bt+' BT');
if(!$('tema').options.length)d.temi.forEach((t,i)=>$('tema').add(new Option(t,i)));
$('tema').value=d.tema;$('luce').value=d.luminosita;
[['suono',d.suono],['olo',d.olo],['led',d.led]].forEach(([i,v])=>$(i).classList.toggle('on',!!v));
[...$('tabs').children].forEach((b,i)=>b.classList.toggle('on',i==d.tab))}).catch(()=>document.body.classList.add('off'))}
function set(q){fetch('/api/set?'+q).then(st)}
$('tema').onchange=e=>set('tema='+e.target.value);$('luce').onchange=e=>set('luce='+e.target.value);
['suono','olo','led'].forEach(i=>$(i).onclick=()=>set(i+'='+(S[i]?0:1)));
$('send').onclick=()=>{const t=$('msg').value.trim();if(!t)return;fetch('/api/msg?t='+encodeURIComponent(t))
.then(r=>{$('msg').value='';$('msg').placeholder=r.ok?'Inviato!':'Schermo occupato, riprova'})};
$('msg').onkeydown=e=>{if(e.key=='Enter')$('send').click()};
shot();st();setInterval(st,2000);
</script></body></html>)rawliteral";

void webNote() { webHits++; webLastHit = millis(); }

// immagine BMP a 16 colori presa direttamente dal framebuffer
void webScreen() {
  webNote();
  const uint32_t off = 14 + 40 + 64, img = 320 * 240 / 2;
  uint8_t h[off];
  memset(h, 0, off);
  auto le32 = [&](int i, uint32_t v) { h[i] = v; h[i + 1] = v >> 8; h[i + 2] = v >> 16; h[i + 3] = v >> 24; };
  h[0] = 'B'; h[1] = 'M';
  le32(2, off + img); le32(10, off); le32(14, 40); le32(18, 320); le32(22, 240);
  h[26] = 1; h[28] = 4;
  le32(34, img); le32(38, 2835); le32(42, 2835); le32(46, 16);
  for (int i = 0; i < 16; i++) {
    uint16_t c = pal[i];
    uint8_t r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31;
    h[54 + i * 4] = (b << 3) | (b >> 2);
    h[55 + i * 4] = (g << 2) | (g >> 4);
    h[56 + i * 4] = (r << 3) | (r >> 2);
  }
  web.setContentLength(off + img);
  web.sendHeader("Cache-Control", "no-store");
  web.send(200, "image/bmp", "");
  WiFiClient cl = web.client();
  cl.write(h, off);
  const uint8_t* buf = (const uint8_t*)spr.getPointer();
  static uint8_t chunk[160 * 8];
  for (int y = 239; y >= 0; y -= 8) {               // il BMP va dal basso verso l'alto
    for (int k = 0; k < 8; k++) memcpy(chunk + k * 160, buf + (y - k) * 160, 160);
    if (cl.write(chunk, sizeof(chunk)) == 0) break;
  }
}

String jsonEsc(const String& s) {
  String o;
  for (int i = 0; i < (int)s.length(); i++) {
    char c = s[i];
    if (c == '"' || c == '\\') o += '\\';
    if ((uint8_t)c >= 32) o += c;
  }
  return o;
}

void webStato() {
  webNote();
  bool wc = WiFi.status() == WL_CONNECTED;
  Weather w;
  portENTER_CRITICAL(&wxMux);
  w = wx;
  portEXIT_CRITICAL(&wxMux);
  int lv = levelOf(xp);
  Theme& t = THEMES[cfg.theme];
  char col[8];
  snprintf(col, sizeof(col), "#%02x%02x%02x", t.r, t.g, t.b);
  String temi;
  for (int i = 0; i < THEME_N; i++) temi += String(i ? "," : "") + "\"" + THEMES[i].name + "\"";
  String j = "{\"ver\":\"6.0\",\"up\":\"" + uptimeStr() + "\",\"ram\":" + String(sRam) + ",\"temp\":" + String((int)sTemp) +
             ",\"luce\":" + String(sLight) + ",\"wifi\":" + (wc ? "true" : "false") + ",\"ssid\":\"" + jsonEsc(wc ? WiFi.SSID() : String("")) +
             "\",\"rssi\":" + String(wc ? WiFi.RSSI() : 0) + ",\"ap\":" + (cfg.ap ? "true" : "false") +
             ",\"apClienti\":" + String(cfg.ap ? WiFi.softAPgetStationNum() : 0) + ",\"liv\":" + String(lv) +
             ",\"xp\":" + String(xp) + ",\"xpDa\":" + String(xpFor(lv)) + ",\"xpA\":" + String(xpFor(lv + 1)) +
             ",\"tema\":" + String(cfg.theme) + ",\"temi\":[" + temi + "],\"colore\":\"" + col + "\",\"luminosita\":" + String(cfg.bright) +
             ",\"suono\":" + (cfg.sound ? "1" : "0") + ",\"olo\":" + (cfg.crt ? "1" : "0") + ",\"led\":" + (cfg.led ? "1" : "0") +
             ",\"meteo\":" + (w.ok ? "true" : "false") + ",\"t\":" + String((int)lroundf(w.ok ? w.t : 0)) +
             ",\"citta\":\"" + jsonEsc(w.city) + "\",\"cond\":\"" + (w.ok ? wxText(w.code) : "") + "\",\"tab\":" + String(tab) +
             ",\"sub\":" + String(sub[tab]) + ",\"reti\":" + String(netCount) + ",\"bt\":" + String((int)bdevCount) +
             ",\"timer\":\"" + (tmMode == 1 ? crStr(cronoNow()) : mmss(timerLeft(), true)) + "\",\"timerOn\":" + (tmRun || crRun ? "true" : "false") + "}";
  web.sendHeader("Cache-Control", "no-store");
  web.send(200, "application/json", j);
}

void wakeUp() {
  lastInput = millis();
  if (saverOn) { saverOn = false; applyBrightness(); }
  dirty = true;
}

void webTap() {
  webNote();
  int x = web.arg("x").toInt(), y = web.arg("y").toInt();
  if (x >= 0 && x < 320 && y >= 0 && y < 240) { onTouch(x, y); dirty = true; }
  web.send(204);
}

void webVai() {
  webNote();
  int t = web.arg("tab").toInt();
  if (modal == M_NONE && t >= 0 && t < NTABS) {
    wakeUp();
    if (t != tab) { tab = t; glitchUntil = millis() + 160; chirp(); }
    if (web.hasArg("sub")) sub[t] = constrain((int)web.arg("sub").toInt(), 0, SUBN[t] - 1);
  }
  web.send(204);
}

void webSet() {
  if (web.hasArg("tema")) { cfg.theme = constrain((int)web.arg("tema").toInt(), 0, THEME_N - 1); applyTheme(); }
  if (web.hasArg("luce")) { cfg.bright = constrain((int)web.arg("luce").toInt(), 20, 255); cfg.autoBright = false; applyBrightness(); }
  if (web.hasArg("suono")) cfg.sound = web.arg("suono") == "1";
  if (web.hasArg("olo")) cfg.crt = web.arg("olo") == "1";
  if (web.hasArg("led")) cfg.led = web.arg("led") == "1";
  saveConfig();
  dirty = true;
  webStato();
}

// tiene solo caratteri ASCII stampabili (le vocali accentate diventano lettere semplici)
String foldAscii(const String& in, int maxLen) {
  String out;
  for (int i = 0; i < (int)in.length() && (int)out.length() < maxLen; i++) {
    uint8_t c = in[i];
    if (c >= 32 && c < 127) out += (char)c;
    else if (c == '\n' || c == '\t') out += ' ';
    else if (c == 0xC3 && i + 1 < (int)in.length()) {
      uint8_t b = (uint8_t)in[++i];
      bool low = b >= 0xA0;
      b &= 0xDF;
      char m = b <= 0x85 ? 'A' : (b >= 0x88 && b <= 0x8B) ? 'E' : (b >= 0x8C && b <= 0x8F) ? 'I'
             : (b >= 0x92 && b <= 0x96) ? 'O' : (b >= 0x99 && b <= 0x9C) ? 'U' : 0;
      if (m) out += low ? (char)tolower(m) : m;
    }
  }
  out.trim();
  return out;
}

void webMsg() {
  webNote();
  String t = foldAscii(web.arg("t"), 96);
  if (!t.length()) { web.send(400, "text/plain", "vuoto"); return; }
  if (modal != M_NONE && modal != M_MSG && modal != M_RX) { web.send(409, "text/plain", "occupato"); return; }
  rxText = t;
  modal = M_RX;
  wakeUp();
  for (int i = 0; i < 3; i++) { queueTone(1800, 50); queueTone(0, 40); }
  queueTone(2600, 160);
  addLog("MSG RICEVUTO VIA LINK");
  addXp(5);
  web.send(200, "text/plain", "ok");
}

void webBegin() {
  web.on("/", []() { webNote(); web.send_P(200, "text/html", PAGE); });
  web.on("/screen.bmp", webScreen);
  web.on("/api/stato", webStato);
  web.on("/api/tap", webTap);
  web.on("/api/vai", webVai);
  web.on("/api/set", webSet);
  web.on("/api/msg", webMsg);
  web.onNotFound([]() { web.send(404, "text/plain", "VX-26: pagina non trovata"); });
  web.begin();
}

// =================================================================
//  GIOCO - DIFESA (abbatti i missili prima che colpiscano i rifugi)
// =================================================================
int dfCitiesLeft() { int n = 0; for (int i = 0; i < 4; i++) n += dfCity[i]; return n; }

// raggio di un'esplosione: cresce in fretta, poi si spegne piano
int dfBoomR(const DfBoom& e) { return e.age * 2 <= e.maxR ? e.age * 2 : e.maxR - (e.age - e.maxR / 2); }

void dfBoomAt(float x, float y, int r, bool player) {
  for (int i = 0; i < DF_EX; i++)
    if (!dfEx[i].on) { dfEx[i] = {x, y, 0, r, true, player}; return; }
}

void dfSpawn(float sx, float sy, bool canSplit) {
  for (int i = 0; i < DF_EN; i++) {
    if (dfEn[i].on) continue;
    int opts[5], n = 0;
    for (int c = 0; c < 4; c++) if (dfCity[c]) opts[n++] = c;
    opts[n++] = 4;                                   // 4 = torretta: bersaglio di disturbo
    int t = opts[random(n)];
    float tx = t < 4 ? DF_CITY_X[t] : 160, dx = tx - sx, dy = DF_GROUND - sy, d = sqrtf(dx * dx + dy * dy);
    float sp = 0.55f + dfWave * 0.1f;
    dfEn[i] = {sx, sy, sx, sy, dx / d * sp, dy / d * sp, t, true, canSplit && dfWave >= 3 && random(100) < 30};
    return;
  }
}

void dfNewWave() {
  for (int i = 0; i < DF_EN; i++) dfEn[i].on = false;
  for (int i = 0; i < DF_SH; i++) dfSh[i].on = false;
  for (int i = 0; i < DF_EX; i++) dfEx[i].on = false;
  dfToSpawn = 6 + dfWave * 2;
  dfAmmo = dfToSpawn + 6;
  dfSpawnT = 15;
}

void dfReset() {
  dfWave = 1;
  dfScore = 0;
  for (int i = 0; i < 4; i++) dfCity[i] = true;
  dfNewWave();
}

void dfGameOver() {
  dfState = 2;
  dfStateT = millis();
  glitchUntil = millis() + 300;
  sndErr();
  if (dfScore > dfHi) {
    dfHi = dfScore;
    prefs.putInt("dfhi", dfHi);
    addLog("DIFESA: RECORD " + String(dfHi));
  }
  addXp(dfScore / 25);
}

void dfStep() {
  if (dfToSpawn > 0 && --dfSpawnT <= 0) {
    int n = dfWave >= 2 && random(100) < 35 ? 2 : 1;
    for (int k = 0; k < n && dfToSpawn > 0; k++, dfToSpawn--) dfSpawn(random(10, 310), 52, true);
    dfSpawnT = max(10, 42 - dfWave * 4) + random(24);
  }
  for (int i = 0; i < DF_EN; i++) {
    DfMissile& m = dfEn[i];
    if (!m.on) continue;
    m.x += m.vx;
    m.y += m.vy;
    if (m.split && m.y > 105) {                      // testata multipla: si divide in due
      m.split = false;
      dfSpawn(m.x, m.y, false);
      dfSpawn(m.x, m.y, false);
      queueTone(1500, 25);
    }
    if (m.y >= DF_GROUND) {
      m.on = false;
      dfBoomAt(m.x, DF_GROUND - 2, 14, false);
      if (m.target < 4 && dfCity[m.target]) {
        dfCity[m.target] = false;
        glitchUntil = millis() + 180;
        queueTone(140, 160);
        if (dfCitiesLeft() == 0) { dfGameOver(); return; }
      } else queueTone(200, 60);
    }
  }
  for (int i = 0; i < DF_SH; i++) {
    DfShot& s = dfSh[i];
    if (!s.on) continue;
    s.x += s.vx;
    s.y += s.vy;
    if (--s.n <= 0) { s.on = false; dfBoomAt(s.tx, s.ty, 20, true); queueTone(320, 30); queueTone(170, 50); }
  }
  for (int i = 0; i < DF_EX; i++) {
    DfBoom& e = dfEx[i];
    if (!e.on) continue;
    e.age++;
    int r = dfBoomR(e);
    if (r <= 0) { e.on = false; continue; }
    if (!e.player) continue;
    for (int k = 0; k < DF_EN; k++) {                // reazione a catena
      DfMissile& m = dfEn[k];
      if (!m.on) continue;
      float dx = m.x - e.x, dy = m.y - e.y;
      if (dx * dx + dy * dy <= r * r) {
        m.on = false;
        dfScore += 25;
        dfBoomAt(m.x, m.y, 12, true);
        queueTone(900, 20);
      }
    }
  }
  bool busy = dfToSpawn > 0;
  for (int i = 0; i < DF_EN && !busy; i++) busy = dfEn[i].on;
  for (int i = 0; i < DF_EX && !busy; i++) busy = dfEx[i].on;
  if (!busy) {
    dfBonus = dfCitiesLeft() * 100 + dfAmmo * 10;
    dfScore += dfBonus;
    dfState = 4;
    dfStateT = millis();
    sndOk();
  }
}

void dfTouch(int x, int y) {
  if (dfState == 2 && millis() - dfStateT < 800) return;
  if (dfState == 0 || dfState == 2) { dfReset(); dfState = 1; dfLast = millis(); return; }
  if (dfState == 3) { dfState = 1; dfLast = millis(); return; }
  if (dfState != 1 || y < 56 || y > 190) return;
  if (dfAmmo <= 0) { queueTone(120, 80); return; }
  for (int i = 0; i < DF_SH; i++) {
    DfShot& s = dfSh[i];
    if (s.on) continue;
    float dx = x - 160, dy = y - (DF_GROUND - 16), d = sqrtf(dx * dx + dy * dy);
    int n = max(1, (int)(d / 6));
    s = {160, (float)(DF_GROUND - 16), dx / n, dy / n, (float)x, (float)y, n, true};
    dfAmmo--;
    queueTone(1300, 15);
    queueTone(800, 20);
    return;
  }
}

void drawDifesa() {
  txt("PUNTI " + String(dfScore), 8, 47, C_HI, TL_DATUM, 1);
  txt("ONDATA " + String(dfWave), 160, 47, C_MAIN, TC_DATUM, 1);
  txt("COLPI " + String(dfAmmo), 312, 47, dfAmmo < 4 && dfState == 1 ? C_HI : C_DIM, TR_DATUM, 1);
  for (int i = 0; i < 26; i++) spr.drawPixel((i * 97 + 13) % 314 + 3, 62 + (i * 53) % 110, i % 5 ? C_DIM2 : C_DIM);
  spr.drawFastHLine(0, DF_GROUND + 1, 320, C_MID);
  for (int x = 2; x < 320; x += 6) spr.drawPixel(x, DF_GROUND + 4, C_DIM2);

  unsigned long t = millis();
  for (int c = 0; c < 4; c++) {                      // rifugi
    int cx = DF_CITY_X[c];
    if (dfCity[c]) {
      spr.fillCircle(cx, DF_GROUND - 4, 9, C_MAIN);
      spr.fillRect(cx - 13, DF_GROUND - 4, 27, 6, C_MAIN);
      spr.drawCircleHelper(cx, DF_GROUND - 4, 12, 1 | 2, C_DIM);
      for (int k = -1; k <= 1; k++) spr.fillRect(cx + k * 5 - 1, DF_GROUND - 6, 2, 2, (t / 400 + c + k) % 4 ? BG : C_HI);
      spr.drawFastVLine(cx + 6, DF_GROUND - 18, 6, C_MID);
      if ((t / 500 + c) % 2) spr.drawPixel(cx + 6, DF_GROUND - 19, C_HI);
    } else {
      spr.fillRect(cx - 11, DF_GROUND - 2, 7, 3, C_DIM);
      spr.fillRect(cx - 3, DF_GROUND - 5, 6, 6, C_DIM);
      spr.fillRect(cx + 5, DF_GROUND - 2, 6, 3, C_DIM);
      for (int k = 0; k < 4; k++) {                  // fumo
        int sy = (t / 60 + k * 9) % 30;
        spr.drawPixel(cx - 2 + (k % 3) * 2 + (sy / 8) % 2, DF_GROUND - 6 - sy, sy < 15 ? C_DIM : C_DIM2);
      }
    }
  }
  spr.fillTriangle(160, DF_GROUND - 13, 149, DF_GROUND, 171, DF_GROUND, C_HI);   // torretta
  spr.fillRect(158, DF_GROUND - 19, 4, 7, C_MAIN);

  for (int i = 0; i < DF_EN; i++) {
    DfMissile& m = dfEn[i];
    if (!m.on) continue;
    spr.drawLine(m.sx, m.sy, m.x, m.y, C_DIM);
    spr.fillRect((int)m.x - 1, (int)m.y - 1, 3, 3, (t / 90 + i) % 2 ? C_HI : C_MAIN);
  }
  for (int i = 0; i < DF_SH; i++) {
    DfShot& s = dfSh[i];
    if (!s.on) continue;
    spr.drawLine(160, DF_GROUND - 19, s.x, s.y, C_MID);
    spr.fillRect((int)s.x - 1, (int)s.y - 1, 2, 2, C_HI);
    int tx = s.tx, ty = s.ty;
    spr.drawLine(tx - 3, ty - 3, tx + 3, ty + 3, C_MAIN);
    spr.drawLine(tx - 3, ty + 3, tx + 3, ty - 3, C_MAIN);
  }
  for (int i = 0; i < DF_EX; i++) {
    DfBoom& e = dfEx[i];
    if (!e.on) continue;
    int r = dfBoomR(e);
    if (r <= 0) continue;
    spr.fillCircle(e.x, e.y, r, e.player ? C_MID : C_DIM);
    spr.drawCircle(e.x, e.y, r, C_HI);
    if (r > 5) spr.fillCircle(e.x, e.y, r / 3, C_HI);
  }

  if (dfState != 1) {
    chamferFill(60, 88, 200, 74, 8, BG);
    chamfer(60, 88, 200, 74, 8, C_MAIN);
    const char* t1 = dfState == 0 ? "DIFESA" : dfState == 2 ? "GAME OVER" : dfState == 3 ? "PAUSA" : "ONDATA SUPERATA";
    txtG(t1, 160, 106, C_HI, MC_DATUM, dfState == 4 ? 2 : 4);
    String l2 = dfState == 0 ? String("PROTEGGI I 4 RIFUGI") : dfState == 2 ? "PUNTI " + String(dfScore) + "   RECORD " + String(dfHi)
              : dfState == 4 ? "BONUS +" + String(dfBonus) + "  (RIFUGI E COLPI)" : "ONDATA " + String(dfWave);
    txt(l2, 160, 130, C_MAIN, MC_DATUM, dfState == 4 ? 1 : 2);
    const char* l3 = dfState == 0 ? "TOCCA IL CIELO PER SPARARE" : dfState == 3 ? "TOCCA PER RIPRENDERE" : dfState == 4 ? "ARRIVA LA PROSSIMA..." : "TOCCA PER RIGIOCARE";
    if (dfState == 4 || (millis() / 500) % 2) txt(l3, 160, 150, C_DIM, MC_DATUM, 1);
  }
}

// =================================================================
//  LED RGB DI STATO (attivo basso)
// =================================================================
void ledSetup() {
  ledcSetup(LED_CH_R, 5000, 8); ledcAttachPin(LED_R, LED_CH_R);
  ledcSetup(LED_CH_G, 5000, 8); ledcAttachPin(LED_G, LED_CH_G);
  ledcSetup(LED_CH_B, 5000, 8); ledcAttachPin(LED_B, LED_CH_B);
  ledRGB(0, 0, 0);
}

void ledRGB(int r, int g, int b) {
  ledcWrite(LED_CH_R, 255 - constrain(r, 0, 255));
  ledcWrite(LED_CH_G, 255 - constrain(g, 0, 255));
  ledcWrite(LED_CH_B, 255 - constrain(b, 0, 255));
}

void updateLed() {
  int r = 0, g = 0, b = 0;
  if (cfg.led && !saverOn) {
    unsigned long t = millis();
    int br = 6 + (int)((sin(t / 650.0) * 0.5 + 0.5) * 40);
    if (tmAlarm) r = (t / 150) % 2 ? 120 : 0;
    else if (modal == M_RX) { g = br; b = br; }
    else if (modal == M_CONN) { r = (t / 120) % 2 ? 70 : 0; g = r / 2; }
    else if (wifiScanning || btScanning || wxState == 1) b = (t / 150) % 2 ? 60 : 4;
    else if (WiFi.status() == WL_CONNECTED) g = br;
    else r = br / 2;
  }
  ledRGB(r, g, b);
}

// =================================================================
//  RENDER
// =================================================================
void drawContent() {
  switch (tab) {
    case 0:
      if (sub[0] == 0) drawStato(); else if (sub[0] == 1) drawSistema();
      else if (sub[0] == 2) drawGrafici(); else drawConfig();
      break;
    case 1: drawInv(); break;
    case 2:
      if (sub[2] == S_ORA) drawOra(); else if (sub[2] == S_METEO) drawMeteo();
      else if (sub[2] == S_TIMER) drawTimer();
      else if (sub[2] == S_MISSIONI) drawMissioni(); else drawLog();
      break;
    case 3: drawRadar(); break;
    case 4:
      if (sub[4] == S_WIFI) drawWifi(); else if (sub[4] == S_BT) drawBt();
      else if (sub[4] == S_CANALI) drawCanali(); else drawLink();
      break;
    case 5:
      if (sub[5] == S_TERM) drawTerminal(); else if (sub[5] == S_SNAKE) drawSnake(); else drawDifesa();
      break;
  }
}

void render() {
  spr.fillSprite(BG);
  if (saverOn) drawSaver();
  else if (modal == M_KB) drawKeyboard();
  else if (modal == M_CAL) drawCalib();
  else {
    bgGrid();
    drawHeader();
    drawSubtabs();
    drawContent();
    drawFooter();
    if (millis() < toastUntil) {
      chamferFill(40, 50, 240, 24, 6, BG);
      chamfer(40, 50, 240, 24, 6, C_HI);
      txtG(toastText, 160, 62, C_HI, MC_DATUM);
    }
    if (modal == M_CONN || modal == M_MSG || modal == M_RX) drawModalBox();
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
    rawX = p.x; rawY = p.y;
    x = constrain(map(p.x, cfg.tminx, cfg.tmaxx, 0, 320), 0, 319);
    y = constrain(map(p.y, cfg.tminy, cfg.tmaxy, 0, 240), 0, 239);
    return true;
  }
  if (!now) was = false;
  return false;
}

void touchConfig(int x, int y) {
  int pages = (CI_N + CFG_ROWS - 1) / CFG_ROWS;
  if (y >= 186 && y < 216) {
    if (x < 60) cfgPage = (cfgPage + pages - 1) % pages;
    else if (x >= 260) cfgPage = (cfgPage + 1) % pages;
    return;
  }
  if (y < 48 || y >= 48 + CFG_ROWS * 28) return;
  int id = cfgPage * CFG_ROWS + (y - 48) / 28;
  if (id >= CI_N) return;
  bool L = x >= 170 && x < 210, R = x >= 284, T = x >= 226;
  switch (id) {
    case CI_THEME:
      if (L) cfg.theme = (cfg.theme + THEME_N - 1) % THEME_N;
      else if (R) cfg.theme = (cfg.theme + 1) % THEME_N;
      else return;
      applyTheme(); break;
    case CI_BRIGHT:
      if (L) cfg.bright = max(20, blTarget() - 30);
      else if (R) cfg.bright = min(255, blTarget() + 30);
      else return;
      cfg.autoBright = false;
      applyBrightness(); break;
    case CI_AUTO:  if (!T) return; cfg.autoBright = !cfg.autoBright; blAuto = cfg.bright; applyBrightness(); break;
    case CI_SOUND: if (!T) return; cfg.sound = !cfg.sound; break;
    case CI_CRT:   if (!T) return; cfg.crt = !cfg.crt; break;
    case CI_LED:   if (!T) return; cfg.led = !cfg.led; break;
    case CI_SAVER:
      if (L) cfg.saver = (cfg.saver + 3) % 4;
      else if (R) cfg.saver = (cfg.saver + 1) % 4;
      else return;
      break;
    case CI_CAL:   if (!T) return; startCalib(); return;
    case CI_WIFI:
      if (!T) return;
      cfg.ssid = ""; cfg.pass = ""; WiFi.disconnect(); addLog("WIFI: credenziali cancellate");
      break;
    case CI_SYS:
      if (!T) return;
      saveConfig();
      spr.fillSprite(BG);
      txtG("RIAVVIO...", 160, 120, C_HI, MC_DATUM, 4);
      present();
      delay(600);
      ESP.restart();
      return;
  }
  saveConfig();
}

void onTouch(int x, int y) {
  lastInput = millis();
  if (saverOn) { saverOn = false; applyBrightness(); return; }   // il tocco sveglia e basta
  click();
  if (tmAlarm) { tmAlarm = false; if (modal == M_MSG) modal = M_NONE; return; }
  if (modal == M_CAL) { calTouch(); return; }
  if (modal == M_KB)  { kbTouch(x, y); return; }
  if (modal == M_MSG || modal == M_RX) { modal = M_NONE; return; }
  if (modal == M_CONN) return;

  if (y < 24) {
    int nt = constrain(x / TAB_W, 0, NTABS - 1);
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
      if (sub[0] == 3) touchConfig(x, y);
      break;
    case 1:
      if (x < 170 && y >= 50 && y < 50 + INV_N * 26) invSel[sub[1]] = (y - 50) / 26;
      break;
    case 2:
      if (sub[2] == S_METEO) startWeather();
      else if (sub[2] == S_TIMER) timerTouch(x, y);
      else if (sub[2] == S_MISSIONI && y >= 50 && y < 180) {
        int i = (y - 50) / 26;
        if (i >= 0 && i < 5) { qDone[i] = !qDone[i]; saveQuests(); }
      }
      break;
    case 3:
      if (inRect(x, y, 6, 186, 90, 28)) { startWifiScan(); startBtScan(); }
      break;
    case 4:
      if (sub[4] == S_CANALI) {
        if (inRect(x, y, 0, 186, 76, 30)) startWifiScan();
      } else if (sub[4] == S_LINK) linkTouch(x, y);
      else if (sub[4] == S_WIFI) {
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
    case 5:
      if (sub[5] == S_TERM) termTouch(x, y); else if (sub[5] == S_SNAKE) snakeTouch(x, y); else dfTouch(x, y);
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

bool bootSkip = false;
bool skipBoot() {
  if (!bootSkip && ts.tirqTouched() && ts.touched()) bootSkip = true;
  return bootSkip;
}

void bootSequence() {
  // accensione: linea che si espande
  for (int w = 4; w <= 320 && !skipBoot(); w += 28) { spr.fillSprite(BG); spr.fillRect(160 - w / 2, 119, w, 2, C_HI); spr.pushSprite(0, 0); }
  // flusso dati
  for (int f = 0; f < 22 && !skipBoot(); f++) {
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
  for (int f = 0; f < 56 && !skipBoot(); f++) {
    spr.fillSprite(BG);
    bgGrid();
    drawHexLogo(160, 80, 34, f / 4, f * 0.05);
    if (f == 26) glitchUntil = millis() + 180;
    if (f > 26) {
      txtG("VX-26", 160, 140, C_HI, MC_DATUM, 4);
      txt("OPERATOR SYSTEM  //  2026", 160, 166, C_MAIN, MC_DATUM);
    }
    if (f > 40) txt("INTERFACCIA OLOGRAFICA PERSONALE", 160, 198, C_DIM, MC_DATUM, 1);
    txt("TOCCA PER SALTARE", 160, 228, C_DIM2, MC_DATUM, 1);
    present();
  }
  if (!bootSkip) chirp();
  const char* lines[] = {
    "VX-26 OPERATOR SYSTEM  v6.0",
    "BUILD 2026.10 // CORE XTENSA LX6",
    "",
    "> MEMORIA",
    "> SENSORI",
    "> MODULO WIFI",
    "> MODULO BLUETOOTH",
    "> VX-LINK // PANNELLO WEB",
    "> METEO // GIOCHI // OLOGRAFIA",
  };
  const int N = sizeof(lines) / sizeof(lines[0]);
  for (int l = 0; l < N && !skipBoot(); l++) {
    int len = strlen(lines[l]);
    for (int c = 0; c <= len && !skipBoot(); c += 3) {
      spr.fillSprite(BG);
      for (int k = 0; k < l; k++) {
        txt(lines[k], 14, 10 + k * 18, C_MAIN);
        if (k >= 3) txt("[ OK ]", 306, 10 + k * 18, C_HI, TR_DATUM);
      }
      String part = String(lines[l]).substring(0, c);
      txtG(part, 14, 10 + l * 18, C_HI);
      spr.fillRect(16 + spr.textWidth(part, 2), 12 + l * 18, 7, 13, C_MAIN);
      present();
    }
    if (!bootSkip) click();
  }
  for (int p = 0; p <= 100 && !skipBoot(); p += 4) {
    spr.fillRect(0, 178, 320, 62, BG);
    chamfer(14, 184, 292, 18, 5, C_MAIN);
    segBar(20, 189, 282, 8, p, 28);
    txt("CARICAMENTO " + String(p) + "%", 160, 216, C_DIM, MC_DATUM);
    present();
  }
  glitchUntil = millis() + 200;
  for (int f = 0; f < 20 && !skipBoot(); f++) {
    spr.fillSprite(BG);
    bgGrid();
    brackets(30, 80, 260, 80, 14, C_MAIN);
    txtG("ACCESSO CONSENTITO", 160, 112, C_HI, MC_DATUM, 4);
    txt("BENVENUTO, OPERATORE", 160, 140, C_MAIN, MC_DATUM);
    present();
  }
  if (!bootSkip) delay(400);
  while (ts.touched()) delay(10);      // aspetta che il dito si sollevi
}

void setup() {
  Serial.begin(115200);
  ledSetup();                                          // LED RGB spento
  ledcSetup(SPK_CH, 2000, 10);
  ledcAttachPin(SPK_PIN, SPK_CH);
  ledcWrite(SPK_CH, 0);
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
  if (cfg.ap) applyAp();
  webBegin();
  randomSeed(analogRead(LDR_PIN) ^ micros());
  newTerminal();
  snReset();
  dfReset();

  bootSequence();
  updateStats();
  addLog("SISTEMA AVVIATO");
  lastInput = millis();

  if (cfg.ssid.length()) {
    WiFi.begin(cfg.ssid.c_str(), cfg.pass.c_str());
    addLog("WIFI: connessione a " + cfg.ssid.substring(0, 14));
  }
}

void loop() {
  int x, y;
  if (getTouch(x, y)) { onTouch(x, y); dirty = true; }

  pollSound();
  pollWifiScan();
  handleConnecting();
  checkWifiStatus();
  checkBtDone();
  pollWeather();
  pollTimer();
  web.handleClient();

  unsigned long now = millis();
  if (now - lastStats >= 1000) { lastStats = now; updateStats(); }

  // serpente: avanza solo se visibile, altrimenti va in pausa
  if (snState == 1) {
    if (!(tab == 5 && sub[5] == S_SNAKE) || modal != M_NONE) snState = 3;
    else if (now - snLast >= (unsigned long)max(55, 130 - snScore * 3)) { snLast = now; snStep(); dirty = true; }
  }

  // difesa: 30 passi al secondo, in pausa se non e' visibile
  if (dfState == 1 || dfState == 4) {
    bool vis = tab == 5 && sub[5] == S_DIFESA && modal == M_NONE;
    if (!vis) { if (dfState == 1) dfState = 3; }
    else if (dfState == 4) { if (now - dfStateT > 2400) { dfWave++; dfNewWave(); dfState = 1; dfLast = now; } }
    else if (now - dfLast >= 33) { dfLast += 33; if (now - dfLast > 200) dfLast = now; dfStep(); }
  }

  // salvaschermo
  int smin = SAVER_MIN[cfg.saver];
  if (!saverOn && smin && modal == M_NONE && snState != 1 && dfState != 1 && !tmAlarm && !wifiScanning && !btScanning &&
      now - lastInput > (unsigned long)smin * 60000UL) {
    saverOn = true;
    initSaver();
    applyBrightness();
  }

  static unsigned long lastLed = 0;
  if (now - lastLed >= 30) { lastLed = now; updateLed(); }

  bool anim = saverOn || cfg.crt || tab == 1 || tab == 3 || tab == 5 || (tab == 0 && sub[0] == 0) ||
              (tab == 2 && (sub[2] == S_METEO || sub[2] == S_TIMER)) || (tab == 4 && sub[4] == S_LINK) ||
              wifiScanning || btScanning || wxState == 1 || modal != M_NONE || millis() < toastUntil || tmAlarm;
  unsigned long iv = anim ? 40 : 250;
  if (dirty || now - lastFrame >= iv) {
    lastFrame = now;
    dirty = false;
    render();
  }
}
