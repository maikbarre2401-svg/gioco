package com.maik.subs;

import android.content.Context;
import android.net.Uri;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * Serve l'app (assets/www) come se fosse un sito: https://maik.local/...
 * Tutto il resto (solo i loghi dei servizi) va normalmente in rete.
 */
final class LocalWeb {
    static final String HOST = "maik.local";
    static final String HOME = "https://" + HOST + "/";

    private LocalWeb() {}

    /** null = lascia andare la richiesta in rete. */
    static WebResourceResponse intercept(Context c, WebResourceRequest req) {
        Uri u = req.getUrl();
        if (!HOST.equals(u.getHost())) return null;
        String path = u.getPath();
        if (path == null || path.equals("/")) path = "/index.html";
        path = path.substring(1);
        if (path.contains("..")) return notFound();
        // Le pagine dell'app (/premium, /subscription/xyz…) sono tutte index.html: ci pensa il router.
        String last = path.substring(path.lastIndexOf('/') + 1);
        if (!last.contains(".")) path = "index.html";
        try {
            InputStream in = c.getAssets().open("www/" + path);
            WebResourceResponse r = new WebResourceResponse(mime(path), mime(path).startsWith("text/") ? "utf-8" : null, in);
            Map<String, String> h = new HashMap<>();
            h.put("Cache-Control", path.equals("index.html") ? "no-cache" : "max-age=31536000");
            r.setResponseHeaders(h);
            return r;
        } catch (IOException e) {
            return notFound();
        }
    }

    private static WebResourceResponse notFound() {
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", new HashMap<>(),
            new ByteArrayInputStream(new byte[0]));
    }

    private static String mime(String p) {
        if (p.endsWith(".html")) return "text/html";
        if (p.endsWith(".js")) return "application/javascript";
        if (p.endsWith(".css")) return "text/css";
        if (p.endsWith(".json")) return "application/json";
        if (p.endsWith(".png")) return "image/png";
        if (p.endsWith(".jpg") || p.endsWith(".jpeg")) return "image/jpeg";
        if (p.endsWith(".svg")) return "image/svg+xml";
        if (p.endsWith(".ico")) return "image/x-icon";
        if (p.endsWith(".ttf")) return "font/ttf";
        if (p.endsWith(".woff2")) return "font/woff2";
        return "application/octet-stream";
    }
}
