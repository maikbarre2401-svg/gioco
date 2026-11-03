// Genera index.html autonomo (un solo file) da src/index.html + css + js.
// Uso: node build.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const src = join(root, 'src');
let html = readFileSync(join(src, 'index.html'), 'utf8');

html = html.replace(/<link rel="stylesheet" href="([^"]+)" data-inline>/g, (_, f) =>
  `<style>\n${readFileSync(join(src, f), 'utf8')}</style>`);
html = html.replace(/<script src="([^"]+)" data-inline><\/script>/g, (_, f) => {
  const js = readFileSync(join(src, f), 'utf8');
  if (/<\/script/i.test(js)) throw new Error(`${f} contiene "</script": romperebbe l'inline`);
  return `<script>\n/* ── ${f} ── */\n${js}</script>`;
});
const stamp = new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
html = html.replace(/__OJO_BUILD__/g, stamp);
html = html.replace('<!DOCTYPE html>', '<!DOCTYPE html>\n<!-- GENERATO da build.mjs: modifica i file in src/ e poi esegui `node build.mjs` -->');
writeFileSync(join(root, 'index.html'), html);
console.log(`index.html: ${(html.length / 1024).toFixed(1)} KB`);
