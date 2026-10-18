package it.zeph.compagno;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.ComponentName;
import android.content.Context;
import android.graphics.Path;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.accessibility.AccessibilityEvent;

/**
 * «Comandi del telefono»: i pulsanti di sistema a voce (indietro, app recenti,
 * notifiche, screenshot, blocca schermo, scorri…). Si accende solo se lo attivi
 * tu in Impostazioni → Accessibilità. Non legge cosa c'è sullo schermo
 * (canRetrieveWindowContent="false"): preme soltanto i tasti che gli chiedi.
 */
public class ZephAccess extends AccessibilityService {
    private static volatile ZephAccess self;
    private static final Handler H = new Handler(Looper.getMainLooper());

    static boolean enabled(Context c) {
        if (self != null) return true;
        String s = Settings.Secure.getString(c.getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        return s != null && s.contains(new ComponentName(c, ZephAccess.class).flattenToString());
    }

    static boolean connected() { return self != null; }

    @Override protected void onServiceConnected() { self = this; }

    @Override public boolean onUnbind(android.content.Intent i) { self = null; return super.onUnbind(i); }

    @Override public void onDestroy() { self = null; super.onDestroy(); }

    @Override public void onAccessibilityEvent(AccessibilityEvent e) { /* non guarda lo schermo */ }

    @Override public void onInterrupt() { }

    /** Esegue il comando dopo «delay» ms (il tempo di chiudere la finestra dell'assistente). */
    static boolean perform(String what, long delay) {
        ZephAccess s = self;
        if (s == null) return false;
        int action;
        switch (what) {
            case "back": action = GLOBAL_ACTION_BACK; break;
            case "recents": action = GLOBAL_ACTION_RECENTS; break;
            case "notifications": action = GLOBAL_ACTION_NOTIFICATIONS; break;
            case "quick": action = GLOBAL_ACTION_QUICK_SETTINGS; break;
            case "power": action = GLOBAL_ACTION_POWER_DIALOG; break;
            case "split": action = GLOBAL_ACTION_TOGGLE_SPLIT_SCREEN; break;
            case "screenshot":
                if (Build.VERSION.SDK_INT < 28) return false;
                action = GLOBAL_ACTION_TAKE_SCREENSHOT;
                break;
            case "lock":
                if (Build.VERSION.SDK_INT < 28) return false;
                action = GLOBAL_ACTION_LOCK_SCREEN;
                break;
            case "scrollDown": H.postDelayed(() -> s.swipe(true), Math.max(0, delay)); return true;
            case "scrollUp": H.postDelayed(() -> s.swipe(false), Math.max(0, delay)); return true;
            default: return false;
        }
        H.postDelayed(() -> s.performGlobalAction(action), Math.max(0, delay));
        return true;
    }

    /** Un dito che scorre al centro dello schermo. */
    private void swipe(boolean down) {
        DisplayMetrics m = getResources().getDisplayMetrics();
        float x = m.widthPixels / 2f, top = m.heightPixels * 0.3f, bottom = m.heightPixels * 0.72f;
        Path p = new Path();
        // per far scendere la pagina il dito va verso l'alto
        p.moveTo(x, down ? bottom : top);
        p.lineTo(x, down ? top : bottom);
        GestureDescription g = new GestureDescription.Builder()
            .addStroke(new GestureDescription.StrokeDescription(p, 0, 320))
            .build();
        dispatchGesture(g, null, null);
    }
}
