package it.zeph.compagno;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.annotation.SuppressLint;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ServiceInfo;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.Icon;
import android.hardware.display.DisplayManager;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.DisplayMetrics;
import android.util.Log;
import android.util.TypedValue;
import android.view.Display;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.animation.AccelerateInterpolator;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Zeph sul telefono: un servizio in primo piano (con la notifica fissa) che
 * tiene una finestrella trasparente sopra tutte le app. Dentro c'è una
 * WebView che disegna il personaggio in 3D (android/web/overlay.js).
 * Per farlo camminare, saltare o volare si sposta la finestra stessa.
 */
public class ZephService extends Service {
    private static final String TAG = "Zeph";
    static final String ACTION_START = "it.zeph.compagno.START";
    static final String ACTION_TOGGLE = "it.zeph.compagno.TOGGLE";
    static final String ACTION_STOP = "it.zeph.compagno.STOP";
    static final String ACTION_CHAT = "it.zeph.compagno.CHAT";
    static final String ACTION_CMD = "it.zeph.compagno.CMD";
    static final String ACTION_RELOAD = "it.zeph.compagno.RELOAD";
    static final String ACTION_AVATAR = "it.zeph.compagno.AVATAR";
    static final String EXTRA_TEXT = "text";
    static final String EXTRA_CMD = "cmd";

    private static final String CH_MAIN = "zeph_main";
    private static final String CH_REMIND = "zeph_promemoria";
    private static final int NOTIF_ID = 7;
    private static final String HOST = "zeph.local";

    static volatile boolean running = false;

    private Handler main;
    private Context ui;          // contesto adatto alle finestre (Android 11+)
    private WindowManager wm;
    private FrameLayout frame;
    private WebView web;
    private WindowManager.LayoutParams lp;
    private TextView bubble;
    private WindowManager.LayoutParams blp;
    private boolean bubbleAdded;

    private TextToSpeech tts;
    private volatile boolean ttsReady;
    private int utterance;

    private boolean hidden;
    private boolean dragging;
    private boolean falling;
    private ValueAnimator fall;
    private float density;
    private int screenW, screenH, winW, winH, groundY;
    private int curX, curLift;
    private int reminderId = 100;
    private BroadcastReceiver screenRx;

    // ---------------------------------------------------------------- ciclo di vita

    @Override
    public void onCreate() {
        super.onCreate();
        main = new Handler(Looper.getMainLooper());
        if (Build.VERSION.SDK_INT >= 30) {
            Display d = getSystemService(DisplayManager.class).getDisplay(Display.DEFAULT_DISPLAY);
            ui = createDisplayContext(d).createWindowContext(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, null);
        } else {
            ui = this;
        }
        wm = ui.getSystemService(WindowManager.class);
        density = getResources().getDisplayMetrics().density;
        createChannels();
        tts = new TextToSpeech(this, status -> {
            if (status != TextToSpeech.SUCCESS) return;
            int r = tts.setLanguage(Locale.ITALY);
            if (r < 0) r = tts.setLanguage(Locale.ITALIAN);
            tts.setSpeechRate(1.04f);
            tts.setPitch(1.05f);
            tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override public void onStart(String id) { js("zephTts('start')"); }
                @Override public void onDone(String id) { js("zephTts('end')"); }
                @Override @Deprecated public void onError(String id) { js("zephTts('end')"); }
                @Override public void onRangeStart(String id, int start, int end, int frame) { js("zephTts('word')"); }
            });
            ttsReady = r >= 0;
        });
        screenRx = new BroadcastReceiver() {
            @Override public void onReceive(Context c, Intent i) {
                boolean on = Intent.ACTION_SCREEN_ON.equals(i.getAction());
                if (!hidden) js("zephVisible(" + on + ")");
            }
        };
        IntentFilter f = new IntentFilter();
        f.addAction(Intent.ACTION_SCREEN_ON);
        f.addAction(Intent.ACTION_SCREEN_OFF);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(screenRx, f, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(screenRx, f);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent != null ? intent.getAction() : null;
        if (ACTION_STOP.equals(action)) {
            Prefs.setRunning(this, false);
            if (Build.VERSION.SDK_INT >= 33) stopForeground(STOP_FOREGROUND_REMOVE);
            else stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        goForeground();
        if (!Settings.canDrawOverlays(this)) {
            // senza il permesso non può apparire: apri l'app per chiederlo
            Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            try { startActivity(open); } catch (Exception ignored) { }
            stopSelf();
            return START_NOT_STICKY;
        }
        running = true;
        Prefs.setRunning(this, true);
        if (frame == null) createOverlay();

        if (ACTION_TOGGLE.equals(action)) setHidden(!hidden);
        else if (ACTION_CHAT.equals(action) && intent.hasExtra(EXTRA_TEXT)) {
            if (hidden) setHidden(false);
            js("zephChat(" + JSONObject.quote(intent.getStringExtra(EXTRA_TEXT)) + ")");
        } else if (ACTION_CMD.equals(action) && intent.hasExtra(EXTRA_CMD)) {
            js("zephCmd(" + JSONObject.quote(intent.getStringExtra(EXTRA_CMD)) + ")");
        } else if (ACTION_AVATAR.equals(action)) {
            js("zephReloadAvatar()");
        } else if (ACTION_RELOAD.equals(action)) {
            destroyOverlay();
            createOverlay();
        }
        return START_STICKY; // se Android lo chiude per memoria, lo fa ripartire
    }

    @Override
    public void onDestroy() {
        running = false;
        try { unregisterReceiver(screenRx); } catch (Exception ignored) { }
        destroyOverlay();
        if (tts != null) tts.shutdown();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public void onConfigurationChanged(Configuration c) {
        super.onConfigurationChanged(c);
        if (frame == null) return;
        measureScreen();
        curX = clampX(curX);
        placeWindow();
        js("zephScreen(" + JSONObject.quote(infoJson()) + ")");
    }

    // ---------------------------------------------------------------- notifica

    private void createChannels() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        NotificationChannel ch = new NotificationChannel(CH_MAIN, "Zeph sullo schermo", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("La notifica fissa per controllare Zeph");
        ch.setShowBadge(false);
        nm.createNotificationChannel(ch);
        NotificationChannel r = new NotificationChannel(CH_REMIND, "Promemoria di Zeph", NotificationManager.IMPORTANCE_HIGH);
        r.setDescription("Quando dici a Zeph «ricordami tra…»");
        nm.createNotificationChannel(r);
    }

    private PendingIntent servicePi(String action, int code) {
        Intent i = new Intent(this, ZephService.class).setAction(action);
        return PendingIntent.getService(this, code, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private Notification buildNotification() {
        Icon icon = Icon.createWithResource(this, R.drawable.ic_stat_zeph);
        PendingIntent openApp = PendingIntent.getActivity(this, 1,
            new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent mic = PendingIntent.getActivity(this, 2,
            new Intent(this, ChatActivity.class).putExtra(ChatActivity.EXTRA_MIC, true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this, CH_MAIN)
            .setSmallIcon(R.drawable.ic_stat_zeph)
            .setContentTitle(hidden ? "Zeph è nascosto" : "Zeph è sul tuo schermo")
            .setContentText(hidden ? "Premi «Mostra» per farlo tornare"
                : "Toccalo per farlo reagire · tienilo premuto per parlargli")
            .setOngoing(true)
            .setShowWhen(false)
            .setContentIntent(openApp)
            .addAction(new Notification.Action.Builder(icon, "🎤 Parla", mic).build())
            .addAction(new Notification.Action.Builder(icon, hidden ? "👁 Mostra" : "🙈 Nascondi",
                servicePi(ACTION_TOGGLE, 3)).build())
            .addAction(new Notification.Action.Builder(icon, "✖ Chiudi", servicePi(ACTION_STOP, 4)).build())
            .build();
    }

    private void goForeground() {
        Notification n = buildNotification();
        if (Build.VERSION.SDK_INT >= 34) startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(NOTIF_ID, n);
    }

    private void refreshNotification() {
        getSystemService(NotificationManager.class).notify(NOTIF_ID, buildNotification());
    }

    private void reminder(String text) {
        Notification n = new Notification.Builder(this, CH_REMIND)
            .setSmallIcon(R.drawable.ic_stat_zeph)
            .setContentTitle("Zeph ⏰")
            .setContentText(text)
            .setAutoCancel(true)
            .build();
        getSystemService(NotificationManager.class).notify(reminderId++, n);
    }

    // ---------------------------------------------------------------- finestre

    private int dp(float v) { return Math.round(v * density); }

    private void measureScreen() {
        Rect b;
        if (Build.VERSION.SDK_INT >= 30) {
            b = wm.getCurrentWindowMetrics().getBounds();
        } else {
            DisplayMetrics m = new DisplayMetrics();
            wm.getDefaultDisplay().getRealMetrics(m);
            b = new Rect(0, 0, m.widthPixels, m.heightPixels);
        }
        screenW = b.width();
        screenH = b.height();
        int navId = getResources().getIdentifier("navigation_bar_height", "dimen", "android");
        int nav = navId > 0 ? getResources().getDimensionPixelSize(navId) : 0;
        if (screenW > screenH) nav = 0; // in orizzontale la barra di solito è di lato
        groundY = screenH - winH - nav - dp(4);
    }

    private int clampX(int x) { return Math.max(0, Math.min(screenW - winW, x)); }

    private String infoJson() {
        try {
            return new JSONObject()
                .put("screenW", screenW).put("screenH", screenH).put("density", density)
                .put("winW", winW).put("winH", winH).put("x", curX)
                .toString();
        } catch (JSONException e) {
            return "{}";
        }
    }

    @SuppressLint({"SetJavaScriptEnabled", "ClickableViewAccessibility"})
    private void createOverlay() {
        float scale = Prefs.scale(this);
        winW = dp(180 * scale);
        winH = dp(260 * scale);
        measureScreen();
        int last = Prefs.lastX(this);
        curX = clampX(last >= 0 ? last : (screenW - winW) / 2);
        curLift = 0;

        web = new WebView(ui);
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
        web.setWebViewClient(new LocalAssets());
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage m) {
                Log.d(TAG, m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
                return true;
            }
        });

        frame = new TouchFrame(ui);
        frame.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        lp = new WindowManager.LayoutParams(winW, winH,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
            PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        lp.x = curX;
        lp.y = groundY;
        if (Prefs.ghost(this)) {
            // modalità fantasma: i tocchi passano attraverso (Android 12+ lo
            // permette solo a finestre con trasparenza almeno del 20%)
            lp.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
            lp.alpha = 0.8f;
        }
        wm.addView(frame, lp);
        frame.setVisibility(hidden ? View.GONE : View.VISIBLE);

        bubble = new TextView(ui);
        bubble.setTextColor(0xFF1E293B);
        bubble.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        bubble.setMaxWidth(dp(250));
        bubble.setPadding(dp(13), dp(9), dp(13), dp(9));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xF8FFFFFF);
        bg.setCornerRadius(dp(14));
        bg.setStroke(dp(1), 0x22000000);
        bubble.setBackground(bg);
        bubble.setElevation(dp(4));
        bubble.setOnClickListener(v -> hideBubble()); // toccalo per chiuderlo
        blp = new WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT);
        blp.gravity = Gravity.TOP | Gravity.START;
        bubbleAdded = false;

        web.loadUrl("https://" + HOST + "/overlay.html");
    }

    private void destroyOverlay() {
        if (fall != null) fall.cancel();
        if (bubble != null && bubbleAdded) {
            try { wm.removeView(bubble); } catch (Exception ignored) { }
        }
        bubbleAdded = false;
        bubble = null;
        if (frame != null) {
            try { wm.removeView(frame); } catch (Exception ignored) { }
            frame = null;
        }
        if (web != null) {
            web.destroy();
            web = null;
        }
    }

    private void placeWindow() {
        if (frame == null || dragging || falling) return;
        lp.x = curX;
        lp.y = groundY - curLift;
        try { wm.updateViewLayout(frame, lp); } catch (Exception ignored) { }
        placeBubble();
    }

    private void placeBubble() {
        if (bubble == null || !bubbleAdded || bubble.getVisibility() != View.VISIBLE) return;
        bubble.measure(View.MeasureSpec.makeMeasureSpec(dp(250), View.MeasureSpec.AT_MOST),
            View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED));
        int bw = bubble.getMeasuredWidth(), bh = bubble.getMeasuredHeight();
        blp.x = Math.max(dp(4), Math.min(screenW - bw - dp(4), lp.x + winW / 2 - bw / 2));
        blp.y = Math.max(dp(24), lp.y + Math.round(winH * 0.1f) - bh);
        try { wm.updateViewLayout(bubble, blp); } catch (Exception ignored) { }
    }

    private void showBubble(String text) {
        if (bubble == null || hidden) return;
        bubble.setText(text);
        bubble.setVisibility(View.VISIBLE);
        if (!bubbleAdded) {
            try { wm.addView(bubble, blp); bubbleAdded = true; } catch (Exception e) { return; }
        }
        placeBubble();
    }

    private void hideBubble() {
        if (bubble != null && bubbleAdded) bubble.setVisibility(View.GONE);
    }

    private void setHidden(boolean h) {
        hidden = h;
        if (frame != null) frame.setVisibility(h ? View.GONE : View.VISIBLE);
        if (h) hideBubble();
        js("zephVisible(" + !h + ")");
        refreshNotification();
    }

    /** Lasciato a mezz'aria: cade fino a terra con la gravità. */
    private void dropToGround() {
        falling = true;
        int from = lp.y;
        int dist = Math.max(0, groundY - from);
        long ms = Math.max(140, Math.min(900, Math.round(Math.sqrt(dist / density) * 55)));
        fall = ValueAnimator.ofInt(from, groundY);
        fall.setDuration(ms);
        fall.setInterpolator(new AccelerateInterpolator(1.6f));
        fall.addUpdateListener(a -> {
            lp.y = (int) a.getAnimatedValue();
            try { wm.updateViewLayout(frame, lp); } catch (Exception ignored) { }
            placeBubble();
        });
        fall.addListener(new AnimatorListenerAdapter() {
            @Override public void onAnimationEnd(Animator a) {
                falling = false;
                dragging = false;
                curX = lp.x;
                curLift = 0;
                Prefs.setLastX(ZephService.this, curX);
                js("zephDrop(" + curX + ")");
            }
        });
        fall.start();
    }

    private void openChat(boolean mic) {
        Intent i = new Intent(this, ChatActivity.class)
            .putExtra(ChatActivity.EXTRA_MIC, mic)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try { startActivity(i); } catch (Exception e) { Log.w(TAG, "chat", e); }
    }

    private void js(String code) {
        main.post(() -> {
            if (web != null) web.evaluateJavascript("try{" + code + "}catch(e){}", null);
        });
    }

    // ---------------------------------------------------------------- tocchi

    /** Prende tutti i tocchi: tap = reagisce, pressione lunga = chat, trascina = sollevalo. */
    private class TouchFrame extends FrameLayout {
        private float downX, downY;
        private int startX, startY;
        private boolean moved, longFired;
        private final int slop;
        private final Runnable longPress = () -> {
            if (!moved) { longFired = true; openChat(false); }
        };

        TouchFrame(Context c) {
            super(c);
            slop = ViewConfiguration.get(c).getScaledTouchSlop();
        }

        @Override public boolean onInterceptTouchEvent(MotionEvent e) { return true; }

        @SuppressLint("ClickableViewAccessibility")
        @Override public boolean onTouchEvent(MotionEvent e) {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    if (fall != null && fall.isRunning()) { fall.cancel(); falling = false; }
                    downX = e.getRawX(); downY = e.getRawY();
                    startX = lp.x; startY = lp.y;
                    moved = false; longFired = false;
                    main.postDelayed(longPress, 550);
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    float dx = e.getRawX() - downX, dy = e.getRawY() - downY;
                    if (!moved && Math.hypot(dx, dy) > slop) {
                        moved = true;
                        dragging = true;
                        main.removeCallbacks(longPress);
                        js("zephGrab()");
                    }
                    if (moved) {
                        lp.x = clampX(Math.round(startX + dx));
                        lp.y = Math.max(0, Math.min(groundY, Math.round(startY + dy)));
                        try { wm.updateViewLayout(frame, lp); } catch (Exception ignored) { }
                        placeBubble();
                    }
                    return true;
                }
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    main.removeCallbacks(longPress);
                    if (moved) dropToGround();
                    else if (!longFired && e.getActionMasked() == MotionEvent.ACTION_UP) js("zephTap()");
                    return true;
                default:
                    return true;
            }
        }
    }

    // ---------------------------------------------------------------- file locali

    /**
     * Serve la pagina, le librerie e l'avatar come se fossero un sito
     * (https://zeph.local/...), così niente esce dal telefono.
     */
    private class LocalAssets extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
            Uri u = req.getUrl();
            if (!HOST.equals(u.getHost())) return notFound(); // niente rete esterna
            String path = u.getPath();
            if (path == null || path.equals("/")) path = "/overlay.html";
            path = path.substring(1);
            if (path.contains("..")) return notFound();
            try {
                InputStream in;
                if (path.equals("avatar.glb")) {
                    File f = new File(getFilesDir(), "avatar.glb");
                    if (f.exists()) in = new FileInputStream(f);
                    else if (Prefs.useBundledAvatar(ZephService.this)) in = getAssets().open("avatar.glb");
                    else return notFound();
                } else {
                    in = getAssets().open(path);
                }
                WebResourceResponse r = new WebResourceResponse(mime(path), "utf-8", in);
                r.setResponseHeaders(headers());
                return r;
            } catch (IOException e) {
                return notFound();
            }
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) { return true; }

        private Map<String, String> headers() {
            Map<String, String> h = new HashMap<>();
            h.put("Access-Control-Allow-Origin", "*");
            h.put("Cache-Control", "no-cache");
            return h;
        }

        private WebResourceResponse notFound() {
            return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", headers(),
                new ByteArrayInputStream(new byte[0]));
        }

        private String mime(String p) {
            if (p.endsWith(".html")) return "text/html";
            if (p.endsWith(".js")) return "application/javascript";
            if (p.endsWith(".glb")) return "model/gltf-binary";
            if (p.endsWith(".png")) return "image/png";
            return "application/octet-stream";
        }
    }

    // ---------------------------------------------------------------- ponte con la pagina

    /** I metodi che overlay.js può chiamare (girano su un thread a parte). */
    private class Bridge {
        @JavascriptInterface public String info() { return infoJson(); }

        @JavascriptInterface public void setPos(int x, int lift) {
            main.post(() -> {
                curX = clampX(x);
                curLift = Math.max(0, Math.min(groundY, lift));
                placeWindow();
            });
        }

        @JavascriptInterface public void bubble(String text) { main.post(() -> showBubble(text)); }

        @JavascriptInterface public void bubbleHide() { main.post(ZephService.this::hideBubble); }

        @JavascriptInterface public boolean speak(String text) {
            if (!ttsReady || hidden) return false;
            String clean = text.replaceAll("[\\p{So}\\p{Cn}]", "");
            return tts.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "z" + (++utterance)) == TextToSpeech.SUCCESS;
        }

        @JavascriptInterface public void stopSpeak() { if (tts != null) tts.stop(); }

        @JavascriptInterface public boolean action(String json) {
            try {
                return PhoneActions.run(ZephService.this, new JSONObject(json));
            } catch (JSONException e) {
                return false;
            }
        }

        @JavascriptInterface public String battery() {
            BatteryManager bm = getSystemService(BatteryManager.class);
            try {
                return new JSONObject()
                    .put("level", bm != null ? bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) : -1)
                    .put("charging", bm != null && bm.isCharging())
                    .toString();
            } catch (JSONException e) {
                return "{\"level\":-1}";
            }
        }

        @JavascriptInterface public void notify(String text) { main.post(() -> reminder(text)); }

        @JavascriptInterface public void openChat() { main.post(() -> ZephService.this.openChat(false)); }
    }
}
