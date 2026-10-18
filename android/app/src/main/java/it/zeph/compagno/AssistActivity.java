package it.zeph.compagno;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Log;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * L'assistente vocale: si apre tenendo premuto il tasto Home (se scegli Zeph
 * come «App assistente digitale»), dal riquadro nelle Impostazioni rapide,
 * dalla scorciatoia sull'icona o dal tasto delle cuffie. Il tuo avatar compare
 * sopra un pannello di vetro, ti ascolta subito, esegue il comando e risponde.
 * Il microfono si usa solo mentre questa finestra è aperta.
 */
public class AssistActivity extends Activity implements RecognitionListener, Voce.Ascolto {
    private static final String TAG = "Zeph";
    private static final int REQ_MIC = 51;

    private final Handler h = new Handler(Looper.getMainLooper());
    private final List<String> queue = new ArrayList<>();
    private WebView web;
    private SpeechRecognizer sr;
    private Voce voce;
    private boolean pageReady, listening, micAsked;
    private long lastLevel;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Window w = getWindow();
        w.setStatusBarColor(Color.TRANSPARENT);
        w.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);

        voce = Voce.get(this);
        voce.prepara();
        voce.setAscolto(this);

        web = new WebView(this);
        web.setBackgroundColor(Color.TRANSPARENT);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        web.addJavascriptInterface(new Bridge(), "ZephAndroid");
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage m) {
                Log.d(TAG, "assistente: " + m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                return LocalWeb.intercept(AssistActivity.this, req);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) { return true; }

            @Override
            public void onPageFinished(WebView v, String url) {
                pageReady = true;
                for (String js : queue) v.evaluateJavascript("try{" + js + "}catch(e){}", null);
                queue.clear();
            }

            @Override
            public boolean onRenderProcessGone(WebView v, RenderProcessGoneDetail d) {
                finish(); // poca memoria: si chiude, la riapri quando vuoi
                return true;
            }
        });
        setContentView(web);
        web.loadUrl("https://" + LocalWeb.HOST + "/assistente.html?src=" + source(getIntent()));
        startMic();
    }

    private static String source(Intent i) {
        String a = i != null ? i.getAction() : null;
        if (Intent.ACTION_ASSIST.equals(a)) return "home";
        if (Intent.ACTION_VOICE_COMMAND.equals(a)) return "cuffie";
        return "app";
    }

    @Override
    protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        // richiamato mentre è già aperto: ricomincia ad ascoltare
        js("assistAgain()");
    }

    private void startMic() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            listen();
        } else if (!micAsked) {
            micAsked = true;
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
        }
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        super.onRequestPermissionsResult(req, perms, res);
        if (req != REQ_MIC) return;
        if (res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED) listen();
        else js("assistState('error'," + JSONObject.quote("Senza il microfono non ti sento: scrivimi qui sotto") + ")");
    }

    private void listen() {
        if (isFinishing()) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) { startMic(); return; }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            js("assistState('error'," + JSONObject.quote("Il riconoscimento vocale non c'è: installa o aggiorna l'app Google, o scrivimi") + ")");
            return;
        }
        if (sr == null) {
            sr = SpeechRecognizer.createSpeechRecognizer(this);
            sr.setRecognitionListener(this);
        }
        if (listening) sr.cancel();
        voce.stop(); // mentre ti ascolta non parla
        Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, getPackageName());
        try {
            sr.startListening(i);
            listening = true;
            js("assistState('listening')");
        } catch (RuntimeException e) {
            listening = false;
            js("assistState('error'," + JSONObject.quote("Il microfono è occupato: riprova") + ")");
        }
    }

    private void stopListen() {
        if (sr != null && listening) sr.cancel();
        listening = false;
    }

    private void js(String code) {
        h.post(() -> {
            if (web == null) return;
            if (!pageReady) { queue.add(code); return; }
            web.evaluateJavascript("try{" + code + "}catch(e){}", null);
        });
    }

    // ---------------------------------------------------------------- voce

    @Override public void onVoce(String ev) {
        js("zephTts('" + ("done".equals(ev) ? "end" : ev) + "')");
    }

    // ---------------------------------------------------------------- riconoscimento vocale

    @Override public void onReadyForSpeech(Bundle p) { js("assistState('listening')"); }
    @Override public void onBeginningOfSpeech() { }
    @Override public void onBufferReceived(byte[] buffer) { }
    @Override public void onEndOfSpeech() { }
    @Override public void onEvent(int type, Bundle params) { }

    @Override public void onRmsChanged(float rms) {
        long now = System.currentTimeMillis();
        if (now - lastLevel < 70) return;
        lastLevel = now;
        float v = Math.max(0f, Math.min(1f, (rms + 2f) / 12f)); // da circa -2 dB (silenzio) a 10 dB (voce forte)
        js("assistLevel(" + v + ")");
    }

    @Override public void onPartialResults(Bundle b) {
        ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (r != null && !r.isEmpty() && !r.get(0).isEmpty()) js("assistHeard(" + JSONObject.quote(r.get(0)) + ",false)");
    }

    @Override public void onResults(Bundle b) {
        listening = false;
        ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        js("assistHeard(" + JSONObject.quote(r != null && !r.isEmpty() ? r.get(0) : "") + ",true)");
    }

    @Override public void onError(int error) {
        listening = false;
        if (isFinishing()) return;
        if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
            js("assistState('nomatch')");
        } else if (error == SpeechRecognizer.ERROR_CLIENT) {
            js("assistState('idle')"); // fermato da noi
        } else if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) {
            h.postDelayed(this::listen, 700);
        } else if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
            js("assistState('error'," + JSONObject.quote("Serve il permesso del microfono") + ")");
        } else {
            js("assistState('error'," + JSONObject.quote("Non ti sento bene (c'è internet?): riprova o scrivimi") + ")");
        }
    }

    // ---------------------------------------------------------------- ciclo di vita

    @Override
    protected void onStop() {
        super.onStop();
        // se apri un'altra app (o torni alla home) l'assistente si chiude; la voce finisce la frase
        if (!isChangingConfigurations()) finish();
    }

    @Override
    protected void onDestroy() {
        h.removeCallbacksAndMessages(null);
        if (voce != null) voce.setAscolto(null);
        if (sr != null) { sr.destroy(); sr = null; }
        if (web != null) {
            web.evaluateJavascript("try{dispatchEvent(new Event('pagehide'))}catch(e){}", null);
            web.destroy();
            web = null;
        }
        // il compagno sullo schermo rilegge la memoria (vi siete detti delle cose)
        if (ZephService.running) {
            try {
                startService(new Intent(this, ZephService.class).setAction(ZephService.ACTION_SYNC));
            } catch (Exception ignored) { }
        }
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        js("zephAssist&&zephAssist.close()");
        h.postDelayed(this::finish, 260);
    }

    @Override
    public void finish() {
        super.finish();
        overridePendingTransition(0, android.R.anim.fade_out);
    }

    // ---------------------------------------------------------------- ponte con la pagina

    private class Bridge extends PhoneBridge {
        Bridge() { super(AssistActivity.this); }

        @JavascriptInterface public String info() {
            try {
                return new JSONObject()
                    .put("mic", checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
                    .put("recog", SpeechRecognizer.isRecognitionAvailable(AssistActivity.this))
                    .put("source", source(getIntent()))
                    .toString();
            } catch (JSONException e) {
                return "{}";
            }
        }

        @JavascriptInterface public void listen() { main.post(AssistActivity.this::listen); }

        @JavascriptInterface public void stopListen() { main.post(AssistActivity.this::stopListen); }

        @JavascriptInterface public boolean speak(String text) { return voce.speak(text); }

        @JavascriptInterface public void stopSpeak() { voce.stop(); }

        @JavascriptInterface public void close() { main.post(AssistActivity.this::finish); }

        @JavascriptInterface public void openApp() {
            open(new Intent(AssistActivity.this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP));
        }
    }
}
