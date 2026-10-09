#!/usr/bin/env python3
"""
Crea l'APK di Maik Subs per Android, tutto da solo.

    python crea_apk.py              ->  MaikSubs.apk (nella cartella principale del progetto)
    python crea_apk.py --installa   ->  e lo installa sul telefono collegato via USB
    python crea_apk.py --web        ->  prima ricompila l'app dai sorgenti in src/ (serve Node.js)

L'app già compilata è dentro android/app/src/main/assets/www, quindi di solito Node NON serve.

La prima volta scarica in android/.strumenti (circa 1 GB, una volta sola):
Java 17 (se non c'è già), Android SDK e Gradle. Le volte dopo è veloce.
Funziona su Windows, macOS e Linux; serve solo Python 3.8 o più recente.
"""
import argparse
import http.client
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import ssl
import tarfile
import time
import urllib.error
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
APK_FINALE = os.path.join(REPO, 'MaikSubs.apk')
APK_PRONTO = 'https://github.com/maikbarre2401-svg/gioco/releases/tag/maik-subs'
WWW = os.path.join(QUI, 'app', 'src', 'main', 'assets', 'www', 'index.html')

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

def _scarica_python(url, tmp):
    req = urllib.request.Request(url, headers={'User-Agent': 'maik-crea-apk'})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
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
        if totale and fatto < totale:
            raise OSError('scaricamento incompleto (%d di %d MB)' % (fatto >> 20, totale >> 20))


def _scarica_sistema(url, tmp):
    """Il programma di download del sistema (curl, o PowerShell su Windows): usa le impostazioni
    di rete di Windows (proxy, certificati dell'antivirus) e spesso passa dove Python viene bloccato."""
    if os.path.exists(tmp):
        os.remove(tmp)
    curl = shutil.which('curl.exe' if WIN else 'curl')
    if curl:
        print('    provo con curl…', flush=True)
        r = subprocess.run([curl, '-L', '--fail', '-#', '--retry', '3', '--retry-delay', '3', '--connect-timeout', '30',
                            '-A', 'maik-crea-apk', '-o', tmp, url])
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            return True
    if WIN:
        print('    provo con PowerShell…', flush=True)
        comando = ("$ProgressPreference='SilentlyContinue'; "
                   "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; "
                   "Invoke-WebRequest -UseBasicParsing -Uri '%s' -OutFile '%s'" % (url, tmp.replace("'", "''")))
        r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', comando])
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            return True
    return False


def _valido(percorso, nome=None):
    # un antivirus o un proxy a volte restituisce una pagina web al posto del file: la scartiamo
    nome = nome or percorso  # il nome vero (il file temporaneo finisce in .parziale)
    if not os.path.exists(percorso) or os.path.getsize(percorso) == 0:
        return False
    if nome.endswith('.zip'):
        return zipfile.is_zipfile(percorso)
    if nome.endswith('.tar.gz'):
        try:
            with tarfile.open(percorso) as t:
                t.next()
            return True
        except (tarfile.TarError, OSError, EOFError):
            return False
    return True


def scarica(urls, dest, cosa='un file'):
    """Scarica dal primo indirizzo che funziona: 3 tentativi ciascuno, poi il downloader del sistema."""
    if isinstance(urls, str):
        urls = [urls]
    if os.path.exists(dest):
        if _valido(dest):
            return dest
        os.remove(dest)  # rimasto rotto da un tentativo precedente
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + '.parziale'
    for url in urls:
        for tentativo in range(1, 4):
            print('    scarico ' + url + ('' if tentativo == 1 else '  (tentativo %d)' % tentativo), flush=True)
            try:
                _scarica_python(url, tmp)
                if _valido(tmp, dest):
                    os.replace(tmp, dest)
                    return dest
                print('    il file arrivato non è valido', flush=True)
            except (urllib.error.URLError, ssl.SSLError, ConnectionError, TimeoutError, OSError, http.client.HTTPException) as e:
                motivo = getattr(e, 'reason', e)
                print('    interrotto: %s' % motivo, flush=True)
                if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                    break  # qui il file non c'è: inutile riprovare
            time.sleep(2 * tentativo)
        if _scarica_sistema(url, tmp) and _valido(tmp, dest):
            os.replace(tmp, dest)
            return dest
        print('    niente da fare con questo indirizzo, provo il prossimo…', flush=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    fallisci(
        'non riesco a scaricare %s: la connessione viene interrotta.\n'
        'Succede con alcuni antivirus o firewall che controllano le connessioni sicure, con reti di scuola o\n'
        'di lavoro, con alcune VPN, o se la rete è lenta.\n\n'
        'Cosa puoi fare:\n'
        '  1) NON serve crearlo tu: l\'app pronta è qui  %s\n'
        '  2) Riprova più tardi, oppure con un\'altra rete (per esempio l\'hotspot del telefono)\n'
        '  3) Spegni per un attimo il controllo HTTPS/web dell\'antivirus e rilancia\n'
        '  4) Oppure scarica a mano questo file:\n       %s\n     e mettilo qui:\n       %s\n     poi rilancia: lo userò senza scaricarlo di nuovo.'
        % (cosa, APK_PRONTO, urls[0], dest))


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
    est = '.zip' if so == 'windows' else '.tar.gz'
    urls = [
        'https://api.adoptium.net/v3/binary/latest/17/ga/%s/%s/jdk/hotspot/normal/eclipse' % (so, arch),
        # riserva: la stessa Java 17 pubblicata su GitHub
        'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.12%%2B7/OpenJDK17U-jdk_%s_%s_hotspot_17.0.12_7%s' % (arch, so, est),
    ]
    archivio = scarica(urls, os.path.join(STRUMENTI, 'scaricati', 'jdk17' + est), 'Java 17')
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
        archivio = scarica(url, os.path.join(STRUMENTI, 'scaricati', 'cmdline-tools.zip'), 'gli strumenti di Android')
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
        fallisci('sdkmanager non è riuscito a installare i pacchetti Android (spesso è la rete: riprova, o usa\n'
                 'un\'altra connessione). Oppure scarica l\'app già pronta: ' + APK_PRONTO)


# ------------------------------------------------------------------ Gradle

def prepara_gradle():
    home = os.path.join(STRUMENTI, 'gradle-' + GRADLE_VER)
    eseguibile = os.path.join(home, 'bin', 'gradle.bat' if WIN else 'gradle')
    if not os.path.exists(eseguibile):
        nome = 'gradle-%s-bin.zip' % GRADLE_VER
        urls = [
            # services.gradle.org rimanda comunque qui: si va dritti su GitHub, poi le riserve
            'https://github.com/gradle/gradle-distributions/releases/download/v%s.0/%s' % (GRADLE_VER, nome),
            'https://services.gradle.org/distributions/' + nome,
            'https://downloads.gradle.org/distributions/' + nome,
            'https://mirrors.cloud.tencent.com/gradle/' + nome,
        ]
        archivio = scarica(urls, os.path.join(STRUMENTI, 'scaricati', nome), 'Gradle ' + GRADLE_VER)
        estrai(archivio, STRUMENTI)
        rendi_eseguibili(home)
    return eseguibile


# ------------------------------------------------------------------ main

def ricompila_web():
    npm = shutil.which('npm.cmd' if WIN else 'npm')
    if not npm:
        fallisci('per --web serve Node.js (https://nodejs.org). Senza --web uso l\'app già compilata.')
    passo('Installo le librerie di Node (la prima volta qualche minuto)')
    if subprocess.run([npm, 'install'], cwd=REPO).returncode != 0:
        fallisci('npm install non è riuscito')
    passo('Compilo l\'app dai sorgenti (src/)')
    if subprocess.run([npm, 'run', 'build:android'], cwd=REPO).returncode != 0:
        fallisci('la compilazione dell\'app web non è riuscita')


def main():
    ap = argparse.ArgumentParser(description='Crea MaikSubs.apk per Android')
    ap.add_argument('--installa', action='store_true', help='installa l\'APK sul telefono collegato via USB')
    ap.add_argument('--web', action='store_true', help='ricompila prima l\'app da src/ (serve Node.js)')
    ap.add_argument('--ci', action='store_true', help='uso su GitHub Actions (SDK già presente)')
    a = ap.parse_args()

    if a.web:
        ricompila_web()
    if not os.path.exists(WWW):
        fallisci('manca l\'app compilata in android/app/src/main/assets/www: rilancia con --web (serve Node.js)')

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

    passo('Creo l\'APK (la prima volta qualche minuto)')
    cmd = [gradle, '-p', QUI, 'assembleDebug', '--no-daemon', '--console=plain']
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
        print('    Installato! Apri l\'app «Maik Subs» sul telefono.')
    else:
        print('\nPer metterlo sul telefono: copia MaikSubs.apk sul telefono (cavo, Drive, WhatsApp a te stesso…)')
        print('e aprilo: Android ti chiederà di permettere l\'installazione da questa fonte.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        fallisci('interrotto. Rilancia quando vuoi: riparto da dove ero rimasto.')
    except Exception as e:  # niente muri di errori: una spiegazione e cosa fare
        fallisci('qualcosa è andato storto: %s\nRiprova; se continua, l\'app pronta è qui: %s' % (e, APK_PRONTO))
