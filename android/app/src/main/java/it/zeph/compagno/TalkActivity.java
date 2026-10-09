package it.zeph.compagno;

import android.Manifest;
import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;

/**
 * Conversazione a voce, senza toccare niente: ascolta, il compagno risponde
 * e, appena ha finito di parlare, ascolta di nuovo. Per finire basta dire
 * «basta» (o «ciao ciao») oppure premere «Fine».
 */
public class TalkActivity extends Activity implements RecognitionListener {
    static final String ACTION_EVENT = "it.zeph.compagno.TALK_EVENT";
    private static final int REQ_MIC = 41;

    private final Handler h = new Handler(Looper.getMainLooper());
    private SpeechRecognizer sr;
    private TextView status, heard, reply;
    private Button pauseBtn;
    private boolean paused, listening, speaking;
    private int silences;
    private final Runnable relisten = this::listen;
    // se la risposta non arriva (niente voce sul telefono, rete lenta…) si torna ad ascoltare
    private final Runnable replyTimeout = () -> { speaking = false; listen(); };

    /** Gli eventi della voce del compagno, mandati dal servizio. */
    private final BroadcastReceiver rx = new BroadcastReceiver() {
        @Override public void onReceive(Context c, Intent i) {
            String ev = i.getStringExtra("ev");
            if ("text".equals(ev)) {
                String t = i.getStringExtra("text");
                if (t != null && !t.startsWith("💭")) reply.setText(Prefs.petName(TalkActivity.this) + ": " + t);
            } else if ("start".equals(ev)) {
                speaking = true;
                h.removeCallbacks(relisten);
                h.removeCallbacks(replyTimeout);
                status.setText("🔊 " + Prefs.petName(TalkActivity.this) + " parla…");
                h.postDelayed(replyTimeout, 30_000);
            } else if ("done".equals(ev)) {
                speaking = false;
                h.removeCallbacks(replyTimeout);
                // aspetta un attimo: a volte dice due frasi di fila
                h.removeCallbacks(relisten);
                if (!paused) h.postDelayed(relisten, 800);
            }
        }
    };

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics()));
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        String pet = Prefs.petName(this);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(18), dp(20), dp(16));
        box.setBackgroundColor(0xFF101827);

        TextView title = new TextView(this);
        title.setText("🎙 Parla con " + pet);
        title.setTextColor(0xFF5EEAD4);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        box.addView(title);
        TextView hint = text("Parla pure: quando ha finito di rispondere ti ascolta di nuovo. Di' «basta» per finire.", 12, 0x99FFFFFF);
        hint.setPadding(0, dp(4), 0, dp(12));
        box.addView(hint);

        status = text("…", 17, Color.WHITE);
        status.setGravity(Gravity.CENTER);
        status.setPadding(dp(12), dp(16), dp(12), dp(16));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xFF1E293B);
        bg.setCornerRadius(dp(14));
        status.setBackground(bg);
        box.addView(status);
        heard = text("", 15, 0xFFEAF2FF);
        heard.setPadding(0, dp(12), 0, 0);
        box.addView(heard);
        reply = text("", 15, 0xFF99F6E4);
        reply.setPadding(0, dp(8), 0, 0);
        box.addView(reply);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.END);
        row.setPadding(0, dp(14), 0, 0);
        pauseBtn = button("⏸ Pausa", 0xFF334155);
        pauseBtn.setOnClickListener(v -> { if (paused) resumeTalk(); else pauseTalk("In pausa: tocca ▶ quando vuoi"); });
        Button end = button("✖ Fine", 0xFF14B8A6);
        end.setOnClickListener(v -> finish());
        row.addView(pauseBtn);
        LinearLayout.LayoutParams ep = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        ep.leftMargin = dp(10);
        row.addView(end, ep);
        box.addView(row);
        setContentView(box);
        if (getWindow() != null) {
            getWindow().setLayout(Math.min(dp(400), getResources().getDisplayMetrics().widthPixels - dp(20)), LinearLayout.LayoutParams.WRAP_CONTENT);
        }

        IntentFilter f = new IntentFilter(ACTION_EVENT);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(rx, f, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(rx, f);

        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) begin();
        else requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        super.onRequestPermissionsResult(req, perms, res);
        if (req != REQ_MIC) return;
        if (res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED) begin();
        else {
            Toast.makeText(this, "Senza il microfono non posso ascoltarti: puoi scrivermi dalla chat", Toast.LENGTH_LONG).show();
            finish();
        }
    }

    private void begin() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Toast.makeText(this, "Il riconoscimento vocale non è disponibile: installa o aggiorna l'app Google", Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        sr = SpeechRecognizer.createSpeechRecognizer(this);
        sr.setRecognitionListener(this);
        listen();
    }

    private void listen() {
        if (paused || sr == null || listening || speaking || isFinishing()) return;
        Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, getPackageName());
        listening = true;
        status.setText("🎙 Ti ascolto…");
        try {
            sr.startListening(i);
        } catch (RuntimeException e) {
            listening = false;
            pauseTalk("Il microfono è occupato: tocca ▶ per riprovare");
        }
    }

    private void pauseTalk(String why) {
        paused = true;
        h.removeCallbacks(relisten);
        if (sr != null && listening) sr.cancel();
        listening = false;
        status.setText(why);
        pauseBtn.setText("▶ Riprendi");
    }

    private void resumeTalk() {
        paused = false;
        silences = 0;
        pauseBtn.setText("⏸ Pausa");
        listen();
    }

    private void handle(String said) {
        silences = 0;
        String t = said.trim();
        if (t.isEmpty()) { h.postDelayed(relisten, 300); return; }
        heard.setText("Tu: " + t);
        String low = t.toLowerCase();
        if (low.matches("^(basta|stop|fine|smetti|chiudi|ciao ciao|fine conversazione|basta così|ho finito)[.!]*$")) {
            status.setText("A dopo! 👋");
            send("ciao, a dopo!");
            h.postDelayed(this::finish, 900);
            return;
        }
        status.setText("💭 …");
        send(t);
        // se non risponde a voce entro un po', si torna comunque ad ascoltare
        h.postDelayed(replyTimeout, 12_000);
    }

    private void send(String text) {
        Intent i = new Intent(this, ZephService.class).setAction(ZephService.ACTION_CHAT).putExtra(ZephService.EXTRA_TEXT, text);
        try {
            startForegroundService(i);
        } catch (Exception e) {
            Toast.makeText(this, "Accendi prima il tuo compagno dall'app", Toast.LENGTH_LONG).show();
        }
    }

    // ---------------------------------------------------------------- riconoscimento vocale

    @Override public void onReadyForSpeech(Bundle p) { status.setText("🎙 Ti ascolto…"); }
    @Override public void onBeginningOfSpeech() { status.setText("🎙 …"); }
    @Override public void onRmsChanged(float rms) { }
    @Override public void onBufferReceived(byte[] buffer) { }
    @Override public void onEndOfSpeech() { status.setText("💭 …"); }

    @Override public void onPartialResults(Bundle b) {
        ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (r != null && !r.isEmpty() && !r.get(0).isEmpty()) heard.setText("Tu: " + r.get(0) + "…");
    }

    @Override public void onResults(Bundle b) {
        listening = false;
        ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        handle(r != null && !r.isEmpty() ? r.get(0) : "");
    }

    @Override public void onError(int error) {
        listening = false;
        if (paused || isFinishing()) return;
        if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
            if (++silences >= 3) pauseTalk("Sono qui quando vuoi: tocca ▶ per parlare");
            else h.postDelayed(relisten, 300);
        } else if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY || error == SpeechRecognizer.ERROR_CLIENT) {
            h.postDelayed(relisten, 900);
        } else if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
            pauseTalk("Serve il permesso del microfono");
        } else {
            pauseTalk("Non ti sento bene (rete?): tocca ▶ per riprovare");
        }
    }

    @Override public void onEvent(int type, Bundle params) { }

    @Override
    protected void onStop() {
        super.onStop();
        // se esci dalla finestra, smette di ascoltare
        if (!isChangingConfigurations()) finish();
    }

    @Override
    protected void onDestroy() {
        h.removeCallbacksAndMessages(null);
        try { unregisterReceiver(rx); } catch (Exception ignored) { }
        if (sr != null) { sr.destroy(); sr = null; }
        super.onDestroy();
    }

    private TextView text(String s, float sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        t.setLineSpacing(0, 1.12f);
        return t;
    }

    private Button button(String s, int color) {
        Button btn = new Button(this);
        btn.setText(s);
        btn.setAllCaps(false);
        btn.setTextColor(Color.WHITE);
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(10));
        btn.setBackground(g);
        btn.setPadding(dp(18), 0, dp(18), 0);
        return btn;
    }
}
