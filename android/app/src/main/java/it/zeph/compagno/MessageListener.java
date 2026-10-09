package it.zeph.compagno;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.RemoteInput;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Parcelable;
import android.provider.Settings;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;

/**
 * «Ti ha scritto Giulia su WhatsApp!»: se nelle Impostazioni gli dai
 * l'accesso alle notifiche, Zeph vede i messaggi delle app di chat (solo
 * quelle in lista), te li annuncia e, se glielo dici tu e confermi, risponde
 * con il pulsante «Rispondi» della notifica. I messaggi restano in memoria
 * solo finché l'app è aperta: non vengono salvati da nessuna parte.
 */
public class MessageListener extends NotificationListenerService {
    private static final Set<String> APPS = new HashSet<>(Arrays.asList(
        "com.whatsapp", "com.whatsapp.w4b", "org.telegram.messenger", "org.telegram.messenger.web",
        "com.google.android.apps.messaging", "com.samsung.android.messaging", "com.android.mms",
        "com.facebook.orca", "com.instagram.android", "org.thoughtcrime.securesms", "com.discord",
        "com.google.android.gm", "com.microsoft.teams", "com.snapchat.android"));

    /** Un messaggio arrivato (con il pulsante per rispondere, se c'è). */
    static final class Msg {
        String key, app, who, text;
        long at;
        Notification.Action reply;
    }

    private static final ArrayDeque<Msg> recent = new ArrayDeque<>();
    private static final int MAX = 20;

    static boolean enabled(Context c) {
        String s = Settings.Secure.getString(c.getContentResolver(), "enabled_notification_listeners");
        return s != null && s.contains(new ComponentName(c, MessageListener.class).flattenToString());
    }

    static String appName(String pkg) {
        switch (pkg) {
            case "com.whatsapp": case "com.whatsapp.w4b": return "WhatsApp";
            case "org.telegram.messenger": case "org.telegram.messenger.web": return "Telegram";
            case "com.facebook.orca": return "Messenger";
            case "com.instagram.android": return "Instagram";
            case "org.thoughtcrime.securesms": return "Signal";
            case "com.discord": return "Discord";
            case "com.google.android.gm": return "Gmail";
            case "com.microsoft.teams": return "Teams";
            case "com.snapchat.android": return "Snapchat";
            default: return "SMS";
        }
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null || !APPS.contains(sbn.getPackageName())) return;
        Notification n = sbn.getNotification();
        if (n == null || (n.flags & Notification.FLAG_GROUP_SUMMARY) != 0 || (n.flags & Notification.FLAG_ONGOING_EVENT) != 0) return;
        Bundle ex = n.extras;
        if (ex == null) return;
        CharSequence title = ex.getCharSequence(Notification.EXTRA_TITLE);
        CharSequence text = ex.getCharSequence(Notification.EXTRA_TEXT);
        // nelle chat «a messaggi» l'ultimo messaggio è il più affidabile
        Parcelable[] msgs = ex.getParcelableArray(Notification.EXTRA_MESSAGES);
        if (msgs != null && msgs.length > 0 && msgs[msgs.length - 1] instanceof Bundle) {
            Bundle last = (Bundle) msgs[msgs.length - 1];
            CharSequence t = last.getCharSequence("text");
            if (t != null) text = t;
        }
        if (title == null || text == null) return;
        Msg m = new Msg();
        m.key = sbn.getKey();
        m.app = appName(sbn.getPackageName());
        m.who = title.toString().trim();
        m.text = text.toString().trim();
        m.at = System.currentTimeMillis();
        m.reply = findReply(n);
        if (m.text.isEmpty() || m.text.length() > 2000) return;
        synchronized (recent) {
            // le app aggiornano spesso la stessa notifica: niente doppioni
            for (Msg o : recent) if (o.who.equals(m.who) && o.text.equals(m.text)) { o.reply = m.reply != null ? m.reply : o.reply; o.key = m.key; return; }
            recent.addFirst(m);
            while (recent.size() > MAX) recent.removeLast();
        }
        if (Prefs.announceMessages(this) && ZephService.running) {
            try {
                JSONObject o = new JSONObject().put("app", m.app).put("who", m.who)
                    .put("text", Prefs.readMessages(this) ? m.text : "");
                startService(new Intent(this, ZephService.class).setAction(ZephService.ACTION_MESSAGE)
                    .putExtra(ZephService.EXTRA_TEXT, o.toString()));
            } catch (JSONException | IllegalStateException | SecurityException ignored) { /* niente annuncio */ }
        }
    }

    private static Notification.Action findReply(Notification n) {
        Notification.Action found = pick(n.actions);
        if (found != null) return found;
        // WhatsApp e altre mettono «Rispondi» anche tra le azioni per l'orologio
        try {
            return pick(new Notification.WearableExtender(n).getActions().toArray(new Notification.Action[0]));
        } catch (RuntimeException e) {
            return null;
        }
    }

    private static Notification.Action pick(Notification.Action[] actions) {
        if (actions == null) return null;
        for (Notification.Action a : actions) {
            RemoteInput[] ri = a.getRemoteInputs();
            if (ri != null && ri.length > 0 && a.actionIntent != null) return a;
        }
        return null;
    }

    /** Gli ultimi messaggi per «chi mi ha scritto?»: [{who, app, text, ago, reply}]. */
    static String recentJson() {
        JSONArray a = new JSONArray();
        long now = System.currentTimeMillis();
        synchronized (recent) {
            for (Msg m : recent) {
                try {
                    a.put(new JSONObject().put("who", m.who).put("app", m.app).put("text", m.text)
                        .put("ago", (now - m.at) / 60000).put("reply", m.reply != null));
                } catch (JSONException ignored) { /* salta */ }
            }
        }
        return a.toString();
    }

    /** Risponde all'ultimo messaggio di «who» (o all'ultimo in assoluto). Solo dopo la tua conferma. */
    static String reply(Context c, String who, String text) {
        if (text == null || text.trim().isEmpty()) return "";
        String w = who == null ? "" : who.trim().toLowerCase();
        Msg target = null;
        synchronized (recent) {
            Iterator<Msg> it = recent.iterator();
            while (it.hasNext()) {
                Msg m = it.next();
                if (m.reply == null) continue;
                if (w.isEmpty() || m.who.toLowerCase().contains(w)) { target = m; break; }
            }
        }
        if (target == null) return "";
        RemoteInput[] inputs = target.reply.getRemoteInputs();
        Intent fill = new Intent();
        Bundle res = new Bundle();
        for (RemoteInput ri : inputs) res.putCharSequence(ri.getResultKey(), text.trim());
        RemoteInput.addResultsToIntent(inputs, fill, res);
        try {
            target.reply.actionIntent.send(c, 0, fill);
            target.reply = null; // una risposta sola per messaggio
            return target.who + "|" + target.app;
        } catch (PendingIntent.CanceledException e) {
            return "";
        }
    }

    /** A chi risponderebbe (per la domanda di conferma). */
    static String peek(String who) {
        String w = who == null ? "" : who.trim().toLowerCase();
        synchronized (recent) {
            for (Msg m : recent) {
                if (m.reply == null) continue;
                if (w.isEmpty() || m.who.toLowerCase().contains(w)) return m.who + "|" + m.app;
            }
        }
        return "";
    }
}
