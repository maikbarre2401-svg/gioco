package com.maik.subs;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Dopo il riavvio del telefono (o un aggiornamento dell'app) rimette in fila i promemoria. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent intent) {
        String a = intent.getAction();
        if (Intent.ACTION_BOOT_COMPLETED.equals(a) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)) {
            Reminders.rearmAll(c);
        }
    }
}
