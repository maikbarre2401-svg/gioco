# 🚀 DEEP FIELD — MK-VI

Gioco spaziale 3D completo in un singolo file HTML. Niente da installare: apri `index.html` in un browser moderno (serve internet per le librerie Three.js/PeerJS da CDN) e gioca.

**Esplora una galassia procedurale di 110 sistemi, atterra sui pianeti (Terra compresa!), combatti pirati e fauna aliena, potenzia la nave e gioca in co-op con gli amici.**

## ▶️ Come si gioca

1. Apri `index.html` nel browser (o pubblicalo su GitHub Pages: Settings → Pages → branch `main`)
2. Clicca **⟶ AVVIA SEQUENZA**
3. Segui le 6 direttive: calibrazione → scansioni → estrazione → combattimento → avamposto → salto iperspaziale
4. Dopo il primo salto la galassia è tutta tua

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

### Sulla superficie (prima persona)
| Tasto | Azione |
|---|---|
| CLIC | blocca il mouse / **spara col blaster** |
| WASD | cammina |
| SHIFT | corri |
| SPAZIO | salta (gravità diversa su ogni mondo!) |
| F | raccogli minerali / manufatti alieni |
| T | decolla (vicino alla nave) |

## 🌌 Caratteristiche

- **Galassia procedurale**: 110 sistemi, fino a 8 pianeti ciascuno, stelle binarie, comete, cinture di asteroidi, stazioni orbitali, relitti
- **Atterraggio planetario**: esplora a piedi mondi con terreno procedurale, laghi/lava, vegetazione per bioma, **ciclo giorno/notte** con albe e tramonti
- **Fauna aliena**: erbivori, predatori che ti cacciano e meduse fluttuanti — difenditi col blaster
- **Rovine precursori**: monoliti con manufatti da recuperare
- **Economia**: mina/raccogli → vendi alla stazione → potenzia cannoni, scudi, motori, missili
- **Nemici**: droni pirata, corvette miniboss, imboscate casuali
- **Grafica MK-VI**: PBR con riflessi, ombre dinamiche, normal map, raggi solari volumetrici, lens flare, tunnel iperspaziale, FXAA, aberrazione cromatica
- **Audio 100% procedurale** (WebAudio): motore, laser, esplosioni, warp, ambiente

## 👥 Multiplayer co-op (P2P)

1. Nel menu, scrivi il tuo nome e premi **CREA STANZA** → ottieni un codice di 4 lettere
2. I tuoi amici aprono il gioco, inseriscono il codice e premono **ENTRA**
3. Avviate tutti la sequenza: vi vedrete volare con il nome sopra la nave, colpi laser inclusi

Usa il servizio gratuito PeerJS. Per un server proprio: `index.html?ph=tuoserver&pp=porta&pt=/percorso`

## 🛠️ Debug (console del browser)

`DF.gotoPlanet(0)` · `DF.land()` · `DF.takeoff()` · `DF.spawnCorvette()` · `DF.addCredits(500)` · `DF.openHangar()` · `DF.state()` · `DF.net()`

---

Costruito con [Three.js](https://threejs.org) r128 + [PeerJS](https://peerjs.com) · Sviluppato con Claude Code
