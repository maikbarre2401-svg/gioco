package it.zeph.compagno;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.annotation.SuppressLint;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.RemoteInput;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
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
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.hardware.display.DisplayManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.service.quicksettings.TileService;
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
import android.webkit.RenderProcessGoneDetail;
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

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

import java.util.Locale;

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
    static final String ACTION_READ = "it.zeph.compagno.READ";
    static final String ACTION_REPLY = "it.zeph.compagno.REPLY";
    static final String ACTION_PREFS = "it.zeph.compagno.PREFS";
    static final String ACTION_SAY = "it.zeph.compagno.SAY";
    static final String ACTION_MESSAGE = "it.zeph.compagno.MESSAGE";
    static final String ACTION_MEMORY = "it.zeph.compagno.MEMORY";
    static final String KEY_REPLY = "zeph_reply";
    static final String EXTRA_TEXT = "text";
    static final String EXTRA_CMD = "cmd";

    private static final String CH_MAIN = "zeph_main";
    private static final String CH_REMIND = "zeph_promemoria";
    private static final int NOTIF_ID = 7;

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
    private BroadcastReceiver phoneRx;
    private SensorManager sensors;
    private long lastShake, shakeWindow;
    private int shakeCount;

    /** Scuoti il telefono (tre scossoni in meno di un secondo): il compagno arriva di corsa. */
    private final SensorEventListener shakeListener = new SensorEventListener() {
        @Override public void onSensorChanged(SensorEvent e) {
            float x = e.values[0], y = e.values[1], z = e.values[2];
            double g = Math.sqrt(x * x + y * y + z * z) / SensorManager.GRAVITY_EARTH;
            if (g < 2.3) return;
            long now = SystemClock.uptimeMillis();
            if (now - shakeWindow > 900) { shakeWindow = now; shakeCount = 0; }
            if (++shakeCount >= 3 && now - lastShake > 3000) {
                lastShake = now;
                shakeCount = 0;
                if (!hidden) js("zephShake()");
            }
        }

        @Override public void onAccuracyChanged(Sensor s, int accuracy) { }
    };

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
                @Override public void onStart(String id) { js("zephTts('start')"); talkEvent("start", null); }
                @Override public void onDone(String id) { js("zephTts('end')"); talkEvent("done", null); }
                @Override @Deprecated public void onError(String id) { js("zephTts('end')"); talkEvent("done", null); }
                @Override public void onRangeStart(String id, int start, int end, int frame) { js("zephTts('word')"); }
            });
            ttsReady = r >= 0;
        });
        screenRx = new BroadcastReceiver() {
            @Override public void onReceive(Context c, Intent i) {
                if (Intent.ACTION_USER_PRESENT.equals(i.getAction())) {
                    // telefono sbloccato: magari è ora del buongiorno
                    if (!hidden && Prefs.briefing(ZephService.this)) js("zephUnlock()");
                    return;
                }
                boolean on = Intent.ACTION_SCREEN_ON.equals(i.getAction());
                if (on) startShake(); else stopShake();
                if (!hidden) js("zephVisible(" + on + ")");
            }
        };
        IntentFilter f = new IntentFilter();
        f.addAction(Intent.ACTION_SCREEN_ON);
        f.addAction(Intent.ACTION_SCREEN_OFF);
        f.addAction(Intent.ACTION_USER_PRESENT);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(screenRx, f, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(screenRx, f);

        // quello che succede al telefono: Zeph ci reagisce
        phoneRx = new BroadcastReceiver() {
            @Override public void onReceive(Context c, Intent i) {
                if (isInitialStickyBroadcast()) return; // stato già presente all'avvio: niente commenti
                String a = i.getAction();
                String ev = null;
                if (Intent.ACTION_POWER_CONNECTED.equals(a)) ev = "charger";
                else if (Intent.ACTION_POWER_DISCONNECTED.equals(a)) ev = "unplug";
                else if (Intent.ACTION_BATTERY_LOW.equals(a)) ev = "batteryLow";
                else if (Intent.ACTION_HEADSET_PLUG.equals(a)) ev = i.getIntExtra("state", 0) == 1 ? "headset" : null;
                if (ev != null && !hidden) js("zephEvent('" + ev + "')");
            }
        };
        IntentFilter pf = new IntentFilter();
        pf.addAction(Intent.ACTION_POWER_CONNECTED);
        pf.addAction(Intent.ACTION_POWER_DISCONNECTED);
        pf.addAction(Intent.ACTION_BATTERY_LOW);
        pf.addAction(Intent.ACTION_HEADSET_PLUG);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(phoneRx, pf, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(phoneRx, pf);
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
        boolean wasRunning = running;
        running = true;
        Prefs.setRunning(this, true);
        if (!wasRunning) updateTile();
        if (frame == null) createOverlay();

        if (ACTION_TOGGLE.equals(action)) setHidden(!hidden);
        else if (ACTION_CHAT.equals(action) && intent.hasExtra(EXTRA_TEXT)) {
            if (hidden) setHidden(false);
            js("zephChat(" + JSONObject.quote(intent.getStringExtra(EXTRA_TEXT)) + ")");
        } else if (ACTION_CMD.equals(action) && intent.hasExtra(EXTRA_CMD)) {
            js("zephCmd(" + JSONObject.quote(intent.getStringExtra(EXTRA_CMD)) + ")");
        } else if (ACTION_REPLY.equals(action)) {
            Bundle r = RemoteInput.getResultsFromIntent(intent);
            CharSequence said = r != null ? r.getCharSequence(KEY_REPLY) : null;
            if (said != null && said.toString().trim().length() > 0) {
                if (hidden) setHidden(false);
                js("zephChat(" + JSONObject.quote(said.toString().trim()) + ")");
            }
            refreshNotification(); // toglie la rotellina dalla notifica
        } else if (ACTION_READ.equals(action) && intent.hasExtra(EXTRA_TEXT)) {
            if (hidden) setHidden(false);
            js("zephRead(" + JSONObject.quote(intent.getStringExtra(EXTRA_TEXT)) + ")");
        } else if (ACTION_AVATAR.equals(action)) {
            js("zephPrefsChanged()");
            js("zephReloadAvatar()");
            refreshNotification();
            updateTile();
        } else if (ACTION_PREFS.equals(action)) {
            js("zephPrefsChanged()");
            refreshNotification();
            updateTile();
            stopShake();
            startShake();
        } else if (ACTION_SAY.equals(action) && intent.hasExtra(EXTRA_TEXT)) {
            if (hidden) setHidden(false);
            String cmd = intent.getStringExtra(EXTRA_CMD);
            js("zephSay(" + JSONObject.quote(intent.getStringExtra(EXTRA_TEXT)) + "," + JSONObject.quote(cmd == null ? "" : cmd) + ")");
        } else if (ACTION_MESSAGE.equals(action) && intent.hasExtra(EXTRA_TEXT)) {
            if (!hidden) js("zephMessage(" + JSONObject.quote(intent.getStringExtra(EXTRA_TEXT)) + ")");
        } else if (ACTION_MEMORY.equals(action)) {
            js("zephRestoreMemory()");
        } else if (ACTION_RELOAD.equals(action)) {
            destroyOverlay();
            createOverlay();
        }
        return START_STICKY; // se Android lo chiude per memoria, lo fa ripartire
    }

    /** Aggiorna il pulsante «Zeph» nelle Impostazioni rapide. */
    private void updateTile() {
        try {
            TileService.requestListeningState(this, new ComponentName(this, ZephTileService.class));
        } catch (Exception ignored) { }
    }

    @Override
    public void onDestroy() {
        running = false;
        updateTile();
        try { unregisterReceiver(screenRx); } catch (Exception ignored) { }
        try { unregisterReceiver(phoneRx); } catch (Exception ignored) { }
        stopShake();
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
        Reminders.channel(this);
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
        // la risposta scritta (o dettata con il microfono della tastiera) arriva al servizio
        int replyFlags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
        PendingIntent replyPi = PendingIntent.getService(this, 2,
            new Intent(this, ZephService.class).setAction(ACTION_REPLY), replyFlags);
        String name = Prefs.petName(this);
        RemoteInput input = new RemoteInput.Builder(KEY_REPLY).setLabel("Scrivi a " + name + "…").build();
        Notification.Action reply = new Notification.Action.Builder(icon, "💬 Scrivi", replyPi)
            .addRemoteInput(input)
            .setAllowGeneratedReplies(false)
            .build();
        return new Notification.Builder(this, CH_MAIN)
            .setSmallIcon(R.drawable.ic_stat_zeph)
            .setContentTitle(hidden ? name + " è nascosto" : name + " è sul tuo schermo")
            .setContentText(hidden ? "Premi «Mostra» per farlo tornare"
                : "Scrivigli da qui · toccalo per farlo reagire · tienilo premuto per la chat")
            .setOngoing(true)
            .setShowWhen(false)
            .setContentIntent(openApp)
            .addAction(reply)
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
            .setContentTitle(Prefs.petName(this) + " ⏰")
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

        web.loadUrl("https://" + LocalWeb.HOST + "/overlay.html");
        startShake();
    }

    private void startShake() {
        if (!Prefs.shake(this) || frame == null) return;
        if (sensors == null) sensors = getSystemService(SensorManager.class);
        Sensor acc = sensors != null ? sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) : null;
        if (acc != null) sensors.registerListener(shakeListener, acc, SensorManager.SENSOR_DELAY_UI);
    }

    private void stopShake() {
        if (sensors != null) sensors.unregisterListener(shakeListener);
    }

    // la memoria del compagno, copiata anche in un file dell'app (per il backup e se la pagina viene azzerata)
    private File memoryFile() { return new File(getFilesDir(), "memory.json"); }

    private void writeMemory(String json) {
        if (json == null || json.length() > 4 * 1024 * 1024) return;
        File tmp = new File(getFilesDir(), "memory.tmp");
        try (OutputStream out = new FileOutputStream(tmp)) {
            out.write(json.getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            return;
        }
        if (!tmp.renameTo(memoryFile())) tmp.delete();
    }

    static String readFile(File f) {
        if (!f.exists() || f.length() > 4 * 1024 * 1024) return "";
        try (InputStream in = new FileInputStream(f)) {
            byte[] b = new byte[(int) f.length()];
            int off = 0, n;
            while (off < b.length && (n = in.read(b, off, b.length - off)) > 0) off += n;
            return new String(b, 0, off, StandardCharsets.UTF_8);
        } catch (IOException e) {
            return "";
        }
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

    /** Per la conversazione a voce: «sta parlando», «ha finito», e cosa dice. */
    private void talkEvent(String ev, String text) {
        try {
            sendBroadcast(new Intent(TalkActivity.ACTION_EVENT).setPackage(getPackageName()).putExtra("ev", ev).putExtra("text", text));
        } catch (Exception ignored) { /* nessuno ascolta */ }
    }

    private void showBubble(String text) {
        talkEvent("text", text);
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

    /** Pagine e file locali (vedi LocalWeb); se Android chiude la pagina, Zeph ricompare. */
    private class LocalAssets extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
            return LocalWeb.intercept(ZephService.this, req);
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) { return true; }

        // se Android chiude il motore della pagina (poca memoria), Zeph ricompare da solo
        @Override
        public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
            Log.w(TAG, "WebView chiusa da Android, la ricreo");
            main.post(() -> {
                destroyOverlay();
                if (running) createOverlay();
            });
            return true;
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
            if (!ttsReady || hidden) {
                // niente voce: la conversazione a voce riparte dopo il tempo di leggere il fumetto
                long ms = 1500 + Math.min(9000, (text == null ? 0 : text.length()) * 55L);
                main.postDelayed(() -> talkEvent("done", null), ms);
                return false;
            }
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

        @JavascriptInterface public void remind(String text) { main.post(() -> reminder(text)); }

        @JavascriptInterface public void openChat() { main.post(() -> ZephService.this.openChat(false)); }

        /** Conversazione a voce, mani libere. */
        @JavascriptInterface public void openTalk() {
            main.post(() -> {
                try {
                    startActivity(new Intent(ZephService.this, TalkActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                } catch (Exception e) { Log.w(TAG, "conversazione", e); }
            });
        }

        /** Apre la pagina «avatar dalla foto». */
        @JavascriptInterface public void openPhoto() {
            main.post(() -> {
                try {
                    startActivity(new Intent(ZephService.this, PhotoActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                } catch (Exception e) { Log.w(TAG, "foto", e); }
            });
        }

        /** Il nome del compagno (lo puoi cambiare dalla chat o dall'app). */
        @JavascriptInterface public String petName() { return Prefs.petName(ZephService.this); }

        @JavascriptInterface public void setPetName(String n) {
            Prefs.setPetName(ZephService.this, n);
            main.post(() -> { refreshNotification(); updateTile(); });
        }

        /** La tua chiave per il cervello AI: sta nelle impostazioni dell'app, non nella pagina. */
        @JavascriptInterface public String aiKey() { return Prefs.aiKey(ZephService.this); }

        @JavascriptInterface public void setAiKey(String k) {
            Prefs.setAiKey(ZephService.this, k != null && (k.isEmpty() || k.startsWith("sk-ant-")) ? k : "");
        }

        /** Cosa può fare adesso: rubrica, agenda, messaggi, cervello AI. */
        @JavascriptInterface public String powers() {
            try {
                return new JSONObject()
                    .put("contacts", Contacts.canReadContacts(ZephService.this))
                    .put("calendar", Contacts.canReadCalendar(ZephService.this))
                    .put("messages", MessageListener.enabled(ZephService.this))
                    .put("ai", !Prefs.aiKey(ZephService.this).isEmpty())
                    .toString();
            } catch (JSONException e) {
                return "{}";
            }
        }

        /** Promemoria vero (AlarmManager): suona anche a Zeph spento. */
        @JavascriptInterface public int remindAt(double at, String text) { return Reminders.add(ZephService.this, (long) at, text); }

        @JavascriptInterface public String reminders() { return Reminders.list(ZephService.this).toString(); }

        @JavascriptInterface public void clearReminders() { Reminders.clear(ZephService.this); }

        @JavascriptInterface public String contact(String name) { return Contacts.find(ZephService.this, name); }

        @JavascriptInterface public String events(int offset) { return Contacts.events(ZephService.this, offset); }

        @JavascriptInterface public String messages() {
            return MessageListener.enabled(ZephService.this) ? MessageListener.recentJson() : "{\"error\":\"perm\"}";
        }

        /** A chi risponderebbe («Giulia|WhatsApp»), per chiederti conferma prima. */
        @JavascriptInterface public String peekReply(String who) { return MessageListener.peek(who); }

        /** Manda la risposta: la pagina la chiama solo dopo il tuo «sì». */
        @JavascriptInterface public String reply(String who, String text) { return MessageListener.reply(ZephService.this, who, text); }

        @JavascriptInterface public void openEyes(String q) {
            main.post(() -> {
                try {
                    startActivity(new Intent(ZephService.this, PhotoActivity.class)
                        .putExtra(PhotoActivity.EXTRA_PAGE, "occhi").putExtra(PhotoActivity.EXTRA_Q, q == null ? "" : q)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                } catch (Exception e) { Log.w(TAG, "occhi", e); }
            });
        }

        @JavascriptInterface public void saveMemory(String json) { writeMemory(json); }

        @JavascriptInterface public String loadMemory() { return readFile(memoryFile()); }
    }
}
