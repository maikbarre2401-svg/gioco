# Sorgenti usati per il firmware in `../firmware/`

- `VX26_Operator.ino` — versione **5.0** (vedi le novita' in `../firmware/README.md`).
  Rispetto all'originale contiene anche la correzione `getCpuFreqMHz()` →
  `getCpuFrequencyMhz()`, che nel core arduino-esp32 2.x bloccava la compilazione.
  Non servono librerie in piu': `HTTPClient` (per il meteo) e' gia' inclusa nel core ESP32.
- `User_Setup.h` — configurazione TFT_eSPI per la Cheap Yellow Display
  (ESP32-2432S028R). Va copiato in `Documenti\Arduino\libraries\TFT_eSPI\`
  al posto del file omonimo se vuoi ricompilare da Arduino IDE.
