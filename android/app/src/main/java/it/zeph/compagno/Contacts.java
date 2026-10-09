package it.zeph.compagno;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.provider.CalendarContract;
import android.provider.ContactsContract;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Calendar;
import java.util.Locale;

/**
 * Rubrica e agenda, solo in lettura e solo se gli dai il permesso:
 * «chiama Giulia» trova il numero, «che impegni ho oggi?» legge il calendario.
 */
final class Contacts {
    private Contacts() {}

    static boolean canReadContacts(Context c) {
        return c.checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED;
    }

    static boolean canReadCalendar(Context c) {
        return c.checkSelfPermission(Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED;
    }

    /** {name, number} del contatto che somiglia di più a «name», oppure {error: "perm" | "none"}. */
    static String find(Context c, String name) {
        try {
            if (!canReadContacts(c)) return new JSONObject().put("error", "perm").toString();
            String q = name == null ? "" : name.trim();
            if (q.isEmpty()) return new JSONObject().put("error", "none").toString();
            Uri uri = Uri.withAppendedPath(ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI, Uri.encode(q));
            String[] proj = {
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER,
                ContactsContract.CommonDataKinds.Phone.TYPE,
                ContactsContract.CommonDataKinds.Phone.IS_SUPER_PRIMARY,
            };
            String bestName = null, bestNum = null;
            int bestScore = -1;
            String lq = q.toLowerCase(Locale.ITALIAN);
            try (Cursor cur = c.getContentResolver().query(uri, proj, null, null, null)) {
                while (cur != null && cur.moveToNext()) {
                    String dn = cur.getString(0), num = cur.getString(1);
                    if (dn == null || num == null) continue;
                    String ld = dn.toLowerCase(Locale.ITALIAN);
                    int score = ld.equals(lq) ? 100 : ld.startsWith(lq + " ") || ld.startsWith(lq) ? 60 : ld.contains(lq) ? 30 : 10;
                    if (cur.getInt(2) == ContactsContract.CommonDataKinds.Phone.TYPE_MOBILE) score += 5;
                    if (cur.getInt(3) != 0) score += 8;
                    if (score > bestScore) { bestScore = score; bestName = dn; bestNum = num; }
                }
            }
            if (bestNum == null) return new JSONObject().put("error", "none").toString();
            return new JSONObject().put("name", bestName).put("number", bestNum).toString();
        } catch (JSONException | SecurityException | IllegalArgumentException e) {
            return "{\"error\":\"none\"}";
        }
    }

    /** Gli impegni di oggi (offset 0), domani (1)…: [{title, begin, allDay}] oppure {error: "perm"}. */
    static String events(Context c, int offset) {
        try {
            if (!canReadCalendar(c)) return new JSONObject().put("error", "perm").toString();
            Calendar from = Calendar.getInstance();
            from.set(Calendar.HOUR_OF_DAY, 0); from.set(Calendar.MINUTE, 0); from.set(Calendar.SECOND, 0); from.set(Calendar.MILLISECOND, 0);
            from.add(Calendar.DAY_OF_YEAR, Math.max(0, Math.min(30, offset)));
            long a = from.getTimeInMillis(), b = a + 24L * 3600_000L;
            Uri.Builder ub = CalendarContract.Instances.CONTENT_URI.buildUpon();
            android.content.ContentUris.appendId(ub, a);
            android.content.ContentUris.appendId(ub, b);
            String[] proj = { CalendarContract.Instances.TITLE, CalendarContract.Instances.BEGIN, CalendarContract.Instances.ALL_DAY };
            JSONArray out = new JSONArray();
            try (Cursor cur = c.getContentResolver().query(ub.build(), proj, null, null, CalendarContract.Instances.BEGIN + " ASC")) {
                while (cur != null && cur.moveToNext() && out.length() < 12) {
                    String t = cur.getString(0);
                    out.put(new JSONObject().put("title", t == null ? "Impegno" : t).put("begin", cur.getLong(1)).put("allDay", cur.getInt(2) != 0));
                }
            }
            return out.toString();
        } catch (JSONException | SecurityException | IllegalArgumentException e) {
            return "[]";
        }
    }
}
