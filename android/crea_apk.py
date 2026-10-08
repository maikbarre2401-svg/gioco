#!/usr/bin/env python3
"""
Crea l'APK di Zeph per Android, tutto da solo.

    python crea_apk.py                       ->  Zeph.apk con Zeph
    python crea_apk.py --avatar avatar.glb   ->  Zeph.apk con il TUO avatar già dentro
    python crea_apk.py --installa            ->  e lo installa sul telefono collegato via USB

La prima volta scarica in android/.strumenti (circa 1 GB, una volta sola):
Java 17 (se non c'è già), Android SDK e Gradle. Le volte dopo è veloce.
Funziona su Windows, macOS e Linux; serve solo Python 3.8 o più recente.
"""
import argparse
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(QUI)
STRUMENTI = os.path.join(QUI, '.strumenti')
WIN = os.name == 'nt'

GRADLE_VER = '8.9'
CMDLINE_TOOLS = '11076708'
SDK_PACCHETTI = ['platforms;android-34', 'build-tools;34.0.0', 'platform-tools']
APK_DEBUG = os.path.join(QUI, 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk')
APK_FINALE = os.path.join(REPO, 'Zeph.apk')

try:
    sys.stdout.reconfigure(errors='replace')  # niente crash su console vecchie
except Exception:
    pass


def passo(msg):
    print('\n==> ' + msg, flush=True)


def fallisci(msg):
    print('\nERRORE: ' + msg, file=sys.stderr, flush=True)
    sys.exit(1)


# ------------------------------------------------------------------ scaricamenti

def scarica(url, dest):
    if os.path.exists(dest):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + '.parziale'
    print('    scarico ' + url, flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'zeph-crea-apk'})
    with urllib.request.urlopen(req) as r, open(tmp, 'wb') as f:
        totale = int(r.headers.get('Content-Length') or 0)
        fatto, ultimo = 0, -1
        while True:
            blocco = r.read(1 << 20)
            if not blocco:
                break
            f.write(blocco)
            fatto += len(blocco)
            if totale:
                perc = fatto * 100 // totale
                if perc != ultimo and perc % 10 == 0:
                    print('    %3d%%  (%d MB)' % (perc, fatto >> 20), flush=True)
                    ultimo = perc
    os.replace(tmp, dest)
    return dest


def estrai(archivio, dest):
    os.makedirs(dest, exist_ok=True)
    if archivio.endswith('.zip'):
        with zipfile.ZipFile(archivio) as z:
            for info in z.infolist():
                percorso = z.extract(info, dest)
                modo = info.external_attr >> 16
                if modo & 0o111:  # zipfile perde i permessi di esecuzione: li rimettiamo
                    os.chmod(percorso, os.stat(percorso).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    else:
        with tarfile.open(archivio) as t:
            t.extractall(dest)


def rendi_eseguibili(cartella):
    if WIN:
        return
    for radice, _, files in os.walk(cartella):
        if os.path.basename(radice) == 'bin':
            for f in files:
                p = os.path.join(radice, f)
                os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# ------------------------------------------------------------------ Java

def versione_java(java):
    try:
        out = subprocess.run([java, '-version'], capture_output=True, text=True).stderr
    except OSError:
        return 0
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out)
    if not m:
        return 0
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major


def trova_java():
    candidati = []
    if os.environ.get('JAVA_HOME'):
        candidati.append(os.environ['JAVA_HOME'])
    jdk_locale = os.path.join(STRUMENTI, 'jdk')
    if os.path.isdir(jdk_locale):
        for radice, dirs, _ in os.walk(jdk_locale):
            if os.path.exists(os.path.join(radice, 'bin', 'java.exe' if WIN else 'java')):
                candidati.append(radice)
                break
    for home in candidati:
        java = os.path.join(home, 'bin', 'java.exe' if WIN else 'java')
        if versione_java(java) >= 17:
            return home
    sul_path = shutil.which('java')
    if sul_path and versione_java(sul_path) >= 17:
        return os.path.dirname(os.path.dirname(os.path.realpath(sul_path)))
    return None


def scarica_java():
    so = {'Windows': 'windows', 'Darwin': 'mac', 'Linux': 'linux'}.get(platform.system())
    arch = {'AMD64': 'x64', 'x86_64': 'x64', 'arm64': 'aarch64', 'aarch64': 'aarch64'}.get(platform.machine())
    if not so or not arch:
        fallisci('non so scaricare Java per questo sistema: installa Java 17 da https://adoptium.net')
    url = 'https://api.adoptium.net/v3/binary/latest/17/ga/%s/%s/jdk/hotspot/normal/eclipse' % (so, arch)
    archivio = scarica(url, os.path.join(STRUMENTI, 'scaricati', 'jdk17' + ('.zip' if so == 'windows' else '.tar.gz')))
    estrai(archivio, os.path.join(STRUMENTI, 'jdk'))
    rendi_eseguibili(os.path.join(STRUMENTI, 'jdk'))
    home = trova_java()
    if not home:
        fallisci('Java scaricato ma non funziona: installa Java 17 da https://adoptium.net')
    return home


# ------------------------------------------------------------------ Android SDK

def sdk_esistente():
    for var in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        p = os.environ.get(var)
        if p and os.path.isdir(p):
            return p
    return None


def sdkmanager(sdk):
    nome = 'sdkmanager.bat' if WIN else 'sdkmanager'
    for p in (os.path.join(sdk, 'cmdline-tools', 'latest', 'bin', nome),):
        if os.path.exists(p):
            return p
    return None


def prepara_sdk(java_home, sdk):
    os.makedirs(sdk, exist_ok=True)
    if not sdkmanager(sdk):
        so = {'Windows': 'win', 'Darwin': 'mac', 'Linux': 'linux'}[platform.system()]
        url = 'https://dl.google.com/android/repository/commandlinetools-%s-%s_latest.zip' % (so, CMDLINE_TOOLS)
        archivio = scarica(url, os.path.join(STRUMENTI, 'scaricati', 'cmdline-tools.zip'))
        tmp = os.path.join(sdk, 'cmdline-tools', '_tmp')
        shutil.rmtree(tmp, ignore_errors=True)
        estrai(archivio, tmp)
        dest = os.path.join(sdk, 'cmdline-tools', 'latest')
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(os.path.join(tmp, 'cmdline-tools'), dest)
        shutil.rmtree(tmp, ignore_errors=True)
        rendi_eseguibili(dest)
    mancanti = [p for p in SDK_PACCHETTI if not os.path.isdir(os.path.join(sdk, *p.split(';')))]
    if not mancanti:
        return
    env = dict(os.environ, JAVA_HOME=java_home)
    sm = sdkmanager(sdk)
    passo('Accetto le licenze di Android SDK')
    subprocess.run([sm, '--sdk_root=' + sdk, '--licenses'], input='y\n' * 40, text=True, env=env,
                   stdout=subprocess.DEVNULL, check=False)
    passo('Installo ' + ', '.join(mancanti) + ' (qualche minuto)')
    r = subprocess.run([sm, '--sdk_root=' + sdk] + mancanti, input='y\n' * 10, text=True, env=env)
    if r.returncode != 0:
        fallisci('sdkmanager non è riuscito a installare i pacchetti Android')


# ------------------------------------------------------------------ Gradle

def prepara_gradle():
    home = os.path.join(STRUMENTI, 'gradle-' + GRADLE_VER)
    eseguibile = os.path.join(home, 'bin', 'gradle.bat' if WIN else 'gradle')
    if not os.path.exists(eseguibile):
        url = 'https://services.gradle.org/distributions/gradle-%s-bin.zip' % GRADLE_VER
        archivio = scarica(url, os.path.join(STRUMENTI, 'scaricati', 'gradle-%s-bin.zip' % GRADLE_VER))
        estrai(archivio, STRUMENTI)
        rendi_eseguibili(home)
    return eseguibile


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description='Crea Zeph.apk per Android')
    ap.add_argument('--avatar', help='il tuo avatar .glb da mettere dentro l\'app')
    ap.add_argument('--installa', action='store_true', help='installa l\'APK sul telefono collegato via USB')
    ap.add_argument('--ci', action='store_true', help='uso su GitHub Actions (SDK già presente)')
    a = ap.parse_args()

    avatar = None
    if a.avatar:
        avatar = os.path.abspath(a.avatar)
        if not os.path.isfile(avatar):
            fallisci('non trovo il file ' + avatar)
        with open(avatar, 'rb') as f:
            if f.read(4) != b'glTF':
                fallisci(avatar + ' non è un file .glb valido')

    passo('Controllo Java')
    java_home = trova_java()
    if not java_home:
        passo('Java 17 non trovato: lo scarico (una volta sola)')
        java_home = scarica_java()
    print('    Java: ' + java_home)

    sdk = sdk_esistente() if a.ci else (sdk_esistente() or os.path.join(STRUMENTI, 'android-sdk'))
    if not sdk:
        fallisci('su GitHub Actions serve ANDROID_HOME')
    if not a.ci:
        passo('Preparo Android SDK')
        prepara_sdk(java_home, sdk)
    print('    SDK: ' + sdk)
    with open(os.path.join(QUI, 'local.properties'), 'w', encoding='utf-8') as f:
        f.write('sdk.dir=' + sdk.replace('\\', '/') + '\n')

    passo('Preparo Gradle ' + GRADLE_VER)
    gradle = prepara_gradle()

    passo('Creo l\'APK' + (' con il tuo avatar' if avatar else '') + ' (la prima volta qualche minuto)')
    cmd = [gradle, '-p', QUI, 'assembleDebug', '--no-daemon', '--console=plain']
    if avatar:
        cmd.append('-PzephAvatar=' + avatar)
    env = dict(os.environ, JAVA_HOME=java_home, ANDROID_HOME=sdk)
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0 or not os.path.exists(APK_DEBUG):
        fallisci('la compilazione non è riuscita (guarda i messaggi qui sopra)')
    shutil.copyfile(APK_DEBUG, APK_FINALE)
    passo('FATTO! L\'app è qui: ' + APK_FINALE + '  (%.1f MB)' % (os.path.getsize(APK_FINALE) / 1e6))

    if a.installa:
        adb = os.path.join(sdk, 'platform-tools', 'adb.exe' if WIN else 'adb')
        passo('Installo sul telefono (deve essere collegato con il debug USB attivo)')
        r = subprocess.run([adb, 'install', '-r', APK_FINALE])
        if r.returncode != 0:
            fallisci('installazione non riuscita: controlla il cavo e il debug USB')
        print('    Installato! Apri l\'app «Zeph» sul telefono.')
    else:
        print('\nPer metterlo sul telefono: copia Zeph.apk sul telefono (cavo, Drive, WhatsApp a te stesso…)')
        print('e aprilo: Android ti chiederà di permettere l\'installazione da questa fonte.')


if __name__ == '__main__':
    main()
