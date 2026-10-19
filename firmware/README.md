# VX26 Operator v7.0 — firmware precompilato (ESP32 Cheap Yellow Display)

**Creator: MAIKGOST**

Compilato con: **arduino-esp32 2.0.17**, TFT_eSPI 2.5.43, XPT2046_Touchscreen 1.4
Scheda: **ESP32 Dev Module**, partizioni: `sketch/partitions.csv` (due slot da 1,98 MB per
l'aggiornamento senza cavo). Dimensione app: 1.923.472 byte (94% dello slot).

## Novita' della v7.0

- **CREATOR: MAIKGOST** nell'avvio (logo, autodiagnosi e schermata finale), in STAT > SISTEMA,
  nel salvaschermo e nel pannello web.
- **Aggiornamento firmware dal telefono/PC, senza cavo**: nel pannello web, sezione
  "AGGIORNA FIRMWARE", scegli `VX26_Operator_APP_0x10000.bin` di una versione nuova, scrivi il
  PIN e premi AGGIORNA. La scheda mostra l'avanzamento e si riavvia da sola. Il file viene
  scritto nello slot libero e controllato prima di essere usato: se qualcosa va storto la
  scheda continua ad avviare la versione vecchia.
- **WiFi dal telefono**: nel pannello web "CERCA RETI", scegli la rete, scrivi password e PIN.
  Utile con l'hotspot: niente piu' password digitate sulla tastierina dello schermo.
- **PIN di sicurezza**: WiFi e aggiornamenti richiedono il PIN a 4 cifre mostrato SOLO sulla
  scheda (RADIO > LINK). Cambia a ogni accensione e dopo 5 tentativi sbagliati.
- **Sveglia** (DATA > TIMER > SVEGLIA): ora reale da internet, suona ogni giorno, anche se la
  scheda e' nel salvaschermo. Ore con H-/H+, minuti a passi di 5 con M-/M+.
- **Grafico dei sensori nel pannello web**: RAM, CPU, luce e WiFi degli ultimi 2 minuti.
- **Riconnessione automatica**: se il WiFi salvato cade, la scheda riprova da sola ogni 45 s.

## Come installarla (la v7 cambia le partizioni: la prima volta serve il cavo)

### Opzione A — un solo file (consigliata, azzera le impostazioni)
1. Apri **https://espressif.github.io/esptool-js/** con Chrome o Edge, Baudrate **460800**, **Connect**
   (se resta su "Connecting..." tieni premuto **BOOT**).
2. **Erase Flash**, poi in "Flash Address" lascia **0x1000** e scegli `VX26_Operator_FULL_0x1000.bin`.
3. **Program**, poi tasto **RST**. Tema, record e WiFi salvato ripartono da zero.

### Opzione B — quattro file (tiene impostazioni, record e WiFi salvato)
Senza Erase Flash, aggiungi in esptool-js quattro righe ("Add File"):

| File | Indirizzo |
|---|---|
| `bootloader_0x1000.bin` | 0x1000 |
| `partitions_0x8000.bin` | 0x8000 |
| `boot_app0_0xe000.bin` | 0xe000 |
| `VX26_Operator_APP_0x10000.bin` | 0x10000 |

```
esptool.py --chip esp32 --port COM3 --baud 921600 write_flash -z \
  0x1000 bootloader_0x1000.bin 0x8000 partitions_0x8000.bin \
  0xe000 boot_app0_0xe000.bin 0x10000 VX26_Operator_APP_0x10000.bin
```

### Dalla v7 in poi — senza cavo
Pannello web > AGGIORNA FIRMWARE con `VX26_Operator_APP_0x10000.bin` e il PIN.
Le impostazioni restano.

## Note

- **Ogni file va scritto al suo indirizzo**, quello nel nome. `FULL_0x0.bin` va solo a 0x0,
  `FULL_0x1000.bin` solo a 0x1000. Se l'indirizzo e' sbagliato lo schermo resta nero.
- Il driver USB **CH340** serve per far comparire la porta COM in Windows.
- All'avvio la scheda stampa un'autodiagnosi sul monitor seriale (115200 baud): se qualcosa
  non va, copiala e mandala.
- Il pannello web e' raggiungibile da chiunque sia sulla tua rete: le azioni importanti
  (WiFi e aggiornamento) chiedono il PIN, ma usalo comunque a casa, non su reti pubbliche.
- Se lo schermo resta bianco o con i colori invertiti e' la variante del controller:
  in `sketch/User_Setup.h` sostituisci `ILI9341_2_DRIVER` con `ILI9341_DRIVER` e ricompila.
- Checksum dei file in `SHA256SUMS.txt`.

## Novita' della v6.1 — niente piu' contenuti finti

- **Nuova scheda NET** al posto dell'inventario inventato:
  - **PING**: 20 ping ICMP veri verso il router, 1.1.1.1, 8.8.8.8 o google.com, con grafico,
    minimo/medio/massimo e pacchetti persi;
  - **VELOCITA'**: test di download reale (speedtest.tele2.net, in alternativa Cloudflare)
    con Mbit/s in tempo reale e media. Il limite e' la scheda stessa, circa 20 Mbit/s;
  - **IP**: IP locale con subnet, router, DNS, rete e canale, IP pubblico, provider e citta'.
- **OBIETTIVI** al posto delle missioni inventate: 8 obiettivi che si spuntano solo quando li
  raggiungi davvero (connettere il WiFi, scansionare, trovare 5 dispositivi BT, violare il
  terminale, 20 punti a Serpente, 3 ondate a Difesa, aprire il pannello, ricevere un messaggio).
- **Avvio con autodiagnosi vera**: i byte mostrati sono letti dalla memoria flash (il
  bootloader), e al posto dei finti "[ OK ]" ci sono i valori misurati: RAM libera, flash,
  dimensione dell'app, temperatura CPU, sensore di luce, MAC, rete salvata. Lo stesso
  rapporto viene stampato sul monitor seriale (115200 baud).
- **STATO**: le barre attorno alla figura ora sono valori veri (CPU, RAM, WiFi, luce,
  spazio dell'app, esperienza) con la loro etichetta.
- **Radar**: la distanza dal centro e' il segnale e l'angolo e' il canale WiFi. La scheda non
  puo' misurare la direzione da cui arriva un segnale, quindi non la inventa.

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
