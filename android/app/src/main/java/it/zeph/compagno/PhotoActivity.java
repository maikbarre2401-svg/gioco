package it.zeph.compagno;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * «Avatar dalla foto»: la pagina foto.html con la fotocamera frontale.
 * La foto resta sul telefono: il look (colori + faccia ritagliata) viene
 * salvato in look.json dentro l'app e il compagno lo indossa subito.
 */
public class PhotoActivity extends Activity {
    private static final String TAG = "ZephFoto";
    private static final int REQ_CAMERA = 31;
    private static final int REQ_FILE = 32;

    private WebView web;
    private PermissionRequest pendingCamera;
    private ValueCallback<Uri[]> pendingFile;

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(0xFF0F1726);
        web = new WebView(this);
        web.setBackgroundColor(0xFF0F1726);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        web.addJavascriptInterface(new Bridge(), "ZephPhoto");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                return LocalWeb.intercept(PhotoActivity.this, req);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) { return true; }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(PermissionRequest r) {
                // la pagina chiede la fotocamera: la diamo solo a lei, solo per il video
                boolean video = false;
                for (String res : r.getResources()) if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res)) video = true;
                if (!video || !LocalWeb.HOST.equals(r.getOrigin().getHost())) { r.deny(); return; }
                if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                    r.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
                } else {
                    pendingCamera = r;
                    requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
                }
            }

            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (pendingFile != null) pendingFile.onReceiveValue(null);
                pendingFile = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*");
                try {
                    startActivityForResult(Intent.createChooser(i, "Scegli una foto"), REQ_FILE);
                } catch (Exception e) {
                    pendingFile = null;
                    return false;
                }
                return true;
            }

            @Override
            public boolean onConsoleMessage(ConsoleMessage m) {
                Log.d(TAG, m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
                return true;
            }
        });
        setContentView(web);
        web.loadUrl("https://" + LocalWeb.HOST + "/foto.html");
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        super.onRequestPermissionsResult(req, perms, res);
        if (req != REQ_CAMERA || pendingCamera == null) return;
        if (res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED) {
            pendingCamera.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
        } else {
            pendingCamera.deny();
        }
        pendingCamera = null;
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_FILE || pendingFile == null) return;
        Uri u = res == RESULT_OK && data != null ? data.getData() : null;
        pendingFile.onReceiveValue(u != null ? new Uri[]{u} : null);
        pendingFile = null;
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }

    /** Salva il look (colori + faccia) e lo fa indossare al compagno. */
    private boolean saveLook(String json) {
        try {
            JSONObject o = new JSONObject(json);
            if (!o.has("skin") || json.length() > 3 * 1024 * 1024) return false;
            String face = o.optString("face", "");
            if (!face.isEmpty() && !face.startsWith("data:image/jpeg;base64,")) return false;
            String pet = o.optString("petName", "").trim();
            if (!pet.isEmpty()) Prefs.setPetName(this, pet);
            o.remove("petName");
            File tmp = new File(getFilesDir(), "look.tmp");
            try (OutputStream out = new FileOutputStream(tmp)) {
                out.write(o.toString().getBytes(StandardCharsets.UTF_8));
            }
            if (!tmp.renameTo(new File(getFilesDir(), "look.json"))) return false;
            Prefs.setPhotoLook(this, true);
            return true;
        } catch (JSONException | java.io.IOException e) {
            Log.w(TAG, "look non salvato", e);
            return false;
        }
    }

    /** I metodi che foto.js può chiamare. */
    private class Bridge {
        @JavascriptInterface public String petName() { return Prefs.petName(PhotoActivity.this); }

        @JavascriptInterface public void save(String json) {
            boolean ok = saveLook(json);
            runOnUiThread(() -> {
                if (ok) {
                    if (ZephService.running) {
                        startService(new Intent(PhotoActivity.this, ZephService.class).setAction(ZephService.ACTION_AVATAR));
                    }
                    Toast.makeText(PhotoActivity.this, "Fatto! Guarda il tuo compagno sullo schermo", Toast.LENGTH_LONG).show();
                    finish();
                } else {
                    Toast.makeText(PhotoActivity.this, "Non sono riuscito a salvare, riprova", Toast.LENGTH_LONG).show();
                    if (web != null) web.evaluateJavascript("document.getElementById('save').disabled=false", null);
                }
            });
        }

        @JavascriptInterface public void openUrl(String url) {
            if (!"https://avaturn.me".equals(url)) return; // solo il link previsto
            runOnUiThread(() -> {
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                } catch (Exception e) {
                    Toast.makeText(PhotoActivity.this, "Non trovo un browser", Toast.LENGTH_SHORT).show();
                }
            });
        }
    }
}
