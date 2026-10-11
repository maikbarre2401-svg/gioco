// Avvio: collega Groq, WhatsApp, Telegram e il pannello di controllo.
import { ENV } from './config.js';
import { AI, descriviErrore } from './ai.js';
import { Memoria } from './memoria.js';
import { stato } from './stato.js';
import { Cervello } from './cervello.js';
import { avviaTelegram } from './telegram.js';
import { avviaWhatsApp } from './whatsapp.js';
import { avviaPannello } from './pannello.js';

console.log('\n🤖 Assistente AI per WhatsApp e Telegram (Groq)\n');

if (!ENV.groqApiKey) {
  console.error('❌ Manca GROQ_API_KEY nel file .env');
  console.error('   1. Crea una chiave gratis su https://console.groq.com/keys');
  console.error('   2. Copia .env.example in .env e incollala dopo GROQ_API_KEY=\n');
  process.exit(1);
}

const ai = new AI(ENV.groqApiKey);
const memoria = new Memoria();
const cervello = new Cervello({ ai, memoria, stato });

ai.verifica()
  .then(({ disponibili, mancanti }) => {
    console.log('✅ Groq collegato');
    stato.impostaPiattaforma('groq', {
      stato: 'connesso',
      errore: mancanti.length ? `modelli non disponibili: ${mancanti.join(', ')}` : null,
    });
    if (mancanti.length) {
      console.warn(`⚠️  Questi modelli non risultano disponibili su Groq: ${mancanti.join(', ')}`);
      console.warn('   Cambiali in config/impostazioni.json. Modelli disponibili ora:');
      console.warn(`   ${disponibili.join(', ')}`);
    }
  })
  .catch((err) => {
    console.error(`❌ Groq: ${descriviErrore(err)}`);
    stato.impostaPiattaforma('groq', { stato: 'errore', errore: descriviErrore(err) });
  });

let telegram = null;
let whatsapp = null;

// Telegram per primo: se configurato, gli avvisi per te arrivano lì
if (ENV.telegramToken) {
  telegram = avviaTelegram({ cervello, stato, memoria });
} else {
  console.log('ℹ️  Telegram non configurato (manca TELEGRAM_BOT_TOKEN nel file .env)');
}

if (ENV.whatsappAttivo) {
  whatsapp = avviaWhatsApp({ cervello, stato });
} else {
  console.log('ℹ️  WhatsApp disattivato (WHATSAPP_ATTIVO=false nel file .env)');
}

avviaPannello({ cervello, stato, memoria, whatsapp });

process.on('unhandledRejection', (err) => {
  console.error('⚠️  Errore non gestito:', err?.message || err);
});

function chiudi() {
  console.log('\n👋 Spegnimento...');
  memoria.salvaOra();
  Promise.resolve(telegram?.ferma())
    .catch(() => {})
    .finally(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}
process.on('SIGINT', chiudi);
process.on('SIGTERM', chiudi);
