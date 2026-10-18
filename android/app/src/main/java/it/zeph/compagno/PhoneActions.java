package it.zeph.compagno;

import android.Manifest;
import android.app.SearchManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.media.AudioManager;
import android.net.Uri;
import android.provider.AlarmClock;
import android.provider.CalendarContract;
import android.provider.MediaStore;
import android.provider.Settings;
import android.view.KeyEvent;

import org.json.JSONObject;

import java.text.Normalizer;
import java.util.List;
import java.util.Locale;

/**
 * Le azioni che Zeph può fare sul telefono: aprire app vere, impostazioni,
 * siti, navigatore, musica, volume, luminosità, non disturbare e i tasti di
 * sistema. Tutto passa da qui ed è in una lista chiusa: nessun comando arbitrario.
 * Niente viene mandato o chiamato da solo: le chiamate dirette partono solo se
 * hai dato il permesso e hai detto «sì» alla domanda di conferma.
 */
final class PhoneActions {
    private PhoneActions() {}

    static boolean run(Context c, JSONObject o) {
        String type = o.optString("type");
        switch (type) {
            case "url": return openUrl(c, o.optString("url"));
            case "appUrl": return openAppUrl(c, o.optString("url"));
            case "app": return openApp(c, o.optString("id"));
            case "volume": return volume(c, o.optString("dir"));
            case "torch": return torch(c, o.optBoolean("on", true));
            case "alarm": return alarm(c, o.optInt("h", -1), o.optInt("m", 0));
            case "timer": return timer(c, o.optInt("seconds", 0));
            case "dial": return dial(c, o.optString("number", ""));
            case "media": return media(c, o.optString("key"));
            case "calAdd": return calendarAdd(c, o.optString("title"), o.optLong("at", 0));
            case "sms": return sms(c, o.optString("number", ""), o.optString("text", ""));
            default: return false;
        }
    }

    /**
     * I comandi dell'assistente. Risponde a parole semplici per la pagina:
     * "ok", "ok:Nome app", "panel" (ti ho aperto le impostazioni giuste),
     * "perm:access" / "perm:settings" / "perm:dnd" / "perm:call" (manca un permesso), "fail".
     */
    static String sys(Context c, JSONObject o) {
        String type = o.optString("type");
        switch (type) {
            case "navigate": return navigate(c, o.optString("q"));
            case "maps": return maps(c, o.optString("q"));
            case "play": return play(c, o.optString("q"), o.optString("app"));
            case "volumeSet": return volumeSet(c, o.optInt("level", 50), o.optBoolean("unmute"));
            case "ringer": return ringer(c, o.optString("mode"));
            case "dnd": return dnd(c, o.optBoolean("on", true));
            case "brightness": return brightness(c, o);
            case "setting": return setting(c, o.optString("what"), o.has("on") && !o.isNull("on") ? o.optBoolean("on") : null);
            case "global": return global(c, o.optString("what"), o.optLong("delay", 0));
            case "camera": return camera(c, o.optBoolean("front"), o.optBoolean("video"));
            case "alarms": return ok(start(c, new Intent(AlarmClock.ACTION_SHOW_ALARMS)));
            case "alarmOff": return ok(start(c, new Intent(AlarmClock.ACTION_DISMISS_ALARM)
                .putExtra(AlarmClock.EXTRA_ALARM_SEARCH_MODE, AlarmClock.ALARM_SEARCH_MODE_ALL)) || start(c, new Intent(AlarmClock.ACTION_SHOW_ALARMS)));
            case "launch": return launchByName(c, o.optString("name"));
            case "call": return call(c, o.optString("number"));
            default: return ok(run(c, o));
        }
    }

    private static String ok(boolean b) { return b ? "ok" : "fail"; }

    private static String enc(String q) { return Uri.encode(q == null ? "" : q.trim()); }

    /** Il navigatore (Google Maps, o l'app di mappe che hai). */
    private static String navigate(Context c, String q) {
        if (q == null || q.trim().isEmpty()) return maps(c, "");
        if (start(c, new Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=" + enc(q))))) return "ok";
        if (start(c, new Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + enc(q))))) return "ok";
        return ok(openUrl(c, "https://www.google.com/maps/dir/?api=1&destination=" + enc(q)));
    }

    private static String maps(Context c, String q) {
        if (q != null && !q.trim().isEmpty()) {
            // «geo:0,0?q=farmacia» cerca vicino a dove sei
            if (start(c, new Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + enc(q))))) return "ok";
            return ok(openUrl(c, "https://www.google.com/maps/search/" + enc(q)));
        }
        if (launch(c, "com.google.android.apps.maps")) return "ok";
        return ok(openUrl(c, "https://www.google.com/maps"));
    }

    /** «Metti Vasco su Spotify»: le app musicali partono da sole con la ricerca. */
    private static String play(Context c, String q, String app) {
        String pkg;
        switch (app == null ? "" : app) {
            case "spotify": pkg = "com.spotify.music"; break;
            case "ytmusic": pkg = "com.google.android.apps.youtube.music"; break;
            case "amazonmusic": pkg = "com.amazon.mp3"; break;
            case "deezer": pkg = "deezer.android.app"; break;
            case "youtube": pkg = "com.google.android.youtube"; break;
            default: pkg = null;
        }
        if ("com.google.android.youtube".equals(pkg)) {
            if (q.isEmpty()) return ok(launch(c, pkg) || openUrl(c, "https://www.youtube.com"));
            Intent s = new Intent(Intent.ACTION_SEARCH).setPackage(pkg).putExtra(SearchManager.QUERY, q).putExtra("query", q);
            if (start(c, s)) return "ok";
            return ok(openUrl(c, "https://www.youtube.com/results?search_query=" + enc(q)));
        }
        Intent i = new Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH)
            .putExtra(SearchManager.QUERY, q == null ? "" : q)
            .putExtra(MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*");
        if (pkg != null) i.setPackage(pkg);
        if (start(c, i)) return "ok";
        if ("com.spotify.music".equals(pkg)) {
            if (start(c, new Intent(Intent.ACTION_VIEW, Uri.parse("spotify:search:" + enc(q))).setPackage(pkg))) return "ok";
            if (launch(c, pkg)) return "ok";
            return ok(openUrl(c, "https://open.spotify.com/search/" + enc(q)));
        }
        if (pkg != null && launch(c, pkg)) return "ok";
        if ("com.google.android.apps.youtube.music".equals(pkg) || pkg == null) {
            if (q.isEmpty()) return "fail";
            return ok(openUrl(c, (pkg == null ? "https://www.youtube.com/results?search_query=" : "https://music.youtube.com/search?q=") + enc(q)));
        }
        return "fail";
    }

    private static String volumeSet(Context c, int level, boolean unmute) {
        AudioManager am = c.getSystemService(AudioManager.class);
        if (am == null) return "fail";
        try {
            if (unmute) am.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_UNMUTE, 0);
            int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
            int v = Math.max(0, Math.min(max, Math.round(max * Math.max(0, Math.min(100, level)) / 100f)));
            if (level > 0 && v == 0) v = 1;
            am.setStreamVolume(AudioManager.STREAM_MUSIC, v, AudioManager.FLAG_SHOW_UI);
            return "ok";
        } catch (SecurityException e) {
            return "perm:dnd"; // con «non disturbare» acceso alcuni telefoni non lo permettono
        }
    }

    /** Suoneria: normale, vibrazione, silenzioso. */
    private static String ringer(Context c, String mode) {
        AudioManager am = c.getSystemService(AudioManager.class);
        if (am == null) return "fail";
        int m = "silent".equals(mode) ? AudioManager.RINGER_MODE_SILENT
            : "vibrate".equals(mode) ? AudioManager.RINGER_MODE_VIBRATE : AudioManager.RINGER_MODE_NORMAL;
        try {
            am.setRingerMode(m);
            return "ok";
        } catch (SecurityException e) {
            // da Android 7 il silenzioso tocca il «non disturbare»: ci prova con l'accesso alle notifiche
            if (m == AudioManager.RINGER_MODE_SILENT) {
                if (MessageListener.setDnd(true)) return "ok";
                try { am.setRingerMode(AudioManager.RINGER_MODE_VIBRATE); return "ok:vibrate"; } catch (SecurityException e2) { return "perm:dnd"; }
            }
            if (MessageListener.setDnd(false)) {
                try { am.setRingerMode(m); return "ok"; } catch (SecurityException e3) { return "perm:dnd"; }
            }
            return "perm:dnd";
        }
    }

    private static String dnd(Context c, boolean on) {
        if (MessageListener.setDnd(on)) return "ok";
        if (start(c, new Intent("android.settings.ZEN_MODE_SETTINGS")) || start(c, new Intent(Settings.ACTION_SOUND_SETTINGS))) return "perm:dnd";
        return "fail";
    }

    /** Luminosità: serve il permesso «Modifica impostazioni di sistema» (lo dai dall'app). */
    private static String brightness(Context c, JSONObject o) {
        if (!Settings.System.canWrite(c)) {
            start(c, new Intent(Settings.ACTION_DISPLAY_SETTINGS));
            return "perm:settings";
        }
        ContentResolver cr = c.getContentResolver();
        try {
            if (o.has("auto")) {
                Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE, o.optBoolean("auto")
                    ? Settings.System.SCREEN_BRIGHTNESS_MODE_AUTOMATIC : Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL);
                return "ok";
            }
            Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE, Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL);
            int cur = Settings.System.getInt(cr, Settings.System.SCREEN_BRIGHTNESS, 128);
            int v;
            if (o.has("level")) v = Math.round(255 * Math.max(1, Math.min(100, o.optInt("level"))) / 100f);
            else v = cur + ("up".equals(o.optString("dir")) ? 64 : -64);
            Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS, Math.max(3, Math.min(255, v)));
            return "ok";
        } catch (SecurityException | IllegalArgumentException e) {
            return "perm:settings";
        }
    }

    /** Wi-Fi, Bluetooth, dati, aereo…: Android non lascia accenderli alle app, quindi apre il pannello giusto. */
    private static String setting(Context c, String what, Boolean on) {
        switch (what) {
            case "wifi":
                if (Build.VERSION.SDK_INT < 29 && on != null) {
                    WifiManager wm = c.getApplicationContext().getSystemService(WifiManager.class);
                    if (wm != null && legacyWifi(wm, on)) return "ok";
                }
                return panel(c, Build.VERSION.SDK_INT >= 29 ? Settings.Panel.ACTION_WIFI : null, Settings.ACTION_WIFI_SETTINGS);
            case "bluetooth": return panel(c, null, Settings.ACTION_BLUETOOTH_SETTINGS);
            case "dati": return panel(c, Build.VERSION.SDK_INT >= 29 ? Settings.Panel.ACTION_INTERNET_CONNECTIVITY : null, Settings.ACTION_DATA_ROAMING_SETTINGS);
            case "nfc": return panel(c, Build.VERSION.SDK_INT >= 29 ? Settings.Panel.ACTION_NFC : null, Settings.ACTION_NFC_SETTINGS);
            case "aereo": return panel(c, null, Settings.ACTION_AIRPLANE_MODE_SETTINGS);
            case "hotspot": {
                Intent t = new Intent().setComponent(new ComponentName("com.android.settings", "com.android.settings.TetherSettings"));
                if (start(c, t)) return "panel";
                return panel(c, "android.settings.TETHER_SETTINGS", Settings.ACTION_WIRELESS_SETTINGS);
            }
            case "posizione": return panel(c, null, Settings.ACTION_LOCATION_SOURCE_SETTINGS);
            case "risparmio": return panel(c, null, Settings.ACTION_BATTERY_SAVER_SETTINGS);
            case "scuro": return panel(c, "android.settings.DARK_THEME_SETTINGS", Settings.ACTION_DISPLAY_SETTINGS);
            case "rotazione": {
                if (!Settings.System.canWrite(c)) {
                    start(c, new Intent(Settings.ACTION_DISPLAY_SETTINGS));
                    return "perm:settings";
                }
                ContentResolver cr = c.getContentResolver();
                boolean now = Settings.System.getInt(cr, Settings.System.ACCELEROMETER_ROTATION, 0) == 1;
                try {
                    Settings.System.putInt(cr, Settings.System.ACCELEROMETER_ROTATION, (on == null ? !now : on) ? 1 : 0);
                    return "ok";
                } catch (SecurityException | IllegalArgumentException e) {
                    return "perm:settings";
                }
            }
            default: return "fail";
        }
    }

    @SuppressWarnings("deprecation")
    private static boolean legacyWifi(WifiManager wm, boolean on) {
        try { return wm.setWifiEnabled(on); } catch (SecurityException e) { return false; }
    }

    private static String panel(Context c, String first, String second) {
        if (first != null && start(c, new Intent(first))) return "panel";
        if (second != null && start(c, new Intent(second))) return "panel";
        return start(c, new Intent(Settings.ACTION_SETTINGS)) ? "panel" : "fail";
    }

    /** I tasti di sistema: la home la apre da solo, il resto con i «Comandi del telefono» (accessibilità). */
    private static String global(Context c, String what, long delay) {
        if ("home".equals(what)) {
            return ok(start(c, new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)));
        }
        if (!ZephAccess.connected()) return "perm:access";
        return ok(ZephAccess.perform(what, delay));
    }

    private static String camera(Context c, boolean front, boolean video) {
        if (video) return ok(start(c, new Intent(MediaStore.INTENT_ACTION_VIDEO_CAMERA)));
        Intent i = new Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA);
        if (front) {
            // ogni marca usa un nome diverso per «parti con la fotocamera davanti»
            i.putExtra("android.intent.extras.CAMERA_FACING", 1)
                .putExtra("android.intent.extras.LENS_FACING_FRONT", 1)
                .putExtra("android.intent.extra.USE_FRONT_CAMERA", true)
                .putExtra("com.google.assistant.extra.USE_FRONT_CAMERA", true);
        }
        return ok(start(c, i));
    }

    /** Chiamata diretta: la pagina la chiede solo dopo il tuo «sì», e solo se hai dato il permesso. */
    private static String call(Context c, String number) {
        String n = number == null ? "" : number.replaceAll("[^0-9+]", "");
        if (n.isEmpty()) return "fail";
        if (c.checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            return dial(c, n) ? "perm:call" : "fail";
        }
        return ok(start(c, new Intent(Intent.ACTION_CALL, Uri.parse("tel:" + n))));
    }

    /** «Apri Instagram»: cerca tra le app installate quella con quel nome. */
    private static String launchByName(Context c, String name) {
        String want = norm(name);
        if (want.length() < 2) return "fail";
        PackageManager pm = c.getPackageManager();
        List<ResolveInfo> apps = pm.queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0);
        ResolveInfo best = null;
        int bestScore = 0;
        for (ResolveInfo r : apps) {
            if (r.activityInfo == null || c.getPackageName().equals(r.activityInfo.packageName)) continue;
            String label = norm(String.valueOf(r.loadLabel(pm)));
            if (label.isEmpty()) continue;
            int score;
            if (label.equals(want)) score = 100;
            else if (label.startsWith(want) || want.startsWith(label) && label.length() >= 4) score = 80;
            else if ((" " + label + " ").contains(" " + want + " ")) score = 70;
            else if (want.length() >= 4 && label.contains(want)) score = 60;
            else if (want.length() >= 5 && distance(label, want) <= (want.length() >= 8 ? 2 : 1)) score = 50;
            else score = 0;
            if (score > bestScore) { bestScore = score; best = r; }
        }
        if (best == null) return "fail";
        Intent i = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
            .setComponent(new ComponentName(best.activityInfo.packageName, best.activityInfo.name))
            .addFlags(Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        return start(c, i) ? "ok:" + best.loadLabel(pm) : "fail";
    }

    private static String norm(String s) {
        String x = Normalizer.normalize(s == null ? "" : s, Normalizer.Form.NFD).replaceAll("\\p{M}", "");
        return x.toLowerCase(Locale.ITALIAN).replaceAll("[^a-z0-9]+", " ").trim();
    }

    private static int distance(String a, String b) {
        int[] prev = new int[b.length() + 1], cur = new int[b.length() + 1];
        for (int j = 0; j <= b.length(); j++) prev[j] = j;
        for (int i = 1; i <= a.length(); i++) {
            cur[0] = i;
            for (int j = 1; j <= b.length(); j++) {
                int cost = a.charAt(i - 1) == b.charAt(j - 1) ? 0 : 1;
                cur[j] = Math.min(Math.min(cur[j - 1] + 1, prev[j] + 1), prev[j - 1] + cost);
            }
            int[] t = prev; prev = cur; cur = t;
        }
        return prev[b.length()];
    }

    /** Torcia: non serve il permesso della fotocamera per accenderla. */
    private static boolean torch(Context c, boolean on) {
        CameraManager cm = c.getSystemService(CameraManager.class);
        if (cm == null) return false;
        try {
            for (String id : cm.getCameraIdList()) {
                CameraCharacteristics ch = cm.getCameraCharacteristics(id);
                Boolean flash = ch.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                Integer facing = ch.get(CameraCharacteristics.LENS_FACING);
                if (Boolean.TRUE.equals(flash) && facing != null && facing == CameraCharacteristics.LENS_FACING_BACK) {
                    cm.setTorchMode(id, on);
                    return true;
                }
            }
        } catch (CameraAccessException | IllegalArgumentException | SecurityException e) {
            return false;
        }
        return false;
    }

    /** Sveglia vera nell'app Orologio del telefono. */
    private static boolean alarm(Context c, int h, int m) {
        if (h < 0 || h > 23 || m < 0 || m > 59) return false;
        Intent i = new Intent(AlarmClock.ACTION_SET_ALARM)
            .putExtra(AlarmClock.EXTRA_HOUR, h)
            .putExtra(AlarmClock.EXTRA_MINUTES, m)
            .putExtra(AlarmClock.EXTRA_MESSAGE, "Sveglia di Zeph")
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true);
        return start(c, i);
    }

    /** Timer vero nell'app Orologio (suona anche se Zeph è chiuso). */
    private static boolean timer(Context c, int seconds) {
        if (seconds <= 0 || seconds > 24 * 3600) return false;
        Intent i = new Intent(AlarmClock.ACTION_SET_TIMER)
            .putExtra(AlarmClock.EXTRA_LENGTH, seconds)
            .putExtra(AlarmClock.EXTRA_MESSAGE, "Timer di Zeph")
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true);
        return start(c, i);
    }

    /** Apre il telefono col numero già scritto: la chiamata la fai tu. */
    private static boolean dial(Context c, String number) {
        String n = number.replaceAll("[^0-9+]", "");
        return start(c, new Intent(Intent.ACTION_DIAL, n.isEmpty() ? null : Uri.parse("tel:" + n)));
    }

    /** SMS già scritto: lo mandi tu. */
    private static boolean sms(Context c, String number, String text) {
        String n = number.replaceAll("[^0-9+]", "");
        if (n.isEmpty()) return false;
        return start(c, new Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + n)).putExtra("sms_body", text));
    }

    /** Nuovo impegno nel calendario, già compilato: lo salvi tu. */
    private static boolean calendarAdd(Context c, String title, long at) {
        if (at <= 0) return false;
        Intent i = new Intent(Intent.ACTION_INSERT)
            .setData(CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, at)
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, at + 3600_000L)
            .putExtra(CalendarContract.Events.TITLE, title == null || title.isEmpty() ? "Impegno" : title);
        return start(c, i);
    }

    /** Tasti multimediali: comandano Spotify, YouTube Music e le altre app musicali. */
    private static boolean media(Context c, String key) {
        AudioManager am = c.getSystemService(AudioManager.class);
        if (am == null) return false;
        int code;
        switch (key) {
            case "play": code = KeyEvent.KEYCODE_MEDIA_PLAY; break;
            case "pause": code = KeyEvent.KEYCODE_MEDIA_PAUSE; break;
            case "next": code = KeyEvent.KEYCODE_MEDIA_NEXT; break;
            case "prev": code = KeyEvent.KEYCODE_MEDIA_PREVIOUS; break;
            default: return false;
        }
        am.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, code));
        am.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, code));
        return true;
    }

    private static boolean start(Context c, Intent i) {
        if (i == null) return false;
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            c.startActivity(i);
            return true;
        } catch (ActivityNotFoundException | SecurityException e) {
            return false;
        }
    }

    private static boolean launch(Context c, String... packages) {
        PackageManager pm = c.getPackageManager();
        for (String pkg : packages) {
            Intent i = pm.getLaunchIntentForPackage(pkg);
            if (i != null && start(c, i)) return true;
        }
        return false;
    }

    private static boolean openUrl(Context c, String url) {
        if (url == null) return false;
        if (url.startsWith("mailto:")) return start(c, new Intent(Intent.ACTION_SENDTO, Uri.parse(url)));
        if (url.startsWith("https://") || url.startsWith("http://")) {
            return start(c, new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        }
        return false;
    }

    /** I "protocolli" che sul PC aprono le app vere, tradotti per Android. */
    private static boolean openAppUrl(Context c, String url) {
        if (url == null) return false;
        if (url.startsWith("whatsapp://send")) {
            // messaggio già scritto: WhatsApp lo apre, tu premi invia
            if (start(c, new Intent(Intent.ACTION_VIEW, Uri.parse(url)))) return true;
            return false;
        }
        if (url.startsWith("whatsapp:")) return launch(c, "com.whatsapp", "com.whatsapp.w4b");
        if (url.startsWith("spotify:")) return launch(c, "com.spotify.music");
        if (url.startsWith("tg:")) return launch(c, "org.telegram.messenger", "org.telegram.messenger.web");
        if (url.startsWith("discord:")) return launch(c, "com.discord");
        if (url.startsWith("steam:")) return launch(c, "com.valvesoftware.android.steam.community");
        if (url.startsWith("ms-windows-store:")) return launch(c, "com.android.vending");
        if (url.startsWith("microsoft.windows.camera:")) {
            return start(c, new Intent(MediaStore.INTENT_ACTION_STILL_IMAGE_CAMERA));
        }
        if (url.startsWith("ms-settings:")) {
            String page = url.substring("ms-settings:".length());
            String action;
            switch (page) {
                case "network-wifi": action = Settings.ACTION_WIFI_SETTINGS; break;
                case "bluetooth": action = Settings.ACTION_BLUETOOTH_SETTINGS; break;
                case "sound": action = Settings.ACTION_SOUND_SETTINGS; break;
                case "display": action = Settings.ACTION_DISPLAY_SETTINGS; break;
                case "batterysaver": action = Settings.ACTION_BATTERY_SAVER_SETTINGS; break;
                case "windowsupdate": action = "android.settings.SYSTEM_UPDATE_SETTINGS"; break;
                case "privacy": action = Settings.ACTION_PRIVACY_SETTINGS; break;
                case "yourinfo": action = Settings.ACTION_SYNC_SETTINGS; break;
                default: action = Settings.ACTION_SETTINGS;
            }
            return start(c, new Intent(action)) || start(c, new Intent(Settings.ACTION_SETTINGS));
        }
        return false;
    }

    /** Le app "del PC", con l'equivalente più vicino su Android. */
    private static boolean openApp(Context c, String id) {
        switch (id) {
            case "calc":
                return start(c, Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, Intent.CATEGORY_APP_CALCULATOR))
                    || launch(c, "com.google.android.calculator", "com.sec.android.app.popupcalculator",
                        "com.miui.calculator", "com.android.calculator2");
            case "notepad":
                return launch(c, "com.google.android.keep", "com.samsung.android.app.notes", "com.miui.notes");
            case "explorer":
                return launch(c, "com.google.android.apps.nbu.files", "com.sec.android.app.myfiles",
                    "com.mi.android.globalFileexplorer");
            case "taskmgr":
                return start(c, new Intent(Settings.ACTION_MANAGE_APPLICATIONS_SETTINGS));
            case "control":
                return start(c, new Intent(Settings.ACTION_SETTINGS));
            case "word":
                return launch(c, "com.microsoft.office.word", "com.microsoft.office.officehubrow");
            case "excel":
                return launch(c, "com.microsoft.office.excel", "com.microsoft.office.officehubrow");
            case "powerpoint":
                return launch(c, "com.microsoft.office.powerpoint", "com.microsoft.office.officehubrow");
            default:
                return false; // paint, terminale, cattura: non esistono come app Android standard
        }
    }

    private static boolean volume(Context c, String dir) {
        AudioManager am = c.getSystemService(AudioManager.class);
        if (am == null) return false;
        int how;
        switch (dir) {
            case "up": how = AudioManager.ADJUST_RAISE; break;
            case "down": how = AudioManager.ADJUST_LOWER; break;
            case "mute": how = AudioManager.ADJUST_TOGGLE_MUTE; break;
            default: return false;
        }
        int times = "mute".equals(dir) ? 1 : 2;
        for (int k = 0; k < times; k++) {
            am.adjustStreamVolume(AudioManager.STREAM_MUSIC, how, AudioManager.FLAG_SHOW_UI);
        }
        return true;
    }
}
