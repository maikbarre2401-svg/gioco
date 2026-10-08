package it.zeph.compagno;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Settings;

/** Riaccende Zeph quando riaccendi il telefono (o aggiorni l'app), se era acceso. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(a) && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)) return;
        if (!Prefs.autostart(c) || !Prefs.wasRunning(c) || !Settings.canDrawOverlays(c)) return;
        try {
            c.startForegroundService(new Intent(c, ZephService.class).setAction(ZephService.ACTION_START));
        } catch (Exception ignored) {
            // alcuni telefoni bloccano l'avvio automatico: si riapre dall'app
        }
    }
}
