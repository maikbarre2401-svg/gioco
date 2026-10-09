package com.ghostlink.app;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Insets;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import org.json.JSONArray;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * Hosts the Ghostlink web app (assets/www) in a full-screen WebView.
 * Files are served from a private https origin so the page runs in a secure context
 * (Web Crypto, sensors, microphone), and a small JavaScript bridge adds what the web
 * platform cannot do inside a WebView: the LED torch, vibration, clipboard and sharing.
 */
public class MainActivity extends Activity {

    private static final String HOST = "appassets.androidplatform.net";
    private static final String START_URL = "https://" + HOST + "/index.html";
    private static final int BG = 0xFF05070D;
    private static final int REQ_WEB = 1;
    private static final int REQ_GEO = 2;

    private WebView web;
    private PermissionRequest pendingWebRequest;
    private GeolocationPermissions.Callback pendingGeoCallback;
    private String pendingGeoOrigin;
    private CameraManager cameraManager;
    private String torchCameraId;
    private boolean torchLookupDone;
    private volatile boolean torchOn;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG);
        // Keep content clear of the status bar, navigation bar, notch and keyboard
        // (Android 15 draws apps edge to edge).
        root.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override
            public WindowInsets onApplyWindowInsets(View v, WindowInsets insets) {
                if (Build.VERSION.SDK_INT >= 30) {
                    Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                    Insets ime = insets.getInsets(WindowInsets.Type.ime());
                    v.setPadding(bars.left, bars.top, bars.right, Math.max(bars.bottom, ime.bottom));
                } else {
                    v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                            insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
                }
                return insets;
            }
        });

        web = new WebView(this);
        web.setBackgroundColor(BG);
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setGeolocationEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);

        web.addJavascriptInterface(new NativeBridge(), "GhostlinkNative");
        web.setWebViewClient(new AssetClient());
        web.setWebChromeClient(new PermissionClient());

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(START_URL);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        setTorch(false);
        web.destroy();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        // Screens are hash routes, so WebView history mirrors the app's navigation.
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    /* ------------------------------------------------------------------ assets */

    private class AssetClient extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            if (!HOST.equals(url.getHost())) {
                return null; // network requests (public IP lookup) go out normally
            }
            String path = url.getPath();
            if (path == null || path.equals("/") || path.isEmpty()) {
                path = "/index.html";
            }
            try {
                InputStream in = getAssets().open("www" + path);
                String mime = mimeType(path);
                return new WebResourceResponse(mime, mime.startsWith("text/") || mime.endsWith("javascript") || mime.endsWith("json") ? "utf-8" : null, in);
            } catch (IOException e) {
                return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", null,
                        new ByteArrayInputStream(new byte[0]));
            }
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            if (HOST.equals(url.getHost())) {
                return false;
            }
            // External links (the map in Sensori) open in the phone's browser or maps app.
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, url));
            } catch (Exception ignored) {
                // no app can open it
            }
            return true;
        }
    }

    private static String mimeType(String path) {
        String p = path.toLowerCase();
        if (p.endsWith(".html")) return "text/html";
        if (p.endsWith(".css")) return "text/css";
        if (p.endsWith(".js")) return "application/javascript";
        if (p.endsWith(".json") || p.endsWith(".webmanifest")) return "application/json";
        if (p.endsWith(".svg")) return "image/svg+xml";
        if (p.endsWith(".png")) return "image/png";
        if (p.endsWith(".woff2")) return "font/woff2";
        return "application/octet-stream";
    }

    /* ------------------------------------------------------------- permissions */

    private class PermissionClient extends WebChromeClient {
        @Override
        public void onPermissionRequest(PermissionRequest request) {
            List<String> missing = new ArrayList<String>();
            for (String res : request.getResources()) {
                String perm = null;
                if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res)) perm = Manifest.permission.RECORD_AUDIO;
                else if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res)) perm = Manifest.permission.CAMERA;
                if (perm != null && checkSelfPermission(perm) != PackageManager.PERMISSION_GRANTED) {
                    missing.add(perm);
                }
            }
            if (missing.isEmpty()) {
                request.grant(request.getResources());
            } else {
                pendingWebRequest = request;
                requestPermissions(missing.toArray(new String[0]), REQ_WEB);
            }
        }

        @Override
        public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
            if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                callback.invoke(origin, true, false);
                return;
            }
            pendingGeoOrigin = origin;
            pendingGeoCallback = callback;
            requestPermissions(new String[]{
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_GEO);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        boolean anyGranted = false;
        boolean allGranted = grantResults.length > 0;
        for (int r : grantResults) {
            if (r == PackageManager.PERMISSION_GRANTED) anyGranted = true;
            else allGranted = false;
        }
        if (requestCode == REQ_WEB && pendingWebRequest != null) {
            if (allGranted) pendingWebRequest.grant(pendingWebRequest.getResources());
            else pendingWebRequest.deny();
            pendingWebRequest = null;
        } else if (requestCode == REQ_GEO && pendingGeoCallback != null) {
            pendingGeoCallback.invoke(pendingGeoOrigin, anyGranted, false);
            pendingGeoCallback = null;
            pendingGeoOrigin = null;
        }
    }

    /* ------------------------------------------------------------------- torch */

    private synchronized String torchCamera() {
        if (torchLookupDone) return torchCameraId;
        torchLookupDone = true;
        try {
            cameraManager = (CameraManager) getSystemService(Context.CAMERA_SERVICE);
            for (String id : cameraManager.getCameraIdList()) {
                CameraCharacteristics c = cameraManager.getCameraCharacteristics(id);
                Boolean flash = c.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                Integer facing = c.get(CameraCharacteristics.LENS_FACING);
                if (Boolean.TRUE.equals(flash) && facing != null && facing == CameraCharacteristics.LENS_FACING_BACK) {
                    torchCameraId = id;
                    break;
                }
            }
        } catch (Exception e) {
            torchCameraId = null;
        }
        return torchCameraId;
    }

    private void setTorch(boolean on) {
        String id = torchCamera();
        if (id == null || torchOn == on) return;
        try {
            cameraManager.setTorchMode(id, on);
            torchOn = on;
        } catch (Exception ignored) {
            // camera busy or torch unavailable
        }
    }

    /* ------------------------------------------------------------------ bridge */

    /** Methods callable from JavaScript as window.GhostlinkNative.*; they run on a background thread. */
    private class NativeBridge {
        @JavascriptInterface
        public boolean hasTorch() {
            return torchCamera() != null;
        }

        @JavascriptInterface
        public void setTorch(boolean on) {
            MainActivity.this.setTorch(on);
        }

        @JavascriptInterface
        public void vibrate(String patternJson) {
            try {
                JSONArray arr = new JSONArray(patternJson);
                long[] timings = new long[arr.length() + 1]; // Android patterns start with a pause
                for (int i = 0; i < arr.length(); i++) timings[i + 1] = arr.getLong(i);
                Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
                if (v == null || !v.hasVibrator()) return;
                if (Build.VERSION.SDK_INT >= 26) {
                    v.vibrate(VibrationEffect.createWaveform(timings, -1));
                } else {
                    v.vibrate(timings, -1);
                }
            } catch (Exception ignored) {
                // bad pattern or no vibrator
            }
        }

        @JavascriptInterface
        public void copy(String text) {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("Ghostlink", text));
        }

        @JavascriptInterface
        public String paste() {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm == null) return "";
            ClipData clip = cm.getPrimaryClip();
            if (clip == null || clip.getItemCount() == 0) return "";
            CharSequence text = clip.getItemAt(0).coerceToText(MainActivity.this);
            return text == null ? "" : text.toString();
        }

        @JavascriptInterface
        public void share(String text) {
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("text/plain");
            send.putExtra(Intent.EXTRA_TEXT, text);
            startActivity(Intent.createChooser(send, getString(R.string.share_title)));
        }
    }
}
