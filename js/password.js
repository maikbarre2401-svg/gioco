window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, copyText, setPressed, humanTime, COLORS } = GL.ui;

  const SETS = {
    up: 'ABCDEFGHJKLMNPQRSTUVWXYZ',
    low: 'abcdefghijkmnopqrstuvwxyz',
    num: '23456789',
    sym: '!#$%&*+-=?@^_~',
  };

  const WORDS = (
    'acqua aereo agosto albero alba allegro alto amico ancora anello angolo anima anno antico ape aprile arancia ' +
    'argento aria arma armadio arte asino astro atlante autunno avvio azzurro bacio bagno balena bambola banco ' +
    'barca basso bello bianco birra bisonte bosco botte braccio brezza brina bruco buio burro bussola cactus ' +
    'caffe calcio caldo campo cane canto capra carbone carta casa castello cavallo cena cervo chiave cielo cigno ' +
    'cinema circo citta coda colle colore cometa conchiglia coniglio corda corvo cosmo cratere cristallo cubo ' +
    'cuore cupola delfino deserto diamante disco dito dolce domino drago duna eco eclissi elefante elica energia ' +
    'estate etere falco faro farfalla fata felce ferro festa fiamma fiume fiore foglia fontana foresta formica ' +
    'fragola freccia freddo fulmine fumo fungo gabbia galassia gatto gelato genio ghiaccio giada giardino giglio ' +
    'giorno giraffa gomma grano grillo grotta gufo icona isola lago lama lampo lana lanterna larice latte leone ' +
    'libro limone lince luce luna lupo magia mago mandorla mare marmo martello maschera mela melodia mercurio ' +
    'meteora miele minuto mirtillo molla mondo montagna mosaico motore mulino muro museo musica nebbia neve ' +
    'nido notte nuvola oasi oceano olio ombra onda oro orso ortica ottobre pace palma panda pane pantera papavero ' +
    'pepe perla pesce piano pietra pigna pino pioggia pirata pixel pizza pollo polvere ponte porto prato prisma ' +
    'pulsar quadro quarzo radar radice ragno rame rana razzo regno rete riccio rifugio robot roccia rosa rubino ' +
    'ruota sabbia sale salice satellite scudo segnale seme sentiero serpente sigillo silenzio sirena sole sonda ' +
    'spada specchio spiga stella strada sughero tamburo tavolo tempesta tempo terra tigre titano topo torre ' +
    'treno trifoglio tuono uccello ulivo uragano uva valle vapore vela veleno vento verde vetro vulcano zaffiro ' +
    'zebra zenit zucca'
  ).split(' ');

  let mode = 'rand';

  function randInt(max) {
    // Uniform integer in [0, max) without modulo bias.
    const limit = Math.floor(0xffffffff / max) * max;
    const buf = new Uint32Array(1);
    do { crypto.getRandomValues(buf); } while (buf[0] >= limit);
    return buf[0] % max;
  }

  function shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) { const j = randInt(i + 1); [arr[i], arr[j]] = [arr[j], arr[i]]; }
    return arr;
  }

  function generateRandom(len, keys) {
    const pool = keys.map(k => SETS[k]).join('');
    const chars = keys.map(k => SETS[k][randInt(SETS[k].length)]); // at least one from each chosen set
    while (chars.length < len) chars.push(pool[randInt(pool.length)]);
    return { pw: shuffle(chars).slice(0, len).join(''), bits: len * Math.log2(pool.length) };
  }

  function generateWords(count) {
    const words = Array.from({ length: count }, () => WORDS[randInt(WORDS.length)]);
    const cap = randInt(count);
    words[cap] = words[cap][0].toUpperCase() + words[cap].slice(1);
    const n = String(randInt(100)).padStart(2, '0');
    return { pw: `${words.join('-')}-${n}`, bits: count * Math.log2(WORDS.length) + Math.log2(count) + Math.log2(100) };
  }

  // 10 billion guesses per second: an offline attack with a gaming GPU against a fast hash.
  const GUESSES = 1e10;
  const crackTime = bits => 2 ** (bits - 1) / GUESSES;

  function strengthColor(bits) {
    if (bits < 36) return COLORS.magenta;
    if (bits < 60) return COLORS.amber;
    if (bits < 80) return COLORS.cyan;
    return COLORS.ok;
  }

  function paintMeter(bar, bits) {
    bar.style.width = `${Math.min(100, (bits / 110) * 100)}%`;
    bar.style.backgroundColor = strengthColor(bits);
  }

  function selectedSets() {
    return [['up', '#pwd-up'], ['low', '#pwd-low'], ['num', '#pwd-num'], ['sym', '#pwd-sym']]
      .filter(([, id]) => $(id).checked).map(([k]) => k);
  }

  function generate() {
    const len = Number($('#pwd-len').value);
    let res;
    if (mode === 'rand') {
      const keys = selectedSets();
      if (!keys.length) { $('#pwd-low').checked = true; keys.push('low'); toast('Serve almeno un tipo di carattere'); }
      res = generateRandom(len, keys);
    } else {
      res = generateWords(len);
    }
    $('#pwd-out').textContent = res.pw;
    paintMeter($('#pwd-gen-bar'), res.bits);
    $('#pwd-gen-info').textContent = `${Math.round(res.bits)} bit · ${humanTime(crackTime(res.bits))}`;
  }

  function setMode(next) {
    mode = next;
    setPressed([$('#pwd-mode-rand'), $('#pwd-mode-words')], next === 'rand' ? $('#pwd-mode-rand') : $('#pwd-mode-words'));
    const range = $('#pwd-len');
    if (next === 'rand') { range.min = 6; range.max = 64; range.value = 20; } else { range.min = 3; range.max = 10; range.value = 5; }
    $('#pwd-sets').hidden = next !== 'rand';
    updateLenLabel();
    generate();
  }

  function updateLenLabel() {
    $('#pwd-len-val').textContent = mode === 'rand' ? $('#pwd-len').value : `${$('#pwd-len').value} parole`;
  }

  /* ---------------- analyzer ---------------- */
  const COMMON = new Set((
    '123456 123456789 12345678 12345 1234567 1234567890 111111 000000 123123 654321 qwerty qwertyuiop asdfgh ' +
    'password password1 passw0rd admin ciao ciaociao amore amoremio tiamo juventus napoli milan inter roma lazio ' +
    'forzanapoli forzajuve francesco andrea giuseppe alessandro marco luca giulia sofia martina chiara iloveyou ' +
    'dragon monkey football calcio abc123 qwerty123 1q2w3e4r 1qaz2wsx letmein welcome sunshine princess'
  ).split(' '));
  const SEQUENCES = ['0123456789', 'abcdefghijklmnopqrstuvwxyz', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm'];

  function analyze(pw) {
    const warn = [];
    if (!pw) return { bits: 0, warn };
    let pool = 0;
    if (/[a-z]/.test(pw)) pool += 26;
    if (/[A-Z]/.test(pw)) pool += 26;
    if (/\d/.test(pw)) pool += 10;
    if (/[^a-zA-Z0-9]/.test(pw)) pool += 33;
    let bits = pw.length * Math.log2(Math.max(pool, 2));
    const lower = pw.toLowerCase();

    if (COMMON.has(lower) || COMMON.has(lower.replace(/[\d!.]+$/, ''))) {
      warn.push('È tra le password più usate: viene provata per prima');
      bits = Math.min(bits, 10);
    }
    if (pw.length < 8) warn.push('Troppo corta: usa almeno 12 caratteri');
    if (/^\d+$/.test(pw)) { warn.push('Solo numeri: si indovina in fretta'); bits = Math.min(bits, pw.length * 3.32); }
    if (/(.)\1{2,}/.test(pw)) { warn.push('Caratteri ripetuti di fila (es. "aaa")'); bits -= 8; }
    for (const seq of SEQUENCES) {
      for (let i = 0; i + 4 <= seq.length; i++) {
        if (lower.includes(seq.slice(i, i + 4))) { warn.push(`Contiene una sequenza da tastiera ("${seq.slice(i, i + 4)}")`); bits -= 10; i = seq.length; }
      }
    }
    if (/(19|20)\d{2}/.test(pw)) { warn.push('Contiene un anno: spesso è una data di nascita'); bits -= 6; }
    if (/^[A-Z][a-z]+\d+[!.]?$/.test(pw)) { warn.push('Schema prevedibile: Parola + numeri'); bits -= 10; }
    return { bits: Math.max(4, bits), warn: [...new Set(warn)] };
  }

  function runAnalyzer() {
    const pw = $('#pwd-test').value;
    const { bits, warn } = analyze(pw);
    paintMeter($('#pwd-test-bar'), bits);
    $('#pwd-test-bits').textContent = pw ? `${Math.round(bits)} bit` : '—';
    $('#pwd-test-time').textContent = pw ? humanTime(crackTime(bits)) : '—';
    const list = $('#pwd-test-warn');
    list.replaceChildren(...warn.map(w => Object.assign(document.createElement('li'), { textContent: w })));
  }

  function init() {
    $('#pwd-new').addEventListener('click', () => { generate(); haptic(); });
    $('#pwd-copy').addEventListener('click', () => {
      copyText($('#pwd-out').textContent, 'Password copiata');
      log('Password generata e copiata', 'ok');
    });
    $('#pwd-len').addEventListener('input', () => { updateLenLabel(); generate(); });
    ['#pwd-up', '#pwd-low', '#pwd-num', '#pwd-sym'].forEach(id => $(id).addEventListener('change', generate));
    $('#pwd-mode-rand').addEventListener('click', () => setMode('rand'));
    $('#pwd-mode-words').addEventListener('click', () => setMode('words'));
    $('#pwd-test').addEventListener('input', runAnalyzer);
    generate();
  }

  GL.password = { init };
})();
