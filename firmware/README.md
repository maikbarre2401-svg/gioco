# VX26 Operator v5.0 — firmware precompilato (ESP32 Cheap Yellow Display)

Compilato con: **arduino-esp32 2.0.17**, TFT_eSPI 2.5.43, XPT2046_Touchscreen 1.4
Scheda: **ESP32 Dev Module**, Partition Scheme: **Huge APP (3MB No OTA / 1MB SPIFFS)**
Dimensione sketch: 1.804.885 byte (57% della partizione da 3 MB)

## Novita' della v5.0

- **STAT > GRAFICI**: storico degli ultimi 2 minuti di RAM, temperatura CPU, luce e segnale WiFi.
- **DATA > METEO**: condizioni attuali e previsioni a 3 giorni (Open-Meteo, nessuna chiave API).
  La posizione e' stimata dall'IP; si aggiorna da solo ogni 15 minuti, oppure tocca lo schermo.
- **Nuova scheda GIOCO**: *Terminale* (trova la password: ogni tentativo dice quante lettere sono
  al posto giusto, 4 tentativi) e *Serpente* (tocca sopra/sotto o a sinistra/destra della testa
  per girare; il record resta salvato).
- **Salvaschermo** a pioggia di codice con orologio, che abbassa la retroilluminazione (1/3/10 min o OFF).
- **Luce automatica** tramite il sensore di luce della scheda.
- **LED RGB di stato**: verde = WiFi connesso, blu = scansione o meteo, ambra = connessione in corso.
- **Calibrazione touch** da CONFIG (se i tocchi risultano spostati).
- Suoni non bloccanti (niente piu' scatti durante i bip), missioni salvate e completate in automatico,
  avvio saltabile con un tocco. CONFIG ora ha due pagine (frecce in basso).

## Opzione A — un solo file, flasher dal browser (consigliata)

File: `VX26_Operator_FULL_0x0.bin` (immagine completa: bootloader + tabella partizioni + boot_app0 + app)

1. Apri **https://espressif.github.io/esptool-js/** con Chrome o Edge (Firefox e Safari non supportano la Web Serial).
2. Collega la scheda via USB e premi **Connect**, poi scegli la porta COM.
3. In "Flash Address" lascia **0x0** e seleziona `VX26_Operator_FULL_0x0.bin`.
4. Premi **Program**. Se appare "Connecting..." senza avanzare, tieni premuto **BOOT** sulla scheda.
5. A fine scrittura premi il tasto **RST** (o scollega e ricollega l'USB).

## Opzione B — esptool da riga di comando

```
pip install esptool
esptool.py --chip esp32 --port COM3 --baud 921600 write_flash -z 0x0 VX26_Operator_FULL_0x0.bin
```

## Opzione C — file separati (se preferisci flashare per indirizzo)

| File | Indirizzo |
|---|---|
| `bootloader_0x1000.bin` | 0x1000 |
| `partitions_0x8000.bin` | 0x8000 |
| `boot_app0_0xe000.bin` | 0xe000 |
| `VX26_Operator_APP_0x10000.bin` | 0x10000 |

```
esptool.py --chip esp32 --port COM3 --baud 921600 write_flash -z \
  0x1000 bootloader_0x1000.bin \
  0x8000 partitions_0x8000.bin \
  0xe000 boot_app0_0xe000.bin \
  0x10000 VX26_Operator_APP_0x10000.bin
```

Se aggiorni un firmware già installato e vuoi cancellare le impostazioni salvate
(Preferences/NVS), aggiungi `--erase-all` al comando.

## Note

- Il driver USB **CH340** serve comunque per far comparire la porta COM in Windows.
- Lo `0x0` dell'opzione A funziona perché l'immagine è "merged": contiene già il
  bootloader all'offset giusto.
- Se lo schermo resta bianco o con i colori invertiti, non è un problema di flash:
  è la variante del controller. In `sketch/User_Setup.h` sostituisci
  `ILI9341_2_DRIVER` con `ILI9341_DRIVER` e ricompila.
- Checksum dei file in `SHA256SUMS.txt`.
