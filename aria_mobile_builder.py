#!/usr/bin/env python3
"""
ARIA Mobile — Builder COMPLETO v4.0 (Android, Kotlin) con build automatica
===========================================================================
Genera l'intero progetto Android Studio per ARIA Mobile in
Desktop/AriaMobile e tenta la compilazione (gradlew assembleDebug)
usando il JDK e l'Android SDK già presenti sul sistema (Android Studio
installato).

NOVITÀ v9.1 (ASCOLTO CHE DURA NEL TEMPO):
- PULSANTE '🔋 Escludi dal risparmio batteria': con un tocco chiedi ad
  Android di non chiudere ARIA. Senza questo, il telefono uccide il
  servizio 'Hey Maik' dopo qualche minuto (era la causa di 'poi non
  mi sente piu').
- RIAVVIO AUTOMATICO dopo il reboot del telefono: se l'ascolto era
  attivo, riparte da solo (BootReceiver).

NOVITÀ v9.0 (ARIA CONTROLLA IL TELEFONO):
- CONTROLLO DEL TELEFONO: chiedi ad ARIA (a voce o per iscritto) di
  aprire app, cercare su Google/YouTube, aprire siti, CHIAMARE, mandare
  messaggi WHATSAPP/SMS/EMAIL, aprire le MAPPE, impostare TIMER/SVEGLIA,
  accendere la TORCIA o aprire la FOTOCAMERA. L'AI emette comandi che
  l'app esegue via Intent Android.
- FUNZIONA ANCHE OFFLINE: comandi naturali diretti ("apri youtube",
  "chiama 333...", "torcia", "timer di 5 minuti") senza bisogno dell'AI.
- FUNZIONA COL WAKE: "Hey Maik, apri WhatsApp" e lo fa a voce.
- SICUREZZA: chiamate e messaggi NON partono di nascosto: ARIA apre
  telefono/WhatsApp/SMS gia' compilati e sei TU a premere invia/chiama.
  Interruttore 'Controllo telefono' nelle impostazioni (attivo).

NOVITÀ v8.0 (LA VERA AI - LIVELLO MONDIALE):
- RISPOSTE IN STREAMING: il testo appare PAROLA PER PAROLA in tempo
  reale come ChatGPT (Server-Sent Events di Groq). La chat scorre da
  sola mentre l'AI scrive e la sfera mostra 'sto scrivendo...'.
- PULSANTE STOP: mentre l'AI scrive, il pulsante Invia diventa un
  pulsante rosso di STOP per fermare subito la generazione.
- BENVENUTO INTELLIGENTE: al primo avvio senza API key appare il
  pulsante 'Configura ARIA in 30 secondi' che porta alle impostazioni.
- NUOVA ICONA APP: orb luminoso viola/ciano con anello orbitale ed
  elettrone, in tema con la sfera 3D.

NOVITÀ v7.0 (AI OFFLINE SCARICABILE + SFERA 3D VERA):
- PULSANTE '⬇ SCARICA AI OFFLINE': scarica il pacchetto di conoscenza
  (65+ risposte: capitali, scienza, storia, geografia, animali,
  conversioni...) che RESTA sul telefono. Prova prima online (versione
  aggiornata da GitHub), altrimenti usa quello incluso nell'APK.
- SELETTORE MODALITA' AI: Auto (consigliato) / Solo online (Groq) /
  Solo offline (senza internet). La modalita' e' mostrata anche nella
  barra della chat.
- PULSANTE '🧪 PROVA AI OFFLINE': testa matematica, ora e conoscenza
  e ti dice esattamente cosa funziona.
- SFERA 3D VERA: illuminazione lambertiana (una sorgente di luce in
  alto a sinistra: il lato illuminato brilla, quello in ombra si
  scurisce), ordinamento per profondita' (le particelle dietro passano
  DIETRO il nucleo, quelle davanti sopra), ombra morbida a terra che
  segue la fluttuazione. Effetto tridimensionale reale.

NOVITÀ v6.2 (GROQ TORNA PRIMARIO):
- FIX: la 'Modalita' offline' NON blocca piu' Groq. Prima intercettava
  ogni messaggio col cervello locale: ecco perche' Groq 'non funzionava
  come prima'. Ora Groq e' SEMPRE il cervello principale quando c'e' la
  API key.
- L'offline resta come rete di sicurezza: interviene solo per ora/data
  (accurate), se manca la key, o se Groq fallisce (niente rete).
- L'AI ora conosce DATA E ORA correnti (inserite nel system prompt):
  risposte piu' precise.
- Memoria di contesto ampliata (24 messaggi). Toggle offline ora vale
  solo per il riconoscimento vocale offline, non blocca le risposte.

NOVITÀ v6.1 (ASCOLTO MOLTO PIU' AFFIDABILE):
- FIX IMPORTANTE: il wake NON usa piu' il riconoscimento 'offline'
  (che senza pacchetto lingua non sentiva NULLA). Ora usa il motore
  piu' affidabile disponibile.
- Risultati PARZIALI: sente 'Hey Maik' mentre parli, non a fine frase.
- Matching FUZZY (Levenshtein + senza accenti): tollera 'maik/mike/
  maic' e piccoli errori del riconoscitore.
- WATCHDOG anti-blocco: se l'ascolto si ferma per qualsiasi motivo,
  viene riavviato automaticamente; recognizer ricreato sugli errori.
- Notifica con stato in tempo reale (In ascolto / Ti ascolto / Sto
  pensando / Parlo).
- Nuovo pulsante '🎤 Prova ascolto' nelle impostazioni: ti dice
  esattamente cosa ha sentito, per capire subito se funziona; avviso
  se il riconoscimento non e' disponibile sul telefono.

NOVITÀ v6.0:
- CERVELLO OFFLINE (funziona SENZA internet): risponde a saluti,
  identita', ora, data, calcoli matematici (con valutatore vero),
  testa o croce, dadi, numeri casuali e battute. Se sei offline o
  attivi la 'Modalita' offline' usa questo; online senza key funziona
  lo stesso per queste cose.
- PULSANTE 'SCARICA VOCE OFFLINE' nelle impostazioni: scarica la voce
  Italiano del telefono, che poi resta installata; il riconoscimento
  vocale usa EXTRA_PREFER_OFFLINE quando la modalita' offline e' attiva.
- WAKE PIU' PERSONALE: dicendo 'Hey <parola>' ARIA risponde
  'Si', dimmi <il tuo nome>' usando il nome impostato.
- SFERA piu' bella e MOLTO piu' calma: si muove meno e piu' lenta,
  soprattutto quando parla (niente piu' rotazione troppo veloce),
  elettroni piu' brillanti, onde sonore piu' morbide.

NOVITÀ v5.0:
- ASSISTENTE VOCALE SEMPRE ATTIVO ("Hey Maik"): un servizio in
  background ascolta anche a SCHERMO BLOCCATO. Quando dici "Hey" +
  la tua parola (default 'maik', cambiabile nelle impostazioni),
  ARIA risponde "Si'?", ascolta il comando e lo esegue a voce.
  Puoi anche dire tutto insieme: "Hey Maik che ore sono".
- COMANDI RAPIDI LOCALI (istantanei, senza internet): ora e data.
  Tutto il resto va all'AI Groq e viene letto a voce.
- Notifica persistente con stato, wake-lock per non addormentarsi,
  richiesta automatica dei permessi microfono/notifiche.

NOVITÀ v4.1:
- SFERA ANCORA PIU' 3D: doppio guscio di particelle (interno +
  esterno controrotante per un vero effetto parallasse), reticolo
  olografico a griglia che ruota, fog di profondita' (i punti dietro
  sfumano nel fondo), onde sonore che si espandono quando parla,
  scie luminose dietro gli elettroni, wobble su piu' assi e jitter
  energetico quando pensa.
- Vibra al tocco; parlando al microfono la voce dell'AI si ferma per
  non sovrapporsi.

NOVITÀ v4.0:
- SFERA 3D VIVA NELLA CHAT (stile Jarvis, ma meglio): nucleo luminoso
  che respira, sfera di 150 particelle in rotazione con prospettiva
  reale, 3 anelli orbitali inclinati che precedono nello spazio con
  elettroni luminosi. La sfera FLUTTUA nella chat ed è VIVA: cambia
  colore e velocità in base a quello che fa l'AI —
    * azzurra e calma quando ascolta
    * viola e velocissima quando sta pensando
    * verde quando parla a voce
    * rossa se c'è un errore
- TOCCA LA SFERA per attivare il microfono e parlarle a voce.

NOVITÀ v3.0:
- VOCE CHE PARLA DAVVERO: voce attiva di default, pulsante altoparlante
  nella barra per accenderla/spegnerla al volo, icona 🔊 su ogni
  risposta per riascoltarla, fallback automatico alla lingua di sistema
  se manca la voce italiana, pulizia dei simboli markdown prima della
  lettura.
- 10 STRUMENTI: il pulsante ✨ accanto alla chat apre un pannello con
  Traduttore, Riassunto, Correttore, Matematica, Email, Idee, Chef,
  Coach fitness, Quiz e Barzellette.
- PERSONALITÀ: scegli come si comporta l'AI (Amichevole, Professionale,
  Divertente, Sarcastica, Motivazionale).
- PROVA CONNESSIONE: nelle impostazioni testi la API key con un tocco.
- SCELTA MODELLO RAPIDA: 3 pulsanti per i modelli Groq più usati.
- CONDIVIDI CHAT: esporta la conversazione su WhatsApp/Telegram/ecc.
- Menu ordinato (cronologia, condividi, svuota) e altre rifiniture.

NOVITÀ v2.0:
- SPLASH SCREEN 3D: all'avvio una sfera di particelle 3D vera (proiezione
  prospettica, rotazione continua) con logo ARIA pulsante e la scritta
  "Creator: MaikGost".
- PULSANTE IMPOSTAZIONI IN CHAT (fix del bug segnalato): nella barra in
  alto ora ci sono le icone Impostazioni, Cronologia e Svuota chat.
- NOME ASSISTENTE PERSONALIZZABILE: nelle impostazioni puoi cambiare
  "ARIA" in qualsiasi nome — appare nella barra e l'AI risponde con
  quella identità.
- IL TUO NOME: l'AI ti chiama per nome se lo imposti.
- INPUT VOCALE: pulsante microfono, detti il messaggio e parte da solo.
- RISPOSTE A VOCE (TTS): attivabile dalle impostazioni, l'AI legge le
  risposte in italiano.
- CHAT PERSISTENTE: riaprendo l'app ritrovi la conversazione.
- MEMORIA ATTIVABILE/DISATTIVABILE dalle impostazioni.
- UI SUPER: sfondo sfumato, bolle con gradiente e orari, indicatore
  "sta scrivendo..." con puntini animati, suggerimenti rapidi al primo
  avvio, tieni premuto un messaggio per copiarlo, dialogo di conferma
  per svuotare la chat.

FIX ereditati dalla v1.1:
- GroqClient su API OkHttp 4.x (toMediaType(), toRequestBody(), ecc.)
- @OptIn(ExperimentalMaterial3Api::class) dove serve.
"""

import os, sys, shutil, subprocess, platform, urllib.request, time, json
from pathlib import Path

class C:
    OK="\033[92m"; WARN="\033[93m"; ERR="\033[91m"
    BOLD="\033[1m"; CYAN="\033[96m"; RESET="\033[0m"

def ok(m):    print(f"{C.OK}  [OK]  {m}{C.RESET}")
def warn(m):  print(f"{C.WARN}  [!]  {m}{C.RESET}")
def err(m):   print(f"{C.ERR}  [X]  {m}{C.RESET}")
def info(m):  print(f"     {m}")
def title(m): print(f"\n{C.BOLD}{C.CYAN}{'-'*64}\n  {m}\n{'-'*64}{C.RESET}")
def step(n, total, m): print(f"{C.CYAN}  [{n}/{total}] {m}{C.RESET}")

DESKTOP     = Path.home() / "Desktop"
PROJECT_DIR = DESKTOP / "AriaMobile"
PKG_ROOT    = "com/aria/mobile"
PKG_UI      = f"{PKG_ROOT}/ui"
PKG_CORE    = f"{PKG_ROOT}/core"
PKG_DATA    = f"{PKG_ROOT}/data"
PKG_NET     = f"{PKG_ROOT}/net"
PKG_VOICE   = f"{PKG_ROOT}/voice"

# Pacchetto di conoscenza offline (scaricabile/incluso nell'APK)
KNOWLEDGE_PACK_JSON = '{\n "version": 1,\n "entries": [\n  {\n   "k": [\n    "capitale",\n    "italia"\n   ],\n   "a": "La capitale dell\'Italia è Roma."\n  },\n  {\n   "k": [\n    "capitale",\n    "francia"\n   ],\n   "a": "La capitale della Francia è Parigi."\n  },\n  {\n   "k": [\n    "capitale",\n    "germania"\n   ],\n   "a": "La capitale della Germania è Berlino."\n  },\n  {\n   "k": [\n    "capitale",\n    "spagna"\n   ],\n   "a": "La capitale della Spagna è Madrid."\n  },\n  {\n   "k": [\n    "capitale",\n    "portogallo"\n   ],\n   "a": "La capitale del Portogallo è Lisbona."\n  },\n  {\n   "k": [\n    "capitale",\n    "inghilterra"\n   ],\n   "a": "La capitale dell\'Inghilterra è Londra."\n  },\n  {\n   "k": [\n    "capitale",\n    "regno"\n   ],\n   "a": "La capitale del Regno Unito è Londra."\n  },\n  {\n   "k": [\n    "capitale",\n    "america"\n   ],\n   "a": "La capitale degli Stati Uniti è Washington D.C."\n  },\n  {\n   "k": [\n    "capitale",\n    "stati"\n   ],\n   "a": "La capitale degli Stati Uniti è Washington D.C."\n  },\n  {\n   "k": [\n    "capitale",\n    "giappone"\n   ],\n   "a": "La capitale del Giappone è Tokyo."\n  },\n  {\n   "k": [\n    "capitale",\n    "cina"\n   ],\n   "a": "La capitale della Cina è Pechino."\n  },\n  {\n   "k": [\n    "capitale",\n    "russia"\n   ],\n   "a": "La capitale della Russia è Mosca."\n  },\n  {\n   "k": [\n    "capitale",\n    "grecia"\n   ],\n   "a": "La capitale della Grecia è Atene."\n  },\n  {\n   "k": [\n    "capitale",\n    "egitto"\n   ],\n   "a": "La capitale dell\'Egitto è Il Cairo."\n  },\n  {\n   "k": [\n    "capitale",\n    "brasile"\n   ],\n   "a": "La capitale del Brasile è Brasilia."\n  },\n  {\n   "k": [\n    "capitale",\n    "canada"\n   ],\n   "a": "La capitale del Canada è Ottawa."\n  },\n  {\n   "k": [\n    "capitale",\n    "australia"\n   ],\n   "a": "La capitale dell\'Australia è Canberra."\n  },\n  {\n   "k": [\n    "capitale",\n    "svizzera"\n   ],\n   "a": "La capitale della Svizzera è Berna."\n  },\n  {\n   "k": [\n    "capitale",\n    "austria"\n   ],\n   "a": "La capitale dell\'Austria è Vienna."\n  },\n  {\n   "k": [\n    "capitale",\n    "olanda"\n   ],\n   "a": "La capitale dei Paesi Bassi è Amsterdam."\n  },\n  {\n   "k": [\n    "quanti",\n    "pianeti"\n   ],\n   "a": "Il sistema solare ha 8 pianeti: Mercurio, Venere, Terra, Marte, Giove, Saturno, Urano e Nettuno."\n  },\n  {\n   "k": [\n    "pianeta",\n    "piu grande"\n   ],\n   "a": "Giove è il pianeta più grande del sistema solare."\n  },\n  {\n   "k": [\n    "pianeta",\n    "vicino",\n    "sole"\n   ],\n   "a": "Mercurio è il pianeta più vicino al Sole."\n  },\n  {\n   "k": [\n    "pianeta",\n    "rosso"\n   ],\n   "a": "Il pianeta rosso è Marte."\n  },\n  {\n   "k": [\n    "velocita",\n    "luce"\n   ],\n   "a": "La luce viaggia a circa 299.792 chilometri al secondo."\n  },\n  {\n   "k": [\n    "acqua",\n    "bolle"\n   ],\n   "a": "L\'acqua bolle a 100 gradi Celsius (al livello del mare)."\n  },\n  {\n   "k": [\n    "acqua",\n    "congela"\n   ],\n   "a": "L\'acqua congela a 0 gradi Celsius."\n  },\n  {\n   "k": [\n    "formula",\n    "acqua"\n   ],\n   "a": "La formula chimica dell\'acqua è H2O."\n  },\n  {\n   "k": [\n    "quante",\n    "ossa"\n   ],\n   "a": "Il corpo umano adulto ha 206 ossa."\n  },\n  {\n   "k": [\n    "simbolo",\n    "oro"\n   ],\n   "a": "Il simbolo chimico dell\'oro è Au."\n  },\n  {\n   "k": [\n    "simbolo",\n    "ossigeno"\n   ],\n   "a": "Il simbolo chimico dell\'ossigeno è O."\n  },\n  {\n   "k": [\n    "satellite",\n    "terra"\n   ],\n   "a": "Il satellite naturale della Terra è la Luna."\n  },\n  {\n   "k": [\n    "stella",\n    "vicina"\n   ],\n   "a": "La stella più vicina alla Terra è il Sole; dopo di lui, Proxima Centauri."\n  },\n  {\n   "k": [\n    "fiume",\n    "piu lungo"\n   ],\n   "a": "Il Nilo e il Rio delle Amazzoni si contendono il primato di fiume più lungo del mondo, circa 6.650 km."\n  },\n  {\n   "k": [\n    "monte",\n    "piu alto"\n   ],\n   "a": "Il monte più alto del mondo è l\'Everest, 8.849 metri."\n  },\n  {\n   "k": [\n    "monte",\n    "piu alto",\n    "italia"\n   ],\n   "a": "Il monte più alto d\'Italia è il Monte Bianco, 4.806 metri."\n  },\n  {\n   "k": [\n    "fiume",\n    "piu lungo",\n    "italia"\n   ],\n   "a": "Il fiume più lungo d\'Italia è il Po, 652 km."\n  },\n  {\n   "k": [\n    "oceano",\n    "piu grande"\n   ],\n   "a": "L\'oceano più grande è il Pacifico."\n  },\n  {\n   "k": [\n    "deserto",\n    "piu grande"\n   ],\n   "a": "Il deserto più grande è l\'Antartide; il più grande deserto caldo è il Sahara."\n  },\n  {\n   "k": [\n    "quante",\n    "regioni",\n    "italia"\n   ],\n   "a": "L\'Italia ha 20 regioni."\n  },\n  {\n   "k": [\n    "vulcano",\n    "europa"\n   ],\n   "a": "Il vulcano attivo più alto d\'Europa è l\'Etna, in Sicilia."\n  },\n  {\n   "k": [\n    "quanti",\n    "continenti"\n   ],\n   "a": "I continenti sono 7: Africa, America del Nord, America del Sud, Antartide, Asia, Europa e Oceania."\n  },\n  {\n   "k": [\n    "seconda",\n    "guerra",\n    "mondiale"\n   ],\n   "a": "La Seconda Guerra Mondiale è durata dal 1939 al 1945."\n  },\n  {\n   "k": [\n    "prima",\n    "guerra",\n    "mondiale"\n   ],\n   "a": "La Prima Guerra Mondiale è durata dal 1914 al 1918."\n  },\n  {\n   "k": [\n    "scoperta",\n    "america"\n   ],\n   "a": "L\'America fu raggiunta da Cristoforo Colombo nel 1492."\n  },\n  {\n   "k": [\n    "unita",\n    "italia"\n   ],\n   "a": "L\'Unità d\'Italia è stata proclamata nel 1861."\n  },\n  {\n   "k": [\n    "uomo",\n    "luna"\n   ],\n   "a": "Il primo uomo sulla Luna fu Neil Armstrong, il 20 luglio 1969."\n  },\n  {\n   "k": [\n    "muro",\n    "berlino"\n   ],\n   "a": "Il Muro di Berlino è caduto il 9 novembre 1989."\n  },\n  {\n   "k": [\n    "quando",\n    "fondata",\n    "roma"\n   ],\n   "a": "Secondo la tradizione, Roma fu fondata nel 753 a.C."\n  },\n  {\n   "k": [\n    "animale",\n    "piu veloce"\n   ],\n   "a": "L\'animale terrestre più veloce è il ghepardo (circa 110 km/h); il falco pellegrino in picchiata supera i 300 km/h."\n  },\n  {\n   "k": [\n    "animale",\n    "piu grande"\n   ],\n   "a": "L\'animale più grande mai esistito è la balenottera azzurra, fino a 30 metri."\n  },\n  {\n   "k": [\n    "animale",\n    "piu alto"\n   ],\n   "a": "L\'animale più alto è la giraffa, fino a 5,5 metri."\n  },\n  {\n   "k": [\n    "quanto",\n    "vive",\n    "gatto"\n   ],\n   "a": "Un gatto domestico vive in media 12-18 anni."\n  },\n  {\n   "k": [\n    "quanto",\n    "vive",\n    "cane"\n   ],\n   "a": "Un cane vive in media 10-13 anni, a seconda della taglia."\n  },\n  {\n   "k": [\n    "quanti",\n    "giorni",\n    "anno"\n   ],\n   "a": "Un anno ha 365 giorni; 366 negli anni bisestili."\n  },\n  {\n   "k": [\n    "anno",\n    "bisestile"\n   ],\n   "a": "L\'anno bisestile arriva ogni 4 anni e ha 366 giorni (febbraio ne ha 29)."\n  },\n  {\n   "k": [\n    "pi greco"\n   ],\n   "a": "Pi greco vale circa 3,14159."\n  },\n  {\n   "k": [\n    "colori",\n    "arcobaleno"\n   ],\n   "a": "L\'arcobaleno ha 7 colori: rosso, arancione, giallo, verde, blu, indaco e violetto."\n  },\n  {\n   "k": [\n    "lingua",\n    "piu parlata"\n   ],\n   "a": "L\'inglese è la lingua più diffusa nel mondo; il cinese mandarino ha più madrelingua."\n  },\n  {\n   "k": [\n    "quante",\n    "ore",\n    "giorno"\n   ],\n   "a": "Un giorno ha 24 ore."\n  },\n  {\n   "k": [\n    "quanti",\n    "minuti",\n    "ora"\n   ],\n   "a": "Un\'ora ha 60 minuti."\n  },\n  {\n   "k": [\n    "cuore",\n    "batte"\n   ],\n   "a": "A riposo il cuore batte in media 60-100 volte al minuto."\n  },\n  {\n   "k": [\n    "miglio",\n    "km"\n   ],\n   "a": "Un miglio equivale a 1,609 chilometri."\n  },\n  {\n   "k": [\n    "pollice",\n    "centimetri"\n   ],\n   "a": "Un pollice equivale a 2,54 centimetri."\n  },\n  {\n   "k": [\n    "litro",\n    "millilitri"\n   ],\n   "a": "Un litro equivale a 1.000 millilitri."\n  },\n  {\n   "k": [\n    "kg",\n    "libbre"\n   ],\n   "a": "Un chilogrammo equivale a circa 2,205 libbre."\n  }\n ]\n}'

# ============================================================
#  GRADLE / BUILD FILES
# ============================================================
BUILD_GRADLE_PROJECT = """\
buildscript {
    repositories { google(); mavenCentral() }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.3.2'
        classpath 'org.jetbrains.kotlin:kotlin-gradle-plugin:1.9.23'
    }
}
task clean(type: Delete) { delete rootProject.buildDir }
"""

BUILD_GRADLE_APP = """\
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
    id 'kotlin-kapt'
}

android {
    namespace 'com.aria.mobile'
    compileSdk 34

    defaultConfig {
        applicationId "com.aria.mobile"
        minSdk 26
        targetSdk 34
        versionCode 13
        versionName "9.1.0"
        multiDexEnabled true
    }

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures { viewBinding true; buildConfig true; compose true }

    composeOptions { kotlinCompilerExtensionVersion "1.5.11" }

    buildTypes {
        debug   { minifyEnabled false; debuggable true }
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }

    lint { abortOnError false; checkReleaseBuilds false }

    packagingOptions {
        resources { excludes += ['META-INF/*.kotlin_module', 'META-INF/DEPENDENCIES'] }
    }
}

dependencies {
    implementation 'androidx.core:core-ktx:1.13.1'
    implementation 'androidx.appcompat:appcompat:1.7.0'
    implementation 'com.google.android.material:material:1.12.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    implementation 'androidx.multidex:multidex:2.0.1'

    def lifecycle_version = "2.8.0"
    implementation "androidx.lifecycle:lifecycle-viewmodel-ktx:$lifecycle_version"
    implementation "androidx.lifecycle:lifecycle-livedata-ktx:$lifecycle_version"
    implementation "androidx.lifecycle:lifecycle-runtime-ktx:$lifecycle_version"

    def compose_bom = "2024.05.00"
    implementation platform("androidx.compose:compose-bom:$compose_bom")
    implementation 'androidx.compose.ui:ui'
    implementation 'androidx.compose.ui:ui-tooling-preview'
    implementation 'androidx.compose.material3:material3'
    implementation 'androidx.compose.material:material-icons-extended'
    implementation 'androidx.activity:activity-compose:1.9.0'
    implementation 'androidx.lifecycle:lifecycle-viewmodel-compose:2.8.0'
    debugImplementation 'androidx.compose.ui:ui-tooling'

    def room_version = "2.6.1"
    implementation "androidx.room:room-runtime:$room_version"
    implementation "androidx.room:room-ktx:$room_version"
    kapt "androidx.room:room-compiler:$room_version"

    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.squareup.retrofit2:retrofit:2.11.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.11.0'
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.0'

    implementation 'androidx.datastore:datastore-preferences:1.1.1'
}
"""

SETTINGS_GRADLE = """\
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "ARIA Mobile"
include ':app'
"""

GRADLE_WRAPPER_PROPS = r"""distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.6-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""

PROGUARD_RULES = """\
-keep class com.aria.mobile.data.** { *; }
-keep @androidx.room.Entity class * { *; }
-keep @androidx.room.Dao interface * { *; }
-keepclassmembers class * extends androidx.room.RoomDatabase { *; }
-keepattributes *Annotation*
-keepattributes Signature
-dontwarn org.jetbrains.**
"""

MANIFEST = """\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>
    <uses-permission android:name="android.permission.WAKE_LOCK"/>
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS"/>

    <queries>
        <intent><action android:name="android.intent.action.VIEW"/>
            <data android:scheme="https"/></intent>
        <intent><action android:name="android.intent.action.DIAL"/></intent>
        <intent><action android:name="android.intent.action.SENDTO"/>
            <data android:scheme="smsto"/></intent>
        <intent><action android:name="android.intent.action.SENDTO"/>
            <data android:scheme="mailto"/></intent>
        <intent><action android:name="android.media.action.STILL_IMAGE_CAMERA"/></intent>
        <package android:name="com.whatsapp"/>
        <package android:name="com.google.android.youtube"/>
        <package android:name="com.instagram.android"/>
        <package android:name="com.facebook.katana"/>
        <package android:name="com.facebook.orca"/>
        <package android:name="org.telegram.messenger"/>
        <package android:name="com.zhiliaoapp.musically"/>
        <package android:name="com.spotify.music"/>
        <package android:name="com.android.chrome"/>
        <package android:name="com.google.android.gm"/>
        <package android:name="com.google.android.apps.maps"/>
        <package android:name="com.netflix.mediaclient"/>
        <package android:name="com.twitter.android"/>
        <package android:name="com.snapchat.android"/>
    </queries>

    <application
        android:name=".AriaApp"
        android:allowBackup="true"
        android:icon="@drawable/ic_aria"
        android:label="ARIA"
        android:roundIcon="@drawable/ic_aria"
        android:supportsRtl="true"
        android:theme="@style/Theme.Aria"
        android:usesCleartextTraffic="true">

        <activity android:name=".ui.SplashActivity" android:exported="true"
            android:theme="@style/Theme.Aria">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>

        <activity android:name=".ui.MainActivity" android:exported="false"
            android:theme="@style/Theme.Aria"/>

        <activity android:name=".ui.SettingsActivity" android:exported="false"/>
        <activity android:name=".ui.HistoryActivity" android:exported="false"/>

        <service android:name=".voice.WakeWordService"
            android:exported="false"
            android:foregroundServiceType="microphone"/>

        <receiver android:name=".voice.BootReceiver" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED"/>
                <action android:name="android.intent.action.QUICKBOOT_POWERON"/>
            </intent-filter>
        </receiver>

    </application>
</manifest>
"""

# ============================================================
#  KOTLIN SOURCE FILES
# ============================================================
ARIA_APP = r"""package com.aria.mobile

import android.app.Application
import androidx.multidex.MultiDex
import android.content.Context

class AriaApp : Application() {
    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(base)
        MultiDex.install(this)
    }

    override fun onCreate() {
        super.onCreate()
    }

    companion object {
        lateinit var instance: AriaApp
            private set
    }

    init {
        instance = this
    }
}
"""

APP_CONFIG = r"""package com.aria.mobile.core

object AppConfig {
    const val PREFS = "aria_prefs"
    const val PREF_API_KEY = "api_key"
    const val PREF_MODEL = "model_name"
    const val PREF_VOICE_ENABLED = "voice_enabled"
    const val PREF_MEMORY_ENABLED = "memory_enabled"
    const val PREF_ASSISTANT_NAME = "assistant_name"
    const val PREF_USER_NAME = "user_name"
    const val PREF_PERSONALITY = "personality"
    const val PREF_WAKE_ENABLED = "wake_enabled"
    const val PREF_WAKE_WORD = "wake_word"
    const val PREF_OFFLINE_MODE = "offline_mode"
    const val PREF_AI_MODE = "ai_mode"  // auto | online | offline
    const val PREF_ACTIONS_ENABLED = "actions_enabled"

    const val CREATOR = "MaikGost"
    const val VERSION = "9.1.0"

    const val COLOR_BG = 0xFF0A0E1A.toInt()
    const val COLOR_SURFACE = 0xFF121826.toInt()
    const val COLOR_PRIMARY = 0xFF7C4DFF.toInt()
    const val COLOR_PRIMARY_LIGHT = 0xFF9C6BFF.toInt()
    const val COLOR_ACCENT = 0xFF00E5FF.toInt()
    const val COLOR_TEXT = 0xFFE8F0FF.toInt()
    const val COLOR_TEXT_DIM = 0xFF5A7A99.toInt()
    const val COLOR_ERROR = 0xFFFF5252.toInt()

    const val DEFAULT_ASSISTANT_NAME = "ARIA"
    const val DEFAULT_PERSONALITY = "Amichevole"
    const val DEFAULT_WAKE_WORD = "maik"
    const val DEFAULT_AI_MODE = "auto"
    const val KNOWLEDGE_URL =
        "https://raw.githubusercontent.com/maikbarre2401-svg/gioco/claude/aria-mobile-android-builder-urk50v/knowledge_pack_it.json"
    const val DEFAULT_MODEL = "llama-3.3-70b-versatile"
    const val GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
}
"""

MESSAGE_ENTITY = r"""package com.aria.mobile.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val role: String,
    val content: String,
    val timestamp: Long = System.currentTimeMillis(),
    val sessionId: Long = 0L
)
"""

MESSAGE_DAO = r"""package com.aria.mobile.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface MessageDao {
    @Insert
    suspend fun insert(message: MessageEntity): Long

    @Query("SELECT * FROM messages ORDER BY timestamp ASC")
    fun getAllLive(): Flow<List<MessageEntity>>

    @Query("SELECT * FROM messages WHERE sessionId = :sid ORDER BY timestamp ASC")
    suspend fun getSession(sid: Long): List<MessageEntity>

    @Query("DELETE FROM messages")
    suspend fun clearAll()

    @Query("SELECT COUNT(*) FROM messages")
    suspend fun count(): Int
}
"""

ARIA_DATABASE = r"""package com.aria.mobile.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [MessageEntity::class], version = 1, exportSchema = false)
abstract class AriaDatabase : RoomDatabase() {
    abstract fun messageDao(): MessageDao

    companion object {
        @Volatile private var INSTANCE: AriaDatabase? = null

        fun getInstance(context: Context): AriaDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AriaDatabase::class.java,
                    "aria_db"
                ).fallbackToDestructiveMigration().build().also { INSTANCE = it }
            }
        }
    }
}
"""

GROQ_CLIENT = r"""package com.aria.mobile.net

import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class GroqClient(private val apiKey: String, private val model: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    interface ResultCallback {
        fun onResult(text: String)
        fun onError(message: String)
    }

    fun sendMessage(history: List<Pair<String, String>>, cb: ResultCallback) {
        try {
            val messagesArray = JSONArray()
            for ((role, content) in history) {
                val m = JSONObject()
                m.put("role", role)
                m.put("content", content)
                messagesArray.put(m)
            }
            val body = JSONObject()
            body.put("model", model)
            body.put("messages", messagesArray)
            body.put("temperature", 0.7)

            val mediaType = "application/json; charset=utf-8".toMediaType()
            val reqBody = body.toString().toRequestBody(mediaType)

            val req = Request.Builder()
                .url("https://api.groq.com/openai/v1/chat/completions")
                .addHeader("Authorization", "Bearer $apiKey")
                .addHeader("Content-Type", "application/json")
                .post(reqBody)
                .build()

            client.newCall(req).enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    cb.onError(e.message ?: "Errore di rete")
                }
                override fun onResponse(call: Call, response: Response) {
                    try {
                        val raw = response.body?.string() ?: ""
                        if (!response.isSuccessful) {
                            cb.onError("HTTP ${response.code}: $raw")
                            return
                        }
                        val json = JSONObject(raw)
                        val choices = json.getJSONArray("choices")
                        val text = choices.getJSONObject(0)
                            .getJSONObject("message").getString("content")
                        cb.onResult(text)
                    } catch (e: Exception) {
                        cb.onError("Parsing risposta: ${e.message}")
                    } finally {
                        response.close()
                    }
                }
            })
        } catch (e: Exception) {
            cb.onError("Errore invio: ${e.message}")
        }
    }

    /**
     * STREAMING (SSE): la risposta arriva parola per parola, come ChatGPT.
     * onToken riceve il testo accumulato ad ogni pezzo; onDone il testo
     * completo. Ritorna la Call per poter ANNULLARE la generazione.
     */
    fun sendMessageStream(
        history: List<Pair<String, String>>,
        onToken: (String) -> Unit,
        onDone: (String) -> Unit,
        onError: (String) -> Unit
    ): Call? {
        try {
            val messagesArray = JSONArray()
            for ((role, content) in history) {
                val m = JSONObject()
                m.put("role", role)
                m.put("content", content)
                messagesArray.put(m)
            }
            val body = JSONObject()
            body.put("model", model)
            body.put("messages", messagesArray)
            body.put("temperature", 0.7)
            body.put("stream", true)

            val mediaType = "application/json; charset=utf-8".toMediaType()
            val reqBody = body.toString().toRequestBody(mediaType)

            val req = Request.Builder()
                .url("https://api.groq.com/openai/v1/chat/completions")
                .addHeader("Authorization", "Bearer $apiKey")
                .addHeader("Content-Type", "application/json")
                .post(reqBody)
                .build()

            val call = client.newCall(req)
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    if (call.isCanceled()) onDone("") else onError(e.message ?: "Errore di rete")
                }
                override fun onResponse(call: Call, response: Response) {
                    val sb = StringBuilder()
                    try {
                        if (!response.isSuccessful) {
                            val raw = response.body?.string() ?: ""
                            onError("HTTP ${response.code}: $raw")
                            return
                        }
                        val source = response.body?.source()
                        if (source == null) { onError("Risposta vuota"); return }
                        while (true) {
                            val line = source.readUtf8Line() ?: break
                            if (!line.startsWith("data:")) continue
                            val payload = line.removePrefix("data:").trim()
                            if (payload == "[DONE]") break
                            try {
                                val delta = JSONObject(payload).getJSONArray("choices")
                                    .getJSONObject(0).optJSONObject("delta")
                                val piece = delta?.optString("content") ?: ""
                                if (piece.isNotEmpty()) {
                                    sb.append(piece)
                                    onToken(sb.toString())
                                }
                            } catch (_: Exception) {
                            }
                        }
                        onDone(sb.toString())
                    } catch (e: Exception) {
                        if (call.isCanceled()) onDone(sb.toString())
                        else onError("Streaming: ${e.message}")
                    } finally {
                        response.close()
                    }
                }
            })
            return call
        } catch (e: Exception) {
            onError("Errore invio: ${e.message}")
            return null
        }
    }
}
"""

ARIA_BRAIN = r"""package com.aria.mobile.core

import android.content.Context
import com.aria.mobile.data.AriaDatabase
import com.aria.mobile.data.MessageEntity
import com.aria.mobile.net.GroqClient
import kotlinx.coroutines.*
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class AriaBrain(private val context: Context) {

    private val prefs = context.getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
    private val db = AriaDatabase.getInstance(context)
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val offline = OfflineBrain(context)
    private var activeCall: okhttp3.Call? = null

    private fun buildSystemPrompt(): String {
        val assistantName = prefs.getString(AppConfig.PREF_ASSISTANT_NAME, AppConfig.DEFAULT_ASSISTANT_NAME)
            ?: AppConfig.DEFAULT_ASSISTANT_NAME
        val userName = prefs.getString(AppConfig.PREF_USER_NAME, "") ?: ""
        val personality = prefs.getString(AppConfig.PREF_PERSONALITY, AppConfig.DEFAULT_PERSONALITY)
            ?: AppConfig.DEFAULT_PERSONALITY
        val personalityDesc = when (personality) {
            "Professionale" -> "Mantieni un tono professionale, preciso e formale."
            "Divertente" -> "Sii spiritosa: usa humour e battute quando è appropriato."
            "Sarcastica" -> "Usa un tono ironico e sarcastico, ma mai offensivo."
            "Motivazionale" -> "Sii energica e motivazionale, incoraggia sempre l'utente."
            else -> "Sii calorosa e amichevole."
        }
        val nowStr = SimpleDateFormat("EEEE d MMMM yyyy, HH:mm", Locale.ITALIAN).format(Date())
        val sb = StringBuilder()
        sb.append("Sei $assistantName, un'assistente AI personale creata da ${AppConfig.CREATOR}. ")
        sb.append("Sei utile, diretta e concisa. $personalityDesc ")
        sb.append("Rispondi in italiano salvo richiesta diversa. ")
        sb.append("Per riferimento, data e ora attuali: $nowStr. ")
        sb.append("Puoi COMANDARE il telefono: quando l'utente chiede di aprire un'app, ")
        sb.append("cercare qualcosa, chiamare, mandare un messaggio, aprire le mappe, ")
        sb.append("impostare timer o sveglia, accendere la torcia o aprire la fotocamera, ")
        sb.append("aggiungi ALLA FINE della risposta un marcatore nel formato ")
        sb.append("[[DO:TIPO|arg1|arg2]] e scrivi anche una breve frase di conferma. ")
        sb.append("Tipi disponibili: OPEN_APP|nome, SEARCH|testo, WEB|url, YOUTUBE|testo, ")
        sb.append("CALL|numero, SMS|numero|testo, WHATSAPP|numero|testo, ")
        sb.append("EMAIL|indirizzo|oggetto|corpo, MAPS|luogo, TIMER|secondi, ")
        sb.append("ALARM|ora|minuti, TORCH|on, TORCH|off, CAMERA, SETTINGS, WIFI, BLUETOOTH. ")
        sb.append("Usa il marcatore SOLO quando l'utente chiede davvero un'azione sul telefono.")
        if (userName.isNotBlank()) {
            sb.append(" L'utente si chiama $userName: chiamalo per nome quando risulta naturale.")
        }
        return sb.toString()
    }

    /**
     * Groq resta SEMPRE il cervello principale quando c'e' la API key.
     * L'offline interviene solo: 1) per ora/data (l'AI non le conosce con
     * precisione); 2) se manca la key; 3) come fallback se Groq fallisce
     * (es. niente rete). Cosi' funziona sempre come prima, ma piu' robusto.
     */
    fun sendMessage(text: String, onResult: (String) -> Unit, onError: (String) -> Unit) {
        sendMessage(text, {}, onResult, onError)
    }

    /** Ferma la generazione in corso (pulsante Stop). */
    fun cancelStream() {
        try { activeCall?.cancel() } catch (_: Exception) {}
    }

    fun sendMessage(
        text: String,
        onPartial: (String) -> Unit,
        onResult: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        val apiKey = prefs.getString(AppConfig.PREF_API_KEY, "") ?: ""
        val model = prefs.getString(AppConfig.PREF_MODEL, AppConfig.DEFAULT_MODEL) ?: AppConfig.DEFAULT_MODEL
        val memoryEnabled = prefs.getBoolean(AppConfig.PREF_MEMORY_ENABLED, true)
        val aiMode = prefs.getString(AppConfig.PREF_AI_MODE, AppConfig.DEFAULT_AI_MODE)
            ?: AppConfig.DEFAULT_AI_MODE

        scope.launch {
            try {
                db.messageDao().insert(MessageEntity(role = "user", content = text))

                // 0) Modalita' SOLO OFFLINE scelta dall'utente
                if (aiMode == "offline") {
                    val local = offline.answer(text) ?: offline.offlineFallback()
                    db.messageDao().insert(MessageEntity(role = "assistant", content = local))
                    withContext(Dispatchers.Main) { onResult(local) }
                    return@launch
                }

                // 1) Ora/data sempre in locale: sono accurate, l'AI no.
                val realtime = offline.quickLocal(text)
                if (realtime != null) {
                    db.messageDao().insert(MessageEntity(role = "assistant", content = realtime))
                    withContext(Dispatchers.Main) { onResult(realtime) }
                    return@launch
                }

                // 2) Nessuna API key: prova il cervello offline.
                if (apiKey.isBlank()) {
                    val local = offline.answer(text)
                    if (local != null) {
                        db.messageDao().insert(MessageEntity(role = "assistant", content = local))
                        withContext(Dispatchers.Main) { onResult(local) }
                    } else {
                        withContext(Dispatchers.Main) {
                            onError("Aggiungi una API key Groq nelle Impostazioni (⚙️) per le risposte complete. Ora, data, calcoli e battute funzionano già senza.")
                        }
                    }
                    return@launch
                }

                // 3) Groq come sempre (cervello principale)
                val history = mutableListOf("system" to buildSystemPrompt())
                if (memoryEnabled) {
                    val past = db.messageDao().getSession(0L)
                    for (m in past.takeLast(24)) history.add(m.role to m.content)
                }
                history.add("user" to text)

                val client = GroqClient(apiKey, model)
                activeCall = client.sendMessageStream(
                    history,
                    onToken = { partial ->
                        scope.launch(Dispatchers.Main) { onPartial(partial) }
                    },
                    onDone = { full ->
                        scope.launch {
                            if (full.isBlank()) {
                                withContext(Dispatchers.Main) { onError("Generazione annullata") }
                            } else {
                                db.messageDao().insert(MessageEntity(role = "assistant", content = full))
                                withContext(Dispatchers.Main) { onResult(full) }
                            }
                        }
                    },
                    onError = { message ->
                        // fallback: se Groq non risponde (rete assente/errore),
                        // prova il cervello locale (solo in modalita' auto).
                        scope.launch {
                            val local = if (aiMode == "auto") offline.answer(text) else null
                            if (local != null) {
                                db.messageDao().insert(MessageEntity(role = "assistant", content = local))
                                withContext(Dispatchers.Main) { onResult(local) }
                            } else {
                                withContext(Dispatchers.Main) { onError(message) }
                            }
                        }
                    }
                )
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { onError("Errore interno: ${e.message}") }
            }
        }
    }

    fun clearHistory(onDone: () -> Unit) {
        scope.launch {
            db.messageDao().clearAll()
            withContext(Dispatchers.Main) { onDone() }
        }
    }
}
"""

CHAT_MESSAGE_MODEL = r"""package com.aria.mobile.ui

data class ChatMessage(
    val role: String,
    val content: String,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun isUser() = role == "user"
}
"""

ARIA_VIEWMODEL = r"""package com.aria.mobile.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.State
import com.aria.mobile.core.AriaBrain
import com.aria.mobile.core.AriaAction
import com.aria.mobile.core.PhoneActions
import com.aria.mobile.core.AppConfig
import com.aria.mobile.data.AriaDatabase
import kotlinx.coroutines.launch

class AriaViewModel(app: Application) : AndroidViewModel(app) {

    private val brain = AriaBrain(app.applicationContext)

    private val _messages = mutableStateOf<List<ChatMessage>>(emptyList())
    val messages: State<List<ChatMessage>> get() = _messages

    private val _isLoading = mutableStateOf(false)
    val isLoading: State<Boolean> get() = _isLoading

    private val _errorMessage = mutableStateOf<String?>(null)
    val errorMessage: State<String?> get() = _errorMessage

    private val _isStreaming = mutableStateOf(false)
    val isStreaming: State<Boolean> get() = _isStreaming

    var onAssistantResponse: ((String) -> Unit)? = null
    var onActions: ((List<AriaAction>) -> Unit)? = null

    init {
        // Ricarica la conversazione salvata all'avvio
        viewModelScope.launch {
            try {
                val past = AriaDatabase.getInstance(app.applicationContext)
                    .messageDao().getSession(0L)
                if (past.isNotEmpty()) {
                    _messages.value = past.map { ChatMessage(it.role, it.content, it.timestamp) }
                }
            } catch (_: Exception) {
            }
        }
    }

    fun sendMessage(text: String) {
        if (text.isBlank() || _isLoading.value || _isStreaming.value) return

        val prefs = getApplication<Application>()
            .getSharedPreferences(AppConfig.PREFS, android.content.Context.MODE_PRIVATE)
        val actionsEnabled = prefs.getBoolean(AppConfig.PREF_ACTIONS_ENABLED, true)

        // Comando naturale diretto (funziona anche offline, senza AI)
        if (actionsEnabled) {
            val nat = PhoneActions.parseNatural(text)
            if (nat != null) {
                _messages.value = _messages.value + ChatMessage("user", text)
                val conf = PhoneActions.describe(nat)
                _messages.value = _messages.value + ChatMessage("assistant", conf)
                onActions?.invoke(listOf(nat))
                onAssistantResponse?.invoke(conf)
                return
            }
        }

        _messages.value = _messages.value + ChatMessage("user", text)
        _isLoading.value = true
        _errorMessage.value = null

        brain.sendMessage(
            text = text,
            onPartial = { raw ->
                val partial = PhoneActions.stripForDisplay(raw)
                // streaming: il messaggio dell'assistente cresce in tempo reale
                if (!_isStreaming.value) {
                    _isStreaming.value = true
                    _isLoading.value = false
                    _messages.value = _messages.value + ChatMessage("assistant", partial)
                } else {
                    val list = _messages.value.toMutableList()
                    if (list.isNotEmpty() && list.last().role == "assistant") {
                        list[list.size - 1] = list.last().copy(content = partial)
                        _messages.value = list
                    }
                }
            },
            onResult = { response ->
                val (clean, actions) = PhoneActions.parseMarkers(response)
                val shown = clean.ifBlank { "Fatto." }
                val list = _messages.value.toMutableList()
                if (_isStreaming.value && list.isNotEmpty() && list.last().role == "assistant") {
                    list[list.size - 1] = list.last().copy(content = shown)
                    _messages.value = list
                } else {
                    _messages.value = list + ChatMessage("assistant", shown)
                }
                _isLoading.value = false
                _isStreaming.value = false
                if (actionsEnabled && actions.isNotEmpty()) onActions?.invoke(actions)
                onAssistantResponse?.invoke(shown)
            },
            onError = { error ->
                _errorMessage.value = error
                _isLoading.value = false
                _isStreaming.value = false
            }
        )
    }

    /** Ferma la generazione in corso. */
    fun stopGeneration() {
        brain.cancelStream()
    }

    fun dismissError() {
        _errorMessage.value = null
    }

    fun clearChat() {
        viewModelScope.launch {
            brain.clearHistory {
                _messages.value = emptyList()
            }
        }
    }
}
"""

PHONE_ACTIONS = r"""package com.aria.mobile.core

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.net.Uri
import android.provider.AlarmClock
import android.provider.MediaStore
import android.provider.Settings
import java.util.Locale

data class AriaAction(val type: String, val args: List<String>)

/**
 * Controllo del telefono: l'AI emette marcatori [[DO:TIPO|arg|arg]] che qui
 * vengono eseguiti come Intent Android. Funziona anche offline tramite
 * comandi naturali ("apri youtube", "chiama...", "torcia"...).
 *
 * Sicurezza: chiamate e messaggi NON vengono inviati di nascosto: apriamo
 * il telefono/WhatsApp/SMS con tutto pronto e sei TU a premere invia/chiama.
 */
object PhoneActions {

    private val knownApps = mapOf(
        "youtube" to "com.google.android.youtube",
        "whatsapp" to "com.whatsapp",
        "instagram" to "com.instagram.android",
        "facebook" to "com.facebook.katana",
        "messenger" to "com.facebook.orca",
        "telegram" to "org.telegram.messenger",
        "tiktok" to "com.zhiliaoapp.musically",
        "spotify" to "com.spotify.music",
        "chrome" to "com.android.chrome",
        "gmail" to "com.google.android.gm",
        "maps" to "com.google.android.apps.maps",
        "mappe" to "com.google.android.apps.maps",
        "netflix" to "com.netflix.mediaclient",
        "twitter" to "com.twitter.android",
        "snapchat" to "com.snapchat.android"
    )

    private val marker = Regex("\\[\\[DO:([^\\]]+)]]")

    fun parseMarkers(text: String): Pair<String, List<AriaAction>> {
        val actions = ArrayList<AriaAction>()
        for (m in marker.findAll(text)) {
            val parts = m.groupValues[1].split("|").map { it.trim() }
            if (parts.isNotEmpty() && parts[0].isNotBlank()) {
                actions.add(AriaAction(parts[0].uppercase(Locale.ROOT), parts.drop(1)))
            }
        }
        return stripForDisplay(text) to actions
    }

    fun stripForDisplay(text: String): String {
        var t = marker.replace(text, "")
        t = t.replace(Regex("\\[\\[DO:[^\\]]*$"), "")  // marcatore incompleto a fine stream
        return t.trim()
    }

    fun parseNatural(raw: String): AriaAction? {
        val t = raw.trim().lowercase(Locale.getDefault())
        fun after(vararg p: String): String? {
            for (x in p) if (t.startsWith(x)) return raw.trim().substring(x.length).trim()
            return null
        }
        after("cerca su google ", "cercami ", "cerca ")?.let { return AriaAction("SEARCH", listOf(it)) }
        after("cerca su youtube ", "su youtube ", "youtube ")?.let { return AriaAction("YOUTUBE", listOf(it)) }
        after("vai sul sito ", "apri il sito ", "vai su ")?.let { return AriaAction("WEB", listOf(it)) }
        after("chiama il numero ", "chiama ", "telefona a ", "telefona ")?.let { return AriaAction("CALL", listOf(it)) }
        after("naviga verso ", "portami a ", "indicazioni per ", "mappa di ", "dove si trova ")?.let { return AriaAction("MAPS", listOf(it)) }
        after("timer di ", "imposta un timer di ", "metti un timer di ")?.let { return AriaAction("TIMER", listOf(it)) }
        after("apri l'app ", "apri app ", "apri ")?.let { return AriaAction("OPEN_APP", listOf(it)) }
        if (t.contains("torcia") || t.contains("flash")) {
            val on = !(t.contains("spegni") || t.contains("spegnere"))
            return AriaAction("TORCH", listOf(if (on) "on" else "off"))
        }
        if (t.contains("fotocamera") || t.contains("scatta") || t.contains("apri la camera")) {
            return AriaAction("CAMERA", emptyList())
        }
        if (t.contains("impostazioni") && (t.startsWith("apri") || t.startsWith("vai"))) {
            return AriaAction("SETTINGS", emptyList())
        }
        return null
    }

    fun describe(a: AriaAction): String {
        val arg = a.args.getOrElse(0) { "" }
        return when (a.type) {
            "OPEN_APP" -> "Apro $arg."
            "SEARCH" -> "Cerco \"$arg\" su Google."
            "WEB" -> "Apro $arg."
            "YOUTUBE" -> "Cerco \"$arg\" su YouTube."
            "CALL" -> "Apro il telefono per chiamare $arg."
            "SMS" -> "Preparo un messaggio per $arg."
            "WHATSAPP" -> "Apro WhatsApp con il messaggio pronto."
            "EMAIL" -> "Preparo un'email."
            "MAPS" -> "Apro le mappe verso $arg."
            "TIMER" -> "Imposto il timer."
            "ALARM" -> "Imposto la sveglia."
            "TORCH" -> if (arg == "off") "Spengo la torcia." else "Accendo la torcia."
            "CAMERA" -> "Apro la fotocamera."
            "SETTINGS" -> "Apro le impostazioni."
            "WIFI" -> "Apro le impostazioni Wi-Fi."
            "BLUETOOTH" -> "Apro le impostazioni Bluetooth."
            else -> "Eseguo il comando."
        }
    }

    /** Esegue l'azione. Ritorna null se ok, altrimenti un messaggio d'errore. */
    fun execute(context: Context, a: AriaAction): String? {
        return try {
            when (a.type) {
                "OPEN_APP" -> openApp(context, a.args.getOrElse(0) { "" })
                "SEARCH" -> view(context, "https://www.google.com/search?q=" + Uri.encode(a.args.getOrElse(0) { "" }))
                "WEB" -> {
                    var u = a.args.getOrElse(0) { "" }.trim()
                    if (!u.startsWith("http")) u = "https://$u"
                    view(context, u)
                }
                "YOUTUBE" -> view(context, "https://www.youtube.com/results?search_query=" + Uri.encode(a.args.getOrElse(0) { "" }))
                "CALL" -> {
                    val num = a.args.getOrElse(0) { "" }.filter { it.isDigit() || it == '+' }
                    launch(context, Intent(Intent.ACTION_DIAL, Uri.parse("tel:$num")))
                }
                "SMS" -> {
                    val i = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + a.args.getOrElse(0) { "" }))
                    i.putExtra("sms_body", a.args.getOrElse(1) { "" })
                    launch(context, i)
                }
                "WHATSAPP" -> {
                    val num = a.args.getOrElse(0) { "" }.filter { it.isDigit() || it == '+' }.trimStart('+')
                    val body = Uri.encode(a.args.getOrElse(1) { "" })
                    val url = if (num.isBlank()) "https://wa.me/?text=$body" else "https://wa.me/$num?text=$body"
                    view(context, url)
                }
                "EMAIL" -> {
                    val i = Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + a.args.getOrElse(0) { "" }))
                    i.putExtra(Intent.EXTRA_SUBJECT, a.args.getOrElse(1) { "" })
                    i.putExtra(Intent.EXTRA_TEXT, a.args.getOrElse(2) { "" })
                    launch(context, i)
                }
                "MAPS" -> launch(context, Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + Uri.encode(a.args.getOrElse(0) { "" }))))
                "TIMER" -> launch(
                    context,
                    Intent(AlarmClock.ACTION_SET_TIMER)
                        .putExtra(AlarmClock.EXTRA_LENGTH, parseSeconds(a.args.getOrElse(0) { "" }))
                        .putExtra(AlarmClock.EXTRA_SKIP_UI, false)
                )
                "ALARM" -> launch(
                    context,
                    Intent(AlarmClock.ACTION_SET_ALARM)
                        .putExtra(AlarmClock.EXTRA_HOUR, a.args.getOrElse(0) { "0" }.toIntOrNull() ?: 0)
                        .putExtra(AlarmClock.EXTRA_MINUTES, a.args.getOrElse(1) { "0" }.toIntOrNull() ?: 0)
                )
                "TORCH" -> torch(context, a.args.getOrElse(0) { "on" } != "off")
                "CAMERA" -> launch(context, Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA))
                "SETTINGS" -> launch(context, Intent(Settings.ACTION_SETTINGS))
                "WIFI" -> launch(context, Intent(Settings.ACTION_WIFI_SETTINGS))
                "BLUETOOTH" -> launch(context, Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                else -> "Comando non riconosciuto: ${a.type}"
            }
        } catch (e: Exception) {
            "Non riesco a eseguire (${a.type}): ${e.message}"
        }
    }

    private fun openApp(context: Context, name: String): String? {
        val key = name.lowercase(Locale.getDefault()).trim()
        val pkg = knownApps.entries.firstOrNull { key.contains(it.key) }?.value
        if (pkg != null) {
            val i = context.packageManager.getLaunchIntentForPackage(pkg)
            if (i != null) {
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(i)
                return null
            }
        }
        return view(context, "https://www.google.com/search?q=" + Uri.encode(name))
    }

    private fun torch(context: Context, on: Boolean): String? {
        val cm = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val id = cm.cameraIdList.firstOrNull {
            cm.getCameraCharacteristics(it).get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
        } ?: return "Nessuna torcia disponibile"
        cm.setTorchMode(id, on)
        return null
    }

    private fun view(context: Context, url: String): String? =
        launch(context, Intent(Intent.ACTION_VIEW, Uri.parse(url)))

    private fun launch(context: Context, intent: Intent): String? {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return null
    }

    private fun parseSeconds(sRaw: String): Int {
        val digits = Regex("\\d+").find(sRaw)?.value?.toIntOrNull() ?: 1
        return when {
            sRaw.contains("minut") -> digits * 60
            sRaw.contains("or") -> digits * 3600
            else -> digits
        }
    }
}
"""

OFFLINE_BRAIN = r"""package com.aria.mobile.core

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.text.Normalizer
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import kotlin.random.Random

/**
 * Cervello OFFLINE: risponde senza internet a saluti, identita', ora,
 * data, calcoli matematici, testa o croce, dadi, numeri casuali e
 * battute. Se non sa rispondere restituisce null (cosi' AriaBrain puo'
 * decidere di usare l'AI online oppure il messaggio di fallback).
 */
class OfflineBrain(private val context: Context) {

    private val prefs = context.getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)

    private fun assistantName() =
        prefs.getString(AppConfig.PREF_ASSISTANT_NAME, AppConfig.DEFAULT_ASSISTANT_NAME)
            ?: AppConfig.DEFAULT_ASSISTANT_NAME

    // ---- PACCHETTO DI CONOSCENZA (scaricabile, resta sul telefono) ----
    private var packEntries: List<Pair<List<String>, String>> = emptyList()

    init {
        reloadPack()
    }

    fun reloadPack() {
        packEntries = try {
            val f = File(context.filesDir, "knowledge_pack.json")
            if (!f.exists()) emptyList()
            else {
                val json = JSONObject(f.readText())
                val arr = json.getJSONArray("entries")
                val list = ArrayList<Pair<List<String>, String>>()
                for (i in 0 until arr.length()) {
                    val e = arr.getJSONObject(i)
                    val ks = e.getJSONArray("k")
                    val keys = ArrayList<String>()
                    for (j in 0 until ks.length()) keys.add(normalizeTxt(ks.getString(j)))
                    list.add(keys to e.getString("a"))
                }
                list
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun packCount(): Int = packEntries.size

    private fun normalizeTxt(s: String): String {
        val d = Normalizer.normalize(s.lowercase(Locale.getDefault()), Normalizer.Form.NFD)
        val sb = StringBuilder()
        for (c in d) if (c in 'a'..'z' || c in '0'..'9' || c == ' ') sb.append(c)
        return sb.toString().trim()
    }

    /** Cerca nel pacchetto: vince la voce con piu' parole chiave presenti. */
    private fun packAnswer(t: String): String? {
        if (packEntries.isEmpty()) return null
        val norm = " " + normalizeTxt(t) + " "
        var best: String? = null
        var bestScore = 0
        for ((keys, ans) in packEntries) {
            if (keys.isEmpty()) continue
            var all = true
            for (k in keys) if (!norm.contains(k)) { all = false; break }
            if (all && keys.size > bestScore) {
                bestScore = keys.size
                best = ans
            }
        }
        return best
    }

    private val jokes = listOf(
        "Perche' gli scienziati non si fidano degli atomi? Perche' compongono tutto!",
        "Come si chiama un boomerang che non torna? Un bastone.",
        "Ho detto a mia moglie che era troppo tesa. Ora e' una molla.",
        "Qual e' il colmo per un elettricista? Non avere corrente... di pensiero!",
        "Cosa fa un pesce quando pensa? Sguazza tra le idee."
    )

    fun answer(raw: String): String? {
        val t = raw.lowercase(Locale.getDefault()).trim()
        if (t.isBlank()) return null
        return greeting(t) ?: identity(t) ?: dateTime(t) ?: games(t) ?: joke(t) ?: math(t) ?: packAnswer(t)
    }

    fun offlineFallback(): String =
        "Ora sono offline. Posso risponderti su ora, data, calcoli, testa o " +
        "croce, dadi e qualche battuta. Per il resto mi serve la connessione."

    /** Solo cose che l'AI non puo' sapere con precisione: ora, data, anno. */
    fun quickLocal(raw: String): String? {
        val t = raw.lowercase(Locale.getDefault()).trim()
        if (t.isBlank()) return null
        return dateTime(t)
    }

    private fun greeting(t: String): String? {
        val g = listOf("ciao", "salve", "buongiorno", "buonasera", "hey", "ehi")
        if (g.any { t == it || t.startsWith("$it ") } && t.length < 25) {
            return "Ciao! Come posso aiutarti?"
        }
        if (t.contains("come stai") || t.contains("come va")) {
            return "Alla grande, grazie! E tu come stai?"
        }
        if (t.contains("grazie")) return "Figurati, sempre qui per te!"
        return null
    }

    private fun identity(t: String): String? {
        if (t.contains("come ti chiami") || t.contains("chi sei") || t.contains("il tuo nome")) {
            return "Sono ${assistantName()}, il tuo assistente personale."
        }
        if (t.contains("chi ti ha creato") || t.contains("chi ti ha fatto") ||
            t.contains("tuo creatore") || t.contains("chi e' il tuo creatore")) {
            return "Mi ha creato ${AppConfig.CREATOR}."
        }
        return null
    }

    private fun dateTime(t: String): String? {
        val now = Calendar.getInstance().time
        if (t.contains("che ore") || t.contains("che ora")) {
            return "Sono le " + SimpleDateFormat("HH:mm", Locale.getDefault()).format(now)
        }
        if (t.contains("che giorno") || t.contains("che data") || t.contains("data di oggi")) {
            return "Oggi e' " + SimpleDateFormat("EEEE d MMMM yyyy", Locale.ITALIAN).format(now)
        }
        if (t.contains("che anno")) {
            return "Siamo nel " + SimpleDateFormat("yyyy", Locale.getDefault()).format(now)
        }
        return null
    }

    private fun games(t: String): String? {
        if (t.contains("testa o croce") || t.contains("lancia la moneta") ||
            t.contains("lancia una moneta") || t.contains("moneta")) {
            return if (Random.nextBoolean()) "E' uscito Testa!" else "E' uscito Croce!"
        }
        if (t.contains("tira un dado") || t.contains("lancia il dado") ||
            t.contains("un dado") || t.contains("il dado")) {
            return "Il dado dice: ${Random.nextInt(1, 7)}"
        }
        if (t.contains("numero casuale") || t.contains("numero a caso")) {
            return "Ecco: ${Random.nextInt(1, 101)}"
        }
        return null
    }

    private fun joke(t: String): String? {
        if (t.contains("barzelletta") || t.contains("battuta") ||
            t.contains("fammi ridere") || t.contains("una storiella")) {
            return jokes[Random.nextInt(jokes.size)]
        }
        return null
    }

    private fun math(t: String): String? {
        var expr = t
        for (k in listOf("quanto fa", "quanto e'", "quanto e", "calcolami", "calcola")) {
            val i = expr.indexOf(k)
            if (i >= 0) expr = expr.substring(i + k.length)
        }
        expr = expr.replace(",", ".")
            .replace(" per ", "*")
            .replace(" diviso ", "/")
            .replace(" piu' ", "+").replace(" piu ", "+").replace(" più ", "+")
            .replace(" meno ", "-")
            .replace("×", "*").replace("÷", "/")
        val sb = StringBuilder()
        for (c in expr) if (c.isDigit() || c in "+-*/().% ") sb.append(c)
        val clean = sb.toString().trim()
        if (clean.isEmpty() || !clean.any { it.isDigit() } || !clean.any { it in "+-*/%" }) return null
        val res = try { Evaluator(clean).parse() } catch (e: Exception) { null } ?: return null
        if (res.isNaN() || res.isInfinite()) return "Non posso dividere per zero."
        val out = if (res == res.toLong().toDouble()) res.toLong().toString()
        else String.format(Locale.ITALIAN, "%.2f", res)
        return "Fa $out"
    }

    /** Valutatore matematico ricorsivo: + - * / % parentesi, meno unario. */
    private class Evaluator(val s: String) {
        var pos = 0
        fun parse(): Double {
            val v = expr(); skipWs()
            if (pos < s.length) throw RuntimeException("resto non valido")
            return v
        }
        private fun skipWs() { while (pos < s.length && s[pos] == ' ') pos++ }
        private fun expr(): Double {
            var v = term()
            while (true) {
                skipWs()
                if (pos < s.length && (s[pos] == '+' || s[pos] == '-')) {
                    val op = s[pos]; pos++
                    val r = term()
                    v = if (op == '+') v + r else v - r
                } else break
            }
            return v
        }
        private fun term(): Double {
            var v = factor()
            while (true) {
                skipWs()
                if (pos < s.length && (s[pos] == '*' || s[pos] == '/' || s[pos] == '%')) {
                    val op = s[pos]; pos++
                    val r = factor()
                    v = when (op) { '*' -> v * r; '/' -> v / r; else -> v % r }
                } else break
            }
            return v
        }
        private fun factor(): Double {
            skipWs()
            if (pos < s.length && s[pos] == '+') { pos++; return factor() }
            if (pos < s.length && s[pos] == '-') { pos++; return -factor() }
            if (pos < s.length && s[pos] == '(') {
                pos++
                val v = expr()
                skipWs()
                if (pos < s.length && s[pos] == ')') pos++
                return v
            }
            return number()
        }
        private fun number(): Double {
            skipWs()
            val start = pos
            while (pos < s.length && (s[pos].isDigit() || s[pos] == '.')) pos++
            if (pos == start) throw RuntimeException("numero mancante")
            return s.substring(start, pos).toDouble()
        }
    }
}
"""

ARIA_ORB = r"""package com.aria.mobile.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalHapticFeedback
import com.aria.mobile.core.AppConfig
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** Stato d'animo della sfera: cambia colori, velocita', energia e reazioni. */
enum class OrbMood { IDLE, THINKING, SPEAKING, ERROR }

private class OrbPoint(val x: Float, val y: Float, val z: Float)

/** Punti distribuiti uniformemente su una sfera (spirale aurea). */
private fun sphericalPoints(n: Int): List<OrbPoint> {
    val golden = PI * (3.0 - sqrt(5.0))
    return List(n) { i ->
        val y = 1f - 2f * (i + 0.5f) / n
        val r = sqrt(1f - y * y)
        val theta = (golden * i).toFloat()
        OrbPoint(r * cos(theta), y, r * sin(theta))
    }
}

/** Reticolo a griglia (paralleli + meridiani) per il look "globo olografico". */
private fun wireframePoints(lat: Int, lon: Int, perLine: Int): List<OrbPoint> {
    val pts = ArrayList<OrbPoint>()
    // paralleli
    for (i in 1 until lat) {
        val phi = (PI * i / lat - PI / 2).toFloat()
        val cy = sin(phi); val rr = cos(phi)
        for (j in 0 until perLine) {
            val t = (2 * PI * j / perLine).toFloat()
            pts.add(OrbPoint(rr * cos(t), cy, rr * sin(t)))
        }
    }
    // meridiani
    for (i in 0 until lon) {
        val lonA = (2 * PI * i / lon).toFloat()
        val cl = cos(lonA); val sl = sin(lonA)
        for (j in 0 until perLine) {
            val t = (PI * j / (perLine - 1) - PI / 2).toFloat()
            val rr = cos(t)
            pts.add(OrbPoint(rr * cl, sin(t), rr * sl))
        }
    }
    return pts
}

/**
 * Sfera 3D "viva" iper-tridimensionale (stile Jarvis, ma piu' avanzata):
 *  - nucleo che respira con bagliore radiale pulsante
 *  - guscio interno di particelle + guscio esterno controrotante (parallasse)
 *  - reticolo olografico a griglia che ruota
 *  - 3 anelli orbitali inclinati con elettroni luminosi e scia
 *  - onde sonore che si espandono quando parla
 *  - fog di profondita': i punti dietro sfumano nel fondo, quelli davanti
 *    sono grandi e brillanti
 *  - fluttua e ondeggia su piu' assi; reagisce allo stato dell'AI
 *  - vibra al tocco.
 */
@Composable
fun AriaOrb3D(
    mood: OrbMood,
    modifier: Modifier = Modifier,
    onTap: () -> Unit = {}
) {
    val haptic = LocalHapticFeedback.current
    val shellInner = remember { sphericalPoints(190) }
    val shellOuter = remember { sphericalPoints(90) }
    val grid = remember { wireframePoints(6, 8, 26) }

    var angle by remember { mutableStateOf(0f) }
    var time by remember { mutableStateOf(0f) }

    val speed by animateFloatAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> 22f
            OrbMood.THINKING -> 120f
            OrbMood.SPEAKING -> 34f
            OrbMood.ERROR -> 12f
        },
        animationSpec = tween(700), label = "orbSpeed"
    )
    val energy by animateFloatAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> 0.32f
            OrbMood.THINKING -> 1f
            OrbMood.SPEAKING -> 0.82f
            OrbMood.ERROR -> 0.5f
        },
        animationSpec = tween(600), label = "orbEnergy"
    )
    val glow by animateFloatAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> 0.55f
            OrbMood.THINKING -> 1f
            OrbMood.SPEAKING -> 0.95f
            OrbMood.ERROR -> 0.7f
        },
        animationSpec = tween(600), label = "orbGlow"
    )
    val mainColor by animateColorAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> Color(AppConfig.COLOR_ACCENT)
            OrbMood.THINKING -> Color(AppConfig.COLOR_PRIMARY_LIGHT)
            OrbMood.SPEAKING -> Color(0xFF00FFB3)
            OrbMood.ERROR -> Color(AppConfig.COLOR_ERROR)
        },
        animationSpec = tween(600), label = "orbColor"
    )
    val ringColor by animateColorAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> Color(AppConfig.COLOR_PRIMARY)
            OrbMood.THINKING -> Color(AppConfig.COLOR_ACCENT)
            OrbMood.SPEAKING -> Color(AppConfig.COLOR_ACCENT)
            OrbMood.ERROR -> Color(0xFFFF8A80)
        },
        animationSpec = tween(600), label = "orbRing"
    )
    val fog = Color(0xFF0A0E1A)

    // motore animazione: avanza in base alla velocita' corrente (fluida)
    LaunchedEffect(Unit) {
        var last = 0L
        while (true) {
            withFrameNanos { now ->
                if (last != 0L) {
                    val dt = (now - last) / 1_000_000_000f
                    angle = (angle + dt * speed) % 360f
                    time += dt
                }
                last = now
            }
        }
    }

    Canvas(
        modifier = modifier.pointerInput(Unit) {
            detectTapGestures(onTap = {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                onTap()
            })
        }
    ) {
        val cx = size.width / 2f
        val cy = size.height / 2f + sin(time * 0.9f) * size.height * 0.028f
        val breathe = 1f + (0.028f + energy * 0.03f) * sin(time * 1.6f)
        val r = size.minDimension * 0.30f * breathe
        val focal = r * 2.9f

        val aY = angle * PI.toFloat() / 180f
        val ca = cos(aY); val sa = sin(aY)
        // guscio esterno: controrotante e piu' lento -> parallasse
        val aY2 = -aY * 0.55f
        val ca2 = cos(aY2); val sa2 = sin(aY2)
        val tiltX = 0.42f + 0.08f * sin(time * 0.4f)
        val ct = cos(tiltX); val st = sin(tiltX)
        val wobZ = 0.06f * sin(time * 0.5f)
        val cw = cos(wobZ); val sw = sin(wobZ)

        // proietta un punto della sfera (raggio rad) con rotazione data
        fun project(px0: Float, py0: Float, pz0: Float, rad: Float,
                    cA: Float, sA: Float): FloatArray {
            val rx = px0 * cA + pz0 * sA
            val rz = -px0 * sA + pz0 * cA
            val ry = py0 * ct - rz * st
            val rz2 = py0 * st + rz * ct
            val fx = rx * cw - ry * sw
            val fy = rx * sw + ry * cw
            val persp = focal / (focal + rz2 * rad)
            val sx = cx + fx * rad * persp
            val sy = cy + fy * rad * persp
            val depth = (1f - rz2) / 2f   // 1 = davanti, 0 = dietro
            return floatArrayOf(sx, sy, depth, persp)
        }

        // ---- ombra a terra (radica la sfera nello spazio 3D) ----
        val floatPhase = sin(time * 0.9f)
        drawOval(
            color = Color.Black,
            topLeft = Offset(cx - r * 0.8f, size.height - r * 0.40f),
            size = Size(r * 1.6f, r * 0.26f),
            alpha = ((0.20f - 0.05f * floatPhase) * (0.5f + glow * 0.5f)).coerceIn(0f, 1f)
        )

        // ---- aura esterna pulsante ----
        for (k in 5 downTo 1) {
            drawCircle(
                color = mainColor,
                radius = r * (1f + k * 0.20f) * (1f + energy * 0.05f * sin(time * 1.8f)),
                center = Offset(cx, cy),
                alpha = (glow * 0.13f / k).coerceIn(0f, 1f)
            )
        }

        // ---- onde sonore quando parla ----
        if (mood == OrbMood.SPEAKING) {
            for (k in 0 until 3) {
                val phase = ((time * 0.55f) + k / 3f) % 1f
                drawCircle(
                    color = mainColor,
                    radius = r * (1f + phase * 1.4f),
                    center = Offset(cx, cy),
                    alpha = ((1f - phase) * 0.35f * glow).coerceIn(0f, 1f),
                    style = Stroke(width = 2.5f)
                )
            }
        }

        // ---- guscio interno: 3D VERO con luce (lambert) e profondita' ----
        // sorgente di luce in alto a sinistra, verso l'osservatore
        val lx = -0.5f
        val ly = -0.55f
        val lz = -0.67f
        val innerList = ArrayList<FloatArray>(shellInner.size)
        for ((i, pt) in shellInner.withIndex()) {
            val jitter = 1f + energy * 0.03f * sin(time * 3.2f + i)
            val rx = pt.x * ca + pt.z * sa
            val rz = -pt.x * sa + pt.z * ca
            val ry = pt.y * ct - rz * st
            val rz2 = pt.y * st + rz * ct
            val fx = rx * cw - ry * sw
            val fy = rx * sw + ry * cw
            val rad = r * jitter
            val persp = focal / (focal + rz2 * rad)
            val px = cx + fx * rad * persp
            val py = cy + fy * rad * persp
            // illuminazione lambertiana: il lato verso la luce brilla
            val lam = (fx * lx + fy * ly + rz2 * lz).coerceAtLeast(0f)
            innerList.add(floatArrayOf(px, py, rz2, persp, lam, (i % 4).toFloat()))
        }
        // ordinamento per profondita': dietro prima, davanti dopo (3D corretto)
        innerList.sortByDescending { it[2] }

        fun drawInner(p: FloatArray) {
            val depth = (1f - p[2]) / 2f
            val base = if (p[5] == 0f) ringColor else mainColor
            val lit = lerp(base, Color.White, p[4] * 0.55f)
            val col = lerp(fog, lit, (0.18f + depth * 0.82f))
            drawCircle(
                color = col,
                radius = (1.0f + 2.0f * depth) * p[3] * (1f + p[4] * 0.35f),
                center = Offset(p[0], p[1]),
                alpha = ((0.1f + 0.9f * depth) * (0.35f + glow * 0.65f)).coerceIn(0f, 1f)
            )
        }

        // meta' POSTERIORE della sfera (dietro il nucleo)
        for (p in innerList) if (p[2] > 0f) drawInner(p)

        // ---- nucleo luminoso che respira ----
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    Color.White.copy(alpha = (0.9f * glow).coerceIn(0f, 1f)),
                    mainColor.copy(alpha = (0.5f * glow).coerceIn(0f, 1f)),
                    Color.Transparent
                ),
                center = Offset(cx, cy),
                radius = r * (0.75f + energy * 0.12f)
            ),
            radius = r * (0.75f + energy * 0.12f),
            center = Offset(cx, cy)
        )

        // ---- reticolo olografico (griglia) ----
        for (g in grid) {
            val p = project(g.x, g.y, g.z, r * 1.02f, ca, sa)
            val depth = p[2]
            val col = lerp(fog, ringColor, (0.25f + depth * 0.75f))
            drawCircle(
                color = col,
                radius = (0.6f + 1.1f * depth) * p[3],
                center = Offset(p[0], p[1]),
                alpha = ((0.05f + 0.30f * depth) * glow).coerceIn(0f, 1f)
            )
        }

        // ---- guscio esterno di particelle (controrotante) ----
        for ((i, pt) in shellOuter.withIndex()) {
            val p = project(pt.x, pt.y, pt.z, r * 1.16f, ca2, sa2)
            val depth = p[2]
            val col = lerp(fog, ringColor, (0.2f + depth * 0.8f))
            drawCircle(
                color = col,
                radius = (0.8f + 1.4f * depth) * p[3],
                center = Offset(p[0], p[1]),
                alpha = ((0.06f + 0.55f * depth) * (0.4f + glow * 0.6f)).coerceIn(0f, 1f)
            )
        }

        // ---- meta' ANTERIORE della sfera (davanti al nucleo, illuminata) ----
        for (p in innerList) if (p[2] <= 0f) drawInner(p)

        // ---- anelli orbitali 3D con elettroni e scia ----
        val rings = listOf(
            Triple(1.34f, 0.95f, 1.7f),
            Triple(1.55f, -0.6f, -1.15f),
            Triple(1.80f, 0.28f, 0.72f)
        )
        for ((ri, ring) in rings.withIndex()) {
            val (rr, tilt, speedFactor) = ring
            val ringR = r * rr
            val rc = cos(tilt); val rs = sin(tilt)
            val ph = aY * speedFactor
            val cph = cos(ph); val sph = sin(ph)

            fun ringPoint(aRad: Float): FloatArray {
                val x0 = cos(aRad) * ringR
                val z0 = sin(aRad) * ringR
                val y1 = -z0 * rs
                val z1 = z0 * rc
                val xr = x0 * cph + z1 * sph
                val zr = -x0 * sph + z1 * cph
                val y2 = y1 * ct - zr * st
                val z2 = y1 * st + zr * ct
                val fx = xr * cw - y2 * sw
                val fy = xr * sw + y2 * cw
                val persp = focal / (focal + z2)
                val depth = ((1f - z2 / ringR) / 2f).coerceIn(0f, 1f)
                return floatArrayOf(cx + fx * persp, cy + fy * persp, depth)
            }

            val steps = 70
            for (sIdx in 0 until steps) {
                val p = ringPoint(2f * PI.toFloat() * sIdx / steps)
                val depth = p[2]
                drawCircle(
                    color = lerp(fog, ringColor, (0.2f + depth * 0.8f)),
                    radius = 0.7f + 1.6f * depth,
                    center = Offset(p[0], p[1]),
                    alpha = ((0.06f + 0.45f * depth) * glow).coerceIn(0f, 1f)
                )
            }

            // scia + elettrone luminoso
            val dir = if (speedFactor < 0f) -1f else 1f
            val headAng = time * (1.2f + ri * 0.7f) * dir
            for (t in 0 until 7) {
                val pe = ringPoint(headAng - t * 0.12f * dir)
                val fade = (1f - t / 7f)
                drawCircle(
                    color = mainColor,
                    radius = (2.0f + 2.5f * pe[2]) * fade,
                    center = Offset(pe[0], pe[1]),
                    alpha = (0.25f * fade * glow).coerceIn(0f, 1f)
                )
            }
            val head = ringPoint(headAng)
            drawCircle(
                color = mainColor,
                radius = 5.5f + 3f * head[2],
                center = Offset(head[0], head[1]),
                alpha = (0.3f * glow).coerceIn(0f, 1f)
            )
            drawCircle(
                color = Color.White,
                radius = 2.9f + 1.9f * head[2],
                center = Offset(head[0], head[1]),
                alpha = (0.95f * glow).coerceIn(0f, 1f)
            )
        }
    }
}
"""

SPLASH_ACTIVITY = r"""package com.aria.mobile.ui

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aria.mobile.core.AppConfig
import kotlinx.coroutines.delay
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

class SplashActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AriaTheme {
                SplashScreen(
                    onFinished = {
                        startActivity(Intent(this@SplashActivity, MainActivity::class.java))
                        finish()
                    }
                )
            }
        }
    }
}

private class Star3D(val x: Float, val y: Float, val z: Float, val big: Boolean)

@Composable
fun SplashScreen(onFinished: () -> Unit) {
    // Punti distribuiti uniformemente su una sfera (spirale aurea)
    val stars = remember {
        val n = 220
        val golden = PI * (3.0 - sqrt(5.0))
        List(n) { i ->
            val y = 1f - 2f * (i + 0.5f) / n
            val r = sqrt(1f - y * y)
            val theta = (golden * i).toFloat()
            Star3D(r * cos(theta), y, r * sin(theta), i % 7 == 0)
        }
    }

    val transition = rememberInfiniteTransition(label = "splash")
    val rotation by transition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(9000, easing = LinearEasing)),
        label = "rotation"
    )
    val pulse by transition.animateFloat(
        initialValue = 0.94f, targetValue = 1.06f,
        animationSpec = infiniteRepeatable(tween(900), RepeatMode.Reverse),
        label = "pulse"
    )

    var entered by remember { mutableStateOf(false) }
    val fade by animateFloatAsState(
        targetValue = if (entered) 1f else 0f,
        animationSpec = tween(1400),
        label = "fade"
    )
    LaunchedEffect(Unit) {
        entered = true
        delay(3200)
        onFinished()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(Color(0xFF05070F), Color(AppConfig.COLOR_BG), Color(0xFF141034))
                )
            ),
        contentAlignment = Alignment.Center
    ) {
        // Sfera 3D di particelle: rotazione attorno all'asse Y + inclinazione,
        // proiezione prospettica reale (i punti vicini sono grandi e luminosi)
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cx = size.width / 2f
            val cy = size.height / 2f
            val sphereR = size.minDimension * 0.34f
            val focal = sphereR * 2.6f
            val angle = rotation * PI.toFloat() / 180f
            val ca = cos(angle)
            val sa = sin(angle)
            val tilt = 0.35f
            val ct = cos(tilt)
            val st = sin(tilt)

            for ((i, s) in stars.withIndex()) {
                // rotazione attorno a Y
                val rx = s.x * ca + s.z * sa
                val rz = -s.x * sa + s.z * ca
                // inclinazione attorno a X
                val ry = s.y * ct - rz * st
                val rz2 = s.y * st + rz * ct
                // proiezione prospettica
                val persp = focal / (focal + rz2 * sphereR)
                val px = cx + rx * sphereR * persp
                val py = cy + ry * sphereR * persp
                val depth = (1f - rz2) / 2f  // 1 = davanti, 0 = dietro
                val alpha = ((0.15f + depth * 0.85f) * fade).coerceIn(0f, 1f)
                val radius = (if (s.big) 4.2f else 2.2f) * persp
                val color = if (i % 3 == 0) Color(AppConfig.COLOR_ACCENT) else Color(AppConfig.COLOR_PRIMARY)
                drawCircle(color = color, radius = radius, center = Offset(px, py), alpha = alpha)
            }

            drawCircle(
                color = Color(AppConfig.COLOR_ACCENT),
                radius = sphereR * 1.18f,
                center = Offset(cx, cy),
                alpha = 0.12f * fade,
                style = Stroke(width = 2f)
            )
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.graphicsLayer(alpha = fade)
        ) {
            Text(
                text = "ARIA",
                fontSize = 62.sp,
                fontWeight = FontWeight.Black,
                letterSpacing = 14.sp,
                color = Color(AppConfig.COLOR_ACCENT),
                modifier = Modifier.graphicsLayer(scaleX = pulse, scaleY = pulse)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Il tuo assistente AI personale",
                fontSize = 14.sp,
                color = Color(AppConfig.COLOR_TEXT)
            )
            Spacer(modifier = Modifier.height(150.dp))
            Text(
                text = "Creator: ${AppConfig.CREATOR}",
                fontSize = 17.sp,
                fontWeight = FontWeight.Bold,
                color = Color(AppConfig.COLOR_PRIMARY_LIGHT)
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "v${AppConfig.VERSION}",
                fontSize = 12.sp,
                color = Color(AppConfig.COLOR_TEXT_DIM)
            )
        }
    }
}
"""

MAIN_ACTIVITY = r"""package com.aria.mobile.ui

import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.StartOffset
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aria.mobile.core.AppConfig
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {

    private val viewModel: AriaViewModel by viewModels()
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private val assistantName = mutableStateOf(AppConfig.DEFAULT_ASSISTANT_NAME)
    private val voiceEnabled = mutableStateOf(true)
    private val speaking = mutableStateOf(false)
    private val aiModeLabel = mutableStateOf("AI auto")
    private val hasApiKey = mutableStateOf(false)

    private val speechLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val spoken = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
            if (!spoken.isNullOrBlank()) viewModel.sendMessage(spoken)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val res = tts?.setLanguage(Locale.ITALIAN) ?: TextToSpeech.LANG_MISSING_DATA
                if (res == TextToSpeech.LANG_MISSING_DATA || res == TextToSpeech.LANG_NOT_SUPPORTED) {
                    // niente voce italiana installata: usa la lingua di sistema
                    tts?.language = Locale.getDefault()
                }
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        runOnUiThread { speaking.value = true }
                    }
                    override fun onDone(utteranceId: String?) {
                        runOnUiThread { speaking.value = false }
                    }
                    @Deprecated("deprecated in API level 21")
                    override fun onError(utteranceId: String?) {
                        runOnUiThread { speaking.value = false }
                    }
                    override fun onError(utteranceId: String?, errorCode: Int) {
                        runOnUiThread { speaking.value = false }
                    }
                })
                ttsReady = true
            } else {
                runOnUiThread {
                    Toast.makeText(
                        this,
                        "Sintesi vocale non disponibile: installa 'Sintesi vocale Google' dal Play Store",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
        viewModel.onActions = { actions ->
            for (a in actions) {
                val err = com.aria.mobile.core.PhoneActions.execute(this, a)
                if (err != null) {
                    Toast.makeText(this, err, Toast.LENGTH_LONG).show()
                }
            }
        }
        viewModel.onAssistantResponse = { text ->
            if (voiceEnabled.value) speak(text)
        }

        setContent {
            AriaTheme {
                ChatScreen(
                    viewModel = viewModel,
                    assistantName = assistantName.value,
                    voiceEnabled = voiceEnabled.value,
                    speaking = speaking.value,
                    aiModeLabel = aiModeLabel.value,
                    hasApiKey = hasApiKey.value,
                    onToggleVoice = { toggleVoice() },
                    onVoiceInput = { startVoiceInput() },
                    onSpeak = { speak(it) },
                    onShareChat = { shareConversation() },
                    onOpenSettings = {
                        startActivity(Intent(this, SettingsActivity::class.java))
                    },
                    onOpenHistory = {
                        startActivity(Intent(this, HistoryActivity::class.java))
                    }
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        val prefs = getSharedPreferences(AppConfig.PREFS, MODE_PRIVATE)
        assistantName.value = prefs.getString(
            AppConfig.PREF_ASSISTANT_NAME, AppConfig.DEFAULT_ASSISTANT_NAME
        ) ?: AppConfig.DEFAULT_ASSISTANT_NAME
        voiceEnabled.value = prefs.getBoolean(AppConfig.PREF_VOICE_ENABLED, true)
        aiModeLabel.value = when (prefs.getString(AppConfig.PREF_AI_MODE, AppConfig.DEFAULT_AI_MODE)) {
            "online" -> "solo online"
            "offline" -> "solo offline"
            else -> "AI auto"
        }
        hasApiKey.value = !prefs.getString(AppConfig.PREF_API_KEY, "").isNullOrBlank()
    }

    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        super.onDestroy()
    }

    private fun speak(text: String) {
        if (!ttsReady) {
            Toast.makeText(this, "Voce in preparazione, riprova tra un attimo", Toast.LENGTH_SHORT).show()
            return
        }
        // toglie i simboli markdown per una lettura naturale
        val clean = text.replace(Regex("[*_#`~\\[\\]>]"), " ")
        tts?.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "aria_tts")
    }

    private fun toggleVoice() {
        val enabled = !voiceEnabled.value
        voiceEnabled.value = enabled
        getSharedPreferences(AppConfig.PREFS, MODE_PRIVATE).edit()
            .putBoolean(AppConfig.PREF_VOICE_ENABLED, enabled)
            .apply()
        if (!enabled) {
            tts?.stop()
            speaking.value = false
        }
        Toast.makeText(
            this,
            if (enabled) "Voce attivata" else "Voce disattivata",
            Toast.LENGTH_SHORT
        ).show()
    }

    private fun shareConversation() {
        val msgs = viewModel.messages.value
        if (msgs.isEmpty()) {
            Toast.makeText(this, "Nessun messaggio da condividere", Toast.LENGTH_SHORT).show()
            return
        }
        val name = assistantName.value
        val text = msgs.joinToString("\n\n") {
            (if (it.isUser()) "Io: " else "$name: ") + it.content
        }
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        startActivity(Intent.createChooser(intent, "Condividi conversazione"))
    }

    private fun startVoiceInput() {
        // ferma la voce dell'AI cosi' non parla sopra di te
        tts?.stop()
        speaking.value = false
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Parla ora...")
            val preferOffline = getSharedPreferences(AppConfig.PREFS, MODE_PRIVATE)
                .getBoolean(AppConfig.PREF_OFFLINE_MODE, false)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, preferOffline)
        }
        try {
            speechLauncher.launch(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "Riconoscimento vocale non disponibile", Toast.LENGTH_SHORT).show()
        }
    }
}

@Composable
fun AriaTheme(content: @Composable () -> Unit) {
    val colors = darkColorScheme(
        primary = Color(AppConfig.COLOR_PRIMARY),
        secondary = Color(AppConfig.COLOR_ACCENT),
        background = Color(AppConfig.COLOR_BG),
        surface = Color(AppConfig.COLOR_SURFACE),
        onBackground = Color(AppConfig.COLOR_TEXT),
        onSurface = Color(AppConfig.COLOR_TEXT)
    )
    MaterialTheme(colorScheme = colors, content = content)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    viewModel: AriaViewModel,
    assistantName: String,
    voiceEnabled: Boolean,
    speaking: Boolean,
    aiModeLabel: String,
    hasApiKey: Boolean,
    onToggleVoice: () -> Unit,
    onVoiceInput: () -> Unit,
    onSpeak: (String) -> Unit,
    onShareChat: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenHistory: () -> Unit
) {
    var input by remember { mutableStateOf("") }
    var showClearDialog by remember { mutableStateOf(false) }
    var showTools by remember { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    val messages = viewModel.messages.value
    val isLoading = viewModel.isLoading.value
    val isStreaming = viewModel.isStreaming.value
    val error = viewModel.errorMessage.value
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    val orbMood = when {
        error != null -> OrbMood.ERROR
        isLoading || isStreaming -> OrbMood.THINKING
        speaking -> OrbMood.SPEAKING
        else -> OrbMood.IDLE
    }

    LaunchedEffect(messages.size, isLoading, messages.lastOrNull()?.content?.length ?: 0) {
        if (messages.isNotEmpty()) {
            scope.launch { listState.animateScrollToItem(messages.size - 1) }
        }
    }

    if (showClearDialog) {
        AlertDialog(
            onDismissRequest = { showClearDialog = false },
            containerColor = Color(AppConfig.COLOR_SURFACE),
            title = { Text("Svuotare la chat?", color = Color(AppConfig.COLOR_TEXT)) },
            text = {
                Text(
                    "Tutti i messaggi e la memoria di $assistantName verranno cancellati.",
                    color = Color(AppConfig.COLOR_TEXT_DIM)
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.clearChat()
                    showClearDialog = false
                }) { Text("Svuota", color = Color(AppConfig.COLOR_ERROR)) }
            },
            dismissButton = {
                TextButton(onClick = { showClearDialog = false }) {
                    Text("Annulla", color = Color(AppConfig.COLOR_ACCENT))
                }
            }
        )
    }

    if (showTools) {
        ModalBottomSheet(
            onDismissRequest = { showTools = false },
            containerColor = Color(AppConfig.COLOR_SURFACE)
        ) {
            ToolsSheetContent(onTool = { tool ->
                showTools = false
                if (tool.sendDirectly) {
                    viewModel.sendMessage(tool.prompt)
                } else {
                    input = tool.prompt
                }
            })
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(10.dp)
                                .background(Color(AppConfig.COLOR_ACCENT), CircleShape)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                assistantName,
                                color = Color(AppConfig.COLOR_ACCENT),
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                "by ${AppConfig.CREATOR} • $aiModeLabel",
                                color = Color(AppConfig.COLOR_TEXT_DIM),
                                fontSize = 10.sp
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = onToggleVoice) {
                        Icon(
                            if (voiceEnabled) Icons.AutoMirrored.Filled.VolumeUp
                            else Icons.AutoMirrored.Filled.VolumeOff,
                            contentDescription = "Voce on/off",
                            tint = if (voiceEnabled) Color(AppConfig.COLOR_ACCENT)
                            else Color(AppConfig.COLOR_TEXT_DIM)
                        )
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(
                            Icons.Filled.Settings,
                            contentDescription = "Impostazioni",
                            tint = Color(AppConfig.COLOR_ACCENT)
                        )
                    }
                    Box {
                        IconButton(onClick = { menuOpen = true }) {
                            Icon(
                                Icons.Filled.MoreVert,
                                contentDescription = "Menu",
                                tint = Color(AppConfig.COLOR_TEXT_DIM)
                            )
                        }
                        DropdownMenu(
                            expanded = menuOpen,
                            onDismissRequest = { menuOpen = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("Cronologia", color = Color(AppConfig.COLOR_TEXT)) },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.History,
                                        contentDescription = null,
                                        tint = Color(AppConfig.COLOR_TEXT_DIM)
                                    )
                                },
                                onClick = {
                                    menuOpen = false
                                    onOpenHistory()
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Condividi chat", color = Color(AppConfig.COLOR_TEXT)) },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.Share,
                                        contentDescription = null,
                                        tint = Color(AppConfig.COLOR_TEXT_DIM)
                                    )
                                },
                                onClick = {
                                    menuOpen = false
                                    onShareChat()
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Svuota chat", color = Color(AppConfig.COLOR_ERROR)) },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.DeleteSweep,
                                        contentDescription = null,
                                        tint = Color(AppConfig.COLOR_ERROR)
                                    )
                                },
                                onClick = {
                                    menuOpen = false
                                    showClearDialog = true
                                }
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(AppConfig.COLOR_SURFACE)
                )
            )
        },
        containerColor = Color(AppConfig.COLOR_BG)
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(
                    Brush.verticalGradient(
                        listOf(Color(AppConfig.COLOR_BG), Color(0xFF0D1226), Color(0xFF10142A))
                    )
                )
        ) {
            // Sfera 3D viva che fluttua e reagisce all'AI. Toccala per parlare.
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(150.dp),
                contentAlignment = Alignment.Center
            ) {
                AriaOrb3D(
                    mood = orbMood,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(150.dp),
                    onTap = onVoiceInput
                )
                Text(
                    text = when (orbMood) {
                        OrbMood.THINKING -> if (isStreaming) "sto scrivendo..." else "sto pensando..."
                        OrbMood.SPEAKING -> "sto parlando..."
                        OrbMood.ERROR -> "qualcosa è andato storto"
                        OrbMood.IDLE -> "tocca la sfera per parlarmi"
                    },
                    fontSize = 11.sp,
                    color = Color(AppConfig.COLOR_TEXT_DIM),
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(bottom = 2.dp)
                )
            }
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                if (messages.isEmpty() && !isLoading) {
                    item {
                        WelcomeCard(assistantName, hasApiKey, onOpenSettings) {
                            viewModel.sendMessage(it)
                        }
                    }
                }
                items(messages) { msg ->
                    MessageBubble(msg, assistantName, onSpeak)
                }
                if (isLoading) {
                    item { TypingIndicator(assistantName) }
                }
                if (error != null) {
                    item {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(
                                    Color(AppConfig.COLOR_ERROR).copy(alpha = 0.12f),
                                    RoundedCornerShape(12.dp)
                                )
                                .clickable { viewModel.dismissError() }
                                .padding(12.dp)
                        ) {
                            Text(
                                "Errore: $error",
                                color = Color(AppConfig.COLOR_ERROR),
                                fontSize = 13.sp
                            )
                            Text(
                                "Tocca per chiudere",
                                color = Color(AppConfig.COLOR_TEXT_DIM),
                                fontSize = 10.sp
                            )
                        }
                    }
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = { showTools = true },
                    modifier = Modifier
                        .size(48.dp)
                        .background(Color(AppConfig.COLOR_SURFACE), CircleShape)
                ) {
                    Icon(
                        Icons.Filled.AutoAwesome,
                        contentDescription = "Strumenti",
                        tint = Color(AppConfig.COLOR_PRIMARY_LIGHT)
                    )
                }
                Spacer(modifier = Modifier.width(6.dp))
                IconButton(
                    onClick = onVoiceInput,
                    modifier = Modifier
                        .size(48.dp)
                        .background(Color(AppConfig.COLOR_SURFACE), CircleShape)
                ) {
                    Icon(
                        Icons.Filled.Mic,
                        contentDescription = "Messaggio vocale",
                        tint = Color(AppConfig.COLOR_ACCENT)
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    modifier = Modifier.weight(1f),
                    maxLines = 4,
                    placeholder = {
                        Text("Scrivi un messaggio...", color = Color(AppConfig.COLOR_TEXT_DIM))
                    },
                    shape = RoundedCornerShape(24.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color(AppConfig.COLOR_TEXT),
                        unfocusedTextColor = Color(AppConfig.COLOR_TEXT),
                        focusedBorderColor = Color(AppConfig.COLOR_ACCENT),
                        unfocusedBorderColor = Color(AppConfig.COLOR_SURFACE),
                        cursorColor = Color(AppConfig.COLOR_ACCENT)
                    )
                )
                Spacer(modifier = Modifier.width(8.dp))
                val busy = isLoading || isStreaming
                Button(
                    onClick = {
                        if (busy) {
                            viewModel.stopGeneration()
                        } else if (input.isNotBlank()) {
                            viewModel.sendMessage(input)
                            input = ""
                        }
                    },
                    shape = CircleShape,
                    contentPadding = PaddingValues(0.dp),
                    modifier = Modifier.size(52.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (busy) Color(AppConfig.COLOR_ERROR)
                        else Color(AppConfig.COLOR_PRIMARY)
                    )
                ) {
                    Icon(
                        if (busy) Icons.Filled.Stop else Icons.AutoMirrored.Filled.Send,
                        contentDescription = if (busy) "Ferma" else "Invia",
                        tint = Color.White
                    )
                }
            }
        }
    }
}

@Composable
fun WelcomeCard(
    assistantName: String,
    hasApiKey: Boolean,
    onOpenSettings: () -> Unit,
    onSuggestion: (String) -> Unit
) {
    val suggestions = listOf(
        "Ciao! Chi sei?",
        "Apri YouTube",
        "Cerca ricette veloci",
        "Imposta un timer di 5 minuti"
    )
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            "✦",
            fontSize = 42.sp,
            color = Color(AppConfig.COLOR_ACCENT)
        )
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            "Ciao! Sono $assistantName",
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold,
            color = Color(AppConfig.COLOR_TEXT)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            "Creata da ${AppConfig.CREATOR} • Chiedimi qualsiasi cosa",
            fontSize = 13.sp,
            color = Color(AppConfig.COLOR_TEXT_DIM)
        )
        if (!hasApiKey) {
            Spacer(modifier = Modifier.height(14.dp))
            Button(
                onClick = onOpenSettings,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(AppConfig.COLOR_PRIMARY)
                )
            ) { Text("⚙️  Configura ARIA in 30 secondi") }
            Text(
                "Serve solo una API key Groq gratuita (console.groq.com)",
                fontSize = 11.sp,
                color = Color(AppConfig.COLOR_TEXT_DIM),
                modifier = Modifier.padding(top = 4.dp)
            )
        }
        Spacer(modifier = Modifier.height(20.dp))
        for (s in suggestions) {
            AssistChip(
                onClick = { onSuggestion(s) },
                label = { Text(s, color = Color(AppConfig.COLOR_TEXT)) },
                modifier = Modifier.padding(vertical = 2.dp)
            )
        }
    }
}

@Composable
fun TypingIndicator(assistantName: String) {
    val transition = rememberInfiniteTransition(label = "typing")
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .background(Color(AppConfig.COLOR_SURFACE), RoundedCornerShape(18.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        Text(
            "$assistantName sta scrivendo",
            fontSize = 12.sp,
            color = Color(AppConfig.COLOR_TEXT_DIM)
        )
        Spacer(modifier = Modifier.width(8.dp))
        for (i in 0..2) {
            val dotAlpha by transition.animateFloat(
                initialValue = 0.2f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(
                    animation = tween(450),
                    repeatMode = RepeatMode.Reverse,
                    initialStartOffset = StartOffset(i * 150)
                ),
                label = "dot$i"
            )
            Box(
                modifier = Modifier
                    .padding(horizontal = 2.dp)
                    .size(7.dp)
                    .background(
                        Color(AppConfig.COLOR_ACCENT).copy(alpha = dotAlpha),
                        CircleShape
                    )
            )
        }
    }
}

@Composable
fun MessageBubble(msg: ChatMessage, assistantName: String, onSpeak: (String) -> Unit) {
    val clipboard = LocalClipboardManager.current
    val context = LocalContext.current
    val isUser = msg.isUser()
    val timeText = remember(msg.timestamp) {
        SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(msg.timestamp))
    }
    val bubbleShape = RoundedCornerShape(
        topStart = 18.dp,
        topEnd = 18.dp,
        bottomStart = if (isUser) 18.dp else 4.dp,
        bottomEnd = if (isUser) 4.dp else 18.dp
    )
    val bubbleBrush = if (isUser) {
        Brush.linearGradient(
            listOf(Color(AppConfig.COLOR_PRIMARY), Color(AppConfig.COLOR_PRIMARY_LIGHT))
        )
    } else {
        Brush.linearGradient(
            listOf(Color(AppConfig.COLOR_SURFACE), Color(0xFF1A2238))
        )
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
        ) {
            Text(
                text = if (isUser) "Tu • $timeText" else "$assistantName • $timeText",
                fontSize = 10.sp,
                color = Color(AppConfig.COLOR_TEXT_DIM)
            )
            if (!isUser) {
                Spacer(modifier = Modifier.width(6.dp))
                Icon(
                    Icons.AutoMirrored.Filled.VolumeUp,
                    contentDescription = "Riascolta",
                    tint = Color(AppConfig.COLOR_ACCENT),
                    modifier = Modifier
                        .size(16.dp)
                        .clickable { onSpeak(msg.content) }
                )
            }
        }
        Box(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .background(brush = bubbleBrush, shape = bubbleShape)
                .pointerInput(msg.content) {
                    detectTapGestures(onLongPress = {
                        clipboard.setText(AnnotatedString(msg.content))
                        Toast.makeText(context, "Messaggio copiato", Toast.LENGTH_SHORT).show()
                    })
                }
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(
                text = msg.content,
                color = Color(AppConfig.COLOR_TEXT),
                fontSize = 15.sp
            )
        }
    }
}

data class AriaTool(
    val emoji: String,
    val title: String,
    val description: String,
    val prompt: String,
    val sendDirectly: Boolean = false
)

private val ARIA_TOOLS = listOf(
    AriaTool("🌍", "Traduttore", "Traduci un testo in un'altra lingua",
        "Traduci in inglese questo testo: "),
    AriaTool("📝", "Riassunto", "Riassumi un testo lungo in pochi punti",
        "Riassumi in 3 punti questo testo: "),
    AriaTool("✍️", "Correttore", "Correggi grammatica e ortografia",
        "Correggi grammatica e ortografia di questo testo: "),
    AriaTool("🧮", "Matematica", "Risolvi calcoli ed espressioni passo passo",
        "Risolvi passo passo: "),
    AriaTool("📧", "Email", "Scrivi un'email professionale",
        "Scrivimi un'email professionale per: "),
    AriaTool("💡", "Idee", "Brainstorming di idee creative",
        "Dammi 5 idee creative su: "),
    AriaTool("🍝", "Chef", "Ricetta con gli ingredienti che hai in casa",
        "Dammi una ricetta usando questi ingredienti: "),
    AriaTool("💪", "Coach", "Allenamento rapido da fare a casa",
        "Creami un allenamento di 20 minuti da fare a casa senza attrezzi", true),
    AriaTool("🎲", "Quiz", "Gioca a un quiz con l'AI",
        "Facciamo un quiz! Fammi una domanda di cultura generale e aspetta la mia risposta", true),
    AriaTool("😂", "Barzelletta", "Una risata al volo",
        "Raccontami una barzelletta divertente", true)
)

@Composable
fun ToolsSheetContent(onTool: (AriaTool) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(bottom = 32.dp)
    ) {
        Text(
            "✨ Strumenti",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = Color(AppConfig.COLOR_ACCENT),
            modifier = Modifier.padding(bottom = 4.dp)
        )
        Text(
            "Tocca uno strumento: alcuni partono subito, altri preparano il messaggio da completare.",
            fontSize = 12.sp,
            color = Color(AppConfig.COLOR_TEXT_DIM),
            modifier = Modifier.padding(bottom = 12.dp)
        )
        for (tool in ARIA_TOOLS) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp)
                    .background(Color(AppConfig.COLOR_BG), RoundedCornerShape(14.dp))
                    .clickable { onTool(tool) }
                    .padding(12.dp)
            ) {
                Text(tool.emoji, fontSize = 24.sp)
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        tool.title,
                        color = Color(AppConfig.COLOR_TEXT),
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                    Text(
                        tool.description,
                        color = Color(AppConfig.COLOR_TEXT_DIM),
                        fontSize = 12.sp
                    )
                }
            }
        }
    }
}
"""

SETTINGS_ACTIVITY = r"""package com.aria.mobile.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.widget.Button
import android.widget.EditText
import android.widget.RadioGroup
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import androidx.core.content.ContextCompat
import com.aria.mobile.R
import androidx.appcompat.app.AlertDialog
import com.aria.mobile.core.AppConfig
import com.aria.mobile.core.OfflineBrain
import com.aria.mobile.net.GroqClient
import com.aria.mobile.voice.WakeWordService
import java.io.File
import java.net.URL

class SettingsActivity : AppCompatActivity() {

    private val speechTestLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val heard = result.data
            ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            ?.firstOrNull()
        if (!heard.isNullOrBlank()) {
            Toast.makeText(this, "Ti ho sentito: \"$heard\"", Toast.LENGTH_LONG).show()
        } else {
            Toast.makeText(
                this, "Non ho sentito nulla. Avvicinati al microfono e riprova.",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private val permLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        val micOk = result[Manifest.permission.RECORD_AUDIO] == true
        if (micOk) {
            restartWakeService()
            Toast.makeText(this, "Ascolto vocale attivato", Toast.LENGTH_SHORT).show()
        } else {
            getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE).edit()
                .putBoolean(AppConfig.PREF_WAKE_ENABLED, false).apply()
            Toast.makeText(
                this,
                "Serve il permesso microfono per l'ascolto sempre attivo",
                Toast.LENGTH_LONG
            ).show()
        }
        finish()
    }

    private fun neededPerms(): Array<String> {
        val p = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            p.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        return p.toTypedArray()
    }

    private fun hasPerms(): Boolean = neededPerms().all {
        ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
    }

    private fun restartWakeService() {
        stopWakeService()
        val i = Intent(this, WakeWordService::class.java)
        ContextCompat.startForegroundService(this, i)
    }

    private fun stopWakeService() {
        stopService(Intent(this, WakeWordService::class.java))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val prefs = getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
        val etAssistantName = findViewById<EditText>(R.id.et_assistant_name)
        val etUserName = findViewById<EditText>(R.id.et_user_name)
        val etKey = findViewById<EditText>(R.id.et_api_key)
        val etModel = findViewById<EditText>(R.id.et_model)
        val rgPersonality = findViewById<RadioGroup>(R.id.rg_personality)
        val swVoice = findViewById<SwitchCompat>(R.id.sw_voice)
        val swMemory = findViewById<SwitchCompat>(R.id.sw_memory)
        val swActions = findViewById<SwitchCompat>(R.id.sw_actions)
        val swWake = findViewById<SwitchCompat>(R.id.sw_wake)
        val etWakeWord = findViewById<EditText>(R.id.et_wake_word)
        val swOffline = findViewById<SwitchCompat>(R.id.sw_offline)
        val rgAiMode = findViewById<RadioGroup>(R.id.rg_ai_mode)
        val btnDownloadAi = findViewById<Button>(R.id.btn_download_ai)
        val btnTestOffline = findViewById<Button>(R.id.btn_test_offline)
        val btnDownloadVoice = findViewById<Button>(R.id.btn_download_voice)
        val btnTestListen = findViewById<Button>(R.id.btn_test_listen)
        val btnBattery = findViewById<Button>(R.id.btn_battery)
        val btnSave = findViewById<Button>(R.id.btn_save_settings)
        val btnBack = findViewById<Button>(R.id.btn_settings_back)
        val btnTest = findViewById<Button>(R.id.btn_test_api)
        val btnModel70 = findViewById<Button>(R.id.btn_model_70b)
        val btnModel8 = findViewById<Button>(R.id.btn_model_8b)
        val btnModelScout = findViewById<Button>(R.id.btn_model_scout)

        val personalityIds = mapOf(
            "Amichevole" to R.id.rb_amichevole,
            "Professionale" to R.id.rb_professionale,
            "Divertente" to R.id.rb_divertente,
            "Sarcastica" to R.id.rb_sarcastica,
            "Motivazionale" to R.id.rb_motivazionale
        )

        etAssistantName.setText(
            prefs.getString(AppConfig.PREF_ASSISTANT_NAME, AppConfig.DEFAULT_ASSISTANT_NAME)
        )
        etUserName.setText(prefs.getString(AppConfig.PREF_USER_NAME, ""))
        etKey.setText(prefs.getString(AppConfig.PREF_API_KEY, ""))
        etModel.setText(prefs.getString(AppConfig.PREF_MODEL, AppConfig.DEFAULT_MODEL))
        swVoice.isChecked = prefs.getBoolean(AppConfig.PREF_VOICE_ENABLED, true)
        swMemory.isChecked = prefs.getBoolean(AppConfig.PREF_MEMORY_ENABLED, true)
        swActions.isChecked = prefs.getBoolean(AppConfig.PREF_ACTIONS_ENABLED, true)
        swWake.isChecked = prefs.getBoolean(AppConfig.PREF_WAKE_ENABLED, false)
        etWakeWord.setText(
            prefs.getString(AppConfig.PREF_WAKE_WORD, AppConfig.DEFAULT_WAKE_WORD)
        )
        swOffline.isChecked = prefs.getBoolean(AppConfig.PREF_OFFLINE_MODE, false)
        when (prefs.getString(AppConfig.PREF_AI_MODE, AppConfig.DEFAULT_AI_MODE)) {
            "online" -> rgAiMode.check(R.id.rb_mode_online)
            "offline" -> rgAiMode.check(R.id.rb_mode_offline)
            else -> rgAiMode.check(R.id.rb_mode_auto)
        }

        // ---- SCARICA AI OFFLINE (resta sul telefono) ----
        btnDownloadAi.setOnClickListener {
            Toast.makeText(this, "Scarico l'AI offline...", Toast.LENGTH_SHORT).show()
            Thread {
                var data: String? = null
                // 1) prova online (versione piu' aggiornata)
                try {
                    val conn = URL(AppConfig.KNOWLEDGE_URL).openConnection()
                    conn.connectTimeout = 8000
                    conn.readTimeout = 8000
                    data = conn.getInputStream().bufferedReader().readText()
                } catch (_: Exception) {}
                // 2) fallback: pacchetto incluso nell'APK (funziona anche offline)
                if (data == null || !data.contains("\"entries\"")) {
                    data = try {
                        assets.open("knowledge_pack_it.json").bufferedReader().readText()
                    } catch (e: Exception) { null }
                }
                if (data != null) {
                    try {
                        File(filesDir, "knowledge_pack.json").writeText(data)
                        val n = OfflineBrain(this).packCount()
                        runOnUiThread {
                            Toast.makeText(
                                this,
                                "AI offline installata: $n risposte pronte. Resta sul telefono!",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    } catch (e: Exception) {
                        runOnUiThread {
                            Toast.makeText(this, "Errore salvataggio: ${e.message}", Toast.LENGTH_LONG).show()
                        }
                    }
                } else {
                    runOnUiThread {
                        Toast.makeText(this, "Download fallito, riprova", Toast.LENGTH_LONG).show()
                    }
                }
            }.start()
        }

        // ---- TEST AI OFFLINE ----
        btnTestOffline.setOnClickListener {
            val ob = OfflineBrain(this)
            val sb = StringBuilder()
            sb.append("Matematica (12*8+4):\n")
            sb.append(ob.answer("quanto fa 12*8+4") ?: "NON RISPONDE").append("\n\n")
            sb.append("Ora:\n")
            sb.append(ob.answer("che ore sono") ?: "NON RISPONDE").append("\n\n")
            val n = ob.packCount()
            if (n > 0) {
                sb.append("Conoscenza (capitale della Francia):\n")
                sb.append(ob.answer("qual e la capitale della francia") ?: "NON RISPONDE")
                sb.append("\n\nPacchetto installato: $n risposte ✓")
            } else {
                sb.append("Pacchetto conoscenza: NON installato.\n")
                sb.append("Tocca '⬇ Scarica AI offline' qui sopra.")
            }
            AlertDialog.Builder(this)
                .setTitle("Test AI offline")
                .setMessage(sb.toString())
                .setPositiveButton("OK", null)
                .show()
        }

        btnBattery.setOnClickListener {
            try {
                val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
                if (pm.isIgnoringBatteryOptimizations(packageName)) {
                    Toast.makeText(this, "Gia' escluso dal risparmio batteria ✓", Toast.LENGTH_LONG).show()
                } else {
                    val i = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                    i.data = Uri.parse("package:$packageName")
                    startActivity(i)
                }
            } catch (e: Exception) {
                try {
                    startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                } catch (_: Exception) {
                    Toast.makeText(this, "Apri Impostazioni > Batteria e togli le restrizioni ad ARIA", Toast.LENGTH_LONG).show()
                }
            }
        }

        btnTestListen.setOnClickListener {
            if (!SpeechRecognizer.isRecognitionAvailable(this)) {
                Toast.makeText(
                    this,
                    "Riconoscimento vocale non disponibile: installa/aggiorna l'app Google",
                    Toast.LENGTH_LONG
                ).show()
                return@setOnClickListener
            }
            val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                )
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
                val hint = etWakeWord.text.toString().trim().ifBlank { AppConfig.DEFAULT_WAKE_WORD }
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Prova a dire: Hey $hint")
            }
            try {
                speechTestLauncher.launch(i)
            } catch (e: Exception) {
                Toast.makeText(this, "Impossibile avviare il test vocale", Toast.LENGTH_SHORT).show()
            }
        }

        btnDownloadVoice.setOnClickListener {
            // apre il download dei dati vocali offline (voce TTS): resta installato
            try {
                val i = Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA)
                startActivity(i)
                Toast.makeText(
                    this,
                    "Scarica la voce Italiano offline, poi resta salvata sul telefono",
                    Toast.LENGTH_LONG
                ).show()
            } catch (e: Exception) {
                Toast.makeText(
                    this,
                    "Apri: Impostazioni Android > Sistema > Lingue > Sintesi vocale per scaricare la voce offline",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
        val savedPersonality = prefs.getString(
            AppConfig.PREF_PERSONALITY, AppConfig.DEFAULT_PERSONALITY
        )
        rgPersonality.check(personalityIds[savedPersonality] ?: R.id.rb_amichevole)

        btnModel70.setOnClickListener { etModel.setText("llama-3.3-70b-versatile") }
        btnModel8.setOnClickListener { etModel.setText("llama-3.1-8b-instant") }
        btnModelScout.setOnClickListener {
            etModel.setText("meta-llama/llama-4-scout-17b-16e-instruct")
        }

        btnTest.setOnClickListener {
            val key = etKey.text.toString().trim()
            val model = etModel.text.toString().trim().ifBlank { AppConfig.DEFAULT_MODEL }
            if (key.isBlank()) {
                Toast.makeText(this, "Inserisci prima la API key", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            Toast.makeText(this, "Test in corso...", Toast.LENGTH_SHORT).show()
            GroqClient(key, model).sendMessage(
                listOf("user" to "Rispondi solo: OK"),
                object : GroqClient.ResultCallback {
                    override fun onResult(text: String) {
                        runOnUiThread {
                            Toast.makeText(
                                this@SettingsActivity,
                                "Connessione OK! Modello: $model",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                    override fun onError(message: String) {
                        runOnUiThread {
                            Toast.makeText(
                                this@SettingsActivity,
                                "Errore: ${message.take(200)}",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                }
            )
        }

        btnSave.setOnClickListener {
            val assistantName = etAssistantName.text.toString().trim()
                .ifBlank { AppConfig.DEFAULT_ASSISTANT_NAME }
            val model = etModel.text.toString().trim()
                .ifBlank { AppConfig.DEFAULT_MODEL }
            val checkedId = rgPersonality.checkedRadioButtonId
            val personality = personalityIds.entries
                .firstOrNull { it.value == checkedId }?.key
                ?: AppConfig.DEFAULT_PERSONALITY
            val wakeWord = etWakeWord.text.toString().trim()
                .ifBlank { AppConfig.DEFAULT_WAKE_WORD }
            prefs.edit()
                .putString(AppConfig.PREF_ASSISTANT_NAME, assistantName)
                .putString(AppConfig.PREF_USER_NAME, etUserName.text.toString().trim())
                .putString(AppConfig.PREF_API_KEY, etKey.text.toString().trim())
                .putString(AppConfig.PREF_MODEL, model)
                .putString(AppConfig.PREF_PERSONALITY, personality)
                .putString(AppConfig.PREF_WAKE_WORD, wakeWord)
                .putBoolean(AppConfig.PREF_VOICE_ENABLED, swVoice.isChecked)
                .putBoolean(AppConfig.PREF_MEMORY_ENABLED, swMemory.isChecked)
                .putBoolean(AppConfig.PREF_WAKE_ENABLED, swWake.isChecked)
                .putBoolean(AppConfig.PREF_ACTIONS_ENABLED, swActions.isChecked)
                .putBoolean(AppConfig.PREF_OFFLINE_MODE, swOffline.isChecked)
                .putString(
                    AppConfig.PREF_AI_MODE,
                    when (rgAiMode.checkedRadioButtonId) {
                        R.id.rb_mode_online -> "online"
                        R.id.rb_mode_offline -> "offline"
                        else -> "auto"
                    }
                )
                .apply()

            Toast.makeText(this, "Impostazioni salvate", Toast.LENGTH_SHORT).show()

            // avvia o ferma l'ascolto sempre attivo
            if (swWake.isChecked) {
                if (!SpeechRecognizer.isRecognitionAvailable(this)) {
                    Toast.makeText(
                        this,
                        "Riconoscimento vocale non disponibile: installa/aggiorna l'app Google, poi riprova",
                        Toast.LENGTH_LONG
                    ).show()
                }
                if (hasPerms()) {
                    restartWakeService()
                    finish()
                } else {
                    // chiede i permessi; la chiusura avviene nel callback
                    permLauncher.launch(neededPerms())
                }
            } else {
                stopWakeService()
                finish()
            }
        }
        btnBack.setOnClickListener { finish() }
    }
}
"""

HISTORY_ACTIVITY = r"""package com.aria.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aria.mobile.R
import com.aria.mobile.data.AriaDatabase
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class HistoryActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_history)

        val tv = findViewById<TextView>(R.id.tv_history_content)
        val btnBack = findViewById<Button>(R.id.btn_history_back)
        val btnClear = findViewById<Button>(R.id.btn_history_clear)
        val fmt = SimpleDateFormat("dd/MM HH:mm", Locale.getDefault())

        btnBack.setOnClickListener { finish() }

        val db = AriaDatabase.getInstance(this)
        btnClear.setOnClickListener {
            lifecycleScope.launch {
                db.messageDao().clearAll()
                tv.text = "Cronologia svuotata."
            }
        }

        lifecycleScope.launch {
            val msgs = db.messageDao().getSession(0L)
            tv.text = if (msgs.isEmpty()) "Nessun messaggio salvato."
                else "Messaggi salvati: ${msgs.size}\n\n" + msgs.joinToString("\n\n") {
                    val who = if (it.role == "user") "TU" else "AI"
                    "[${fmt.format(Date(it.timestamp))}] $who:\n${it.content}"
                }
        }
    }
}
"""

BOOT_RECEIVER = r"""package com.aria.mobile.voice

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.aria.mobile.core.AppConfig

/** Riavvia l'ascolto "Hey ..." dopo il riavvio del telefono, se era attivo. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action == Intent.ACTION_BOOT_COMPLETED ||
            action == "android.intent.action.QUICKBOOT_POWERON"
        ) {
            val prefs = context.getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
            if (prefs.getBoolean(AppConfig.PREF_WAKE_ENABLED, false)) {
                try {
                    ContextCompat.startForegroundService(
                        context, Intent(context, WakeWordService::class.java)
                    )
                } catch (_: Exception) {
                }
            }
        }
    }
}
"""

WAKE_WORD_SERVICE = r"""package com.aria.mobile.voice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.aria.mobile.R
import com.aria.mobile.core.AppConfig
import com.aria.mobile.core.AriaBrain
import com.aria.mobile.ui.MainActivity
import java.text.Normalizer
import java.util.Locale

/**
 * Servizio "sempre in ascolto" PROFESSIONALE e ROBUSTO.
 *
 * Punti chiave per l'affidabilita':
 *  - risultati PARZIALI: la parola di attivazione viene catturata mentre
 *    parli, senza aspettare la fine della frase;
 *  - matching FUZZY (distanza di Levenshtein + normalizzazione senza
 *    accenti): tollera "maik/mike/maic..." e piccoli errori del motore;
 *  - WATCHDOG: un controllo periodico riavvia l'ascolto se per qualsiasi
 *    motivo si e' fermato (il vero tallone d'Achille del riconoscimento
 *    continuo su Android);
 *  - ricreazione del recognizer sugli errori BUSY/CLIENT;
 *  - NIENTE "prefer offline" qui: usa il motore piu' affidabile
 *    disponibile, cosi' ti sente davvero;
 *  - feedback di stato nella notifica.
 */
class WakeWordService : Service() {

    companion object {
        private const val NOTIF_ID = 42
        private const val CHANNEL = "aria_wake"
        private const val WATCHDOG_MS = 2500L
        private const val STUCK_MS = 9000L
    }

    private enum class Mode { WAKE, COMMAND }

    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var brain: AriaBrain? = null
    private var wakeLock: PowerManager.WakeLock? = null

    private var mode = Mode.WAKE
    private var running = false
    private var listening = false
    private var speaking = false
    private var triggered = false
    private var lastActivity = 0L
    private var wakeWord = AppConfig.DEFAULT_WAKE_WORD

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        brain = AriaBrain(applicationContext)
        val prefs = getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
        wakeWord = normalize(
            prefs.getString(AppConfig.PREF_WAKE_WORD, AppConfig.DEFAULT_WAKE_WORD)
                ?: AppConfig.DEFAULT_WAKE_WORD
        ).ifBlank { AppConfig.DEFAULT_WAKE_WORD }

        val pm = getSystemService(PowerManager::class.java)
        wakeLock = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "aria:wakeword")
        wakeLock?.setReferenceCounted(false)

        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val r = tts?.setLanguage(Locale.ITALIAN) ?: TextToSpeech.LANG_MISSING_DATA
                if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) {
                    tts?.language = Locale.getDefault()
                }
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(u: String?) { speaking = true }
                    override fun onDone(u: String?) {
                        speaking = false
                        handler.post { onSpeechFinished(u) }
                    }
                    @Deprecated("deprecated in API level 21")
                    override fun onError(u: String?) {
                        speaking = false; handler.post { onSpeechFinished(u) }
                    }
                    override fun onError(u: String?, code: Int) {
                        speaking = false; handler.post { onSpeechFinished(u) }
                    }
                })
                ttsReady = true
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForegroundNotification("In ascolto - di' \"Hey $wakeWord\"")
        if (wakeLock?.isHeld != true) {
            try { wakeLock?.acquire() } catch (_: Exception) {}
        }
        if (!running) {
            running = true
            handler.postDelayed({ beginWake() }, 700)
            handler.postDelayed(watchdog, WATCHDOG_MS)
        }
        return START_STICKY
    }

    // ---------------------------------------------------------------
    //  WATCHDOG: garanzia anti-blocco
    // ---------------------------------------------------------------
    private val watchdog = object : Runnable {
        override fun run() {
            if (!running) return
            val idle = SystemClock.elapsedRealtime() - lastActivity
            if (!speaking) {
                if (!listening) {
                    beginWake()
                } else if (idle > STUCK_MS) {
                    // bloccato: ricrea tutto
                    recreateRecognizer()
                    beginWake()
                }
            }
            handler.postDelayed(this, WATCHDOG_MS)
        }
    }

    // ---------------------------------------------------------------
    //  RECOGNIZER
    // ---------------------------------------------------------------
    private fun ensureRecognizer(): SpeechRecognizer {
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(this)
            recognizer?.setRecognitionListener(listener)
        }
        return recognizer!!
    }

    private fun recreateRecognizer() {
        try { recognizer?.destroy() } catch (_: Exception) {}
        recognizer = null
        listening = false
    }

    private fun recognizerIntent(partial: Boolean): Intent =
        Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, partial)
            putExtra(packageName + ".pkg", packageName)
            if (!partial) {
                putExtra(
                    RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L
                )
                putExtra(
                    RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L
                )
                putExtra(
                    RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 1800L
                )
            }
        }

    private fun beginWake() {
        if (!running || speaking) return
        mode = Mode.WAKE
        triggered = false
        startRecognizerSafe(true)
    }

    private fun beginCommand() {
        if (!running) return
        mode = Mode.COMMAND
        triggered = false
        startRecognizerSafe(false)
    }

    private fun startRecognizerSafe(partial: Boolean) {
        if (!running || speaking) return
        try {
            recognizer?.cancel()
            ensureRecognizer().startListening(recognizerIntent(partial))
            listening = true
            lastActivity = SystemClock.elapsedRealtime()
        } catch (e: Exception) {
            listening = false
            recreateRecognizer()
            handler.postDelayed({ if (mode == Mode.COMMAND) beginCommand() else beginWake() }, 500)
        }
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) { lastActivity = SystemClock.elapsedRealtime() }
        override fun onBeginningOfSpeech() { lastActivity = SystemClock.elapsedRealtime() }
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() { lastActivity = SystemClock.elapsedRealtime() }

        override fun onError(error: Int) {
            listening = false
            if (speaking) return
            when (error) {
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY,
                SpeechRecognizer.ERROR_CLIENT -> {
                    recreateRecognizer()
                    handler.postDelayed({ beginWake() }, 500)
                }
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> {
                    updateStatus("Manca il permesso microfono")
                    stopSelf()
                }
                else -> {
                    // NO_MATCH, SPEECH_TIMEOUT, NETWORK... -> normale, riprova
                    handler.postDelayed({ if (mode == Mode.COMMAND) beginWake() else beginWake() }, 250)
                }
            }
        }

        override fun onResults(results: Bundle?) {
            lastActivity = SystemClock.elapsedRealtime()
            listening = false
            val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull() ?: ""
            handleFinal(text)
        }

        override fun onPartialResults(partialResults: Bundle?) {
            lastActivity = SystemClock.elapsedRealtime()
            if (mode != Mode.WAKE || triggered) return
            val text = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull() ?: return
            val cmd = wakeCommand(text)
            if (cmd != null) {
                triggered = true
                recognizer?.cancel()
                listening = false
                onWakeDetected(cmd)
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    private fun handleFinal(text: String) {
        when (mode) {
            Mode.WAKE -> {
                if (triggered) return
                val cmd = wakeCommand(text)
                if (cmd != null) {
                    triggered = true
                    onWakeDetected(cmd)
                } else {
                    handler.postDelayed({ beginWake() }, 150)
                }
            }
            Mode.COMMAND -> {
                if (text.isBlank()) { beginWake(); return }
                processCommand(text)
            }
        }
    }

    private fun onWakeDetected(command: String) {
        if (command.length >= 2) {
            processCommand(command)
        } else {
            val userName = getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
                .getString(AppConfig.PREF_USER_NAME, "")?.trim() ?: ""
            val ack = if (userName.isNotBlank()) "Sì, dimmi $userName" else "Sì, dimmi?"
            updateStatus("Ti ascolto...")
            speak(ack, "ack")
        }
    }

    private fun onSpeechFinished(utteranceId: String?) {
        when (utteranceId) {
            "ack" -> beginCommand()
            else -> {
                updateStatus("In ascolto - di' \"Hey $wakeWord\"")
                beginWake()
            }
        }
    }

    private fun processCommand(command: String) {
        updateStatus("Sto pensando...")
        val b = brain
        if (b == null) { speak("Il mio cervello non è pronto.", "answer"); return }
        b.sendMessage(
            text = command,
            onResult = { resp ->
                val (clean, actions) = com.aria.mobile.core.PhoneActions.parseMarkers(resp)
                val actionsEnabled = getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
                    .getBoolean(AppConfig.PREF_ACTIONS_ENABLED, true)
                if (actionsEnabled) for (a in actions) com.aria.mobile.core.PhoneActions.execute(applicationContext, a)
                updateStatus("Parlo...")
                speak(clean.ifBlank { "Fatto" }, "answer")
            },
            onError = { errMsg -> speak("Errore: $errMsg", "answer") }
        )
    }

    private fun speak(text: String, id: String) {
        speaking = true
        recognizer?.cancel()
        listening = false
        if (ttsReady) {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, id)
        } else {
            speaking = false
            handler.postDelayed({ onSpeechFinished(id) }, 500)
        }
    }

    // ---------------------------------------------------------------
    //  MATCHING FUZZY DELLA PAROLA DI ATTIVAZIONE
    // ---------------------------------------------------------------
    /** null = nessun wake; "" = wake senza comando; "..." = comando dopo il wake. */
    private fun wakeCommand(raw: String): String? {
        val norm = normalize(raw)
        if (norm.isEmpty()) return null
        val tokens = norm.split(" ").filter { it.isNotEmpty() }
        if (tokens.isEmpty()) return null
        val w = wakeWord
        val thr = if (w.length <= 4) 1 else 2
        var idx = -1
        for (i in tokens.indices) {
            val tk = tokens[i]
            if (tk == w || levenshtein(tk, w) <= thr) { idx = i; break }
        }
        if (idx == -1) {
            if (norm.contains(w)) idx = 0 else return null
        }
        return tokens.drop(idx + 1).joinToString(" ").trim()
    }

    private fun normalize(s: String): String {
        val lower = s.lowercase(Locale.getDefault())
        val decomposed = Normalizer.normalize(lower, Normalizer.Form.NFD)
        val sb = StringBuilder()
        for (c in decomposed) {
            when {
                c in 'a'..'z' || c in '0'..'9' -> sb.append(c)
                c == ' ' -> sb.append(' ')
                else -> {}
            }
        }
        return sb.toString().split(" ").filter { it.isNotEmpty() }.joinToString(" ")
    }

    private fun levenshtein(a: String, b: String): Int {
        if (a == b) return 0
        if (a.isEmpty()) return b.length
        if (b.isEmpty()) return a.length
        val dp = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            var prev = dp[0]
            dp[0] = i
            for (j in 1..b.length) {
                val tmp = dp[j]
                dp[j] = if (a[i - 1] == b[j - 1]) prev
                else 1 + minOf(prev, dp[j], dp[j - 1])
                prev = tmp
            }
        }
        return dp[b.length]
    }

    // ---------------------------------------------------------------
    //  NOTIFICA
    // ---------------------------------------------------------------
    private fun startForegroundNotification(status: String) {
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(
                CHANNEL, "ARIA ascolto vocale", NotificationManager.IMPORTANCE_LOW
            )
            ch.description = "Ascolto della parola di attivazione"
            nm?.createNotificationChannel(ch)
        }
        val notif = buildNotification(status)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(
                this, NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
            )
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    private fun buildNotification(status: String): Notification {
        val pi = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, CHANNEL)
            .setContentTitle("ARIA")
            .setContentText(status)
            .setSmallIcon(R.drawable.ic_aria)
            .setContentIntent(pi)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateStatus(status: String) {
        try {
            getSystemService(NotificationManager::class.java)
                ?.notify(NOTIF_ID, buildNotification(status))
        } catch (_: Exception) {}
    }

    override fun onDestroy() {
        running = false
        handler.removeCallbacksAndMessages(null)
        try { recognizer?.destroy() } catch (_: Exception) {}
        try { tts?.stop(); tts?.shutdown() } catch (_: Exception) {}
        try { if (wakeLock?.isHeld == true) wakeLock?.release() } catch (_: Exception) {}
        super.onDestroy()
    }
}
"""

# ============================================================
#  LAYOUT XML
# ============================================================
STRINGS_XML = '<resources><string name="app_name">ARIA</string></resources>'

THEMES_XML = """\
<resources>
    <style name="Theme.Aria" parent="Theme.Material3.DayNight.NoActionBar">
        <item name="colorPrimary">#7C4DFF</item>
        <item name="colorSecondary">#00E5FF</item>
        <item name="android:windowBackground">#0A0E1A</item>
        <item name="android:statusBarColor">#0A0E1A</item>
        <item name="android:navigationBarColor">#121826</item>
    </style>
</resources>"""

IC_ARIA_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
  <path android:fillColor="#0A0E1A" android:pathData="M0,0h108v108h-108z"/>
  <path android:fillColor="#151B30"
    android:pathData="M10,54 a44,44 0 1,0 88,0 a44,44 0 1,0 -88,0"/>
  <path android:fillColor="#7C4DFF"
    android:pathData="M26,54 a28,28 0 1,0 56,0 a28,28 0 1,0 -56,0"/>
  <path android:fillColor="#9C6BFF"
    android:pathData="M32,54 a22,22 0 1,0 44,0 a22,22 0 1,0 -44,0"/>
  <path android:fillColor="#00E5FF"
    android:pathData="M42,54 a12,12 0 1,0 24,0 a12,12 0 1,0 -24,0"/>
  <path android:fillColor="#FFFFFF"
    android:pathData="M43,45 a4,4 0 1,0 8,0 a4,4 0 1,0 -8,0"/>
  <path android:strokeColor="#00E5FF" android:strokeWidth="3"
    android:pathData="M12,54 a42,16 0 1,0 84,0 a42,16 0 1,0 -84,0"/>
  <path android:fillColor="#FFFFFF"
    android:pathData="M92,54 a4,4 0 1,0 8,0 a4,4 0 1,0 -8,0"/>
</vector>"""

LAYOUT_SETTINGS = """\
<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:background="#0A0E1A">
<LinearLayout
    android:layout_width="match_parent" android:layout_height="wrap_content"
    android:orientation="vertical" android:padding="20dp">

    <Button android:id="@+id/btn_settings_back"
        android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="&lt; Indietro" android:backgroundTint="#121826" android:textColor="#00E5FF"
        android:layout_marginBottom="20dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="IMPOSTAZIONI" android:textColor="#7C4DFF"
        android:textSize="22sp" android:textStyle="bold" android:layout_marginBottom="20dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Nome assistente" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_assistant_name"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="ARIA" android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Il tuo nome (opzionale)" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_user_name"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="Come ti chiami?" android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Groq API Key" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_api_key"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="gsk_..." android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="8dp"/>

    <Button android:id="@+id/btn_test_api"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Prova connessione" android:backgroundTint="#121826"
        android:textColor="#00E5FF" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Modello" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_model"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="llama-3.3-70b-versatile" android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="8dp"/>

    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="horizontal" android:layout_marginBottom="20dp">
        <Button android:id="@+id/btn_model_70b"
            android:layout_width="0dp" android:layout_height="wrap_content"
            android:layout_weight="1" android:layout_marginEnd="6dp"
            android:text="70B top" android:textSize="11sp"
            android:backgroundTint="#121826" android:textColor="#00E5FF"/>
        <Button android:id="@+id/btn_model_8b"
            android:layout_width="0dp" android:layout_height="wrap_content"
            android:layout_weight="1" android:layout_marginEnd="6dp"
            android:text="8B veloce" android:textSize="11sp"
            android:backgroundTint="#121826" android:textColor="#00E5FF"/>
        <Button android:id="@+id/btn_model_scout"
            android:layout_width="0dp" android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="Llama 4" android:textSize="11sp"
            android:backgroundTint="#121826" android:textColor="#00E5FF"/>
    </LinearLayout>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Personalità" android:textColor="#5A7A99" android:textSize="12sp"/>
    <RadioGroup android:id="@+id/rg_personality"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:layout_marginBottom="20dp">
        <RadioButton android:id="@+id/rb_amichevole"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Amichevole" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF" android:checked="true"/>
        <RadioButton android:id="@+id/rb_professionale"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Professionale" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
        <RadioButton android:id="@+id/rb_divertente"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Divertente" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
        <RadioButton android:id="@+id/rb_sarcastica"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Sarcastica" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
        <RadioButton android:id="@+id/rb_motivazionale"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Motivazionale" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
    </RadioGroup>

    <androidx.appcompat.widget.SwitchCompat android:id="@+id/sw_voice"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Risposte a voce (TTS)" android:textColor="#E8F0FF"
        android:layout_marginBottom="12dp"/>

    <androidx.appcompat.widget.SwitchCompat android:id="@+id/sw_memory"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Memoria conversazione" android:textColor="#E8F0FF"
        android:layout_marginBottom="20dp"/>

    <View android:layout_width="match_parent" android:layout_height="1dp"
        android:background="#1E2A44" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="🤖 CONTROLLO TELEFONO" android:textColor="#00E5FF"
        android:textSize="14sp" android:textStyle="bold"/>
    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="ARIA puo' aprire app, cercare, chiamare, mandare messaggi WhatsApp/SMS/email, aprire mappe, timer, torcia e fotocamera. Chiamate e messaggi restano pronti: premi tu invia."
        android:textColor="#5A7A99" android:textSize="11sp" android:layout_marginBottom="8dp"/>
    <androidx.appcompat.widget.SwitchCompat android:id="@+id/sw_actions"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Consenti ad ARIA di comandare il telefono" android:textColor="#E8F0FF"
        android:layout_marginBottom="20dp"/>

    <View android:layout_width="match_parent" android:layout_height="1dp"
        android:background="#1E2A44" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="🎙️ ASCOLTO SEMPRE ATTIVO" android:textColor="#00E5FF"
        android:textSize="14sp" android:textStyle="bold"/>
    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Rispondi anche a schermo bloccato quando dici 'Hey' + la parola qui sotto. Consuma piu' batteria."
        android:textColor="#5A7A99" android:textSize="11sp" android:layout_marginBottom="8dp"/>

    <androidx.appcompat.widget.SwitchCompat android:id="@+id/sw_wake"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Attiva ascolto sempre attivo" android:textColor="#E8F0FF"
        android:layout_marginBottom="8dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Parola di attivazione (dopo 'Hey')" android:textColor="#5A7A99"
        android:textSize="12sp"/>
    <EditText android:id="@+id/et_wake_word"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="maik" android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#00E5FF" android:layout_marginBottom="8dp"/>

    <Button android:id="@+id/btn_test_listen"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="🎤  Prova ascolto (vedi se ti sente)" android:backgroundTint="#121826"
        android:textColor="#00E5FF" android:layout_marginBottom="8dp"/>

    <Button android:id="@+id/btn_battery"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="🔋  Escludi dal risparmio batteria (consigliato)" android:backgroundTint="#121826"
        android:textColor="#00E5FF" android:layout_marginBottom="20dp"/>

    <View android:layout_width="match_parent" android:layout_height="1dp"
        android:background="#1E2A44" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="🧠 CERVELLO AI" android:textColor="#00E5FF"
        android:textSize="14sp" android:textStyle="bold"/>
    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Auto = Groq online, con passaggio automatico all'offline se manca la rete."
        android:textColor="#5A7A99" android:textSize="11sp" android:layout_marginBottom="6dp"/>

    <RadioGroup android:id="@+id/rg_ai_mode"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:layout_marginBottom="10dp">
        <RadioButton android:id="@+id/rb_mode_auto"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Auto (consigliato)" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF" android:checked="true"/>
        <RadioButton android:id="@+id/rb_mode_online"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Solo online (Groq)" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
        <RadioButton android:id="@+id/rb_mode_offline"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Solo offline (senza internet)" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
    </RadioGroup>

    <Button android:id="@+id/btn_download_ai"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="⬇  Scarica AI offline (resta sul telefono)" android:backgroundTint="#7C4DFF"
        android:textColor="#FFFFFF" android:layout_marginBottom="8dp"/>

    <Button android:id="@+id/btn_test_offline"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="🧪  Prova AI offline (vedi se funziona)" android:backgroundTint="#121826"
        android:textColor="#00E5FF" android:layout_marginBottom="20dp"/>

    <View android:layout_width="match_parent" android:layout_height="1dp"
        android:background="#1E2A44" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="🔌 EXTRA OFFLINE" android:textColor="#00E5FF"
        android:textSize="14sp" android:textStyle="bold"/>
    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Ora, data, calcoli e battute funzionano SEMPRE anche senza internet. Groq resta il cervello principale quando c'e' connessione (non serve toccare nulla)."
        android:textColor="#5A7A99" android:textSize="11sp" android:layout_marginBottom="8dp"/>

    <androidx.appcompat.widget.SwitchCompat android:id="@+id/sw_offline"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Preferisci riconoscimento vocale offline (se scaricato)" android:textColor="#E8F0FF"
        android:layout_marginBottom="10dp"/>

    <Button android:id="@+id/btn_download_voice"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="⬇  Scarica voce offline" android:backgroundTint="#121826"
        android:textColor="#00E5FF" android:layout_marginBottom="24dp"/>

    <Button android:id="@+id/btn_save_settings"
        android:layout_width="match_parent" android:layout_height="52dp"
        android:text="SALVA" android:backgroundTint="#7C4DFF" android:textColor="#FFFFFF"
        android:textStyle="bold"/>

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Creator: MaikGost  •  ARIA Mobile v9.1"
        android:textColor="#5A7A99" android:textSize="12sp"
        android:gravity="center" android:layout_marginTop="24dp"/>
</LinearLayout>
</ScrollView>"""

LAYOUT_HISTORY = """\
<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:background="#0A0E1A">
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
    android:orientation="vertical" android:padding="20dp">

    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="horizontal" android:layout_marginBottom="20dp">
        <Button android:id="@+id/btn_history_back"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="&lt; Indietro" android:backgroundTint="#121826" android:textColor="#00E5FF"
            android:layout_marginEnd="10dp"/>
        <Button android:id="@+id/btn_history_clear"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Svuota" android:backgroundTint="#FF5252" android:textColor="#FFFFFF"/>
    </LinearLayout>

    <TextView android:id="@+id/tv_history_content"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:textColor="#E8F0FF" android:textSize="13sp" android:fontFamily="monospace"/>
</LinearLayout></ScrollView>"""

# ============================================================
#  TOOLCHAIN DISCOVERY (JDK + Android SDK)
# ============================================================
def find_java():
    bases = [
        Path("C:/Program Files/Android/Android Studio/jbr"),
        Path("C:/Program Files/Android/Android Studio/jre"),
        Path("C:/Program Files/Eclipse Adoptium"),
        Path("C:/Program Files/Java"),
        Path("C:/Program Files/Microsoft"),
        Path("C:/Program Files/Amazon Corretto"),
    ]
    for base in bases:
        if base.exists() and (base / "bin" / "java.exe").exists():
            return base
    for v in ("21", "17"):
        for base in [Path("C:/Program Files/Eclipse Adoptium"),
                     Path("C:/Program Files/Java"),
                     Path("C:/Program Files/Microsoft"),
                     Path("C:/Program Files/Amazon Corretto")]:
            if not base.exists(): continue
            try: candidates = sorted(base.iterdir(), reverse=True)
            except: continue
            for d in candidates:
                if d.is_dir() and v in d.name.lower() and (d/"bin"/"java.exe").exists():
                    return d
    jh = os.environ.get("JAVA_HOME")
    if jh and (Path(jh)/"bin"/"java.exe").exists(): return Path(jh)
    jb = shutil.which("java")
    if jb: return Path(jb).parent.parent
    return None

def find_android_sdk():
    candidates = [
        Path(os.environ.get("ANDROID_HOME", "_")),
        Path(os.environ.get("ANDROID_SDK_ROOT", "_")),
        Path(os.environ.get("LOCALAPPDATA", "_")) / "Android" / "Sdk",
        Path.home() / "AppData" / "Local" / "Android" / "Sdk",
        Path("C:/Android"), Path("C:/android-sdk"),
    ]
    for p in candidates:
        try:
            if p.exists() and (p / "platform-tools").exists(): return p
        except: continue
    return None

def download_with_retry(url, dest, attempts=3):
    for i in range(attempts):
        try:
            urllib.request.urlretrieve(url, dest)
            return True
        except Exception as e:
            warn(f"  Fallito: {e}")
            if i < attempts - 1: time.sleep(2 ** i)
    return False

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

# ============================================================
#  PROJECT CREATION
# ============================================================
def build_kotlin_file_map():
    return {
        f"{PKG_ROOT}/AriaApp.kt":                     ARIA_APP,
        f"{PKG_CORE}/AppConfig.kt":                   APP_CONFIG,
        f"{PKG_DATA}/MessageEntity.kt":                MESSAGE_ENTITY,
        f"{PKG_DATA}/MessageDao.kt":                   MESSAGE_DAO,
        f"{PKG_DATA}/AriaDatabase.kt":                 ARIA_DATABASE,
        f"{PKG_NET}/GroqClient.kt":                    GROQ_CLIENT,
        f"{PKG_CORE}/PhoneActions.kt":                 PHONE_ACTIONS,
        f"{PKG_CORE}/OfflineBrain.kt":                 OFFLINE_BRAIN,
        f"{PKG_CORE}/AriaBrain.kt":                    ARIA_BRAIN,
        f"{PKG_UI}/ChatMessage.kt":                    CHAT_MESSAGE_MODEL,
        f"{PKG_UI}/AriaViewModel.kt":                  ARIA_VIEWMODEL,
        f"{PKG_UI}/AriaOrb.kt":                         ARIA_ORB,
        f"{PKG_UI}/SplashActivity.kt":                 SPLASH_ACTIVITY,
        f"{PKG_UI}/MainActivity.kt":                   MAIN_ACTIVITY,
        f"{PKG_UI}/SettingsActivity.kt":                SETTINGS_ACTIVITY,
        f"{PKG_UI}/HistoryActivity.kt":                 HISTORY_ACTIVITY,
        f"{PKG_VOICE}/WakeWordService.kt":              WAKE_WORD_SERVICE,
        f"{PKG_VOICE}/BootReceiver.kt":                 BOOT_RECEIVER,
    }

def create_project(java_path):
    title("STEP 1 - Creazione progetto ARIA Mobile v9.1")
    if PROJECT_DIR.exists():
        answer = input(f"\n  Directory {PROJECT_DIR.name} esiste. Sovrascrivere? (y/N): ").strip().lower()
        if answer == "y":
            shutil.rmtree(PROJECT_DIR)
            ok("Directory rimossa")
        else:
            ok("Uso directory esistente (i file verranno aggiornati)")

    app_src  = PROJECT_DIR / "app" / "src" / "main"
    kt_src   = app_src / "kotlin"
    res_dir  = app_src / "res"

    step(1, 8, "Gradle build files")
    write_file(PROJECT_DIR / "build.gradle",               BUILD_GRADLE_PROJECT)
    write_file(PROJECT_DIR / "settings.gradle",            SETTINGS_GRADLE)
    write_file(PROJECT_DIR / "app" / "build.gradle",       BUILD_GRADLE_APP)
    write_file(PROJECT_DIR / "app" / "proguard-rules.pro", PROGUARD_RULES)
    write_file(PROJECT_DIR / "gradle" / "wrapper" / "gradle-wrapper.properties", GRADLE_WRAPPER_PROPS)
    ok("Gradle files scritti")

    step(2, 8, "gradlew.bat")
    bat = (f"@echo off\r\nset JAVA_HOME={java_path}\r\nset PATH=%JAVA_HOME%\\bin;%PATH%\r\n"
           f"\"%JAVA_HOME%\\bin\\java.exe\" -classpath \"%~dp0gradle\\wrapper\\gradle-wrapper.jar\" "
           f"org.gradle.wrapper.GradleWrapperMain %*\r\n")
    (PROJECT_DIR / "gradlew.bat").write_text(bat, encoding="utf-8")
    ok("gradlew.bat scritto")

    step(3, 8, "Gradle wrapper JAR")
    jar = PROJECT_DIR / "gradle" / "wrapper" / "gradle-wrapper.jar"
    jar.parent.mkdir(parents=True, exist_ok=True)
    if not jar.exists():
        url = "https://raw.githubusercontent.com/gradle/gradle/v8.6.0/gradle/wrapper/gradle-wrapper.jar"
        if download_with_retry(url, jar):
            ok("Wrapper JAR scaricato")
        else:
            warn("JAR mancante - apri il progetto in Android Studio per generarlo")
    else:
        ok("Wrapper JAR presente")

    step(4, 8, "AndroidManifest.xml")
    write_file(app_src / "AndroidManifest.xml", MANIFEST)
    ok("Manifest scritto (launcher = SplashActivity)")

    step(5, 8, "Kotlin source files")
    kt_files = build_kotlin_file_map()
    for rel, content in kt_files.items():
        write_file(kt_src / rel, content)
    ok(f"{len(kt_files)} file Kotlin scritti")

    step(6, 8, "Layout XML e resources")
    layouts = {
        "activity_settings.xml": LAYOUT_SETTINGS,
        "activity_history.xml":  LAYOUT_HISTORY,
    }
    for name, content in layouts.items():
        write_file(res_dir / "layout" / name, content)
    write_file(res_dir / "values" / "strings.xml", STRINGS_XML)
    write_file(res_dir / "values" / "themes.xml", THEMES_XML)
    write_file(res_dir / "drawable" / "ic_aria.xml", IC_ARIA_XML)
    write_file(app_src / "assets" / "knowledge_pack_it.json", KNOWLEDGE_PACK_JSON)
    ok("Layout, resources e knowledge pack scritti")

    step(7, 8, "gradle.properties + local.properties")
    java_esc = str(java_path).replace("\\", "\\\\")
    sdk = find_android_sdk()
    write_file(PROJECT_DIR / "gradle.properties",
        "org.gradle.jvmargs=-Xmx3072m -XX:MaxMetaspaceSize=512m\n"
        "android.useAndroidX=true\n"
        "kotlin.code.style=official\n"
        f"org.gradle.java.home={java_esc}\n"
        "org.gradle.parallel=true\n"
        "org.gradle.configuration-cache=false\n"
        "android.suppressUnsupportedCompileSdk=34\n")
    if sdk:
        write_file(PROJECT_DIR / "local.properties",
            f"sdk.dir={str(sdk).replace(chr(92), '/')}\n")
        ok(f"SDK: {sdk}")
    else:
        warn("SDK non trovato - configura local.properties manualmente")

    step(8, 8, ".gitignore")
    write_file(PROJECT_DIR / ".gitignore",
        ".gradle/\nbuild/\napp/build/\nlocal.properties\n*.jks\n.idea/\n*.iml\n")
    ok(".gitignore scritto")

    kc = sum(1 for _ in kt_src.rglob("*.kt"))
    rc = sum(1 for _ in res_dir.rglob("*") if _.is_file())
    ok(f"Progetto creato: {kc} Kotlin, {rc} resource files")
    ok(f"Location: {PROJECT_DIR}")

# ============================================================
#  BUILD
# ============================================================
def build_apk(java_path):
    title("STEP 2 - Compilazione APK")
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_path)
    env["PATH"] = str(java_path / "bin") + os.pathsep + env.get("PATH", "")
    sdk = find_android_sdk()
    if sdk:
        env["ANDROID_HOME"] = str(sdk)
        env["ANDROID_SDK_ROOT"] = str(sdk)
    info("Prima volta: Gradle scarica le dipendenze (Compose, Room, Retrofit) - 5-15 min con internet")
    try:
        subprocess.run(
            "gradlew.bat assembleDebug --no-daemon --stacktrace",
            shell=True, cwd=PROJECT_DIR, env=env, check=True
        )
        ok("BUILD SUCCESSFUL")
    except subprocess.CalledProcessError:
        err("Build fallita - vedi log sopra")
        return None
    apk = PROJECT_DIR / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    return apk if apk.exists() else None

def summarise(apk):
    title("STEP 3 - Output")
    dest = DESKTOP / "ARIA-Mobile-v9.1.apk"
    if apk and apk.exists():
        shutil.copy2(apk, dest)
        print(f"\n{C.BOLD}{'='*60}")
        print(f"  APK: {dest}")
        print(f"  Dimensione: {dest.stat().st_size/1_048_576:.1f} MB")
        print(f"{'='*60}{C.RESET}")
        ok("APK pronto!")
    else:
        warn("Compila in Android Studio se il builder da riga di comando fallisce")
        info(str(PROJECT_DIR))

    print(f"\n{C.BOLD}SETUP:{C.RESET}")
    info("1. Installa ARIA-Mobile-v9.1.apk sul telefono")
    info("2. All'avvio vedrai la splash 3D con 'Creator: MaikGost'")
    info("3. In chat tocca l'INGRANAGGIO in alto -> inserisci la Groq API key")
    info("   (usa 'Prova connessione' per verificare che funzioni)")
    info("4. Cambia nome assistente, il tuo nome e la personalita' dell'AI")
    info("5. LA VOCE E' GIA' ATTIVA: l'altoparlante in alto la accende/spegne,")
    info("   l'icona 🔊 sotto ogni risposta la fa riascoltare")
    info("   (se non senti nulla: alza il volume media e controlla che sul")
    info("   telefono sia installata 'Sintesi vocale Google')")
    info("6. Il pulsante ✨ apre i 10 STRUMENTI, il microfono detta i messaggi")
    info("7. In alto nella chat c'e' la SFERA 3D VIVA: cambia colore quando")
    info("   pensa/parla e TOCCANDOLA attivi il microfono per parlarle")
    info("8. ASCOLTO SEMPRE ATTIVO: nelle impostazioni attiva l'interruttore")
    info("   e imposta la parola (es. maik). Concedi microfono e notifiche.")
    info("   Poi anche a schermo bloccato di' \"Hey Maik\" e ti risponde!")
    info("   (tienlo escluso dal risparmio batteria per funzionare sempre)")
    info("9. OFFLINE: attiva 'Modalita' offline' e tocca 'Scarica voce offline'.")
    info("   Cosi' ora, data, calcoli e battute funzionano senza internet.")
    info("10. SE NON TI SENTE: usa '🎤 Prova ascolto' nelle impostazioni.")
    info("    Escludi ARIA dal risparmio batteria (Impostazioni Android > App).")
    info("11. GROQ: inserisci la API key e usa 'Prova connessione'. Groq e'")
    info("    sempre il cervello principale; l'offline e' solo rete di sicurezza.")
    info("12. AI OFFLINE: tocca '⬇ Scarica AI offline' (resta sul telefono),")
    info("    scegli la modalita' (Auto/Online/Offline) e verifica con")
    info("    '🧪 Prova AI offline'.")
    info("13. STREAMING: le risposte appaiono parola per parola; il pulsante")
    info("    rosso STOP ferma la generazione in corso.")
    info("14. CONTROLLO TELEFONO: prova 'apri youtube', 'cerca il meteo',")
    info("    'timer di 5 minuti', 'accendi la torcia', 'manda un whatsapp a...'")
    info("    (anche con 'Hey Maik ...'). Disattivabile dalle impostazioni.")
    info("15. AFFIDABILITA': tocca '🔋 Escludi dal risparmio batteria' cosi'")
    info("    l'ascolto 'Hey Maik' non viene chiuso da Android e riparte al reboot.")
    print()

def main():
    if platform.system() == "Windows":
        os.system("color")
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}")
    print("  ARIA Mobile v9.1 - Builder Android (Kotlin + Compose)")
    print("  Creator: MaikGost")
    print(f"{'='*60}{C.RESET}\n")

    title("Prerequisiti")
    java = find_java()
    if not java:
        err("JDK 17/21 non trovato -> https://adoptium.net")
        sys.exit(1)
    ok(f"JDK: {java}")
    sdk = find_android_sdk()
    if sdk:
        ok(f"Android SDK: {sdk}")
    else:
        warn("Android SDK non trovato (serve per compilare)")
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")

    try:
        create_project(java)
        apk = build_apk(java)
        summarise(apk)
        print(f"{C.OK}{C.BOLD}ARIA Mobile v9.1 - Completato!{C.RESET}\n")
    except KeyboardInterrupt:
        print(f"\n{C.WARN}Interrotto.{C.RESET}")
        sys.exit(0)
    except Exception as e:
        err(f"Errore: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
