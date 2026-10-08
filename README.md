# Rick and Morty – Città Interdimensionale

<img src="icon.png" width="96" align="right" alt="icona">

Videogioco **open world 3D in stile GTA**, in **terza e prima persona**, ambientato nel mondo di
**Rick and Morty**. Scritto **da zero** in Python + Panda3D: la città, i personaggi, le auto, il cielo,
le texture, i suoni e la musica sono **tutti generati via codice**, senza nessun file esterno.

> Fan game **non ufficiale**, gratuito e senza scopo di lucro. Rick and Morty © Adult Swim / Williams Street.

| | |
|---|---|
| ![Strada di giorno](docs/screen_strada.jpg) | ![Alla guida al tramonto](docs/screen_guida.jpg) |
| ![Inseguimento della Federazione](docs/screen_polizia.jpg) | ![In volo con la navicella](docs/screen_volo.jpg) |
| ![La città di notte](docs/screen_notte.jpg) | ![Il Cromulon](docs/screen_cromulon.jpg) |

## Cosa c'è nel gioco

- **Una città intera da esplorare**: grattacieli in centro, palazzi con negozi, periferia con le villette
  (c'è anche **casa Smith** con il garage di Rick), parchi, il **Liceo Harry Herpson**, la sala giochi
  **Blips and Chitz**, la sede della **Federazione Galattica**, un distributore, parcheggi e campagna.
- **Terza persona e prima persona** (tasto **V**), a piedi e in auto.
- **Ruba e guida qualsiasi auto** (berline, utilitarie, furgoni, sportive, auto della polizia) con fisica
  arcade: derapate col freno a mano, danni, fumo, incendi ed esplosioni.
- **La navicella spaziale di Rick**: vola sopra la città e atterra sui tetti.
- **Traffico e passanti** che camminano sui marciapiedi, scappano e chiamano la polizia.
- **Livello di ricercato a 5 stelle**: più crimini fai, più la Federazione Galattica (con i Gromflomiti,
  le auto della polizia e i droni) ti dà la caccia. Per seminarli devi sparire dalla loro vista.
- **Armi**: pugni, pistola laser, fucile al plasma e la **pistola portale** per teletrasportarti
  ovunque (anche sui tetti).
- **Morty** ti segue, sale in auto con te, spara (male) e commenta.
- **Ciclo giorno/notte** con luci realistiche: ombre del sole, finestre illuminate di notte, lampioni,
  fari, insegne al neon, nebbia e cielo con nuvole e stelle.
- **5 missioni con dialoghi in italiano**:
  1. *Il garage di Rick* – porta Morty da Blips and Chitz con la navicella
  2. *Mega Semi* – trova i 5 semi sparsi per la città (uno è su un tetto)
  3. *Guai con la Federazione* – distruggi le auto della polizia e seminale
  4. *Dimensione Cronenberg* – si apre un portale e la città si riempie di mostri
  5. *Mostrami cosa sai fare* – combatti contro il **Cromulon**, una testa gigante nel cielo
- HUD stile GTA: **minimappa** che ruota, **mappa grande** (M), vita, armatura, soldi (Schmeckles), stelle.
- Salvataggio automatico dei progressi.

## Come avviarlo

### Opzione 1 – I file `.exe` (Windows, senza installare niente)
1. Vai nella scheda **Actions** di questo repository su GitHub.
2. Apri l'ultima esecuzione verde di **"Crea gli eseguibili Windows (.exe)"**.
3. In fondo, sotto **Artifacts**, scarica **RickAndMorty-Windows** (è uno zip).
4. Estrai lo zip e fai doppio clic su **RickAndMorty3D.exe**.

Windows potrebbe mostrare "Windows ha protetto il PC" (l'exe non è firmato):
clicca **Ulteriori informazioni → Esegui comunque**.

Puoi anche creare gli exe sul tuo PC: installa [Python](https://www.python.org/downloads/)
(spunta *Add Python to PATH*) e fai doppio clic su **`build_exe.bat`**.

### Opzione 2 – Il file `.py`
```bash
pip install panda3d numpy
python rick_morty_3d.py
```
Su Windows basta fare doppio clic su **`gioca.bat`**.

Serve una scheda video che supporti OpenGL 3 (praticamente tutti i PC degli ultimi 10 anni).
Se il gioco va a scatti, in **Opzioni** abbassa la *Qualità ombre* e riavvialo.

## Comandi

| A piedi | |
|---|---|
| **W A S D** | Muoviti |
| **Mouse** | Guarda / mira |
| **Shift** | Scatto |
| **Ctrl** | Cammina piano |
| **Spazio** | Salta |
| **Click sinistro** | Spara |
| **Click destro** | Mira (visuale sopra la spalla) |
| **1 2 3** / rotellina | Cambia arma |
| **E** | Pistola portale: teletrasporto dove miri |
| **F** | Sali / scendi / ruba un veicolo |
| **H** | Bevi dalla fiaschetta di Rick (+vita) *burp* |
| **V** | Prima / terza persona |

| In auto | |
|---|---|
| **W / S** | Acceleratore / freno e retromarcia |
| **A / D** | Sterzo |
| **Spazio** | Freno a mano (derapata) |
| **Click sinistro** | Spara dal finestrino |
| **H** | Clacson |
| **R** | Radio (Schwifty FM, Radio Multiverso) |
| **Navicella** | Spazio sali, Ctrl scendi |

**M** mappa grande · **Esc** pausa · **F11** schermo intero

## Bonus: il gioco 2D

Nel repository c'è anche il primo gioco, un **platform 2D** in stile cartone con 5 dimensioni
(Cronenberg, Federazione, Pickle Rick nelle fogne, Cittadella dei Rick e il Cromulon):
`python rick_and_morty.py` (serve `pip install pygame`) oppure **`gioca_2d.bat`** /
**RickAndMorty2D.exe**.

## File del progetto

- `rick_morty_3d.py` – il gioco 3D open world (un solo file)
- `rick_and_morty.py` – il gioco 2D
- `gioca.bat` / `gioca_2d.bat` – avviano i giochi su Windows (installano le librerie se mancano)
- `build_exe.bat` – crea gli `.exe` su Windows
- `tools/make_icon.py` – genera l'icona
- `.github/workflows/build-exe.yml` – crea automaticamente gli `.exe` su GitHub

Se il gioco si chiude per un errore, il dettaglio viene salvato in `rick_morty_3d_errore.txt`
nella tua cartella utente.
