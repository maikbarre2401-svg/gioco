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
}
