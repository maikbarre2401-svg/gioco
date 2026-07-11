# 🚀 DEEP FIELD — MK-XIII

Gioco spaziale 3D completo in un singolo file HTML. Niente da installare: apri `index.html` in un browser moderno (serve internet per le librerie Three.js/PeerJS da CDN) e gioca.

**Esplora una galassia procedurale di 110 sistemi, atterra sui pianeti, cammina o vola in due città complete in 3D — Roma sulla Terra e la metropoli aliena Nyx Prime — combatti pirati e fauna aliena, svolgi missioni, potenzia la nave e gioca in co-op con gli amici.**

## ▶️ Come si gioca

1. Apri `index.html` nel browser (o pubblicalo su GitHub Pages: Settings → Pages → branch `main`)
2. Clicca **⟶ AVVIA SEQUENZA**
3. Segui le 6 direttive: calibrazione → scansioni → estrazione → combattimento → avamposto → salto iperspaziale
4. Dopo il primo salto la galassia è tutta tua — parti dal Sistema Sol con la **Terra** (atterra e visita Roma!) e **Nyx Prime** (la città aliena, 3° pianeta)

## 🎮 Comandi

### Nello spazio
| Tasto | Azione |
|---|---|
| MOUSE | rotta |
| W / S | spinta +/− |
| SHIFT | turbo |
| SPAZIO / clic | cannone a impulsi |
| R | missile a guida |
| TAB | aggancia bersaglio |
| F | scansiona / interagisci / attracca |
| G (tieni premuto) | estrai minerali dagli asteroidi |
| L | **atterra sul pianeta agganciato** |
| M | mappa galattica (ENTER per saltare) |
| V | audio on/off |
| ESC | pausa / impostazioni (qualità, audio, salvataggio) |
| P | modalità foto (nasconde l'HUD) |

### A piedi sulla superficie (prima persona)
| Tasto | Azione |
|---|---|
| CLIC | blocca il mouse / **spara col blaster** |
| WASD | cammina |
| SHIFT | corri |
| SPAZIO | salta (gravità diversa su ogni mondo!) |
| F | raccogli minerali / manufatti / **parla con NPC** / accetta missioni |
| E | **sali sulla nave e vola in atmosfera** |
| T | decolla verso l'orbita |

### Pilotando la nave sul pianeta (volo atmosferico)
| Tasto | Azione |
|---|---|
| MOUSE | rotta · W/S spinta · SHIFT turbo |
| CLIC / SPAZIO | **cannone** (sui mondi ostili) |
| L | atterra qui e scendi dalla nave |
| T | risali in orbita |

## 🌌 Caratteristiche

- **Galassia procedurale**: 110 sistemi, fino a 8 pianeti ciascuno, stelle binarie, comete, cinture di asteroidi, stazioni orbitali, relitti
- **Atterraggio planetario**: esplora a piedi o **in volo** mondi con terreno procedurale, laghi/lava, vegetazione per bioma, **ciclo giorno/notte** con albe, tramonti e notti stellate
- **🏛️ ROMA in 3D** sulla Terra: Colosseo, Pantheon, Basilica di San Pietro, Castel Sant'Angelo, obelisco, arco di trionfo, acquedotto, Tevere coi ponti, palazzi con facciate texturizzate e finestre che si accendono di notte, sampietrini, traffico, uccelli e cittadini romani con cui parlare
- **🛸 NYX PRIME**, metropoli aliena al neon su un mondo di cristallo: torri luminose, pavimento a griglia cyberpunk, guglia centrale, piattaforme fluttuanti, ologrammi, abitanti alieni e droni sintetici
- **📜 Missioni (taglie)**: gli NPC segnati dal marcatore dorato affidano incarichi — raccogli minerali o abbatti predatori — in cambio di crediti
- **Mondi ostili**: alcuni pianeti hanno difese nemiche — torrette di terra e droni volanti che ti sparano; distruggile a piedi (blaster) o sorvolandole col cannone della nave, per crediti
- **Fauna aliena**: erbivori, predatori che ti cacciano e meduse fluttuanti — difenditi col blaster
- **Rovine precursori**: monoliti con manufatti da recuperare
- **Economia**: mina/raccogli → vendi alla stazione o ai mercanti di città → potenzia cannoni, scudi, motori, missili
- **Nemici**: droni pirata, corvette miniboss, imboscate casuali
- **Grafica**: PBR con riflessi, ombre dinamiche, normal map, raggi solari volumetrici, lens flare, tunnel iperspaziale, luna, illuminazione notturna, FXAA, aberrazione cromatica
- **Audio 100% procedurale** (WebAudio): motore, laser, esplosioni, warp, ambiente
- **Salvataggio automatico** dei progressi (crediti, potenziamenti, missili, missioni) nel browser: riprendi da dove avevi lasciato
- **Menu di pausa** (ESC) con qualità grafica regolabile (per PC meno potenti), audio e modalità foto
- **Meteo**: pioggia atmosferica su alcuni mondi con acqua

## 👥 Multiplayer co-op (P2P)

1. Nel menu, scrivi il tuo nome e premi **CREA STANZA** → ottieni un codice di 4 lettere
2. I tuoi amici aprono il gioco, inseriscono il codice e premono **ENTRA**
3. Avviate tutti la sequenza: vi vedrete volare con il nome sopra la nave, colpi laser inclusi

Usa il servizio gratuito PeerJS. Per un server proprio: `index.html?ph=tuoserver&pp=porta&pt=/percorso`

## 🛠️ Debug (console del browser)

`DF.gotoPlanet(n)` · `DF.land()` · `DF.takeoff()` · `DF.spawnCorvette()` · `DF.addCredits(500)` · `DF.openHangar()` · `DF.setTime(0.8)` (0=notte, 0.25=alba) · `DF.talkGiver()` · `DF.state()` · `DF.net()`

---

Costruito con [Three.js](https://threejs.org) r128 + [PeerJS](https://peerjs.com) · Sviluppato con Claude Code
