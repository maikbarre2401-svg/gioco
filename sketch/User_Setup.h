// ===== User_Setup.h - ESP32 Cheap Yellow Display (ESP32-2432S028R) =====
#define USER_SETUP_LOADED

#define ILI9341_2_DRIVER      // variante CYD (se i colori sono invertiti usa ILI9341_DRIVER)

#define TFT_WIDTH  240
#define TFT_HEIGHT 320

// --- display SPI (bus HSPI della CYD) ---
#define TFT_MISO 12
#define TFT_MOSI 13
#define TFT_SCLK 14
#define TFT_CS   15
#define TFT_DC    2
#define TFT_RST  -1

#define TFT_BL   21
#define TFT_BACKLIGHT_ON HIGH

// --- font ---
#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_FONT7
#define LOAD_FONT8
#define LOAD_GFXFF
#define SMOOTH_FONT

// --- frequenze SPI ---
#define SPI_FREQUENCY       55000000
#define SPI_READ_FREQUENCY  20000000
#define SPI_TOUCH_FREQUENCY  2500000
