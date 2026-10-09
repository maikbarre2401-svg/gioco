package com.maik.subs;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Promemoria dei rinnovi gestiti da Android (AlarmManager): arrivano anche con l'app chiusa
 * e dopo un riavvio del telefono vengono rimessi in fila.
 * L'app web manda la lista completa ogni volta che cambia qualcosa (schedule()).
 */
final class Reminders {
    static final String CHANNEL = "maik_rinnovi";
    private static final String KEY = "list";
    private static final int MAX = 60;
    private static final int TEST_ID = 9999;

    private Reminders() {}

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences("maik_rinnovi", Context.MODE_PRIVATE);
    }

    static void channel(Context c) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm == null || nm.getNotificationChannel(CHANNEL) != null) return;
        NotificationChannel ch = new NotificationChannel(CHANNEL, c.getString(R.string.channel_name), NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription(c.getString(R.string.channel_desc));
        nm.createNotificationChannel(ch);
    }

    private static JSONArray stored(Context c) {
        try {
            return new JSONArray(prefs(c).getString(KEY, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    /** Sostituisce tutti i promemoria con quelli nuovi: [{at, title, body, subId}, ...] */
    static synchronized void replaceAll(Context c, String json) {
        JSONArray old = stored(c);
        for (int k = 0; k < old.length(); k++) {
            JSONObject o = old.optJSONObject(k);
            if (o != null) cancel(c, o.optInt("id"));
        }
        JSONArray in;
        try {
            in = new JSONArray(json);
        } catch (JSONException e) {
            in = new JSONArray();
        }
        JSONArray keep = new JSONArray();
        long now = System.currentTimeMillis();
        for (int k = 0; k < in.length() && keep.length() < MAX; k++) {
            JSONObject o = in.optJSONObject(k);
            if (o == null || o.optLong("at") <= now) continue;
            try {
                o.put("id", k + 1);
            } catch (JSONException ignored) {
                continue;
            }
            keep.put(o);
            arm(c, o.optInt("id"), o.optLong("at"));
        }
        prefs(c).edit().putString(KEY, keep.toString()).apply();
    }

    /** Dopo il riavvio o un aggiornamento: rimette le sveglie ancora nel futuro. */
    static synchronized void rearmAll(Context c) {
        JSONArray a = stored(c);
        long now = System.currentTimeMillis();
        for (int k = 0; k < a.length(); k++) {
            JSONObject o = a.optJSONObject(k);
            if (o != null && o.optLong("at") > now) arm(c, o.optInt("id"), o.optLong("at"));
        }
    }

    private static synchronized JSONObject take(Context c, int id) {
        JSONArray a = stored(c), keep = new JSONArray();
        JSONObject found = null;
        for (int k = 0; k < a.length(); k++) {
            JSONObject o = a.optJSONObject(k);
            if (o == null) continue;
            if (o.optInt("id") == id) found = o;
            else keep.put(o);
        }
        prefs(c).edit().putString(KEY, keep.toString()).apply();
        return found;
    }

    private static PendingIntent alarmIntent(Context c, int id) {
        Intent i = new Intent(c, Fire.class).putExtra("id", id);
        return PendingIntent.getBroadcast(c, id, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private static void arm(Context c, int id, long at) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        if (am == null) return;
        PendingIntent p = alarmIntent(c, id);
        boolean exact = Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms();
        try {
            if (exact) am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);
            else am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p); // al massimo qualche minuto di ritardo
        } catch (SecurityException e) {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);
        }
    }

    private static void cancel(Context c, int id) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        if (am != null) am.cancel(alarmIntent(c, id));
    }

    static void show(Context c, int id, String title, String body, String subId) {
        channel(c);
        Intent open = new Intent(c, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (subId != null && !subId.isEmpty()) open.putExtra(MainActivity.EXTRA_SUB, subId);
        PendingIntent tap = PendingIntent.getActivity(c, 20000 + id, open,
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification n = new Notification.Builder(c, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_maik)
            .setColor(c.getColor(R.color.maik_violet))
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(new Notification.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(tap)
            .build();
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        try {
            if (nm != null) nm.notify(id, n);
        } catch (SecurityException ignored) {
            // notifiche non permesse dall'utente
        }
    }

    static void test(Context c, String title, String body) {
        show(c, TEST_ID, title, body, null);
    }

    /** Arriva l'ora di un promemoria. */
    public static class Fire extends BroadcastReceiver {
        @Override
        public void onReceive(Context c, Intent intent) {
            int id = intent.getIntExtra("id", -1);
            JSONObject o = take(c, id);
            if (o != null) show(c, id, o.optString("title"), o.optString("body"), o.optString("subId"));
        }
    }
}
