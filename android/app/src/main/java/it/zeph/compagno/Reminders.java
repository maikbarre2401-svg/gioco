package it.zeph.compagno;

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
 * Promemoria veri: li tiene Android (AlarmManager), quindi suonano anche se
 * Zeph è chiuso, e dopo un riavvio del telefono vengono rimessi in fila.
 */
final class Reminders {
    static final String CHANNEL = "zeph_promemoria";
    private static final String KEY = "list";
    private static final int MAX = 50;

    private Reminders() {}

    private static SharedPreferences p(Context c) {
        return c.getSharedPreferences("zeph_promemoria", Context.MODE_PRIVATE);
    }

    static void channel(Context c) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm == null || nm.getNotificationChannel(CHANNEL) != null) return;
        NotificationChannel r = new NotificationChannel(CHANNEL, "Promemoria di Zeph", NotificationManager.IMPORTANCE_HIGH);
        r.setDescription("Quando dici a Zeph «ricordami…»");
        nm.createNotificationChannel(r);
    }

    static synchronized JSONArray list(Context c) {
        try {
            return new JSONArray(p(c).getString(KEY, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    private static void store(Context c, JSONArray a) {
        p(c).edit().putString(KEY, a.toString()).apply();
    }

    /** Nuovo promemoria; restituisce il suo numero (o -1). */
    static synchronized int add(Context c, long at, String text) {
        if (at <= System.currentTimeMillis() - 60_000 || text == null) return -1;
        String t = text.trim();
        if (t.length() > 200) t = t.substring(0, 200);
        JSONArray a = list(c);
        if (a.length() >= MAX) return -1;
        int id = p(c).getInt("nextId", 1);
        p(c).edit().putInt("nextId", id + 1).apply();
        try {
            a.put(new JSONObject().put("id", id).put("at", at).put("text", t));
        } catch (JSONException e) {
            return -1;
        }
        store(c, a);
        arm(c, id, at, t);
        return id;
    }

    static synchronized void clear(Context c) {
        JSONArray a = list(c);
        for (int k = 0; k < a.length(); k++) {
            JSONObject o = a.optJSONObject(k);
            if (o != null) cancel(c, o.optInt("id"));
        }
        store(c, new JSONArray());
    }

    private static synchronized JSONObject take(Context c, int id) {
        JSONArray a = list(c), keep = new JSONArray();
        JSONObject found = null;
        for (int k = 0; k < a.length(); k++) {
            JSONObject o = a.optJSONObject(k);
            if (o == null) continue;
            if (o.optInt("id") == id) found = o;
            else keep.put(o);
        }
        store(c, keep);
        return found;
    }

    /** Dopo il riavvio: rimette le sveglie e avvisa di quelle perse mentre era spento. */
    static synchronized void rearmAll(Context c) {
        JSONArray a = list(c);
        long now = System.currentTimeMillis();
        for (int k = 0; k < a.length(); k++) {
            JSONObject o = a.optJSONObject(k);
            if (o == null) continue;
            long at = o.optLong("at");
            arm(c, o.optInt("id"), Math.max(at, now + 5_000), o.optString("text"));
        }
    }

    private static PendingIntent pi(Context c, int id, String text) {
        Intent i = new Intent(c, Fire.class).putExtra("id", id).putExtra("text", text);
        return PendingIntent.getBroadcast(c, 1000 + id, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private static void arm(Context c, int id, long at, String text) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        if (am == null) return;
        PendingIntent p = pi(c, id, text);
        boolean exact = Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms();
        try {
            if (exact) am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);
            else am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p); // qualche minuto di ritardo al massimo
        } catch (SecurityException e) {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);
        }
    }

    private static void cancel(Context c, int id) {
        AlarmManager am = c.getSystemService(AlarmManager.class);
        if (am != null) am.cancel(pi(c, id, ""));
    }

    /** È l'ora: notifica e, se Zeph è sullo schermo, te lo dice lui. */
    public static class Fire extends BroadcastReceiver {
        @Override
        public void onReceive(Context c, Intent i) {
            int id = i.getIntExtra("id", -1);
            JSONObject o = take(c, id);
            String text = o != null ? o.optString("text") : i.getStringExtra("text");
            if (text == null || text.isEmpty()) return;
            channel(c);
            PendingIntent open = PendingIntent.getActivity(c, 2000 + id,
                new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE);
            Notification n = new Notification.Builder(c, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat_zeph)
                .setContentTitle(Prefs.petName(c) + " ⏰ Promemoria")
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setCategory(Notification.CATEGORY_REMINDER)
                .setContentIntent(open)
                .setAutoCancel(true)
                .build();
            NotificationManager nm = c.getSystemService(NotificationManager.class);
            if (nm != null) nm.notify(3000 + id, n);
            if (ZephService.running) {
                try {
                    c.startService(new Intent(c, ZephService.class).setAction(ZephService.ACTION_SAY)
                        .putExtra(ZephService.EXTRA_TEXT, "Ehi! Promemoria: " + text)
                        .putExtra(ZephService.EXTRA_CMD, "jump"));
                } catch (Exception ignored) { /* servizio non raggiungibile: basta la notifica */ }
            }
        }
    }
}
