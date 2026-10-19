# VX26 Operator v6.0 — firmware precompilato (ESP32 Cheap Yellow Display)

Compilato con: **arduino-esp32 2.0.17**, TFT_eSPI 2.5.43, XPT2046_Touchscreen 1.4
Scheda: **ESP32 Dev Module**, Partition Scheme: **Huge APP (3MB No OTA / 1MB SPIFFS)**
Dimensione sketch: 1.887.765 byte (60% della partizione da 3 MB)

## Novita' della v6.0

- **RADIO > LINK — pannello web**: dal telefono o dal PC apri l'indirizzo mostrato
  (es. `http://192.168.1.42` oppure `http://vx26.local`) e hai:
  - lo **schermo della scheda dal vivo**: toccando l'immagine tocchi lo schermo vero;
  - i pulsanti delle schede, lo stato (livello, memoria, CPU, luce, WiFi, meteo, timer);
  - tema, luminosita', suono, effetto olo e LED;
  - **messaggi**: scrivi un testo e sulla scheda appare "TRASMISSIONE IN ARRIVO".
  Sulla scheda c'e' un **codice QR**: lo inquadri con la fotocamera e il pannello si apre.
- **Hotspot VX26** (RADIO > LINK > HOTSPOT ON): la scheda crea la rete `VX26-OPERATOR`
  (password `vx26-2026`), cosi' il pannello funziona anche senza router, all'indirizzo
  `http://192.168.4.1`. Il pulsante "QR: HOTSPOT" mostra un QR che collega il telefono alla rete.
- **RADIO > CANALI**: analizzatore dello spettro WiFi. Disegna ogni rete come una campana
  sul suo canale (altezza = segnale) e consiglia il canale meno affollato tra 1, 6 e 11.
- **GIOCO > DIFESA**: i missili cadono sui 4 rifugi e tu tocchi il cielo per far esplodere
  le contromisure; le esplosioni fanno reazione a catena. Ondate sempre piu' veloci, dalla
  terza arrivano testate che si dividono in due. Bonus per rifugi salvati e colpi avanzati,
  record salvato.
- **DATA > TIMER**: conto alla rovescia (-1/+1/+5 minuti, allarme con suono e LED rosso
  anche se sei in un'altra scheda) e cronometro con tempi parziali.
- **Livelli ed esperienza veri**: giochi, missioni, scansioni e messaggi danno punti XP;
  il livello in STAT > STATO ora e' reale e viene salvato. Avviso "LIVELLO N RAGGIUNTO".

### Cose da sapere
- Il pannello web funziona sulla stessa rete WiFi della scheda (o collegandosi all'hotspot).
  Chiunque sia sulla stessa rete puo' aprirlo: usalo a casa, non su reti pubbliche.
- Il file unico `FULL` riscrive anche la zona delle impostazioni: dopo il flash tema, record
  e WiFi salvato tornano ai valori iniziali (la password WiFi va reinserita). Per conservarli
  usa l'opzione C e scrivi solo `VX26_Operator_APP_0x10000.bin` all'indirizzo 0x10000.

## Opzione A — un solo file, flasher dal browser (consigliata)

File: `VX26_Operator_FULL_0x1000.bin` (immagine completa: bootloader + tabella partizioni + boot_app0 + app,
pensata per l'indirizzo **0x1000**, che è quello già proposto da esptool-js)

1. Apri **https://espressif.github.io/esptool-js/** con Chrome o Edge (Firefox e Safari non supportano la Web Serial).
2. Collega la scheda via USB, imposta Baudrate **460800** e premi **Connect**, poi scegli la porta COM.
   Se appare "Connecting..." senza avanzare, tieni premuto **BOOT** sulla scheda.
3. Premi **Erase Flash** e aspetta che finisca (cancella anche i resti di versioni vecchie).
4. In "Flash Address" lascia **0x1000** e seleziona `VX26_Operator_FULL_0x1000.bin`
   (attenzione a non prendere un file vecchio dalla cartella Download).
5. Premi **Program**, poi a fine scrittura premi **RST** (o scollega e ricollega l'USB).

## Opzione B — immagine per 0x0 / esptool da riga di comando

`VX26_Operator_FULL_0x0.bin` è la stessa immagine con 4 KB vuoti davanti: va scritta **solo a 0x0**.

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
- **Ogni file va scritto al suo indirizzo**, quello scritto nel nome. Se si scrive
  `FULL_0x0.bin` a 0x1000 il bootloader finisce nel posto sbagliato: la scheda non si avvia
  e lo schermo resta **nero** (sul monitor seriale a 115200 si vede `invalid header: 0xffffffff`
  in ciclo). Si risolve rifacendo il flash con il file e l'indirizzo giusti.
- Se lo schermo resta bianco o con i colori invertiti, non è un problema di flash:
  è la variante del controller. In `sketch/User_Setup.h` sostituisci
  `ILI9341_2_DRIVER` con `ILI9341_DRIVER` e ricompila.
- Checksum dei file in `SHA256SUMS.txt`.
