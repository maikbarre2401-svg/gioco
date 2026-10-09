package it.zeph.compagno;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.content.res.ColorStateList;
import android.graphics.LinearGradient;
import android.graphics.Shader;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.view.ViewOutlineProvider;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.text.InputType;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

/** La schermata dell'app: permessi, avvio, il tuo avatar e le opzioni. */
public class MainActivity extends Activity {
    private static final int REQ_AVATAR = 21;
    private static final int REQ_NOTIF = 22;
    private static final int REQ_CONTACTS = 23;
    private static final int REQ_CALENDAR = 24;
    private static final int REQ_BACKUP_SAVE = 25;
    private static final int REQ_BACKUP_LOAD = 26;
    private static final int TEAL = 0xFF14B8A6;

    private TextView status, friendship;
    private Button overlayBtn, notifBtn, startBtn, batteryBtn, chatBtn, contactsBtn, calendarBtn, messagesBtn;
    private EditText nameEdit, keyEdit;
    private Button updateBtn;
    private WebView vetrina;
    private TextView vetrinaLabel;
    private String vetrinaSig = "";
    private final java.util.List<TextView> styleChips = new java.util.ArrayList<>();
    static final String[] STYLES = {"normale", "ologramma", "neon", "oro", "cristallo", "cartone", "fantasma"};
    private static final String[] STYLE_LABELS = {"✨ Normale", "🛸 Ologramma", "💠 Neon", "🏆 Oro", "💎 Cristallo", "🎨 Cartone", "👻 Fantasma"};
    private static final String RELEASE_API = "https://api.github.com/repos/maikbarre2401-svg/gioco/releases/tags/android";
    private static final String APK_URL = "https://github.com/maikbarre2401-svg/gioco/releases/download/android/Zeph.apk";

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics()));
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(0xFF070B14);
        getWindow().setNavigationBarColor(0xFF0B1220);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, new int[]{0xFF070B14, 0xFF0D1526, 0xFF111A2E}));
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(18), dp(20), dp(18), dp(32));
        scroll.addView(box);

        // intestazione: il nome con la scritta sfumata e la firma
        TextView title = new TextView(this) {
            @Override protected void onSizeChanged(int w, int h, int ow, int oh) {
                super.onSizeChanged(w, h, ow, oh);
                getPaint().setShader(new LinearGradient(0, 0, getPaint().measureText("ZEPH") + dp(20), 0,
                    new int[]{0xFF5EEAD4, 0xFF38BDF8, 0xFFA78BFA}, null, Shader.TileMode.CLAMP));
            }
        };
        title.setText("ZEPH");
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 34);
        title.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        title.setLetterSpacing(0.28f);
        title.setShadowLayer(dp(12), 0, 0, 0x5538BDF8);
        box.addView(title);
        TextView creator = text("CREATOR · MAIKGOST", 11, 0xCCA78BFA);
        creator.setLetterSpacing(0.3f);
        box.addView(creator);

        // la vetrina 3D: il tuo avatar sul piedistallo di luce
        FrameLayout stage = new FrameLayout(this);
        GradientDrawable stageBg = new GradientDrawable();
        stageBg.setGradientType(GradientDrawable.RADIAL_GRADIENT);
        stageBg.setColors(new int[]{0xFF1B2A48, 0xFF0B1220});
        stageBg.setGradientRadius(dp(260));
        stageBg.setCornerRadius(dp(22));
        stageBg.setStroke(dp(1), 0x665EEAD4);
        stage.setBackground(stageBg);
        stage.setOutlineProvider(ViewOutlineProvider.BACKGROUND);
        stage.setClipToOutline(true);
        vetrina = makeVetrina();
        stage.addView(vetrina, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        vetrinaLabel = text("", 13, 0xFFEAF2FF);
        vetrinaLabel.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        vetrinaLabel.setPadding(dp(12), dp(6), dp(12), dp(6));
        vetrinaLabel.setBackground(glass(0xAA0B1220, 0x445EEAD4, 14));
        FrameLayout.LayoutParams lp1 = new FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM | Gravity.START);
        lp1.setMargins(dp(12), 0, 0, dp(12));
        stage.addView(vetrinaLabel, lp1);
        TextView hint3d = text("↔ trascina · 2 tocchi: balla", 11, 0x88EAF2FF);
        FrameLayout.LayoutParams lp2 = new FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.TOP | Gravity.END);
        lp2.setMargins(0, dp(10), dp(12), 0);
        stage.addView(hint3d, lp2);
        LinearLayout.LayoutParams stp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(320));
        stp.topMargin = dp(14);
        box.addView(stage, stp);

        // le modalità: un tocco e il tuo compagno cambia
        HorizontalScrollView chipsScroll = new HorizontalScrollView(this);
        chipsScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout chips = new LinearLayout(this);
        chips.setOrientation(LinearLayout.HORIZONTAL);
        chips.setPadding(0, dp(10), 0, dp(2));
        for (int k = 0; k < STYLES.length; k++) {
            final String st = STYLES[k];
            TextView chip = text(STYLE_LABELS[k], 14, Color.WHITE);
            chip.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
            chip.setPadding(dp(14), dp(9), dp(14), dp(9));
            chip.setTag(st);
            chip.setOnClickListener(v -> chooseStyle(st));
            LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            cp.rightMargin = dp(8);
            chips.addView(chip, cp);
            styleChips.add(chip);
        }
        chipsScroll.addView(chips);
        box.addView(chipsScroll);
        paintChips();

        // c'è una versione nuova su GitHub? (controllo ogni qualche ora)
        updateBtn = button("", 0xFF7C3AED);
        updateBtn.setVisibility(View.GONE);
        updateBtn.setOnClickListener(v -> openWeb(APK_URL));
        LinearLayout.LayoutParams up = full();
        up.topMargin = dp(14);
        box.addView(updateBtn, up);

        status = text("", 14, Color.WHITE);
        status.setPadding(dp(16), dp(14), dp(16), dp(14));
        status.setBackground(glass(0xCC111C30, 0x555EEAD4, 16));
        LinearLayout.LayoutParams sp = full();
        sp.topMargin = dp(18);
        box.addView(status, sp);
        // la vostra amicizia, dalla memoria del compagno
        friendship = text("", 13, 0xFFFDE68A);
        friendship.setPadding(dp(16), dp(11), dp(16), dp(11));
        friendship.setBackground(glass(0xCC231B3A, 0x66A78BFA, 16));
        LinearLayout.LayoutParams fp = full();
        fp.topMargin = dp(8);
        box.addView(friendship, fp);

        section(box, "1 · Permessi");
        overlayBtn = button("Permetti di apparire sopra le altre app", 0xFF334155);
        overlayBtn.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:" + getPackageName()))));
        box.addView(overlayBtn, full());
        notifBtn = button("Permetti le notifiche (per i comandi)", 0xFF334155);
        notifBtn.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= 33) requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
        });
        box.addView(notifBtn, gap(full()));
        batteryBtn = button("Non farlo mai chiudere dal risparmio batteria", 0xFF334155);
        batteryBtn.setOnClickListener(v -> askBattery());
        box.addView(batteryBtn, gap(full()));

        section(box, "2 · Il tuo compagno");
        startBtn = button("", TEAL);
        startBtn.setOnClickListener(v -> {
            if (ZephService.running) {
                startService(new Intent(this, ZephService.class).setAction(ZephService.ACTION_STOP));
                ZephService.running = false;
            } else if (Settings.canDrawOverlays(this)) {
                startForegroundService(new Intent(this, ZephService.class).setAction(ZephService.ACTION_START));
            } else {
                Toast.makeText(this, "Prima dai il permesso di apparire sopra le altre app", Toast.LENGTH_LONG).show();
            }
            startBtn.postDelayed(this::refresh, 400);
        });
        box.addView(startBtn, full());
        chatBtn = button("🎤 Parla con Zeph", 0xFF334155);
        chatBtn.setOnClickListener(v -> startActivity(new Intent(this, TalkActivity.class)));
        box.addView(chatBtn, gap(full()));

        section(box, "3 · Il tuo avatar");
        box.addView(text("Fatti un selfie: il tuo compagno prende i tuoi colori e la tua faccia (la foto resta sul telefono).", 13, 0x99FFFFFF));
        Button photo = button("📸 Crea l'avatar con una foto", TEAL);
        photo.setOnClickListener(v -> startActivity(new Intent(this, PhotoActivity.class)));
        box.addView(photo, gap(full()));
        box.addView(gapped(text("Per un avatar 3D realistico: sul sito Avaturn fai un selfie, scarica il file .glb e sceglilo qui sotto. Il tuo compagno diventa quell'avatar e lo fa camminare, parlare e ballare.", 13, 0x99FFFFFF)));
        Button avaturn = button("✨ Avatar 3D realistico (sito Avaturn)", 0xFF334155);
        avaturn.setOnClickListener(v -> openWeb("https://avaturn.me"));
        box.addView(avaturn, gap(full()));
        Button pick = button("🧑 Scegli il mio avatar (.glb)", 0xFF334155);
        pick.setOnClickListener(v -> {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
            startActivityForResult(i, REQ_AVATAR);
        });
        box.addView(pick, gap(full()));
        Button reset = button("↩ Torna a Zeph", 0xFF334155);
        reset.setOnClickListener(v -> {
            new File(getFilesDir(), "avatar.glb").delete();
            new File(getFilesDir(), "look.json").delete();
            Prefs.setUseBundledAvatar(this, false);
            Prefs.setPhotoLook(this, false);
            tellService(ZephService.ACTION_AVATAR);
            Toast.makeText(this, "Ecco di nuovo Zeph!", Toast.LENGTH_SHORT).show();
        });
        box.addView(reset, gap(full()));

        section(box, "4 · Il tuo amico");
        box.addView(text("Come si chiama? (puoi anche dirglielo in chat: «ti chiamerò Leo»)", 13, 0x99FFFFFF));
        nameEdit = new EditText(this);
        nameEdit.setSingleLine(true);
        nameEdit.setText(Prefs.petName(this));
        nameEdit.setTextColor(Color.WHITE);
        nameEdit.setHintTextColor(0x66FFFFFF);
        nameEdit.setHint("Zeph");
        box.addView(nameEdit, full());
        Button saveName = button("💾 Salva il nome", 0xFF334155);
        saveName.setOnClickListener(v -> {
            Prefs.setPetName(this, nameEdit.getText().toString());
            nameEdit.setText(Prefs.petName(this));
            tellService(ZephService.ACTION_PREFS);
            Toast.makeText(this, "Da adesso si chiama " + Prefs.petName(this) + "!", Toast.LENGTH_SHORT).show();
            refresh();
        });
        box.addView(saveName, gap(full()));
        box.addView(gapped(text(
            "Si ricorda di te: il tuo nome, cosa ti piace, le persone di cui parli, com'è andata la giornata, cosa hai in programma. " +
            "Ogni tanto ti fa domande per conoscerti meglio. Chiedigli «cosa sai di me?» oppure «cosa ti ho detto ieri?». " +
            "Per fargli dimenticare tutto scrivigli «dimentica tutto».", 13, 0x99FFFFFF)));

        section(box, "🧠 Cervello AI (facoltativo)");
        box.addView(text(
            "Di base usa un cervello offline, gratis. Se vuoi che chiacchieri davvero come un amico, metti qui la TUA chiave di Claude " +
            "(si crea su console.anthropic.com; costa circa uno o due centesimi di dollaro a messaggio e li paghi tu). " +
            "La chiave resta su questo telefono e i comandi (torcia, sveglie, app…) continuano a funzionare senza AI.", 13, 0x99FFFFFF));
        keyEdit = new EditText(this);
        keyEdit.setSingleLine(true);
        keyEdit.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        keyEdit.setTextColor(Color.WHITE);
        keyEdit.setHintTextColor(0x66FFFFFF);
        keyEdit.setHint(Prefs.aiKey(this).isEmpty() ? "sk-ant-…" : "Chiave salvata ✓ (scrivine un'altra per cambiarla)");
        box.addView(keyEdit, gap(full()));
        LinearLayout keyRow = new LinearLayout(this);
        keyRow.setOrientation(LinearLayout.HORIZONTAL);
        Button saveKey = button("💾 Salva chiave", 0xFF334155);
        saveKey.setOnClickListener(v -> {
            String k = keyEdit.getText().toString().trim();
            if (!k.startsWith("sk-ant-") || k.length() < 30) {
                Toast.makeText(this, "Questa non sembra una chiave di Claude (inizia con sk-ant-)", Toast.LENGTH_LONG).show();
                return;
            }
            Prefs.setAiKey(this, k);
            keyEdit.setText("");
            keyEdit.setHint("Chiave salvata ✓ (scrivine un'altra per cambiarla)");
            tellService(ZephService.ACTION_PREFS);
            Toast.makeText(this, "Cervello AI acceso!", Toast.LENGTH_SHORT).show();
            refresh();
        });
        Button delKey = button("🗑 Togli", 0xFF334155);
        delKey.setOnClickListener(v -> {
            Prefs.setAiKey(this, "");
            keyEdit.setHint("sk-ant-…");
            tellService(ZephService.ACTION_PREFS);
            Toast.makeText(this, "Chiave tolta: torna il cervello offline", Toast.LENGTH_SHORT).show();
            refresh();
        });
        LinearLayout.LayoutParams kp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        keyRow.addView(saveKey, kp);
        LinearLayout.LayoutParams kp2 = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.6f);
        kp2.leftMargin = dp(8);
        keyRow.addView(delKey, kp2);
        box.addView(keyRow, gap(full()));
        Button console = button("🔑 Crea una chiave (console.anthropic.com)", 0xFF334155);
        console.setOnClickListener(v -> openWeb("https://console.anthropic.com/settings/keys"));
        box.addView(console, gap(full()));

        section(box, "⚡ Poteri del telefono");
        box.addView(text("Tutto facoltativo: dai solo i permessi che vuoi. Rubrica e agenda sono in sola lettura e niente esce dal telefono.", 13, 0x99FFFFFF));
        contactsBtn = button("", 0xFF334155);
        contactsBtn.setOnClickListener(v -> requestPermissions(new String[]{Manifest.permission.READ_CONTACTS}, REQ_CONTACTS));
        box.addView(contactsBtn, gap(full()));
        calendarBtn = button("", 0xFF334155);
        calendarBtn.setOnClickListener(v -> requestPermissions(new String[]{Manifest.permission.READ_CALENDAR}, REQ_CALENDAR));
        box.addView(calendarBtn, gap(full()));
        messagesBtn = button("", 0xFF334155);
        messagesBtn.setOnClickListener(v -> {
            try {
                startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));
                Toast.makeText(this, "Attiva «Zeph: avvisi dei messaggi»", Toast.LENGTH_LONG).show();
            } catch (Exception e) {
                Toast.makeText(this, "Apri Impostazioni → Notifiche → Accesso alle notifiche", Toast.LENGTH_LONG).show();
            }
        });
        box.addView(messagesBtn, gap(full()));
        box.addView(gapped(text("Se l'interruttore di Zeph è grigio («impostazione con limitazioni», Android 13+): apri Impostazioni → App → Zeph, " +
            "tocca i tre puntini in alto a destra → «Consenti impostazioni con limitazioni», poi riprova.", 12, 0x88FFFFFF)));
        CheckBox announce = check("Annuncia i messaggi in arrivo («Ti ha scritto Giulia!»)", Prefs.announceMessages(this));
        announce.setOnCheckedChangeListener((c, on) -> Prefs.setAnnounceMessages(this, on));
        box.addView(announce);
        CheckBox readAloud = check("Leggi ad alta voce anche il testo dei messaggi", Prefs.readMessages(this));
        readAloud.setOnCheckedChangeListener((c, on) -> Prefs.setReadMessages(this, on));
        box.addView(readAloud);
        CheckBox shake = check("Scuoti il telefono: arriva di corsa", Prefs.shake(this));
        shake.setOnCheckedChangeListener((c, on) -> { Prefs.setShake(this, on); tellService(ZephService.ACTION_PREFS); });
        box.addView(shake);
        CheckBox brief = check("Il buongiorno (meteo, impegni, promemoria) quando sblocchi il telefono la mattina", Prefs.briefing(this));
        brief.setOnCheckedChangeListener((c, on) -> Prefs.setBriefing(this, on));
        box.addView(brief);
        box.addView(gapped(text("I promemoria («ricordami domani alle 9 di…») sono veri: suonano anche se il compagno è spento o riavvii il telefono.", 13, 0x99FFFFFF)));

        section(box, "💾 Backup della memoria");
        box.addView(text("Salva in un file tutto quello che il tuo amico sa di te (e il look della foto). Se cambi telefono o reinstalli l'app, lo ripristini e si ricorda di tutto. La chiave AI non viene salvata.", 13, 0x99FFFFFF));
        Button saveBk = button("💾 Salva backup", 0xFF334155);
        saveBk.setOnClickListener(v -> {
            Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType("application/json").putExtra(Intent.EXTRA_TITLE, "memoria-" + Prefs.petName(this).toLowerCase() + ".json");
            startActivityForResult(i, REQ_BACKUP_SAVE);
        });
        box.addView(saveBk, gap(full()));
        Button loadBk = button("📂 Ripristina backup", 0xFF334155);
        loadBk.setOnClickListener(v -> {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
            startActivityForResult(i, REQ_BACKUP_LOAD);
        });
        box.addView(loadBk, gap(full()));

        section(box, "5 · Opzioni");
        box.addView(text("Grandezza", 13, 0x99FFFFFF));
        RadioGroup size = new RadioGroup(this);
        size.setOrientation(RadioGroup.HORIZONTAL);
        String[] names = {"Piccolo", "Medio", "Grande"};
        float[] scales = {0.75f, 1f, 1.3f};
        float cur = Prefs.scale(this);
        for (int k = 0; k < 3; k++) {
            RadioButton r = new RadioButton(this);
            r.setText(names[k]);
            r.setTextColor(Color.WHITE);
            r.setId(View.generateViewId());
            final float s = scales[k];
            size.addView(r);
            if (Math.abs(cur - s) < 0.01f) r.setChecked(true);
            r.setOnCheckedChangeListener((btn, on) -> {
                if (!on) return;
                Prefs.setScale(this, s);
                tellService(ZephService.ACTION_RELOAD);
            });
        }
        box.addView(size);

        CheckBox ghost = check("Modalità fantasma: i tocchi passano attraverso Zeph", Prefs.ghost(this));
        ghost.setOnCheckedChangeListener((c, on) -> { Prefs.setGhost(this, on); tellService(ZephService.ACTION_RELOAD); });
        box.addView(ghost);
        CheckBox boot = check("Riaccendi Zeph quando riaccendi il telefono", Prefs.autostart(this));
        boot.setOnCheckedChangeListener((c, on) -> Prefs.setAutostart(this, on));
        box.addView(boot);

        section(box, "Come si usa");
        box.addView(text(
            "• Tocca Zeph: reagisce (saluta, balla, salta…). Toccalo tante volte: soffre il solletico!\n" +
            "• Tienilo premuto: si apre la chat (scrivi o parla)\n" +
            "• Trascinalo: lo sollevi, e se lo lasci cade giù\n" +
            "• Dalla notifica: 💬 Scrivi (anche dettando), 🙈 Nascondi / 👁 Mostra, ✖ Chiudi\n" +
            "• Nelle Impostazioni rapide (tendina dall'alto) aggiungi il pulsante «Zeph» per accenderlo al volo\n" +
            "• Da qualsiasi app: Condividi → «Leggi con Zeph» e te lo legge ad alta voce\n" +
            "• Di notte, se lo lasci tranquillo, si addormenta. Toccalo per svegliarlo\n" +
            "• Raccontagli la tua giornata: se lo ricorda e il giorno dopo ti chiede com'è andata\n" +
            "• Chiudi l'app quando vuoi: Zeph resta sullo schermo\n\n" +
            "Poteri: «ricordami domani alle 9 di chiamare la mamma», «chiama mia sorella», «scrivi a Giulia che arrivo», " +
            "«chi mi ha scritto?», «rispondi: arrivo subito» (ti chiede conferma), «che impegni ho oggi?», «aggiungi al calendario dentista domani alle 10», " +
            "«com'è la mia giornata?», «chi era Leonardo da Vinci?», «traduci buongiorno in inglese», «cosa vedi?» (con il cervello AI), «modalità neon / oro / cristallo / cartone / fantasma / ologramma», «torna normale». " +
            "Scuoti il telefono e arriva di corsa!\n\n" +
            "Prova a dirgli: «oggi sono andato al mare», «domani ho un esame», «mi piace la pizza», «cosa sai di me?», " +
            "«se ti dico buongiorno rispondi ciao campione», «ti chiamerò Leo», «che tempo fa a Roma», «accendi la torcia», «svegliami alle 7 e mezza», " +
            "«timer di 10 minuti», «prossima canzone», «chiama 333 1234567», «apri whatsapp», " +
            "«apri impostazioni wifi», «alza il volume», «quanta batteria ho?», «10 km in miglia», " +
            "«tira un dado», «quanti giorni mancano a Natale», «balla», «barzelletta».",
            14, 0xDDFFFFFF));

        TextView version = text("Zeph " + versionName() + " · build " + versionCode() + " · creator MaikGost", 12, 0x66FFFFFF);
        version.setGravity(Gravity.CENTER);
        version.setPadding(0, dp(28), 0, 0);
        box.addView(version, full());

        setContentView(scroll);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (vetrina != null) {
            vetrina.onResume();
            String sig = avatarSignature();
            if (!vetrinaSig.isEmpty() && !sig.equals(vetrinaSig)) vetrina.evaluateJavascript("window.vetrinaReload&&vetrinaReload()", null);
            vetrinaSig = sig;
        }
        refresh();
        showUpdate();
        checkUpdate();
    }

    @Override
    protected void onPause() {
        if (vetrina != null) vetrina.onPause(); // solo questa pagina: il compagno sullo schermo continua
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (vetrina != null) { vetrina.destroy(); vetrina = null; }
        super.onDestroy();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private WebView makeVetrina() {
        WebView w = new WebView(this);
        w.setBackgroundColor(Color.TRANSPARENT);
        WebSettings ws = w.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(false);
        w.setVerticalScrollBarEnabled(false);
        w.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                return LocalWeb.intercept(MainActivity.this, req);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) { return true; }
        });
        // trascinando in orizzontale ruoti il personaggio; in verticale scorre la pagina
        final float[] down = new float[2];
        w.setOnTouchListener((v, e) -> {
            if (e.getActionMasked() == android.view.MotionEvent.ACTION_DOWN) { down[0] = e.getX(); down[1] = e.getY(); }
            else if (e.getActionMasked() == android.view.MotionEvent.ACTION_MOVE) {
                boolean horizontal = Math.abs(e.getX() - down[0]) > Math.abs(e.getY() - down[1]);
                v.getParent().requestDisallowInterceptTouchEvent(horizontal);
            }
            return false;
        });
        w.loadUrl("https://" + LocalWeb.HOST + "/vetrina.html?style=" + Prefs.style(this));
        vetrinaSig = avatarSignature();
        return w;
    }

    /** Cambia se cambi avatar o look: allora la vetrina si ricarica. */
    private String avatarSignature() {
        File a = new File(getFilesDir(), "avatar.glb"), l = new File(getFilesDir(), "look.json");
        return a.lastModified() + "|" + l.lastModified() + "|" + Prefs.photoLook(this) + "|" + Prefs.useBundledAvatar(this);
    }

    private void chooseStyle(String st) {
        Prefs.setStyle(this, st);
        if (vetrina != null) vetrina.evaluateJavascript("window.vetrinaStyle&&vetrinaStyle('" + st + "')", null);
        tellService(ZephService.ACTION_PREFS);
        paintChips();
    }

    private void paintChips() {
        String cur = Prefs.style(this);
        for (TextView c : styleChips) {
            boolean on = cur.equals(c.getTag());
            if (on) {
                GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{0xFF14B8A6, 0xFF0EA5E9, 0xFF8B5CF6});
                g.setCornerRadius(dp(18));
                c.setBackground(g);
                c.setTextColor(Color.WHITE);
            } else {
                c.setBackground(glass(0xFF111C30, 0x445EEAD4, 18));
                c.setTextColor(0xCCEAF2FF);
            }
        }
        if (vetrinaLabel != null) {
            int k = java.util.Arrays.asList(STYLES).indexOf(cur);
            vetrinaLabel.setText(Prefs.petName(this) + " · " + (k >= 0 ? STYLE_LABELS[k] : "✨ Normale"));
        }
    }

    private void refresh() {
        boolean overlay = Settings.canDrawOverlays(this);
        boolean notif = Build.VERSION.SDK_INT < 33 || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
        PowerManager pm = getSystemService(PowerManager.class);
        boolean battery = pm != null && pm.isIgnoringBatteryOptimizations(getPackageName());
        mark(overlayBtn, overlay, "✅ Può apparire sopra le altre app", "Permetti di apparire sopra le altre app");
        mark(notifBtn, notif, "✅ Notifiche permesse", "Permetti le notifiche (per i comandi)");
        mark(batteryBtn, battery, "✅ Il risparmio batteria non lo chiude", "Non farlo mai chiudere dal risparmio batteria");
        mark(contactsBtn, Contacts.canReadContacts(this), "✅ Rubrica: «chiama Giulia», «scrivi a Marco che…»", "📇 Permetti la rubrica («chiama Giulia»)");
        mark(calendarBtn, Contacts.canReadCalendar(this), "✅ Agenda: «che impegni ho oggi?»", "📅 Permetti l'agenda («che impegni ho oggi?»)");
        mark(messagesBtn, MessageListener.enabled(this), "✅ Ti avvisa dei messaggi («chi mi ha scritto?»)", "📩 Avvisami dei messaggi (accesso alle notifiche)");
        boolean on = ZephService.running;
        String name = Prefs.petName(this);
        paintChips();
        String fr = friendshipText();
        friendship.setText(fr);
        friendship.setVisibility(fr.isEmpty() ? View.GONE : View.VISIBLE);
        startBtn.setText(on ? "⏹ Togli " + name + " dallo schermo" : "▶ Metti " + name + " sullo schermo");
        chatBtn.setText("🎙 Parla con " + name + " (conversazione a voce)");
        String av = Prefs.photoLook(this) && new File(getFilesDir(), "look.json").exists() ? "con il look della tua foto"
            : new File(getFilesDir(), "avatar.glb").exists() ? "con il tuo avatar" : "come Zeph";
        String brain = Prefs.aiKey(this).isEmpty() ? "cervello offline" : "cervello AI acceso";
        status.setText(on ? "🟢 " + name + " è sul tuo schermo (" + av + ", " + brain + "). Puoi chiudere l'app: resta lì."
            : overlay ? "⚪ " + name + " è spento. Premi «Metti " + name + " sullo schermo»."
            : "⚠️ Serve il permesso di apparire sopra le altre app (punto 1).");
    }

    /** «Grandi amici · insieme da 12 giorni · 85 chiacchierate · sa 9 cose di te», dal file della memoria. */
    private String friendshipText() {
        String snap = ZephService.readFile(new File(getFilesDir(), "memory.json"));
        if (snap.isEmpty()) return "";
        try {
            org.json.JSONObject o = new org.json.JSONObject(snap);
            org.json.JSONObject m = new org.json.JSONObject(o.optString("zephMemory", "{}"));
            org.json.JSONArray days = m.optJSONArray("days");
            int n = days == null ? 0 : days.length(), talks = m.optInt("talks");
            if (talks == 0) return "";
            long since = 0;
            String first = m.optString("firstMet", "");
            if (first.length() == 10) {
                java.util.Calendar c = java.util.Calendar.getInstance();
                c.set(Integer.parseInt(first.substring(0, 4)), Integer.parseInt(first.substring(5, 7)) - 1, Integer.parseInt(first.substring(8, 10)), 0, 0, 0);
                since = Math.max(0, (System.currentTimeMillis() - c.getTimeInMillis()) / 86_400_000L);
            }
            int known = count(m, "likes") + count(m, "dislikes") + count(m, "notes") + (m.optJSONObject("people") != null ? m.optJSONObject("people").length() : 0)
                + (m.optJSONObject("facts") != null ? m.optJSONObject("facts").length() : 0);
            String level = n >= 30 ? "Migliori amici" : n >= 10 ? "Grandi amici" : n >= 3 ? "Amici" : "Nuovi amici";
            return "💛 " + level + " · " + (since > 0 ? "insieme da " + since + (since == 1 ? " giorno" : " giorni") : "vi siete conosciuti oggi") +
                " · " + talks + (talks == 1 ? " chiacchierata" : " chiacchierate") + (known > 0 ? " · sa " + known + " cose di te" : "");
        } catch (Exception e) {
            return "";
        }
    }

    private static int count(org.json.JSONObject m, String k) {
        org.json.JSONArray a = m.optJSONArray(k);
        return a == null ? 0 : a.length();
    }

    private void mark(Button b, boolean ok, String yes, String no) {
        b.setText(ok ? yes : no);
        b.setEnabled(!ok);
        b.setAlpha(ok ? 0.6f : 1f);
    }

    @SuppressLint("BatteryLife")
    private void askBattery() {
        try {
            startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + getPackageName())));
        } catch (Exception e) {
            startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
        }
    }

    private long versionCode() {
        try {
            android.content.pm.PackageInfo pi = getPackageManager().getPackageInfo(getPackageName(), 0);
            return Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : legacyCode(pi);
        } catch (Exception e) {
            return 0;
        }
    }

    @SuppressWarnings("deprecation")
    private static long legacyCode(android.content.pm.PackageInfo pi) { return pi.versionCode; }

    private String versionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "";
        }
    }

    /** Il numero dell'ultima versione pubblicata su GitHub (dal titolo «… · build N»). */
    private void checkUpdate() {
        if (System.currentTimeMillis() - Prefs.lastUpdateCheck(this) < 3 * 3600_000L) return;
        Prefs.setLastUpdateCheck(this, System.currentTimeMillis());
        new Thread(() -> {
            java.net.HttpURLConnection c = null;
            try {
                c = (java.net.HttpURLConnection) new java.net.URL(RELEASE_API).openConnection();
                c.setRequestProperty("Accept", "application/vnd.github+json");
                c.setRequestProperty("User-Agent", "Zeph-Android");
                c.setConnectTimeout(8000);
                c.setReadTimeout(8000);
                if (c.getResponseCode() != 200) return;
                java.io.ByteArrayOutputStream buf = new java.io.ByteArrayOutputStream();
                try (InputStream in = c.getInputStream()) {
                    byte[] b = new byte[16 * 1024];
                    int n;
                    while ((n = in.read(b)) > 0 && buf.size() < 512 * 1024) buf.write(b, 0, n);
                }
                org.json.JSONObject o = new org.json.JSONObject(buf.toString("UTF-8"));
                java.util.regex.Matcher m = java.util.regex.Pattern.compile("build (\\d+)").matcher(o.optString("name"));
                if (m.find()) {
                    Prefs.setLatestBuild(this, Integer.parseInt(m.group(1)));
                    runOnUiThread(this::showUpdate);
                }
            } catch (Exception ignored) {
                // niente internet o GitHub irraggiungibile: riproverà più tardi
            } finally {
                if (c != null) c.disconnect();
            }
        }).start();
    }

    private void showUpdate() {
        int latest = Prefs.latestBuild(this);
        long mine = versionCode();
        if (latest > mine && mine > 0) {
            updateBtn.setText("⬆️ C'è una versione nuova (build " + latest + ")! Prima premi «Salva backup» qui sotto, poi tocca qui per scaricarla");
            updateBtn.setVisibility(View.VISIBLE);
        } else {
            updateBtn.setVisibility(View.GONE);
        }
    }

    private void openWeb(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            Toast.makeText(this, "Non trovo un browser", Toast.LENGTH_SHORT).show();
        }
    }

    private TextView gapped(TextView t) {
        t.setPadding(0, dp(12), 0, 0);
        return t;
    }

    private void tellService(String action) {
        if (ZephService.running) startService(new Intent(this, ZephService.class).setAction(action));
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        super.onRequestPermissionsResult(req, perms, res);
        refresh();
        if ((req == REQ_CONTACTS || req == REQ_CALENDAR) && res.length > 0 && res[0] != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Permesso negato: se cambi idea lo trovi in Impostazioni → App → Zeph → Autorizzazioni", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (res != RESULT_OK || data == null || data.getData() == null) return;
        if (req == REQ_BACKUP_SAVE) { saveBackup(data.getData()); return; }
        if (req == REQ_BACKUP_LOAD) { loadBackup(data.getData()); return; }
        if (req != REQ_AVATAR) return;
        Uri uri = data.getData();
        new Thread(() -> {
            boolean ok = copyAvatar(uri);
            runOnUiThread(() -> {
                if (ok) {
                    Prefs.setUseBundledAvatar(this, true);
                    Prefs.setPhotoLook(this, false);
                    tellService(ZephService.ACTION_AVATAR);
                    Toast.makeText(this, "Avatar caricato! Guarda lo schermo", Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(this, "Questo file non sembra un avatar .glb", Toast.LENGTH_LONG).show();
                }
                refresh();
            });
        }).start();
    }

    /** Il backup: memoria, nome e look della foto (mai la chiave AI). */
    private void saveBackup(Uri uri) {
        new Thread(() -> {
            boolean ok;
            try (OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
                org.json.JSONObject o = new org.json.JSONObject()
                    .put("zeph", 1)
                    .put("petName", Prefs.petName(this))
                    .put("memory", ZephService.readFile(new File(getFilesDir(), "memory.json")))
                    .put("look", Prefs.photoLook(this) ? ZephService.readFile(new File(getFilesDir(), "look.json")) : "");
                if (out == null) throw new java.io.IOException("niente file");
                out.write(o.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
                ok = true;
            } catch (Exception e) {
                ok = false;
            }
            final boolean done = ok;
            runOnUiThread(() -> Toast.makeText(this, done ? "Backup salvato! Tienilo al sicuro" : "Non sono riuscito a salvare il backup", Toast.LENGTH_LONG).show());
        }).start();
    }

    private void loadBackup(Uri uri) {
        new Thread(() -> {
            boolean ok = false;
            try (InputStream in = getContentResolver().openInputStream(uri)) {
                if (in == null) throw new java.io.IOException("niente file");
                java.io.ByteArrayOutputStream buf = new java.io.ByteArrayOutputStream();
                byte[] b = new byte[64 * 1024];
                int n;
                while ((n = in.read(b)) > 0) {
                    buf.write(b, 0, n);
                    if (buf.size() > 8 * 1024 * 1024) throw new java.io.IOException("troppo grande");
                }
                org.json.JSONObject o = new org.json.JSONObject(buf.toString("UTF-8"));
                if (o.optInt("zeph") == 1) {
                    String mem = o.optString("memory", "");
                    if (!mem.isEmpty()) new org.json.JSONObject(mem); // dev'essere JSON valido
                    writeText(new File(getFilesDir(), "memory.json"), mem);
                    String look = o.optString("look", "");
                    if (!look.isEmpty()) {
                        new org.json.JSONObject(look);
                        writeText(new File(getFilesDir(), "look.json"), look);
                        Prefs.setPhotoLook(this, true);
                    }
                    if (o.has("petName")) Prefs.setPetName(this, o.optString("petName"));
                    ok = true;
                }
            } catch (Exception e) {
                ok = false;
            }
            final boolean done = ok;
            runOnUiThread(() -> {
                if (done) {
                    tellService(ZephService.ACTION_MEMORY);
                    tellService(ZephService.ACTION_AVATAR);
                    nameEdit.setText(Prefs.petName(this));
                    Toast.makeText(this, "Memoria ripristinata: si ricorda di te!", Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(this, "Questo file non sembra un backup di Zeph", Toast.LENGTH_LONG).show();
                }
                refresh();
            });
        }).start();
    }

    private static void writeText(File f, String s) throws java.io.IOException {
        try (OutputStream out = new FileOutputStream(f)) {
            out.write(s.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
    }

    /** Copia il .glb scelto dentro l'app, controllando che sia davvero un glTF. */
    private boolean copyAvatar(Uri uri) {
        File tmp = new File(getFilesDir(), "avatar.tmp");
        try (InputStream in = getContentResolver().openInputStream(uri); OutputStream out = new FileOutputStream(tmp)) {
            if (in == null) return false;
            byte[] buf = new byte[64 * 1024];
            int n, total = 0;
            boolean first = true;
            while ((n = in.read(buf)) > 0) {
                if (first) {
                    if (n < 4 || buf[0] != 'g' || buf[1] != 'l' || buf[2] != 'T' || buf[3] != 'F') return false;
                    first = false;
                }
                out.write(buf, 0, n);
                total += n;
                if (total > 60 * 1024 * 1024) return false; // oltre 60 MB è troppo per un overlay
            }
        } catch (Exception e) {
            return false;
        }
        File dest = new File(getFilesDir(), "avatar.glb");
        return tmp.renameTo(dest);
    }

    // ---------------------------------------------------------------- piccoli aiuti per l'interfaccia

    private TextView text(String s, float sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        t.setLineSpacing(0, 1.15f);
        return t;
    }

    /** Titolo di sezione: maiuscolo, spaziato, con una riga di luce sotto. */
    private void section(LinearLayout box, String title) {
        TextView t = text(title.toUpperCase(java.util.Locale.ITALIAN), 12, 0xFF5EEAD4);
        t.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        t.setLetterSpacing(0.16f);
        t.setPadding(0, dp(26), 0, dp(6));
        box.addView(t);
        View line = new View(this);
        line.setBackground(new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{0xFF5EEAD4, 0x88A78BFA, 0x00A78BFA}));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(1.5f));
        lp.bottomMargin = dp(10);
        box.addView(line, lp);
    }

    /** Vetro scuro con bordo luminoso. */
    private GradientDrawable glass(int fill, int stroke, float radius) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(radius));
        g.setStroke(dp(1), stroke);
        return g;
    }

    private GradientDrawable round(int color, float radius) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(radius));
        return g;
    }

    /** Pulsanti: principali con sfumatura luminosa, gli altri in vetro con bordo; onda al tocco. */
    private Button button(String s, int color) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        b.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        b.setPadding(dp(16), dp(13), dp(16), dp(13));
        b.setStateListAnimator(null);
        GradientDrawable bg;
        if (color == TEAL) {
            bg = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{0xFF14B8A6, 0xFF0EA5E9});
            bg.setCornerRadius(dp(14));
        } else if (color == 0xFF7C3AED) {
            bg = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{0xFF7C3AED, 0xFFDB2777});
            bg.setCornerRadius(dp(14));
        } else {
            bg = glass(0xFF111C30, 0x335EEAD4, 14);
        }
        GradientDrawable mask = new GradientDrawable();
        mask.setColor(Color.WHITE);
        mask.setCornerRadius(dp(14));
        b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x555EEAD4), bg, mask));
        return b;
    }

    private CheckBox check(String s, boolean on) {
        CheckBox c = new CheckBox(this);
        c.setText(s);
        c.setTextColor(0xEEEAF2FF);
        c.setButtonTintList(ColorStateList.valueOf(0xFF5EEAD4));
        c.setChecked(on);
        c.setPadding(dp(6), dp(10), 0, dp(10));
        return c;
    }

    private LinearLayout.LayoutParams full() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams gap(LinearLayout.LayoutParams p) {
        p.topMargin = dp(8);
        return p;
    }
}
