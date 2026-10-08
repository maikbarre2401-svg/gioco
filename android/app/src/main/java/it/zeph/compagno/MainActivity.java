package it.zeph.compagno;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
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
    private static final int TEAL = 0xFF14B8A6;

    private TextView status;
    private Button overlayBtn, notifBtn, startBtn, batteryBtn, chatBtn;
    private EditText nameEdit, keyEdit;

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics()));
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(0xFF0F1726);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(0xFF0F1726);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(24), dp(20), dp(32));
        scroll.addView(box);

        TextView title = text("ZEPH", 30, 0xFF5EEAD4);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setLetterSpacing(0.15f);
        box.addView(title);
        box.addView(text("Il tuo avatar che vive sullo schermo del telefono", 14, 0xBBFFFFFF));

        status = text("", 14, Color.WHITE);
        status.setPadding(dp(14), dp(12), dp(14), dp(12));
        status.setBackground(round(0xFF1E293B, 12));
        LinearLayout.LayoutParams sp = full();
        sp.topMargin = dp(18);
        box.addView(status, sp);

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
        chatBtn.setOnClickListener(v -> startActivity(new Intent(this, ChatActivity.class).putExtra(ChatActivity.EXTRA_MIC, true)));
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
            "Prova a dirgli: «oggi sono andato al mare», «domani ho un esame», «mi piace la pizza», «cosa sai di me?», " +
            "«se ti dico buongiorno rispondi ciao campione», «ti chiamerò Leo», «che tempo fa a Roma», «accendi la torcia», «svegliami alle 7 e mezza», " +
            "«timer di 10 minuti», «prossima canzone», «chiama 333 1234567», «apri whatsapp», " +
            "«apri impostazioni wifi», «alza il volume», «quanta batteria ho?», «10 km in miglia», " +
            "«tira un dado», «quanti giorni mancano a Natale», «balla», «barzelletta».",
            14, 0xDDFFFFFF));

        setContentView(scroll);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refresh();
    }

    private void refresh() {
        boolean overlay = Settings.canDrawOverlays(this);
        boolean notif = Build.VERSION.SDK_INT < 33 || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
        PowerManager pm = getSystemService(PowerManager.class);
        boolean battery = pm != null && pm.isIgnoringBatteryOptimizations(getPackageName());
        mark(overlayBtn, overlay, "✅ Può apparire sopra le altre app", "Permetti di apparire sopra le altre app");
        mark(notifBtn, notif, "✅ Notifiche permesse", "Permetti le notifiche (per i comandi)");
        mark(batteryBtn, battery, "✅ Il risparmio batteria non lo chiude", "Non farlo mai chiudere dal risparmio batteria");
        boolean on = ZephService.running;
        String name = Prefs.petName(this);
        startBtn.setText(on ? "⏹ Togli " + name + " dallo schermo" : "▶ Metti " + name + " sullo schermo");
        chatBtn.setText("🎤 Parla con " + name);
        String av = Prefs.photoLook(this) && new File(getFilesDir(), "look.json").exists() ? "con il look della tua foto"
            : new File(getFilesDir(), "avatar.glb").exists() ? "con il tuo avatar" : "come Zeph";
        String brain = Prefs.aiKey(this).isEmpty() ? "cervello offline" : "cervello AI acceso";
        status.setText(on ? "🟢 " + name + " è sul tuo schermo (" + av + ", " + brain + "). Puoi chiudere l'app: resta lì."
            : overlay ? "⚪ " + name + " è spento. Premi «Metti " + name + " sullo schermo»."
            : "⚠️ Serve il permesso di apparire sopra le altre app (punto 1).");
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
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_AVATAR || res != RESULT_OK || data == null || data.getData() == null) return;
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

    private void section(LinearLayout box, String title) {
        TextView t = text(title, 13, 0xFF5EEAD4);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(22), 0, dp(8));
        box.addView(t);
    }

    private GradientDrawable round(int color, float radius) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(radius));
        return g;
    }

    private Button button(String s, int color) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        b.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        b.setPadding(dp(16), dp(12), dp(16), dp(12));
        b.setBackground(round(color, 12));
        return b;
    }

    private CheckBox check(String s, boolean on) {
        CheckBox c = new CheckBox(this);
        c.setText(s);
        c.setTextColor(Color.WHITE);
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
