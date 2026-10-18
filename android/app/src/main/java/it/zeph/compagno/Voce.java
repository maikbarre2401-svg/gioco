package it.zeph.compagno;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;

import java.util.Locale;

/**
 * La voce dell'assistente. Vive nell'app e non nella finestra: così quando
 * dici «apri WhatsApp» la finestra si chiude, WhatsApp si apre e la frase
 * «Apro WhatsApp!» finisce lo stesso. Si spegne da sola dopo un minuto di silenzio.
 */
final class Voce {
    /** Chi vuole sapere quando parla (la finestra dell'assistente). */
    interface Ascolto {
        void onVoce(String ev); // "start", "word", "done"
    }

    private static Voce self;

    private final Context app;
    private final Handler h = new Handler(Looper.getMainLooper());
    private TextToSpeech tts;
    private boolean ready, failed;
    private String waiting;
    private int seq;
    private Ascolto ascolto;
    private final Runnable sleep = this::shutdown;

    private Voce(Context c) { app = c.getApplicationContext(); }

    static synchronized Voce get(Context c) {
        if (self == null) self = new Voce(c);
        return self;
    }

    void setAscolto(Ascolto a) { ascolto = a; }

    /** Avvia il motore della voce in anticipo (la prima frase parte prima). */
    void prepara() {
        h.post(() -> { if (tts == null) init(); });
    }

    private void init() {
        failed = false;
        ready = false;
        tts = new TextToSpeech(app, status -> h.post(() -> {
            if (tts == null) return;
            if (status != TextToSpeech.SUCCESS) { failed = true; flushFail(); return; }
            int r = tts.setLanguage(Locale.ITALY);
            if (r < 0) r = tts.setLanguage(Locale.ITALIAN);
            tts.setSpeechRate(1.06f);
            tts.setPitch(1.03f);
            tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override public void onStart(String id) { evento("start"); }
                @Override public void onDone(String id) { if (id.equals("v" + seq)) evento("done"); }
                @Override @Deprecated public void onError(String id) { evento("done"); }
                @Override public void onRangeStart(String id, int start, int end, int frame) { evento("word"); }
            });
            ready = r >= 0;
            failed = !ready;
            if (waiting != null) { String w = waiting; waiting = null; if (ready) speakNow(w); else flushFail(); }
        }));
    }

    private void evento(String ev) {
        h.post(() -> {
            if ("done".equals(ev)) restartSleep();
            if (ascolto != null) ascolto.onVoce(ev);
        });
    }

    private void flushFail() {
        waiting = null;
        if (ascolto != null) ascolto.onVoce("done");
    }

    /** Dice la frase (interrompe quella prima). Restituisce false se il telefono non ha la voce. */
    boolean speak(String text) {
        String clean = text == null ? "" : text.replaceAll("[\\p{So}\\p{Cn}]", "").trim();
        if (clean.isEmpty()) return false;
        h.post(() -> {
            h.removeCallbacks(sleep);
            if (tts == null) init();
            if (failed) { flushFail(); return; }
            if (!ready) { waiting = clean; return; }
            speakNow(clean);
        });
        return true;
    }

    private void speakNow(String clean) {
        tts.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "v" + (++seq));
    }

    void stop() {
        h.post(() -> { waiting = null; if (tts != null) tts.stop(); restartSleep(); });
    }

    private void restartSleep() {
        h.removeCallbacks(sleep);
        h.postDelayed(sleep, 60_000);
    }

    private void shutdown() {
        if (tts != null && !tts.isSpeaking()) {
            tts.shutdown();
            tts = null;
            ready = false;
        } else if (tts != null) {
            restartSleep();
        }
    }
}
