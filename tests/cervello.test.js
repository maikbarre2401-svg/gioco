// Test automatici del cervello di Zeph (zeph-core.js): memoria, poteri,
// orari, correttore e cervello AI con risposte finte (nessuna chiamata vera).
// Si lanciano con: node --test tests/
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

// un localStorage finto, come nel browser
const store = {};
global.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
let fetchImpl = null;
global.fetch = (...a) => fetchImpl(...a);

require(path.join(__dirname, '..', 'anthropic-sdk.js')); // globalThis.Anthropic, l'SDK ufficiale
const Z = require(path.join(__dirname, '..', 'zeph-core.js')).ZephCore;

function fresh() {
  for (const k of Object.keys(store)) delete store[k];
  Z.memory.reload();
  return {};
}
const say = (text, ctx) => Z.botReply(text, ctx) || {};

test('comandi di base e refusi', () => {
  const ctx = fresh();
  assert.equal(say('balla', ctx).action, 'dance');
  assert.match(say('bala', ctx).say, /^Ho capito «balla»/);
  assert.equal(say('accendi la torca', ctx).torch, true);
  // le parole comuni non vengono «corrette» (prima «alla» diventava «balla»)
  assert.equal(say('rispondi alla domanda', ctx).action, undefined);
  assert.equal(say('quanto fa 25 per 4', ctx).say, 'Fa 100!');
});

test('memoria: nome, gusti, persone, diario, riassunto', () => {
  const ctx = fresh();
  const n = say('mi chiamo Marco', ctx);
  assert.equal(n.setName, 'Marco');
  ctx.name = 'Marco';
  assert.match(say('mi piace la pizza', ctx).say, /ti piace la pizza/);
  assert.match(say('mia sorella si chiama giulia', ctx).say, /Giulia/);
  assert.match(say('oggi sono andato al mare con mia sorella', ctx).say, /./);
  const s = say('cosa sai di me', ctx).say;
  assert.match(s, /ti chiami Marco/);
  assert.match(s, /ti piace la pizza/);
  assert.match(s, /tua sorella si chiama Giulia/);
  assert.match(say('cosa ho fatto oggi', ctx).say, /sei andato al mare con tua sorella/);
});

test('programmi: il giorno dopo chiede com\'è andata', () => {
  const ctx = fresh();
  say('domani ho un esame di storia', ctx);
  const M = Z.memory.get();
  M.lastSeen = Date.now() - 2 * 864e5;
  M.diary.forEach(e => { if (e.k === 'piano') e.d = Z.dayOf(new Date(Date.now() - 864e5)); });
  const g = Z.memory.greeting(ctx);
  assert.match(g.say, /domani ho un esame di storia/);
  assert.match(g.say, /Com’è andata/);
  assert.equal(ctx.pending, 'listen');
});

test('nome del compagno e risposte insegnate', () => {
  const ctx = fresh();
  assert.equal(say('ti chiamerò Leo', ctx).setPetName, 'Leo');
  assert.match(say('chi sei', ctx).say, /^Sono Leo!/);
  assert.equal(say('ti chiamo dopo', ctx).setPetName, undefined);
  say('se ti dico pizza rispondi margherita', ctx);
  assert.equal(say('pizza', ctx).say, 'margherita');
});

test('dimentica tutto (con conferma)', () => {
  const ctx = fresh();
  say('mi piace il calcio', ctx);
  say('dimentica tutto', ctx);
  assert.equal(ctx.pending, 'forget');
  assert.equal(say('sì', ctx).forgot, true);
  assert.deepEqual(Z.memory.summary(null), []);
});

test('crisi: risposta seria con i numeri di aiuto', () => {
  const ctx = fresh();
  const r = say('a volte vorrei farla finita', ctx).say;
  assert.match(r, /112/);
  assert.match(r, /02 2327 2327/);
});

test('date e ore dette a voce', () => {
  const now = new Date(2026, 9, 8, 21, 47); // giovedì 8 ottobre, sera
  const at = t => new Date(Z.parseWhen(t, now).at);
  assert.deepEqual([at('domani alle 9').getDate(), at('domani alle 9').getHours()], [9, 9]);
  const d = at('domani alle 18 e mezza');
  assert.deepEqual([d.getHours(), d.getMinutes()], [18, 30]);
  assert.equal(at('lunedì').getDay(), 1);
  assert.equal(at('lunedì').getDate(), 12);
  assert.deepEqual([at('il 12 marzo alle 10').getFullYear(), at('il 12 marzo alle 10').getMonth()], [2027, 2]);
  assert.equal(at('alle 8').getDate(), 9); // le 8 sono passate: domattina
  assert.equal(Z.parseWhen('alle 27', now).bad, true);
  assert.equal(Z.parseWhen('ciao come stai', now), null);
});

test('poteri del telefono', () => {
  const ctx = fresh();
  say('mia sorella si chiama giulia', ctx);
  const r = say('ricordami domani alle 9 di chiamare la mamma', ctx).remindAt;
  assert.equal(r.text, 'Chiamare la mamma');
  assert.equal(new Date(r.at).getHours(), 9);
  assert.deepEqual(say('chiama mia sorella', ctx).callName, { name: 'Giulia', alt: undefined, label: 'Giulia (tua sorella)' });
  assert.equal(say('chiama 333 1234567', ctx).dial, '3331234567');
  assert.equal(say('chiama il cane', ctx).dog, 'on');
  assert.equal(say('scrivi a giulia che arrivo tra 5 minuti!', ctx).msgName.text, 'arrivo tra 5 minuti!');
  assert.equal(say('chi mi ha scritto?', ctx).readMsgs, true);
  assert.deepEqual(say('rispondi: arrivo subito', ctx).replyMsg, { to: null, text: 'arrivo subito' });
  assert.equal(say('che impegni ho domani?', ctx).agenda, 1);
  assert.equal(say('aggiungi al calendario dentista domani alle 10', ctx).calAdd.title, 'Dentista');
  assert.ok(say('cosa vedi?', ctx).see);
  assert.equal(say('modalità ologramma', ctx).style, 'ologramma');
  assert.equal(say('modalità neon', ctx).style, 'neon');
  assert.equal(say('diventa d\'oro', ctx).style, 'oro');
  assert.equal(say('torna normale', ctx).style, 'normale');
  assert.equal(say('hai paura dei fantasmi?', ctx).style, undefined);
  assert.match(say('traduci buongiorno in inglese', ctx).open, /translate\.google\.com.*tl=en/);
  assert.equal(say('chi era leonardo da vinci?', ctx).wikiQuery, 'leonardo da vinci');
});

test('conferma prima di rispondere a un messaggio', () => {
  const ctx = fresh();
  ctx.pending = 'confirm'; ctx.pendingAt = Date.now(); ctx.confirmData = { kind: 'reply', text: 'ok' };
  assert.deepEqual(say('sì', ctx).confirmed, { kind: 'reply', text: 'ok' });
  ctx.pending = 'confirm'; ctx.pendingAt = Date.now(); ctx.confirmData = { kind: 'reply', text: 'ok' };
  assert.match(say('no', ctx).say, /annullato/);
});

test('Wikipedia: risposta pulita per la voce', async () => {
  fetchImpl = async () => ({ ok: true, json: async () => ({ query: { pages: { 1: { title: 'Leonardo da Vinci',
    extract: 'Leonardo da Vinci (Anchiano, 15 aprile 1452 – Amboise, 2 maggio 1519) è stato un artista italiano. Fu pittore.' } } } }) });
  const r = await Z.wikiAnswer('leonardo da vinci');
  assert.equal(r.say, 'Leonardo da Vinci è stato un artista italiano. Fu pittore. (L’ho letto su Wikipedia.)');
});

function fakeClaude(handler) {
  const calls = [];
  fetchImpl = async (url, init) => {
    const body = JSON.parse(init.body);
    const headers = init.headers;
    const get = n => (typeof headers.get === 'function' ? headers.get(n) : headers[n]);
    calls.push({ url: String(url && url.url || url), body, beta: get('anthropic-beta') });
    return handler(body);
  };
  return calls;
}
const J = (status, o) => new Response(JSON.stringify(o), { status, headers: { 'content-type': 'application/json', 'request-id': 'req_test' } });
const msg = content => J(200, { id: 'msg', type: 'message', role: 'assistant', model: 'claude-opus-5-5', stop_reason: 'end_turn',
  content, usage: { input_tokens: 10, output_tokens: 5 } });

test('cervello AI: richiesta, risposta strutturata, memoria', async () => {
  const ctx = fresh();
  ctx.name = 'Marco';
  const calls = fakeClaude(() => msg([{ type: 'text', text: JSON.stringify({ reply: 'Ciao Marco! Come stai?', action: 'wave', remember: ['ti piace il calcio'] }) }]));
  Z.ai.setKey('sk-ant-api03-test-test-test-test-test');
  assert.equal(Z.ai.enabled(), true);
  const r = await Z.ai.ask('ciao!', ctx, 'offline');
  assert.deepEqual([r.say, r.action], ['Ciao Marco! Come stai?', 'wave']);
  const c = calls[0];
  assert.match(c.url, /\/v1\/messages/);
  assert.equal(c.body.model, 'claude-opus-5-5');
  assert.equal(c.body.fallbacks, 'default');
  assert.equal(c.beta, 'server-side-fallback-2026-07-01');
  assert.equal(c.body.output_config.effort, 'low');
  assert.equal(c.body.output_config.format.type, 'json_schema');
  assert.match(c.body.system, /Marco/);
  assert.ok(Z.memory.get().notes.includes('ti piace il calcio'));
  Z.ai.setKey('');
});

test('cervello AI: rifiuto, chiave sbagliata, niente rete', async () => {
  const ctx = fresh();
  Z.ai.setKey('sk-ant-api03-test-test-test-test-test');
  fakeClaude(() => J(200, { id: 'm', type: 'message', role: 'assistant', model: 'claude-opus-5-5', content: [], stop_reason: 'refusal',
    stop_details: { category: null, explanation: 'x' }, usage: { input_tokens: 1, output_tokens: 1 } }));
  assert.equal((await Z.ai.ask('x', ctx, 'offline')).refusal, true);
  fakeClaude(() => J(401, { type: 'error', error: { type: 'authentication_error', message: 'invalid x-api-key' } }));
  assert.equal((await Z.ai.ask('x', ctx, 'offline')).keyError, true);
  fetchImpl = async () => { throw new TypeError('Failed to fetch'); };
  const off = await Z.ai.ask('x', ctx, 'offline');
  assert.equal(off.offline, true);
  assert.match(off.say, /^offline/);
  Z.ai.setKey('');
});

test('cervello AI: gli occhi mandano foto e domanda', async () => {
  const ctx = fresh();
  Z.ai.setKey('sk-ant-api03-test-test-test-test-test');
  const calls = fakeClaude(() => msg([{ type: 'text', text: 'È un basilico!' }]));
  const r = await Z.ai.see('QUJD', 'che pianta è?', ctx);
  assert.equal(r.say, 'È un basilico!');
  const parts = calls[0].body.messages[0].content;
  assert.deepEqual(parts.map(p => p.type), ['image', 'text']);
  assert.equal(parts[0].source.media_type, 'image/jpeg');
  Z.ai.setKey('');
});

test('la chiave incollata in chat non finisce nei ricordi', () => {
  const ctx = fresh();
  const out = say('ecco sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ', ctx);
  assert.ok(out.setAiKey);
  assert.equal(JSON.stringify(Z.memory.get().log).includes('sk-ant'), false);
  Z.ai.setKey('');
});

test('parlato naturale: richieste gentili, numeri e ore a parole', () => {
  const ctx = fresh();
  assert.equal(say('potresti accendere la torcia?', ctx).torch, true);
  assert.equal(say('mi accendi la luce per favore', ctx).torch, true);
  assert.equal(say('ehi zeph, mi dici che ore sono?', ctx).say.indexOf('Sono le'), 0);
  assert.equal(say('mi ricordi tra mezz\'ora di spegnere il forno?', ctx).remind.seconds, 1800);
  assert.equal(say('metti un timer di cinque minuti', ctx).timer.seconds, 300);
  assert.deepEqual(say('mi svegli domani alle sette?', ctx).alarm, { h: 7, m: 0 });
  assert.equal(say('potresti chiamare la mamma?', ctx).callName.name, 'mamma');
  assert.equal(Z.normalizeRequest('puoi ricordarmi domattina di comprare il pane', 'Zeph'), 'ricordami domattina di comprare il pane');
  assert.equal(Z.normalizeRequest('Leo, mi fai una foto?', 'Leo'), 'fammi una foto'); // è una richiesta: niente «?»
  assert.equal(Z.normalizeRequest('oggi sono andato al mare', 'Zeph'), 'oggi sono andato al mare'); // i racconti non si toccano
});

test('date: domattina, domani sera, pomeriggio', () => {
  const now = new Date(2026, 9, 8, 21, 47);
  const at = t => new Date(Z.parseWhen(t, now).at);
  assert.deepEqual([at('domattina').getDate(), at('domattina').getHours()], [9, 9]);
  assert.equal(at('domani sera').getHours(), 20);
  assert.equal(at('domani sera alle 8').getHours(), 20);
  assert.equal(at('domani pomeriggio alle 3').getHours(), 15);
  const r = say('ricordami domani sera di chiamare Luca', fresh()).remindAt;
  assert.equal(r.text, 'Chiamare Luca');
});

test('cervello AI: propone un comando, e solo comandi innocui', async () => {
  const ctx = fresh();
  Z.ai.setKey('sk-ant-api03-test-test-test-test-test');
  fakeClaude(() => msg([{ type: 'text', text: JSON.stringify({ reply: 'Certo!', action: 'none', remember: [], command: 'accendi la torcia' }) }]));
  const r = await Z.ai.ask('ho paura del buio', ctx, 'offline');
  assert.equal(r.command, 'accendi la torcia');
  assert.equal(Z.ai.safeCommand('dimentica tutto'), '');
  assert.equal(Z.ai.safeCommand('togli la chiave'), '');
  assert.equal(Z.ai.safeCommand('sk-ant-123'), '');
  assert.equal(Z.ai.safeCommand('svegliami alle 7'), 'svegliami alle 7');
  Z.ai.setKey('');
});

test('conversazione a voce', () => {
  const ctx = fresh();
  assert.equal(say('parliamo a voce', ctx).talk, true);
  assert.equal(say('facciamo due chiacchiere', ctx).talk, true);
  assert.equal(say('parliamo di calcio', ctx).talk, undefined);
});
