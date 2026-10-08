package it.zeph.compagno;

import android.content.Context;
import android.net.Uri;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * Serve le pagine, le librerie, il tuo avatar e il tuo look come se fossero
 * un sito (https://zeph.local/...). Verso internet passano solo il meteo e,
 * se hai messo la tua chiave, il cervello AI di Claude.
 */
final class LocalWeb {
    static final String HOST = "zeph.local";

    private LocalWeb() {}

    /** null = lascia andare la richiesta in rete (solo i servizi permessi). */
    static WebResourceResponse intercept(Context c, WebResourceRequest req) {
        Uri u = req.getUrl();
        String h = u.getHost();
        if (h != null && (h.equals("api.open-meteo.com") || h.equals("geocoding-api.open-meteo.com"))) {
            return null; // il meteo vero
        }
        if ("api.anthropic.com".equals(h) && Prefs.aiKey(c).length() > 0) {
            return null; // il cervello AI, solo se hai messo la tua chiave
        }
        if (!HOST.equals(h)) return notFound(); // nessun'altra rete esterna
        String path = u.getPath();
        if (path == null || path.equals("/")) path = "/overlay.html";
        path = path.substring(1);
        if (path.contains("..")) return notFound();
        try {
            InputStream in;
            if (path.equals("avatar.glb")) {
                if (Prefs.photoLook(c)) return notFound(); // c'è il look fatto con la foto
                File f = new File(c.getFilesDir(), "avatar.glb");
                if (f.exists()) in = new FileInputStream(f);
                else if (Prefs.useBundledAvatar(c)) in = c.getAssets().open("avatar.glb");
                else return notFound();
            } else if (path.equals("look.json")) {
                File f = new File(c.getFilesDir(), "look.json");
                if (!Prefs.photoLook(c) || !f.exists()) return notFound();
                in = new FileInputStream(f);
            } else {
                in = c.getAssets().open(path);
            }
            WebResourceResponse r = new WebResourceResponse(mime(path), "utf-8", in);
            r.setResponseHeaders(headers());
            return r;
        } catch (IOException e) {
            return notFound();
        }
    }

    private static Map<String, String> headers() {
        Map<String, String> h = new HashMap<>();
        h.put("Access-Control-Allow-Origin", "*");
        h.put("Cache-Control", "no-cache");
        return h;
    }

    private static WebResourceResponse notFound() {
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", headers(),
            new ByteArrayInputStream(new byte[0]));
    }

    private static String mime(String p) {
        if (p.endsWith(".html")) return "text/html";
        if (p.endsWith(".js")) return "application/javascript";
        if (p.endsWith(".json")) return "application/json";
        if (p.endsWith(".glb")) return "model/gltf-binary";
        if (p.endsWith(".png")) return "image/png";
        return "application/octet-stream";
    }
}
