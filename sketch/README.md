# Sorgenti usati per il firmware in `../firmware/`

- `VX26_Operator.ino` — versione **7.0** (creator MAIKGOST) (vedi le novita' in `../firmware/README.md`).
  Rispetto all'originale contiene anche la correzione `getCpuFreqMHz()` →
  `getCpuFrequencyMhz()`, che nel core arduino-esp32 2.x bloccava la compilazione.
  Non servono librerie in piu': `HTTPClient` (meteo), `WebServer` ed `ESPmDNS` (pannello web)
  sono gia' inclusi nel core ESP32.
- `User_Setup.h` — configurazione TFT_eSPI per la Cheap Yellow Display
  (ESP32-2432S028R). Va copiato in `Documenti\Arduino\libraries\TFT_eSPI\`
  al posto del file omonimo se vuoi ricompilare da Arduino IDE.
- `partitions.csv` — tabella delle partizioni con due slot da 1,98 MB per l'aggiornamento
  dal pannello web. Arduino IDE la usa da sola se sta nella stessa cartella dello sketch.
