package it.zeph.compagno;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.BatteryManager;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import android.webkit.JavascriptInterface;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * I poteri del telefono che le pagine del compagno (overlay.js) e
 * dell'assistente (assistente.js) possono usare: azioni, promemoria,
 * rubrica, agenda, messaggi, memoria. È lo stesso ponte «ZephAndroid» per
 * tutte e due, così il cervello fa le stesse cose ovunque.
 */
class PhoneBridge {
    private static final String TAG = "Zeph";
    protected final Context ctx;
    protected final Handler main = new Handler(Looper.getMainLooper());

    PhoneBridge(Context c) { ctx = c; }

    /** Quando cambia il nome (la notifica e il riquadro lo mostrano). */
    protected void onPetName() { }

    @JavascriptInterface public boolean action(String json) {
        try {
            return PhoneActions.run(ctx, new JSONObject(json));
        } catch (JSONException e) {
            return false;
        }
    }

    /** I comandi dell'assistente: risponde "ok", "panel", "perm:…" o "fail". */
    @JavascriptInterface public String sys(String json) {
        try {
            return PhoneActions.sys(ctx, new JSONObject(json));
        } catch (JSONException | RuntimeException e) {
            Log.w(TAG, "comando", e);
            return "fail";
        }
    }

    @JavascriptInterface public String battery() {
        BatteryManager bm = ctx.getSystemService(BatteryManager.class);
        try {
            return new JSONObject()
                .put("level", bm != null ? bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) : -1)
                .put("charging", bm != null && bm.isCharging())
                .toString();
        } catch (JSONException e) {
            return "{\"level\":-1}";
        }
    }

    @JavascriptInterface public void remind(String text) { Reminders.notifyNow(ctx, text); }

    /** Conversazione a voce, mani libere. */
    @JavascriptInterface public void openTalk() { open(new Intent(ctx, TalkActivity.class)); }

    /** Apre la pagina «avatar dalla foto». */
    @JavascriptInterface public void openPhoto() { open(new Intent(ctx, PhotoActivity.class)); }

    /** Il nome del compagno (lo puoi cambiare dalla chat o dall'app). */
    @JavascriptInterface public String petName() { return Prefs.petName(ctx); }

    @JavascriptInterface public void setPetName(String n) {
        Prefs.setPetName(ctx, n);
        main.post(this::onPetName);
    }

    /** La tua chiave per il cervello AI: sta nelle impostazioni dell'app, non nella pagina. */
    @JavascriptInterface public String aiKey() { return Prefs.aiKey(ctx); }

    @JavascriptInterface public void setAiKey(String k) {
        Prefs.setAiKey(ctx, k != null && (k.isEmpty() || k.startsWith("sk-ant-")) ? k : "");
    }

    /** La modalità scelta (nell'app o in chat). */
    @JavascriptInterface public String style() { return Prefs.style(ctx); }

    @JavascriptInterface public void setStyle(String st) { Prefs.setStyle(ctx, st); }

    /** Cosa può fare adesso: rubrica, agenda, messaggi, chiamate, comandi di sistema, impostazioni, cervello AI. */
    @JavascriptInterface public String powers() {
        try {
            return new JSONObject()
                .put("contacts", Contacts.canReadContacts(ctx))
                .put("calendar", Contacts.canReadCalendar(ctx))
                .put("messages", MessageListener.enabled(ctx))
                .put("call", ctx.checkSelfPermission(Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED)
                .put("access", ZephAccess.enabled(ctx))
                .put("settings", Settings.System.canWrite(ctx))
                .put("ai", !Prefs.aiKey(ctx).isEmpty())
                .toString();
        } catch (JSONException e) {
            return "{}";
        }
    }

    /** Promemoria vero (AlarmManager): suona anche a Zeph spento. */
    @JavascriptInterface public int remindAt(double at, String text) { return Reminders.add(ctx, (long) at, text); }

    @JavascriptInterface public String reminders() { return Reminders.list(ctx).toString(); }

    @JavascriptInterface public void clearReminders() { Reminders.clear(ctx); }

    @JavascriptInterface public String contact(String name) { return Contacts.find(ctx, name); }

    @JavascriptInterface public String events(int offset) { return Contacts.events(ctx, offset); }

    @JavascriptInterface public String messages() {
        return MessageListener.enabled(ctx) ? MessageListener.recentJson() : "{\"error\":\"perm\"}";
    }

    /** A chi risponderebbe («Giulia|WhatsApp»), per chiederti conferma prima. */
    @JavascriptInterface public String peekReply(String who) { return MessageListener.peek(who); }

    /** Manda la risposta: la pagina la chiama solo dopo il tuo «sì». */
    @JavascriptInterface public String reply(String who, String text) { return MessageListener.reply(ctx, who, text); }

    @JavascriptInterface public void openEyes(String q) {
        open(new Intent(ctx, PhotoActivity.class)
            .putExtra(PhotoActivity.EXTRA_PAGE, "occhi").putExtra(PhotoActivity.EXTRA_Q, q == null ? "" : q));
    }

    @JavascriptInterface public void saveMemory(String json) { writeMemory(ctx, json); }

    @JavascriptInterface public String loadMemory() { return readFile(memoryFile(ctx)); }

    protected void open(Intent i) {
        main.post(() -> {
            try {
                ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Exception e) { Log.w(TAG, "apertura", e); }
        });
    }

    // ---------------------------------------------------------------- memoria su file

    // la memoria del compagno, copiata anche in un file dell'app (per il backup e se la pagina viene azzerata)
    static File memoryFile(Context c) { return new File(c.getFilesDir(), "memory.json"); }

    static synchronized void writeMemory(Context c, String json) {
        if (json == null || json.length() > 4 * 1024 * 1024) return;
        File tmp = new File(c.getFilesDir(), "memory.tmp");
        try (OutputStream out = new FileOutputStream(tmp)) {
            out.write(json.getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            return;
        }
        if (!tmp.renameTo(memoryFile(c))) tmp.delete();
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
}
