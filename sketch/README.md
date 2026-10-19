# Sorgenti usati per il firmware in `../firmware/`

- `VX26_Operator.ino` — identico a quello inviato, con **una correzione**:
  `getCpuFreqMHz()` → `getCpuFrequencyMhz()` (riga 625). La prima forma non
  esiste nel core arduino-esp32 2.x e bloccava la compilazione.
- `User_Setup.h` — configurazione TFT_eSPI per la Cheap Yellow Display
  (ESP32-2432S028R). Va copiato in `Documenti\Arduino\libraries\TFT_eSPI\`
  al posto del file omonimo se vuoi ricompilare da Arduino IDE.
