/* I poteri del telefono, uguali per il compagno sullo schermo (overlay.js) e
   per l'assistente vocale (assistente.js): eseguono le risposte del cervello
   (zeph-core.js) con il ponte Android «ZephAndroid». Ogni pagina passa i suoi
   «ganci»: come parlare, quale animazione fare, cosa fare di speciale. */
(function () {
'use strict';

// ---------- la memoria: copiata anche nell'app (per il backup e se la pagina viene azzerata) ----------
const MEM_KEYS = ['zephMemory', 'zephName', 'zephPrefs'];
function memorySnapshot() {
  const o = {};
  try { MEM_KEYS.forEach(k => { const v = localStorage.getItem(k); if (v != null) o[k] = v; }); } catch (e) {}
  return JSON.stringify(o);
}
function restoreMemory(A, force) {
  if (!A || !A.loadMemory) return false;
  try {
    if (!force && localStorage.getItem('zephMemory')) return false;
    const snap = JSON.parse(A.loadMemory() || '{}');
    if (!snap.zephMemory) return false;
    MEM_KEYS.forEach(k => { if (snap[k] != null) localStorage.setItem(k, snap[k]); else localStorage.removeItem(k); });
    ZephCore.memory.reload();
    return true;
  } catch (e) { return false; }
}
function syncMemory(A) {
  restoreMemory(A, false);
  let timer = null;
  ZephCore.memory.setOnSave(() => {
    if (!A || !A.saveMemory) return;
    clearTimeout(timer);
    timer = setTimeout(() => A.saveMemory(memorySnapshot()), 1500);
  });
  // chiudendo la pagina salva subito (l'assistente si chiude spesso)
  window.addEventListener('pagehide', () => { if (A && A.saveMemory) { clearTimeout(timer); A.saveMemory(memorySnapshot()); } });
  return { flush() { if (A && A.saveMemory) { clearTimeout(timer); A.saveMemory(memorySnapshot()); } } };
}

function create(opt) {
  const A = opt.A || null;
  const botCtx = opt.ctx || {};
  const speak = opt.speak;
  const act = opt.act || (() => {});
  const burst = opt.burst || (() => {});
  const thinking = opt.thinking || (() => {});
  const opened = opt.opened || (() => {});

  function phone(o) {
    if (!A) return true;
    try { return !!A.action(JSON.stringify(o)); } catch (e) { return false; }
  }
  // i comandi dell'assistente: "ok", "ok:Nome", "panel", "perm:…", "fail"
  function sys(o) {
    if (!A) return 'ok';
    if (!A.sys) return 'old';
    if (o.type === 'global' && o.what !== 'home') o = Object.assign({ delay: opt.globalDelay || 0 }, o);
    try { return String(A.sys(JSON.stringify(o)) || 'fail'); } catch (e) { return 'fail'; }
  }
  function powers() {
    try { return JSON.parse(A && A.powers ? A.powers() : '{}'); } catch (e) { return {}; }
  }
  const pet = () => ZephCore.memory.petName();

  function batteryReport() {
    try {
      const b = JSON.parse(A ? A.battery() : '{"level":-1}');
      if (b.level < 0) throw new Error('n/d');
      return 'La batteria è al ' + b.level + ' per cento' +
        (b.charging ? ' e si sta caricando!' : b.level < 20 ? '… mettila in carica!' : '!');
    } catch (e) { return 'Non riesco a leggere la batteria del telefono!'; }
  }

  // ---------- comandi di sistema: cosa dire dopo ----------
  const PANNELLI = {
    wifi: 'il Wi-Fi', bluetooth: 'il Bluetooth', dati: 'i dati mobili', nfc: 'l’NFC', aereo: 'la modalità aereo',
    hotspot: 'l’hotspot', posizione: 'la posizione', risparmio: 'il risparmio energetico', scuro: 'il tema scuro', rotazione: 'la rotazione',
  };
  function sysSay(s, r, said) {
    if (r === 'ok') return said;
    if (r.indexOf('ok:') === 0) return r === 'ok:vibrate' ? 'Il silenzioso vero Android non me lo lascia fare: ho messo la vibrazione.' : said;
    if (r === 'perm:access') return 'Per questo mi servono i «Comandi del telefono»: attivali nell’app, sezione «Poteri del telefono». Poi chiedimelo di nuovo!';
    if (r === 'perm:settings') return 'Per farlo da solo mi serve il permesso «Modifica impostazioni di sistema»: lo dai dall’app, sezione «Poteri del telefono». Intanto ti ho aperto le impostazioni.';
    if (r === 'perm:dnd') return 'Per il «non disturbare» dammi l’accesso alle notifiche nell’app, sezione «Poteri del telefono». Intanto ti ho aperto le impostazioni.';
    if (r === 'panel') {
      const n = PANNELLI[s.what] || 'le impostazioni';
      return s.on === null || s.on === undefined ? 'Ecco ' + n + '!'
        : 'Ti ho aperto ' + n + ': tocca l’interruttore (Android non lascia farlo alle app da sole).';
    }
    if (r === 'old') return 'Per questo aggiorna l’app Zeph all’ultima versione!';
    switch (s.type) {
      case 'navigate': case 'maps': return 'Non trovo un’app di mappe sul telefono…';
      case 'play': return s.app ? 'Non trovo ' + ({ spotify: 'Spotify', youtube: 'YouTube', ytmusic: 'YouTube Music', amazonmusic: 'Amazon Music', deezer: 'Deezer' }[s.app] || 'quell’app') + ' sul telefono…' : 'Non trovo un’app per la musica…';
      case 'camera': return 'Non trovo la fotocamera…';
      case 'global': return 'Questo il tuo telefono non me lo lascia fare (serve Android 9 o più nuovo).';
      default: return 'Uffa, questo non ci sono riuscito.';
    }
  }
  function runSys(out) {
    const s = out.sys;
    const r = sys(s);
    const extern = /^(?:navigate|maps|play|camera|alarms|alarmOff|setting)$/.test(s.type) || r === 'panel' || r === 'perm:settings' || r === 'perm:dnd';
    out.say = sysSay(s, r, out.say);
    if (s.type === 'global' && (r === 'ok') && s.what !== 'home') opened('global');
    else if ((r === 'ok' || r.indexOf('ok:') === 0 || r === 'panel' || r === 'perm:settings' || r === 'perm:dnd') && (extern || s.what === 'home')) opened('app');
    return r;
  }

  // ---------- promemoria, agenda, buongiorno ----------
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function remindersReport() {
    let list = [];
    try { list = JSON.parse(A && A.reminders ? A.reminders() : '[]'); } catch (e) {}
    list = list.filter(r => r.at > Date.now() - 60e3).sort((a, b) => a.at - b.at);
    if (!list.length) return 'Non hai promemoria. Dimmi tipo «ricordami domani alle 9 di chiamare la mamma».';
    return 'Hai ' + plural(list.length, 'promemoria', 'promemoria') + ': ' +
      list.slice(0, 5).map(r => ZephCore.whenLabel(r.at) + ', ' + r.text).join('; ') + '.';
  }
  function eventsOf(offset) {
    try { return JSON.parse(A && A.events ? A.events(offset) : '{"error":"perm"}'); } catch (e) { return []; }
  }
  function agendaReport(offset) {
    const quando = offset === 0 ? 'Oggi' : offset === 1 ? 'Domani' : 'Dopodomani';
    const ev = eventsOf(offset);
    const day = (() => { const d = new Date(); d.setDate(d.getDate() + offset); return ZephCore.dayOf(d); })();
    const piani = ZephCore.memory.get().diary.filter(e => e.k === 'piano' && e.d === day).map(e => '«' + e.t + '»');
    if (ev && ev.error === 'perm') {
      return 'Per leggere l’agenda dammi il permesso nell’app, sezione «Poteri del telefono».' +
        (piani.length ? ' Però mi avevi detto: ' + piani.join(', ') + '.' : '');
    }
    const items = (Array.isArray(ev) ? ev : []).map(e => (e.allDay ? 'tutto il giorno' : ZephCore.whenLabel(e.begin).replace(/^\S+\s/, '')) + ' ' + e.title);
    if (!items.length && !piani.length) return quando + ' non hai impegni in agenda. Giornata libera!';
    return quando + (items.length ? ' hai ' + plural(items.length, 'impegno', 'impegni') + ': ' + items.join(', ') + '.' : ' l’agenda è vuota.') +
      (piani.length ? ' E mi avevi detto: ' + piani.join(', ') + '.' : '');
  }
  let briefingBusy = false;
  function briefing(onDemand) {
    if (briefingBusy) return;
    briefingBusy = true;
    const h = new Date().getHours();
    const nome = botCtx.name ? ', ' + botCtx.name : '';
    const parts = [(h < 12 ? 'Buongiorno' : h < 18 ? 'Ciao' : 'Buonasera') + nome + '! ' +
      'Oggi è ' + new Date().toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' }) + '.'];
    const city = (() => { try { return JSON.parse(localStorage.getItem('zephPrefs') || '{}')['città']; } catch (e) { return null; } })();
    const meteo = city ? Promise.race([ZephCore.weatherReport({ city, when: 'oggi' }), new Promise(r => setTimeout(() => r(null), 6000))]) : Promise.resolve(null);
    meteo.then(w => {
      if (w && w.code !== undefined) parts.push(w.say);
      const ag = agendaReport(0);
      if (!/permesso/.test(ag) || onDemand) parts.push(ag);
      let rem = [];
      try { rem = JSON.parse(A && A.reminders ? A.reminders() : '[]'); } catch (e) {}
      const today = ZephCore.dayOf();
      rem = rem.filter(r => ZephCore.dayOf(new Date(r.at)) === today && r.at > Date.now());
      if (rem.length) parts.push('Promemoria di oggi: ' + rem.map(r => ZephCore.whenLabel(r.at).replace(/^oggi /, '') + ' ' + r.text).join(', ') + '.');
      const bd = ZephCore.daysUntil('compleanno');
      if (/È OGGI/.test(bd)) parts.push(bd);
      else if (/^Manca 1 giorno|^Mancano [2-7] giorni/.test(bd)) parts.push(bd);
      if (!city && onDemand) parts.push('Se mi dici «la mia città è …» ti dico anche il meteo.');
      act('wave');
      speak(parts.join(' '));
      briefingBusy = false;
    });
  }

  // ---------- rubrica: chiamate e messaggi ----------
  function contactOf(name) {
    try { return JSON.parse(A && A.contact ? A.contact(name) : '{"error":"perm"}'); } catch (e) { return { error: 'none' }; }
  }
  function lookupPerson(p) {
    let c = contactOf(p.name);
    if (c.error === 'none' && p.alt) c = contactOf(p.alt);
    return c;
  }
  // con il permesso delle chiamate chiede «Chiamo Giulia?» e, dopo il tuo sì, chiama davvero
  function askCall(name, number) {
    botCtx.pending = 'confirm';
    botCtx.pendingAt = Date.now();
    botCtx.confirmData = { kind: 'call', name, number };
    speak('Chiamo ' + name + '? Dimmi sì o no.', '📞 Chiamo ' + name + '? (sì / no)');
  }
  function callByName(p) {
    const c = lookupPerson(p);
    if (c.error === 'perm') {
      phone({ type: 'dial', number: '' });
      opened('app');
      speak('Per chiamare per nome dammi il permesso della rubrica nell’app. Intanto ti apro il telefono!');
      return;
    }
    if (c.error) { speak('Non trovo «' + p.label + '» nella rubrica… Come l’hai salvato?'); return; }
    if (powers().call) { askCall(c.name, c.number); return; }
    if (!phone({ type: 'dial', number: c.number })) { speak('Non riesco ad aprire il telefono per chiamare.'); return; }
    opened('app');
    act('wave');
    speak('Ecco ' + c.name + ': premi il tasto verde per chiamare!');
  }
  // numero in formato internazionale per WhatsApp (i cellulari italiani senza prefisso diventano +39)
  function intlNumber(n) {
    const d = String(n).replace(/[^\d+]/g, '');
    if (d.indexOf('+') === 0) return d.slice(1);
    if (d.indexOf('00') === 0) return d.slice(2);
    if (/^3\d{8,9}$/.test(d)) return '39' + d;
    return d;
  }
  function messageByName(p) {
    const c = lookupPerson(p);
    if (c.error === 'perm') { speak('Per scrivere a qualcuno per nome dammi il permesso della rubrica nell’app, sezione «Poteri del telefono».'); return; }
    if (c.error) { speak('Non trovo «' + p.label + '» nella rubrica…'); return; }
    const wa = 'whatsapp://send?phone=' + intlNumber(c.number) + '&text=' + encodeURIComponent(p.text);
    if (phone({ type: 'appUrl', url: wa })) { opened('app'); speak('Ti ho preparato il messaggio per ' + c.name + ' su WhatsApp: premi invia!'); return; }
    if (phone({ type: 'sms', number: c.number, text: p.text })) { opened('app'); speak('Ti ho preparato l’SMS per ' + c.name + ': premi invia!'); return; }
    speak('Non riesco ad aprire né WhatsApp né i messaggi…');
  }
  function messagesList() {
    try { return JSON.parse(A && A.messages ? A.messages() : '{"error":"perm"}'); } catch (e) { return []; }
  }
  function messagesReport() {
    const list = messagesList();
    if (list && list.error === 'perm') return 'Per sapere chi ti scrive dammi l’accesso alle notifiche nell’app, sezione «Poteri del telefono».';
    if (!list.length) return 'Nessun messaggio nuovo da quando sono acceso!';
    const top = list.slice(0, 3).map(m => m.who + ' su ' + m.app + (m.ago > 0 ? ', ' + (m.ago < 60 ? m.ago + ' minuti fa' : 'un po’ di tempo fa') : '') + ': «' + m.text.slice(0, 120) + '»');
    return (list.length === 1 ? 'Ti ha scritto ' : 'Ultimi messaggi: ') + top.join('. ') + '. Per rispondere dimmi «rispondi: …».';
  }
  function askReply(r) {
    const target = A && A.peekReply ? A.peekReply(r.to || '') : '';
    if (!target) {
      const list = messagesList();
      speak(list && list.error === 'perm' ? 'Per rispondere ai messaggi dammi l’accesso alle notifiche nell’app.'
        : 'Non trovo un messaggio a cui rispondere' + (r.to ? ' di «' + r.to + '»' : '') + '. Le risposte funzionano sui messaggi arrivati da quando sono acceso.');
      return;
    }
    const [who, app] = target.split('|');
    botCtx.pending = 'confirm';
    botCtx.pendingAt = Date.now();
    botCtx.confirmData = { kind: 'reply', to: r.to || '', text: r.text, who };
    speak('Rispondo a ' + who + ' su ' + app + ': «' + r.text + '». Lo mando? Dimmi sì o no.', '✉️ A ' + who + ': «' + r.text + '» — lo mando? (sì / no)');
  }
  function doConfirmed(d) {
    if (!d) return;
    if (d.kind === 'reply') {
      const done = A && A.reply ? A.reply(d.to, d.text) : '';
      if (done) { act('jump'); speak('Inviato a ' + done.split('|')[0] + '!'); }
      else speak('Non ci sono riuscito: forse quel messaggio non si può più rispondere dalla notifica.');
    } else if (d.kind === 'call') {
      const r = sys({ type: 'call', number: d.number });
      if (r === 'ok') { opened('app'); speak('Chiamo ' + d.name + '!'); }
      else if (r === 'perm:call') { opened('app'); speak('Ti ho aperto il telefono con ' + d.name + ': premi il tasto verde.'); }
      else if (phone({ type: 'dial', number: d.number })) { opened('app'); speak('Ecco ' + d.name + ': premi il tasto verde per chiamare!'); }
      else speak('Non riesco ad aprire il telefono per chiamare.');
    }
  }

  // ---------- il cervello proposto dall'AI: passa dagli stessi controlli dei tuoi comandi ----------
  function runAiCommand(cmd) {
    if (!cmd) return false;
    const out = ZephCore.botReply(cmd, botCtx);
    if (!out || out.aiQuery || out.generic) return false;
    respondWith(out, true);
    return true;
  }

  function respond(text) {
    const out = ZephCore.botReply(String(text || ''), botCtx);
    if (out) respondWith(out, false);
    return out;
  }

  function respondWith(out, fromAI) {
    if (out.setPetName && A && A.setPetName) A.setPetName(out.setPetName);
    if (out.party) burst(24);
    // quello che è solo di questa pagina (camminare, volare, la musica di Zeph…)
    if (opt.local && opt.local(out) === true) return;
    if (out.setName) { try { localStorage.setItem('zephName', out.setName); } catch (e) {} botCtx.name = out.setName; }
    if (out.whoami) {
      out.say = botCtx.name ? 'Ti chiami ' + botCtx.name + '! Come potrei dimenticarlo?'
        : 'Non me l’hai ancora detto! Dimmi «mi chiamo…» e me lo ricorderò.';
    }
    if (out.setPref) {
      try {
        const p = JSON.parse(localStorage.getItem('zephPrefs') || '{}');
        p[out.setPref.k] = out.setPref.v;
        localStorage.setItem('zephPrefs', JSON.stringify(p));
      } catch (e) {}
    }
    if (out.getPref) {
      let p = {};
      try { p = JSON.parse(localStorage.getItem('zephPrefs') || '{}'); } catch (e) {}
      out.say = p[out.getPref] ? 'Il tuo ' + out.getPref + ' preferito è ' + p[out.getPref] + '!'
        : 'Non me l’hai ancora detto! Dimmi «il mio ' + out.getPref + ' preferito è …»';
    }
    // app vere del telefono: prima quella installata con quel nome, poi i protocolli, poi il sito
    if (out.appName || out.appUrl || out.app || out.open) {
      let ok = false;
      if (out.appName) {
        const r = sys({ type: 'launch', name: out.appName });
        if (r.indexOf('ok') === 0) { ok = true; if (r.indexOf('ok:') === 0) out.say = 'Apro ' + r.slice(3) + '!'; else if (out.appSay) out.say = out.appSay; }
      }
      if (!ok && out.appUrl) ok = phone({ type: 'appUrl', url: out.appUrl });
      if (!ok && out.app) ok = phone({ type: 'app', id: out.app });
      if (!ok && out.open) ok = phone({ type: 'url', url: out.open });
      if (!ok) out.say = 'Uffa, sul telefono questa non la trovo: forse l’app non è installata.';
      else opened('app');
    }
    if (out.sys) runSys(out);
    else if (out.photo) {
      // «fai una foto»: sul telefono apre la fotocamera vera
      const r = sys({ type: 'camera', front: false });
      out.say = r === 'ok' ? 'Ti apro la fotocamera: mettiti in posa!' : 'Non trovo la fotocamera…';
      if (r === 'ok') opened('app');
    }
    if (out.volume) {
      phone({ type: 'volume', dir: out.volume });
      out.say = out.say.replace(/del PC/g, 'del telefono');
    }
    if (out.torch !== undefined && !phone({ type: 'torch', on: out.torch })) {
      out.say = 'Uffa, su questo telefono non riesco a usare la torcia.';
    }
    if (out.alarm && !phone({ type: 'alarm', h: out.alarm.h, m: out.alarm.m })) {
      out.say = 'Non riesco a puntare la sveglia: c’è l’app Orologio sul telefono?';
    }
    if (out.timer) {
      // il timer vero dell'Orologio suona anche se Zeph è chiuso: allora niente doppione
      if (phone({ type: 'timer', seconds: out.timer.seconds })) {
        delete out.remind;
        out.say += ' L’ho messo anche nell’Orologio del telefono.';
      }
    }
    if (out.dial !== undefined) {
      const num = String(out.dial || '');
      // un numero detto a voce: con il permesso delle chiamate chiede conferma e chiama (mai le emergenze)
      if (num.length >= 5 && powers().call) { askCall(num.replace(/^(\+?\d{3})(\d{3})(\d+)$/, '$1 $2 $3'), num); return; }
      if (!phone({ type: 'dial', number: num })) out.say = 'Non riesco ad aprire il telefono per chiamare.';
      else opened('app');
    }
    if (out.media) {
      if (opt.media) opt.media(out.media);
      phone({ type: 'media', key: out.media });
    }
    if (out.weatherQuery) {
      speak(ZephCore.pick(['Un attimo che guardo fuori…', 'Controllo il cielo…', 'Vediamo cosa dicono le nuvole…']));
      ZephCore.weatherReport(out.weatherQuery).then(r => {
        if (r.kind === 'rain' || r.kind === 'snow') act('stretch');
        else if (r.kind === 'clear') act('wave');
        speak(r.say);
      });
    }
    if (out.battery) out.say = batteryReport();
    if (out.remind) {
      // promemoria vero (lo tiene Android: suona anche se chiudi Zeph); altrimenti un timer della pagina
      const r = out.remind;
      if (!(A && A.remindAt && A.remindAt(Date.now() + r.seconds * 1000, r.text) > 0)) {
        setTimeout(() => { act('jump'); speak('Ehi! Promemoria: ' + r.text); if (A) A.remind(r.text); }, r.seconds * 1000);
      }
    }
    if (out.remindAt) {
      const r = out.remindAt;
      if (A && A.remindAt) {
        if (A.remindAt(r.at, r.text) <= 0) out.say = 'Uffa, non sono riuscito a segnare il promemoria (forse ne hai già tanti?).';
      } else if (r.at - Date.now() < 864e5) {
        setTimeout(() => { act('jump'); speak('Ehi! Promemoria: ' + r.text); }, r.at - Date.now());
      }
    }
    if (out.listReminders) out.say = remindersReport();
    if (out.clearReminders && A && A.clearReminders) A.clearReminders();
    if (out.calAdd) {
      if (!phone({ type: 'calAdd', title: out.calAdd.title, at: out.calAdd.at })) out.say = 'Non trovo l’app del calendario sul telefono…';
      else opened('app');
    }
    if (out.agenda !== undefined) { speak(agendaReport(out.agenda)); return; }
    if (out.briefing) { briefing(true); return; }
    if (out.callName) { callByName(out.callName); return; }
    if (out.msgName) { messageByName(out.msgName); return; }
    if (out.readMsgs) { speak(messagesReport()); return; }
    if (out.replyMsg) { askReply(out.replyMsg); return; }
    if (out.confirmed) { doConfirmed(out.confirmed); return; }
    if (out.see) {
      if (!ZephCore.ai.enabled()) out.say = 'Per vedere mi serve il cervello AI: metti la tua chiave nell’app, nella sezione 🧠.';
      else if (A && A.openEyes) { A.openEyes(out.see); opened('app'); }
    }
    if (out.wikiQuery) {
      speak(out.say);
      ZephCore.wikiAnswer(out.wikiQuery).then(r => { act('wave'); speak(r.say); });
      return;
    }
    if (out.style && opt.setStyle) opt.setStyle(out.style);
    if (out.talk) {
      if (opt.talk) opt.talk();
      else if (!(A && A.openTalk && (A.openTalk(), true))) out.say = 'Aggiorna l’app per parlare a voce senza mani!';
    }
    if (out.dog) out.say = 'Rocky è rimasto a casa nel computer! Qui sul telefono c’è spazio solo per me.';
    if (out.photoAvatar) {
      if (A && A.openPhoto) { A.openPhoto(); opened('app'); } else out.say = 'Apri l’app e premi «Crea l’avatar con una foto»!';
    }
    if (out.sky || out.weather || out.autoSky !== undefined || out.stars ||
        out.missions || out.fireworks || out.camMode || out.quality || out.ball) {
      out.say = 'Questa la so fare nel mio mondo sul computer! Sul telefono ti aiuto con le app, la musica, il navigatore e tanto altro.';
    }
    // chiacchiere: con il cervello AI risponde Claude (il cervello offline resta di riserva)
    if (out.aiQuery && ZephCore.ai.enabled() && !fromAI) {
      thinking();
      ZephCore.ai.ask(out.aiQuery, botCtx, out.say).then(r => {
        if (runAiCommand(r.command)) return; // il cervello AI ha capito un comando: lo esegue davvero
        const a = r.action || out.action;
        if (a) act(a);
        speak(r.say);
      });
      return;
    }
    if (out.action) act(out.action);
    if (out.say) speak(out.say);
  }

  return { respond, respondWith, runAiCommand, briefing, phone, sys, powers, batteryReport, messagesReport, agendaReport };
}

window.ZephTelefono = { create, syncMemory, restoreMemory, memorySnapshot };
})();
