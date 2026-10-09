package it.zeph.compagno;

import android.content.Context;
import android.content.SharedPreferences;

/** Le impostazioni di Zeph, salvate sul telefono. */
final class Prefs {
    private Prefs() {}

    private static SharedPreferences p(Context c) {
        return c.getSharedPreferences("zeph", Context.MODE_PRIVATE);
    }

    /** Riaccendi Zeph quando riaccendi il telefono (se era acceso). */
    static boolean autostart(Context c) { return p(c).getBoolean("autostart", true); }
    static void setAutostart(Context c, boolean v) { p(c).edit().putBoolean("autostart", v).apply(); }

    /** Era acceso l'ultima volta? (serve per riaccenderlo dopo il riavvio) */
    static boolean wasRunning(Context c) { return p(c).getBoolean("running", false); }
    static void setRunning(Context c, boolean v) { p(c).edit().putBoolean("running", v).apply(); }

    /** Dimensione del personaggio: 0.75 piccolo, 1 medio, 1.3 grande. */
    static float scale(Context c) { return p(c).getFloat("scale", 1f); }
    static void setScale(Context c, float v) { p(c).edit().putFloat("scale", v).apply(); }

    /** Modalità fantasma: i tocchi passano attraverso il personaggio. */
    static boolean ghost(Context c) { return p(c).getBoolean("ghost", false); }
    static void setGhost(Context c, boolean v) { p(c).edit().putBoolean("ghost", v).apply(); }

    /** Usa l'avatar incluso nell'APK (se c'è) quando non ne hai scelto un altro. */
    static boolean useBundledAvatar(Context c) { return p(c).getBoolean("bundled", true); }
    static void setUseBundledAvatar(Context c, boolean v) { p(c).edit().putBoolean("bundled", v).apply(); }

    /** Ultima posizione orizzontale (px), per ripartire da dove l'avevi lasciato. */
    static int lastX(Context c) { return p(c).getInt("lastX", -1); }
    static void setLastX(Context c, int v) { p(c).edit().putInt("lastX", v).apply(); }

    /** Il nome che hai dato al tuo compagno (di base «Zeph»). */
    static String petName(Context c) { return p(c).getString("petName", "Zeph"); }
    static void setPetName(Context c, String v) {
        String n = v == null ? "" : v.replaceAll("[^\\p{L}' -]", "").trim();
        if (n.length() > 16) n = n.substring(0, 16).trim();
        p(c).edit().putString("petName", n.isEmpty() ? "Zeph" : n).apply();
    }

    /**
     * La TUA chiave per il cervello AI (Claude). Resta solo su questo telefono:
     * sta in un file a parte escluso dai backup (res/xml/backup_rules.xml).
     */
    private static SharedPreferences secret(Context c) {
        return c.getSharedPreferences("zeph_secret", Context.MODE_PRIVATE);
    }
    static String aiKey(Context c) { return secret(c).getString("aiKey", ""); }
    static void setAiKey(Context c, String v) { secret(c).edit().putString("aiKey", v == null ? "" : v.trim()).apply(); }

    /** Annuncia i messaggi in arrivo (serve l'accesso alle notifiche). */
    static boolean announceMessages(Context c) { return p(c).getBoolean("announceMsg", true); }
    static void setAnnounceMessages(Context c, boolean v) { p(c).edit().putBoolean("announceMsg", v).apply(); }

    /** Legge ad alta voce anche il testo dei messaggi (di base: solo chi ti ha scritto). */
    static boolean readMessages(Context c) { return p(c).getBoolean("readMsg", false); }
    static void setReadMessages(Context c, boolean v) { p(c).edit().putBoolean("readMsg", v).apply(); }

    /** Scuoti il telefono: arriva di corsa. */
    static boolean shake(Context c) { return p(c).getBoolean("shake", true); }
    static void setShake(Context c, boolean v) { p(c).edit().putBoolean("shake", v).apply(); }

    /** Il buongiorno con meteo e impegni, la prima volta che sblocchi il telefono la mattina. */
    static boolean briefing(Context c) { return p(c).getBoolean("briefing", true); }
    static void setBriefing(Context c, boolean v) { p(c).edit().putBoolean("briefing", v).apply(); }

    /** Controllo degli aggiornamenti su GitHub: quando e qual è l'ultima versione vista. */
    static long lastUpdateCheck(Context c) { return p(c).getLong("updCheck", 0); }
    static void setLastUpdateCheck(Context c, long v) { p(c).edit().putLong("updCheck", v).apply(); }
    static int latestBuild(Context c) { return p(c).getInt("latestBuild", 0); }
    static void setLatestBuild(Context c, int v) { p(c).edit().putInt("latestBuild", v).apply(); }

    /** Usa il look fatto con la foto (al posto del file .glb). */
    static boolean photoLook(Context c) { return p(c).getBoolean("photoLook", false); }
    static void setPhotoLook(Context c, boolean v) { p(c).edit().putBoolean("photoLook", v).apply(); }
}
