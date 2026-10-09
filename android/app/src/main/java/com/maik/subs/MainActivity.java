package com.maik.subs;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.View;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Maik Subs: l'app (fatta con Expo / React Native Web) gira in una WebView con i file dentro l'APK,
 * quindi funziona offline. Il ponte "MaikAndroid" le dà notifiche vere, vibrazione, condivisione
 * e salvataggio dei backup.
 */
public class MainActivity extends Activity {
    static final String EXTRA_SUB = "subId";
    private static final int REQ_PICK = 1;
    private static final int REQ_SAVE = 2;
    private static final int REQ_NOTIF = 3;

    private WebView web;
    private ValueCallback<Uri[]> pickCallback;
    private String pendingSave;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        Reminders.channel(this);

        web = new WebView(this);
        web.setBackgroundColor(Color.TRANSPARENT); // finché l'app non è pronta si vede la schermata viola col logo
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // qui vengono salvati gli abbonamenti
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setTextZoom(100);
        s.setMediaPlaybackRequiresUserGesture(true);

        web.addJavascriptInterface(new Bridge(), "MaikAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                return LocalWeb.intercept(MainActivity.this, req);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (LocalWeb.HOST.equals(u.getHost())) return false;
                openExternal(u.toString()); // i link ai siti dei servizi si aprono nel browser
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> callback, FileChooserParams params) {
                // "Importa backup": scegli il file .json
                if (pickCallback != null) pickCallback.onReceiveValue(null);
                pickCallback = callback;
                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
                    .putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/json", "text/plain", "application/octet-stream"});
                try {
                    startActivityForResult(i, REQ_PICK);
                } catch (ActivityNotFoundException e) {
                    pickCallback = null;
                    return false;
                }
                return true;
            }
        });

        if (saved != null && web.restoreState(saved) != null) return;
        web.loadUrl(startUrl(getIntent()));
    }

    private static String startUrl(Intent intent) {
        String sub = intent == null ? null : intent.getStringExtra(EXTRA_SUB);
        return sub == null ? LocalWeb.HOME : LocalWeb.HOME + "subscription/" + Uri.encode(sub);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String sub = intent.getStringExtra(EXTRA_SUB);
        if (sub == null) return;
        // Tocco su un promemoria con l'app già aperta: apri quell'abbonamento.
        String id = JSONObject.quote(sub);
        web.evaluateJavascript("window.__maikOpen ? window.__maikOpen(" + id + ") : location.assign('/subscription/' + encodeURIComponent(" + id + "))", null);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @SuppressWarnings("deprecation")
    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == REQ_PICK && pickCallback != null) {
            pickCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, data));
            pickCallback = null;
        } else if (request == REQ_SAVE) {
            String content = pendingSave;
            pendingSave = null;
            if (result != RESULT_OK || data == null || data.getData() == null || content == null) return;
            try (OutputStream os = getContentResolver().openOutputStream(data.getData())) {
                if (os == null) throw new java.io.IOException("no stream");
                os.write(content.getBytes(StandardCharsets.UTF_8));
                Toast.makeText(this, R.string.saved, Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(this, R.string.save_failed, Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int request, String[] perms, int[] results) {
        super.onRequestPermissionsResult(request, perms, results);
        if (request == REQ_NOTIF) answerPermission(notificationsAllowed());
    }

    private void answerPermission(boolean granted) {
        web.evaluateJavascript("window.__maikPerm && window.__maikPerm(" + granted + ")", null);
    }

    private boolean notificationsAllowed() {
        if (Build.VERSION.SDK_INT >= 33
            && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return false;
        }
        NotificationManager nm = getSystemService(NotificationManager.class);
        return nm != null && nm.areNotificationsEnabled();
    }

    private void openExternal(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (ActivityNotFoundException ignored) {
            // nessun browser
        }
    }

    /** Metodi chiamati dall'app web come window.MaikAndroid.xxx(). Girano fuori dal thread grafico. */
    private final class Bridge {
        @JavascriptInterface
        public boolean notificationsAllowed() {
            return MainActivity.this.notificationsAllowed();
        }

        @JavascriptInterface
        public void requestNotifications() {
            runOnUiThread(() -> {
                if (Build.VERSION.SDK_INT >= 33 && !MainActivity.this.notificationsAllowed()) {
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
                } else {
                    answerPermission(MainActivity.this.notificationsAllowed());
                }
            });
        }

        @JavascriptInterface
        public void schedule(String json) {
            Reminders.replaceAll(getApplicationContext(), json);
        }

        @JavascriptInterface
        public void test(String title, String body) {
            Reminders.test(getApplicationContext(), title, body);
        }

        @JavascriptInterface
        public void vibrate(int ms) {
            Vibrator v = getSystemService(Vibrator.class);
            if (v == null || !v.hasVibrator()) return;
            v.vibrate(VibrationEffect.createOneShot(Math.max(5, Math.min(ms, 100)), VibrationEffect.DEFAULT_AMPLITUDE));
        }

        @JavascriptInterface
        public void shareText(String text) {
            runOnUiThread(() -> {
                Intent i = new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text);
                startActivity(Intent.createChooser(i, getString(R.string.share)));
            });
        }

        @JavascriptInterface
        public void saveFile(String name, String content, String mimeType) {
            runOnUiThread(() -> {
                pendingSave = content;
                Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                    .setType(mimeType == null || mimeType.isEmpty() ? "application/octet-stream" : mimeType)
                    .putExtra(Intent.EXTRA_TITLE, name);
                try {
                    startActivityForResult(i, REQ_SAVE);
                } catch (ActivityNotFoundException e) {
                    pendingSave = null;
                }
            });
        }

        @JavascriptInterface
        public void openUrl(String url) {
            runOnUiThread(() -> openExternal(url));
        }

        @JavascriptInterface
        public void setBars(String color, boolean dark) {
            runOnUiThread(() -> {
                int c;
                try {
                    c = Color.parseColor(color);
                } catch (IllegalArgumentException e) {
                    return;
                }
                Window w = getWindow();
                w.setStatusBarColor(c);
                w.setNavigationBarColor(c);
                View d = w.getDecorView();
                int flags = d.getSystemUiVisibility();
                if (dark) flags &= ~(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
                else flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                d.setSystemUiVisibility(flags);
            });
        }
    }
}
