// Collegamento a Telegram con un bot (creato con @BotFather).
//
// Funziona in due modi:
// 1. Le persone scrivono al tuo bot e lui risponde.
// 2. Telegram Business (serve Telegram Premium): colleghi il bot al TUO
//    account da Impostazioni > Telegram Business > Chatbot, e il bot
//    risponde al posto tuo nelle tue chat private.
import { Bot } from 'grammy';
import { ENV, impostazioni, salvaImpostazioni } from './config.js';

function nomeCompleto(utente) {
  return [utente?.first_name, utente?.last_name].filter(Boolean).join(' ') || utente?.username || 'Sconosciuto';
}

function mediaDi(m) {
  if (m.photo) return { tipo: 'immagine', mime: 'image/jpeg' };
  if (m.voice) return { tipo: 'audio', mime: m.voice.mime_type || 'audio/ogg' };
  if (m.audio) return { tipo: 'audio', mime: m.audio.mime_type || 'audio/mpeg' };
  if (m.document?.mime_type?.startsWith('image/')) return { tipo: 'immagine', mime: m.document.mime_type };
  if (m.video || m.video_note || m.animation) return { tipo: 'video' };
  if (m.sticker) return { tipo: 'sticker' };
  if (m.document) return { tipo: 'documento' };
  if (m.location || m.venue) return { tipo: 'posizione' };
  if (m.contact) return { tipo: 'contatto' };
  return null;
}

export function creaBotTelegram({
  cervello,
  stato,
  memoria,
  token = ENV.telegramToken,
  proprietario = ENV.telegramOwnerId,
  botInfo,
}) {
  const bot = new Bot(token, botInfo ? { botInfo } : {});
  const titolari = new Map(); // business_connection_id -> id del tuo account

  const eProprietario = (ctx) => Boolean(proprietario) && String(ctx.from?.id) === proprietario;

  async function idTitolare(ctx) {
    const id = ctx.businessConnectionId;
    if (!titolari.has(id)) {
      const conn = await ctx.getBusinessConnection();
      titolari.set(id, conn.user.id);
    }
    return titolari.get(id);
  }

  bot.on('business_connection', (ctx) => {
    const c = ctx.businessConnection;
    titolari.set(c.id, c.user.id);
    console.log(
      c.is_enabled
        ? `✅ Telegram Business: bot collegato all'account di ${nomeCompleto(c.user)}`
        : `ℹ️  Telegram Business: bot scollegato dall'account di ${nomeCompleto(c.user)}`,
    );
  });

  // ---- Comandi (solo nella chat con il bot) ----
  const privato = bot.on('message');

  privato.command('start', async (ctx) => {
    const imp = impostazioni();
    const di = imp.nome_proprietario ? ` di ${imp.nome_proprietario}` : '';
    await ctx.reply(`Ciao ${ctx.from?.first_name || ''}! 👋 Sono l'assistente${di}. Scrivimi pure, ti rispondo subito.`);
  });

  privato.command('id', (ctx) => ctx.reply(`Il tuo id Telegram è: ${ctx.from?.id}`));

  privato.command('reset', async (ctx) => {
    memoria.cancella(`telegram:${ctx.chat.id}`);
    await ctx.reply('🧹 Conversazione azzerata, ricominciamo da capo.');
  });

  privato.command(['pausa', 'riprendi', 'stato', 'aiuto'], async (ctx) => {
    if (!eProprietario(ctx)) {
      return ctx.reply(
        proprietario
          ? 'Questo comando è riservato al proprietario.'
          : `Per usare questo comando metti TELEGRAM_OWNER_ID=${ctx.from?.id} nel file .env e riavvia il bot.`,
      );
    }
    const imp = impostazioni();
    const comando = ctx.message.text.slice(1).split(/[\s@]/)[0].toLowerCase();
    if (comando === 'pausa') {
      salvaImpostazioni({ ...imp, attivo: false });
      return ctx.reply('⏸ Bot in pausa: non risponde a nessuno finché non scrivi /riprendi');
    }
    if (comando === 'riprendi') {
      salvaImpostazioni({ ...imp, attivo: true });
      return ctx.reply('▶️ Bot attivo: risponde di nuovo automaticamente');
    }
    if (comando === 'stato') {
      const s = stato.statistiche;
      const wa = stato.piattaforme.whatsapp.stato;
      return ctx.reply(
        `🤖 Bot ${imp.attivo ? 'ATTIVO' : 'IN PAUSA'}\n` +
          `WhatsApp: ${wa}\n` +
          `Ricevuti: ${s.ricevuti} · Risposti: ${s.risposti} · Ignorati: ${s.ignorati} · Errori: ${s.errori}\n` +
          `Chat in pausa: ${stato.elencoPause().length}`,
      );
    }
    return ctx.reply(
      'Comandi del proprietario:\n/pausa - ferma le risposte automatiche\n/riprendi - riattiva\n/stato - statistiche\n/reset - azzera questa conversazione\n/id - mostra il tuo id',
    );
  });

  // ---- Messaggi normali ----
  bot.on(['message', 'business_message'], async (ctx) => {
    const m = ctx.msg;
    const business = Boolean(ctx.update.business_message);
    const chat = m.chat;
    const isGruppo = chat.type === 'group' || chat.type === 'supergroup';
    const chiave = `telegram:${business ? 'business:' : ''}${chat.id}`;
    const media = mediaDi(m);
    const testo = (m.text || m.caption || (m.sticker?.emoji ?? '')).trim();
    if (!testo && !media) return;

    if (business) {
      if (m.sender_business_bot) return; // inviato da un bot (cioè da noi)
      if (m.from?.id === (await idTitolare(ctx))) {
        // hai scritto tu di persona: il bot si fa da parte in questa chat
        cervello.messaggioMio(chiave, testo || `[${media?.tipo}]`);
        return;
      }
    }

    const nomeBot = bot.botInfo.username.toLowerCase();
    const menzionato =
      isGruppo &&
      (testo.toLowerCase().includes(`@${nomeBot}`) || m.reply_to_message?.from?.id === bot.botInfo.id);

    cervello.ricevi({
      piattaforma: 'telegram',
      chiave,
      chatId: String(chat.id),
      idContatto: String(m.from?.id ?? chat.id),
      username: m.from?.username,
      nomeContatto: nomeCompleto(m.from),
      nomeChat: isGruppo ? chat.title : null,
      isGruppo,
      menzionato,
      testo,
      tipoMedia: media?.tipo,
      ora: m.date * 1000,
      scaricaMedia: async () => {
        const file = await ctx.getFile();
        const r = await fetch(`https://api.telegram.org/file/bot${token}/${file.file_path}`);
        if (!r.ok) throw new Error(`download non riuscito (${r.status})`);
        return { buffer: Buffer.from(await r.arrayBuffer()), mime: media?.mime };
      },
      invia: (risposta) =>
        ctx.reply(risposta, isGruppo ? { reply_parameters: { message_id: m.message_id } } : {}),
      staScrivendo: () => ctx.replyWithChatAction('typing'),
      segnaLetto: async () => {
        if (business) await ctx.api.readBusinessMessage(ctx.businessConnectionId, chat.id, m.message_id);
      },
    });
  });

  bot.catch((err) => {
    console.error('❌ Telegram:', err.error?.message || err.message);
  });

  // Avvisi al proprietario in chat privata con il bot
  if (proprietario) {
    cervello.aggiungiNotificatore(async (testo) => {
      if (stato.piattaforme.telegram.stato !== 'connesso') return false;
      await bot.api.sendMessage(proprietario, testo);
      return true;
    });
  }

  return bot;
}

export function avviaTelegram({ cervello, stato, memoria }) {
  const bot = creaBotTelegram({ cervello, stato, memoria });
  stato.impostaPiattaforma('telegram', { stato: 'avvio' });
  bot
    .start({
      allowed_updates: ['message', 'business_message', 'business_connection'],
      onStart: (info) => {
        console.log(`✅ Telegram collegato: @${info.username}`);
        stato.impostaPiattaforma('telegram', { stato: 'connesso', username: info.username });
        bot.api
          .setMyCommands([
            { command: 'start', description: 'Inizia' },
            { command: 'reset', description: 'Azzera la conversazione' },
            { command: 'id', description: 'Mostra il tuo id Telegram' },
          ])
          .catch(() => {});
      },
    })
    .catch((err) => {
      const msg = err?.error_code === 401 ? 'TELEGRAM_BOT_TOKEN non valido' : err.message;
      console.error(`❌ Telegram non avviato: ${msg}`);
      stato.impostaPiattaforma('telegram', { stato: 'errore', errore: msg });
    });

  return { ferma: () => bot.stop() };
}
