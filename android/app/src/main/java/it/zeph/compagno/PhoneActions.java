package it.zeph.compagno;

import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.media.AudioManager;
import android.net.Uri;
import android.provider.AlarmClock;
import android.provider.MediaStore;
import android.provider.Settings;
import android.view.KeyEvent;

import org.json.JSONObject;

/**
 * Le azioni che Zeph può fare sul telefono: aprire app vere, impostazioni,
 * siti e cambiare il volume. Tutto passa da qui ed è in una lista chiusa:
 * nessun comando arbitrario.
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
            default: return false;
        }
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
