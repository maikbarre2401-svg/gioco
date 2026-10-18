package com.ghostlink.app;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.graphics.Insets;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.net.Uri;
import android.provider.Settings;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.speech.tts.TextToSpeech;
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
import java.util.Locale;

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
    private static final int REQ_CAMERA = 10;
    private static final int REQ_MIC = 11;
    private static final int REQ_LOCATION = 12;

    private WebView web;
    private PermissionRequest pendingWebRequest;
    private GeolocationPermissions.Callback pendingGeoCallback;
    private String pendingGeoOrigin;
    private CameraManager cameraManager;
    private String torchCameraId;
    private boolean torchLookupDone;
    private volatile boolean torchOn;
    private TextToSpeech tts;
    private volatile boolean ttsReady;

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

        tts = new TextToSpeech(getApplicationContext(), new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int status) {
                if (status == TextToSpeech.SUCCESS) {
                    int r = tts.setLanguage(Locale.ITALIAN);
                    ttsReady = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED;
                    tts.setPitch(0.7f);
                    tts.setSpeechRate(0.98f);
                }
            }
        });
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
        if (tts != null) { tts.stop(); tts.shutdown(); }
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
        if (requestCode == REQ_CAMERA || requestCode == REQ_MIC || requestCode == REQ_LOCATION) {
            String kind = requestCode == REQ_CAMERA ? "camera" : requestCode == REQ_MIC ? "mic" : "location";
            sendPermResult(kind, anyGranted, anyGranted ? "granted" : "denied");
            return;
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

    /* -------------------------------------------------------------- permissions */

    private String[] permsFor(String kind) {
        if ("camera".equals(kind)) return new String[]{Manifest.permission.CAMERA};
        if ("mic".equals(kind)) return new String[]{Manifest.permission.RECORD_AUDIO};
        if ("location".equals(kind)) {
            return new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION};
        }
        return new String[0];
    }

    private int codeFor(String kind) {
        if ("camera".equals(kind)) return REQ_CAMERA;
        if ("mic".equals(kind)) return REQ_MIC;
        return REQ_LOCATION;
    }

    private boolean held(String kind) {
        String[] perms = permsFor(kind);
        if (perms.length == 0) return false;
        for (String p : perms) {
            if (checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED) return true;
        }
        return false;
    }

    /** Asks Android for a permission before the page touches the matching API. */
    private void ensurePermission(final String kind) {
        if (held(kind)) { sendPermResult(kind, true, "granted"); return; }
        final String[] perms = permsFor(kind);
        if (perms.length == 0) { sendPermResult(kind, false, "unknown"); return; }
        // A permission the user permanently denied returns instantly with no dialog: say so,
        // so the page can offer to open the system settings instead of looping.
        final boolean canAsk = shouldShowRequestPermissionRationale(perms[0]) || !askedAlready.contains(kind);
        askedAlready.add(kind);
        if (!canAsk) { sendPermResult(kind, false, "blocked"); return; }
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                requestPermissions(perms, codeFor(kind));
            }
        });
    }

    private final java.util.Set<String> askedAlready = new java.util.HashSet<String>();

    private void sendPermResult(final String kind, final boolean ok, final String state) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript("window.GL && GL.ui && GL.ui._perm && GL.ui._perm('"
                        + kind + "'," + ok + ",'" + state + "')", null);
            }
        });
    }

    /* --------------------------------------------------------------- biometrics */

    /**
     * What this device can actually verify for an app: 'face', 'biometric', 'credential'
     * (the phone's own PIN/pattern) or 'none'. Many phones expose face unlock only as a WEAK
     * authenticator — or not at all — so weak is accepted and device credential is the fallback.
     */
    private String biometricKind() {
        if (Build.VERSION.SDK_INT < 28) return "none";
        boolean hasFace = getPackageManager().hasSystemFeature(PackageManager.FEATURE_FACE);
        boolean hasFinger = getPackageManager().hasSystemFeature(PackageManager.FEATURE_FINGERPRINT);
        BiometricManager bm = Build.VERSION.SDK_INT >= 29
                ? (BiometricManager) getSystemService(Context.BIOMETRIC_SERVICE) : null;
        if (Build.VERSION.SDK_INT >= 30 && bm != null) {
            if (bm.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK)
                    == BiometricManager.BIOMETRIC_SUCCESS) return hasFace ? "face" : "biometric";
            if (bm.canAuthenticate(BiometricManager.Authenticators.DEVICE_CREDENTIAL)
                    == BiometricManager.BIOMETRIC_SUCCESS) return "credential";
            return "none";
        }
        if (bm != null && bm.canAuthenticate() != BiometricManager.BIOMETRIC_SUCCESS) return "none";
        return hasFace ? "face" : (hasFinger ? "biometric" : "none");
    }

    /** Human-readable capability line for the diagnostics screen. */
    private String biometricDetail() {
        if (Build.VERSION.SDK_INT < 28) return "Android troppo vecchio per lo sblocco biometrico nelle app";
        StringBuilder sb = new StringBuilder();
        sb.append(getPackageManager().hasSystemFeature(PackageManager.FEATURE_FACE) ? "sensore volto presente" : "nessun sensore volto");
        sb.append(getPackageManager().hasSystemFeature(PackageManager.FEATURE_FINGERPRINT) ? ", impronta presente" : ", nessuna impronta");
        if (Build.VERSION.SDK_INT >= 30) {
            BiometricManager bm = (BiometricManager) getSystemService(Context.BIOMETRIC_SERVICE);
            if (bm != null) {
                sb.append("; per le app: debole=").append(statusWord(bm.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK)));
                sb.append(", forte=").append(statusWord(bm.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)));
                sb.append(", codice telefono=").append(statusWord(bm.canAuthenticate(BiometricManager.Authenticators.DEVICE_CREDENTIAL)));
            }
        }
        return sb.toString();
    }

    private String statusWord(int status) {
        if (status == BiometricManager.BIOMETRIC_SUCCESS) return "ok";
        if (status == BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED) return "non registrato";
        if (status == BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE) return "assente";
        if (status == BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE) return "non disponibile";
        return "no";
    }

    /** Shows the system biometric prompt; the verdict goes back to the page. */
    private void promptBiometric(final String title, final String subtitle) {
        if (Build.VERSION.SDK_INT < 28) { sendBioResult(false, "non supportato"); return; }
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    BiometricPrompt.Builder b = new BiometricPrompt.Builder(MainActivity.this)
                            .setTitle(title == null || title.isEmpty() ? "Ghostlink" : title);
                    if (subtitle != null && !subtitle.isEmpty()) b.setSubtitle(subtitle);
                    // Accept a weak authenticator (that is how most phones expose face unlock) and
                    // let the phone's own PIN/pattern stand in. A negative button is not allowed
                    // together with device credential, so it is only set on older releases.
                    if (Build.VERSION.SDK_INT >= 30) {
                        b.setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK
                                | BiometricManager.Authenticators.DEVICE_CREDENTIAL);
                    } else if (Build.VERSION.SDK_INT >= 29) {
                        b.setDeviceCredentialAllowed(true);
                    } else {
                        b.setNegativeButton(getString(R.string.cancel), getMainExecutor(),
                                new android.content.DialogInterface.OnClickListener() {
                                    @Override
                                    public void onClick(android.content.DialogInterface d, int w) {
                                        sendBioResult(false, "annullato");
                                    }
                                });
                    }
                    b.build().authenticate(new CancellationSignal(), getMainExecutor(),
                            new BiometricPrompt.AuthenticationCallback() {
                                @Override
                                public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult r) {
                                    sendBioResult(true, "");
                                }

                                @Override
                                public void onAuthenticationError(int code, CharSequence err) {
                                    sendBioResult(false, err == null ? "errore" : err.toString());
                                }

                                @Override
                                public void onAuthenticationFailed() {
                                    // a single mismatch: the prompt stays open, so don't resolve yet
                                }
                            });
                } catch (Exception e) {
                    sendBioResult(false, "non disponibile");
                }
            }
        });
    }

    private void sendBioResult(final boolean ok, final String msg) {
        final String safe = msg == null ? "" : msg.replace("\\", "").replace("'", "").replace("\n", " ");
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                web.evaluateJavascript("window.GL && GL.face && GL.face._native(" + ok + ",'" + safe + "')", null);
            }
        });
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
        public void ensurePermission(String kind) {
            MainActivity.this.ensurePermission(kind);
        }

        @JavascriptInterface
        public String permState(String kind) {
            return held(kind) ? "granted" : "unknown";
        }

        @JavascriptInterface
        public void openAppSettings() {
            try {
                Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.fromParts("package", getPackageName(), null));
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(i);
            } catch (Exception ignored) {
                // settings screen unavailable
            }
        }

        @JavascriptInterface
        public String bioAvailable() {
            return biometricKind();
        }

        @JavascriptInterface
        public String bioDetail() {
            return biometricDetail();
        }

        @JavascriptInterface
        public void bioAuth(String title, String subtitle) {
            promptBiometric(title, subtitle);
        }

        @JavascriptInterface
        public void speak(String text) {
            if (!ttsReady || tts == null) return;
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "ghostlink");
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
