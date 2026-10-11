import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizza, regoleApplicabili, regoleDirette, decidi } from '../src/regole.js';

const info = { piattaforma: 'whatsapp', idContatto: '393331234567', username: undefined, nomeContatto: 'Mario Rossi' };

test('normalizza toglie accenti, maiuscole e spazi doppi', () => {
  assert.equal(normalizza('  Perché   COSTA così?  '), 'perche costa cosi?');
});

test('regole disattivate o per altri contatti/piattaforme vengono escluse', () => {
  const elenco = [
    { nome: 'spenta', attiva: false },
    { nome: 'telegram', solo_piattaforma: 'telegram' },
    { nome: 'altro numero', solo_contatti: ['393339999999'] },
    { nome: 'mio numero', solo_contatti: ['+39 333 123 4567'] },
    { nome: 'per nome', solo_contatti: ['mario rossi'] },
    { nome: 'per tutti' },
  ];
  const nomi = regoleApplicabili(elenco, info).map((r) => r.nome);
  assert.deepEqual(nomi, ['mio numero', 'per nome', 'per tutti']);
});

test('username Telegram con o senza @', () => {
  const elenco = [{ nome: 'u', solo_contatti: ['@Mario_R'] }];
  const tg = { piattaforma: 'telegram', idContatto: '123', username: 'mario_r', nomeContatto: 'Mario' };
  assert.equal(regoleApplicabili(elenco, tg).length, 1);
});

test('regoleDirette: parole chiave, regex, regole sempre valide; le semantiche no', () => {
  const elenco = [
    { nome: 'prezzi', quando_contiene: ['quanto costa'] },
    { nome: 'spam', quando_regex: 'bitcoin|crypto' },
    { nome: 'sempre', istruzioni_per_ai: 'sii gentile' },
    { nome: 'semantica', quando_significa: 'vuole un appuntamento' },
    { nome: 'regex rotta', quando_regex: '(' },
  ];
  assert.deepEqual(
    regoleDirette(elenco, 'Ciao, QUANTO COSTA?').map((r) => r.nome),
    ['prezzi', 'sempre'],
  );
  assert.deepEqual(
    regoleDirette(elenco, 'Investi in Bitcoin').map((r) => r.nome),
    ['spam', 'sempre'],
  );
});

test('decidi: non_rispondere vince, poi risposta fissa, istruzioni sommate', () => {
  assert.equal(decidi([{ rispondi_con: 'x' }, { non_rispondere: true }]).azione, 'ignora');

  const d = decidi([
    { nome: 'a', istruzioni_per_ai: 'uno', avvisami: true },
    { nome: 'b', istruzioni_per_ai: 'due' },
  ]);
  assert.equal(d.azione, 'ai');
  assert.deepEqual(d.istruzioni, ['uno', 'due']);
  assert.equal(d.avvisa, true);

  const f = decidi([{ nome: 'f', rispondi_con: ['ciao', 'salve'] }]);
  assert.equal(f.azione, 'fissa');
  assert.ok(['ciao', 'salve'].includes(f.testoFisso));

  assert.equal(decidi([{ rispondi_con: '' }]).azione, 'ai');
});
